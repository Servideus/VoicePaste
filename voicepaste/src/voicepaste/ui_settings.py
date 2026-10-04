from __future__ import annotations

from typing import Optional, Tuple
from dataclasses import replace

from PySide6 import QtCore, QtGui, QtWidgets

from .settings import DEFAULT_GEMINI_MODEL, GEMINI_MODEL_CHOICES, Settings, get_api_key, set_api_key
from .utils import format_hotkey_str


class HotkeyCaptureLine(QtWidgets.QLineEdit):
    captured = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self._mods: set[str] = set()
        self._key: Optional[str] = None
        self.setPlaceholderText("Нажмите сочетание (Ctrl/Shift/Alt/Win + клавиша)")

    @staticmethod
    def _qt_key_to_name(e: QtGui.QKeyEvent) -> Optional[str]:
        k = e.key()
        QtK = QtCore.Qt.Key
        # Ignore pure modifier keys as the main key
        if k in (QtK.Key_Control, QtK.Key_Shift, QtK.Key_Alt, QtK.Key_Meta):
            return None
        # Function keys
        if QtK.Key_F1 <= k <= QtK.Key_F35:
            return f"f{k - QtK.Key_F1 + 1}"
        # Specials
        mapping = {
            QtK.Key_Tab: "tab",
            QtK.Key_Return: "enter",
            QtK.Key_Enter: "enter",
            QtK.Key_Escape: "esc",
            QtK.Key_Space: "space",
            QtK.Key_Backspace: "backspace",
            QtK.Key_Delete: "delete",
            QtK.Key_Insert: "insert",
            QtK.Key_Home: "home",
            QtK.Key_End: "end",
            QtK.Key_Left: "left",
            QtK.Key_Right: "right",
            QtK.Key_Up: "up",
            QtK.Key_Down: "down",
            QtK.Key_PageUp: "page up",
            QtK.Key_PageDown: "page down",
            QtK.Key_Print: "print screen",
        }
        if k in mapping:
            return mapping[k]
        # Letters/digits and other single printable characters
        text = e.text() or ""
        if len(text) == 1 and text.isprintable():
            return text.lower()
        return None

    def keyPressEvent(self, e: QtGui.QKeyEvent):
        mod = e.modifiers()
        mods: set[str] = set()
        if mod & QtCore.Qt.KeyboardModifier.ControlModifier:
            mods.add("ctrl")
        if mod & QtCore.Qt.KeyboardModifier.ShiftModifier:
            mods.add("shift")
        if mod & QtCore.Qt.KeyboardModifier.AltModifier:
            mods.add("alt")
        if mod & QtCore.Qt.KeyboardModifier.MetaModifier:
            mods.add("windows")
        self._mods = mods
        key = HotkeyCaptureLine._qt_key_to_name(e)
        if key:
            self._key = key
        s = format_hotkey_str(self._mods, self._key)
        self.setText(s)
        e.accept()

    def keyReleaseEvent(self, e: QtGui.QKeyEvent):
        s = format_hotkey_str(self._mods, self._key)
        self.captured.emit(s)
        e.accept()


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки VoicePaste")
        self.setMinimumWidth(420)
        self._original_settings = settings
        self._settings = replace(settings)

        layout = QtWidgets.QVBoxLayout(self)

        # API key
        api_group = QtWidgets.QGroupBox("API‑ключ Gemini")
        api_layout = QtWidgets.QGridLayout(api_group)
        api_label = QtWidgets.QLabel("Ключ:")
        self.api_edit = QtWidgets.QLineEdit()
        self.api_edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        model_label = QtWidgets.QLabel("Модель:")
        self.model_combo = QtWidgets.QComboBox()
        for label, model_id in GEMINI_MODEL_CHOICES:
            self.model_combo.addItem(label, model_id)
        idx = self.model_combo.findData(settings.gemini_model or DEFAULT_GEMINI_MODEL)
        if idx < 0:
            idx = self.model_combo.findData(DEFAULT_GEMINI_MODEL)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        btn_check = QtWidgets.QPushButton("Проверить")
        btn_save_key = QtWidgets.QPushButton("Сохранить ключ")
        api_layout.addWidget(api_label, 0, 0)
        api_layout.addWidget(self.api_edit, 0, 1, 1, 2)
        api_layout.addWidget(model_label, 1, 0)
        api_layout.addWidget(self.model_combo, 1, 1, 1, 2)
        api_layout.addWidget(btn_check, 2, 1)
        api_layout.addWidget(btn_save_key, 2, 2)
        layout.addWidget(api_group)

        # Hotkey
        hk_group = QtWidgets.QGroupBox("Горячая клавиша (hold‑to‑talk)")
        hk_layout = QtWidgets.QHBoxLayout(hk_group)
        self.hk_edit = HotkeyCaptureLine()
        self.hk_edit.setText(settings.hotkey)
        hk_layout.addWidget(self.hk_edit)
        layout.addWidget(hk_group)

        # Buttons
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(btns)

        # Load existing key
        current_key = get_api_key()
        if current_key:
            self.api_edit.setText(current_key)

        # Connections
        self.hk_edit.captured.connect(self._on_hotkey_captured)
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        btn_check.clicked.connect(self._on_check)
        btn_save_key.clicked.connect(self._on_save_key)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

    def _on_hotkey_captured(self, s: str):
        if s:
            self._settings.hotkey = s

    def _on_model_changed(self, index: int):
        model = self.model_combo.itemData(index)
        if isinstance(model, str) and model:
            self._settings.gemini_model = model

    def _on_save_key(self):
        key = self.api_edit.text().strip()
        try:
            set_api_key(key or None)
        except Exception as error:
            QtWidgets.QMessageBox.critical(self, "VoicePaste", f"Не удалось сохранить ключ: {error}")
            return
        QtWidgets.QMessageBox.information(self, "VoicePaste", "Ключ сохранён в Credential Manager.")

    def _on_check(self):
        from .gemini import GeminiTranscriber
        key = self.api_edit.text().strip() or None
        model = self.model_combo.currentData() or DEFAULT_GEMINI_MODEL
        try:
            transcriber = GeminiTranscriber(api_key=key, model=model, timeout_sec=10)
            try:
                transcriber.client.models.get(model=model)
            finally:
                transcriber.client.close()
            QtWidgets.QMessageBox.information(self, "VoicePaste", "API ответил: ключ и модель доступны. Квота на распознавание проверяется при записи.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "VoicePaste", f"Ошибка проверки ключа: {e}")

    def accept(self) -> None:
        # Save settings
        model = self.model_combo.currentData()
        if isinstance(model, str) and model:
            self._settings.gemini_model = model
        try:
            self._settings.save()
        except Exception as error:
            QtWidgets.QMessageBox.critical(self, "VoicePaste", f"Не удалось сохранить настройки: {error}")
            return
        self._original_settings.hotkey = self._settings.hotkey
        self._original_settings.gemini_model = self._settings.gemini_model
        super().accept()
