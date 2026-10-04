# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
import io
import wave

# Allow running this file directly: add "src" to sys.path
if __package__ in (None, ""):
    SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    if SRC_DIR not in sys.path:
        sys.path.insert(0, SRC_DIR)

from PySide6 import QtCore, QtGui, QtWidgets
from loguru import logger

from voicepaste.audio_recorder import AudioRecorder
from voicepaste.gemini import GeminiTranscriber
from voicepaste.hotkeys import HotkeyManager
from voicepaste.injector import insert_text
from voicepaste.settings import Settings, get_api_key
from voicepaste.ui_settings import SettingsDialog
from voicepaste.utils import logs_dir


class TrayApp(QtWidgets.QSystemTrayIcon):
    transcribe_error_signal = QtCore.Signal(str)
    status_signal = QtCore.Signal(str)

    def __init__(self, app: QtWidgets.QApplication):
        # icon.ico или favicon.ico - не важно. Qt разберет ICO с несколькими слоями.
        # Важно: дальше мы всегда работаем в логическом размере self._icon_size.
        _meipass = getattr(sys, "_MEIPASS", None)
        icon_candidates = [
            (Path(_meipass) / "assets" / "icon.ico") if _meipass else None,
            Path(__file__).resolve().parent.parent.parent / "assets" / "icon.ico",
            Path(__file__).resolve().parent.parent.parent / "assets" / "favicon.ico",
        ]
        icon_path = next((p for p in icon_candidates if p and p.exists()), None)
        base_icon = QtGui.QIcon(str(icon_path)) if icon_path else QtGui.QIcon()
        super().__init__(base_icon, app)
        # If no packaged icon was found, draw a simple fallback once
        if icon_path is None:
            size = 32
            pm = QtGui.QPixmap(size, size)
            pm.fill(QtCore.Qt.GlobalColor.transparent)
            painter = QtGui.QPainter(pm)
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
            grad = QtGui.QRadialGradient(QtCore.QPointF(size*0.35, size*0.35), size*0.8)
            grad.setColorAt(0.0, QtGui.QColor(80, 140, 255))
            grad.setColorAt(1.0, QtGui.QColor(40, 90, 220))
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(grad)
            painter.drawEllipse(1, 1, size-2, size-2)
            painter.setBrush(QtGui.QColor("white"))
            painter.setPen(QtGui.QPen(QtGui.QColor("white"), 2))
            mic_w = size*0.30; mic_h = size*0.42
            x = (size - mic_w)/2; y = (size - mic_h)/2 - 2
            painter.drawRoundedRect(QtCore.QRectF(x, y, mic_w, mic_h), 4, 4)
            painter.drawLine(QtCore.QPointF(size/2, y+mic_h), QtCore.QPointF(size/2, y+mic_h+6))
            painter.drawLine(QtCore.QPointF(size*0.35, y+mic_h+6), QtCore.QPointF(size*0.65, y+mic_h+6))
            painter.end()
            base_icon = QtGui.QIcon(pm)
            self._base_icon = base_icon
            self.setIcon(base_icon)

        # Logging setup
        log_file = logs_dir() / "voicepaste.log"
        logger.remove()
        logger.add(str(log_file), rotation="1 MB", retention=5, enqueue=True, level="INFO")

        self.app = app
        self.settings = Settings.load()
        self.setToolTip("VoicePaste - Idle")

        # State
        self.recording = False
        self.processing = False
        self.paused = False
        self.listening_enabled = True
        self.current_status = "Idle"
        self._level_cache = 0.0
        self._anim_step = 0
        self._base_icon = base_icon

        # Логический размер иконки для отрисовки оверлеев.
        # Реальный пиксельный размер будет умножен на DPR.
        self._icon_size = 32

        # Core components
        self.recorder = AudioRecorder()
        self.hk = HotkeyManager(
            self.settings.hotkey,
            on_start=self._on_hold_start,
            on_stop=self._on_hold_stop,
        )

        # Menu
        menu = QtWidgets.QMenu()
        self.act_listen = QtGui.QAction("Запись при удержании", self, checkable=True, checked=True)
        self.act_pause = QtGui.QAction("Пауза", self, checkable=True, checked=False)
        self.act_settings = QtGui.QAction("Настройки...", self)
        self.act_exit = QtGui.QAction("Выход", self)
        menu.addAction(self.act_listen)
        menu.addAction(self.act_pause)
        menu.addSeparator()
        menu.addAction(self.act_settings)
        menu.addSeparator()
        menu.addAction(self.act_exit)
        self.setContextMenu(menu)

        self.act_listen.toggled.connect(self._toggle_listen)
        self.act_pause.toggled.connect(self._toggle_pause)
        self.act_settings.triggered.connect(self._open_settings)
        self.act_exit.triggered.connect(self._quit)
        self.transcribe_error_signal.connect(self._show_transcribe_error, QtCore.Qt.ConnectionType.QueuedConnection)
        self.status_signal.connect(self._apply_status, QtCore.Qt.ConnectionType.QueuedConnection)

        # Tooltip + animation timer (drives spinner during transcribing)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(120)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start()

        self.activated.connect(self._on_activated)

        # Initialize hotkey
        self.hk.enable()
        # Initial icon
        self._update_icon()

    # UI handlers
    def _on_activated(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:
            # Left click: toggle pause
            self.act_pause.toggle()

    def _toggle_listen(self, checked: bool):
        self.listening_enabled = checked
        if checked:
            self.hk.enable()
            self._set_status("Idle")
        else:
            self.hk.disable()
            self._set_status("Paused")

    def _toggle_pause(self, checked: bool):
        self.paused = checked
        if checked:
            self._set_status("Paused")
        else:
            self._set_status("Idle")

    def _open_settings(self):
        dlg = SettingsDialog(self.settings)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # Update hotkey
            self.hk.set_hotkey(self.settings.hotkey)
            logger.info(f"Hotkey updated to: {self.settings.hotkey}")

    def _quit(self):
        self.paused = True
        self.hk.disable()
        if self.recording:
            self.paused = True
            self._on_hold_stop()
        self.timer.stop()
        self.hide()
        QtWidgets.QApplication.quit()

    @QtCore.Slot(str)
    def _show_transcribe_error(self, message: str):
        QtWidgets.QMessageBox.warning(None, "VoicePaste", message)

    def _format_transcribe_error(self, error: Exception) -> str:
        msg = str(error)
        msg_l = msg.lower()
        model = self.settings.gemini_model
        if (
            "resource_exhausted" in msg_l
            or "quota exceeded" in msg_l
            or ("429" in msg_l and "quota" in msg_l)
        ):
            return (
                f"Квота исчерпана для выбранной модели Gemini ({model}).\n"
                "Выберите другую модель или проверьте лимиты/биллинг в Gemini API."
            )
        return f"Ошибка транскрибации: {msg}"

    # Status & tooltip
    def _set_status(self, status: str):
        self.status_signal.emit(status)

    @QtCore.Slot(str)
    def _apply_status(self, status: str):
        self.current_status = status
        self._update_tooltip()
        self._update_icon()

    def _update_tooltip(self):
        status = self.current_status
        if status == "Recording":
            level = self.recorder.get_level()
            self._level_cache = level
            bars = int(max(0, min(10, round(level * 10))))
            vu = "█" * bars + "░" * (10 - bars)
            self.setToolTip(f"VoicePaste - Recording {vu}")
        else:
            self.setToolTip(f"VoicePaste - {status}")

    def _on_tick(self):
        # Animation + tooltip update
        # Use 240 steps for a full 360° rotation (24 units per step in 1/16°)
        self._anim_step = (self._anim_step + 1) % 240
        self._update_tooltip()
        self._update_icon()

    def _update_icon(self):
        try:
            # 1) Получаем базовый pixmap в логическом размере.
            base_pm = self._base_icon.pixmap(self._icon_size, self._icon_size)
            if base_pm.isNull():
                return

            # DPR базового слоя. Используем его для холста.
            dpr = base_pm.devicePixelRatioF() or 1.0

            size = float(self._icon_size)

            # 2) Создаем свой прозрачный холст. Размер в пикселях умножаем на DPR.
            canvas = QtGui.QPixmap(int(size * dpr), int(size * dpr))
            canvas.setDevicePixelRatio(dpr)
            canvas.fill(QtCore.Qt.GlobalColor.transparent)

            p = QtGui.QPainter(canvas)
            p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

            # 3) Кладем базовую иконку на холст один в один по логическим координатам.
            target_rect = QtCore.QRectF(0.0, 0.0, size, size)
            p.drawPixmap(target_rect.toRect(), base_pm, base_pm.rect())

            # 4) Рисуем оверлеи в тех же логических координатах.
            rect = target_rect
            center = QtCore.QPointF(rect.center())

            status = self.current_status

            if status == "Recording":
                # VU-бар внизу
                level = self._level_cache
                w = rect.width() - 6.0
                vu_w = w * max(0.0, min(1.0, level))
                bar_rect = QtCore.QRectF(3.0, rect.bottom() - 3.0, vu_w, 3.0)
                if level > 0.66:
                    color = QtGui.QColor(200, 0, 0)
                elif level > 0.33:
                    color = QtGui.QColor(220, 180, 0)
                else:
                    color = QtGui.QColor(0, 200, 0)
                # VU bar disabled to avoid green dot at low levels
                _ = None

                # Красный пульсирующий круг строго по центру
                r = 4 + int((self._anim_step % 10) / 9 * 2)
                p.setPen(QtCore.Qt.PenStyle.NoPen)
                p.setBrush(QtGui.QColor(220, 40, 40))
                p.drawEllipse(center, r, r)

            elif status == "Transcribing":
                pen = QtGui.QPen(QtGui.QColor(240, 196, 25), 6.0)
                p.setPen(pen)
                inset = 4.0
                arc_rect = QtCore.QRectF(
                    rect.x() + inset,
                    rect.y() + inset,
                    rect.width() - 2 * inset,
                    rect.height() - 2 * inset,
                )
                start = (self._anim_step * 24) % 5760  # в 1/16 градуса
                span = 90 * 16
                # Spin clockwise and 4x faster than original (96 units per tick)
                start = (5760 - (self._anim_step * 384) % 5760)
                p.drawArc(arc_rect, start, span)

            elif status == "Inserting":
                pen = QtGui.QPen(
                    QtGui.QColor(40, 200, 40),
                    6.0,
                    QtCore.Qt.PenStyle.SolidLine,
                    QtCore.Qt.PenCapStyle.RoundCap,
                    QtCore.Qt.PenJoinStyle.RoundJoin,
                )
                p.setPen(pen)
                p.drawLine(
                    QtCore.QPointF(rect.width() * 0.25, rect.height() * 0.50),
                    QtCore.QPointF(rect.width() * 0.50, rect.height() * 0.67),
                )
                p.drawLine(
                    QtCore.QPointF(rect.width() * 0.50, rect.height() * 0.67),
                    QtCore.QPointF(rect.width() * 0.80, rect.height() * 0.33),
                )

            elif status == "Paused":
                p.setPen(QtCore.Qt.PenStyle.NoPen)
                p.setBrush(QtGui.QColor(160, 160, 160, 200))
                bw = 4.0
                h = rect.height() - 10.0
                x1 = rect.width() * 0.5 - 6.0
                x2 = rect.width() * 0.5 + 2.0
                y = 5.0
                p.drawRect(QtCore.QRectF(x1, y, bw, h))
                p.drawRect(QtCore.QRectF(x2, y, bw, h))

            # else: Idle -> только базовая иконка
            p.end()

            # 5) Ставим собранный холст как иконку
            self.setIcon(QtGui.QIcon(canvas))

        except Exception as e:
            logger.error(f"Icon paint failed: {e}")
            self.setIcon(self._base_icon)

    # Hotkey events
    def _on_hold_start(self):
        if not self.listening_enabled or self.paused or self.recording or self.processing:
            return
        try:
            logger.info("Start recording")
            self.recording = True
            self._set_status("Recording")
            self._t_record_start = time.perf_counter()
            self.recorder.start()
        except Exception as e:
            logger.error(f"Recorder start failed: {e}")
            self.recording = False
            self._set_status("Idle")

    def _on_hold_stop(self):
        if not self.recording:
            return
        try:
            logger.info("Stop recording")
            wav_bytes = self.recorder.stop()
            # Compute audio metrics
            audio_bytes = len(wav_bytes) if wav_bytes else 0
            dur_s = 0.0
            if wav_bytes:
                try:
                    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                        frames = wf.getnframes()
                        rate = wf.getframerate() or 16000
                        dur_s = float(frames) / float(rate)
                except Exception:
                    # Fallback to wall-clock
                    took = time.perf_counter() - getattr(self, "_t_record_start", time.perf_counter())
                    dur_s = max(0.0, took)
            logger.info(f"audio_duration_sec={dur_s:.3f} audio_bytes={audio_bytes}")
        except Exception as e:
            logger.error(f"Recorder stop failed: {e}")
            wav_bytes = b""
        finally:
            self.recording = False

        if not wav_bytes or self.paused:
            self._set_status("Idle")
            return

        # Transcribe and insert in background
        self.processing = True
        self._set_status("Transcribing")
        threading.Thread(target=self._transcribe_and_insert, args=(wav_bytes,), daemon=True).start()

    def _transcribe_and_insert(self, wav_bytes: bytes):
        try:
            self._process_audio(wav_bytes)
        finally:
            self.processing = False

    def _process_audio(self, wav_bytes: bytes):
        try:
            api_key = get_api_key()
            transcriber = GeminiTranscriber(api_key=api_key, model=self.settings.gemini_model)
            t0 = time.perf_counter()
            try:
                text = transcriber.transcribe(wav_bytes)
            finally:
                transcriber.client.close()
            took_ms = int((time.perf_counter() - t0) * 1000)
            logger.info(f"processing_ms={took_ms}")
        except Exception as e:
            logger.error(f"Transcribe failed: {e}")
            self.transcribe_error_signal.emit(self._format_transcribe_error(e))
            self._set_status("Idle")
            return

        if not text:
            self._set_status("Idle")
            return

        # Insert
        self._set_status("Inserting")
        try:
            injector = insert_text(text)
            logger.info(f"injector={injector}")
        except Exception as e:
            logger.error(f"Insert failed: {e}")
        finally:
            self._set_status("Idle")


def main():
    app = QtWidgets.QApplication(sys.argv)
    # Keep running with tray icon even when dialogs close
    app.setQuitOnLastWindowClosed(False)
    tray = TrayApp(app)
    tray.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
