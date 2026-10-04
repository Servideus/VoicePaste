import io
import threading
import time
import wave
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6 import QtCore, QtWidgets
from voicepaste import app as vp
from voicepaste import audio_recorder, gemini, injector, settings, ui_settings


@pytest.fixture
def tray(monkeypatch):
    qt = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    qt.setQuitOnLastWindowClosed(False)
    monkeypatch.setattr(vp.HotkeyManager, "enable", lambda self: None)
    monkeypatch.setattr(vp.HotkeyManager, "disable", lambda self: None)
    monkeypatch.setattr(vp.TrayApp, "_show_transcribe_error", lambda self, message: None)
    monkeypatch.setattr(vp, "get_api_key", lambda: "test-only")
    instance = vp.TrayApp(qt)
    yield instance, qt
    instance.timer.stop()
    instance.hide()
    instance.deleteLater()
    qt.processEvents()


def test_record_transcribe_insert_pipeline(tray, monkeypatch):
    instance, qt = tray
    captured = {}
    class Stream:
        def __init__(self, **kwargs):
            self.callback = kwargs["callback"]
        def start(self):
            self.callback(np.array([[-32768], [1000]], dtype=np.int16), 2, None, None)
        def stop(self): pass
        def close(self): pass
    monkeypatch.setattr(audio_recorder.sd, "InputStream", Stream)
    def generate(**kwargs):
        captured["request"] = kwargs
        return SimpleNamespace(text="Проверка VoicePaste.")
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate), close=lambda: None)
    monkeypatch.setattr(gemini.genai, "Client", lambda **kwargs: client)
    clipboard = {"text": "previous clipboard"}
    monkeypatch.setattr(injector.pyperclip, "paste", lambda: clipboard["text"])
    monkeypatch.setattr(injector.pyperclip, "copy", lambda text: clipboard.update(text=text))
    monkeypatch.setattr(injector.keyboard, "send", lambda key: captured.update(key=key, text=clipboard["text"]))
    instance._on_hold_start()
    assert instance.recorder.get_level() == 1.0
    instance._on_hold_stop()
    deadline = time.monotonic() + 3
    while instance.processing and time.monotonic() < deadline:
        qt.processEvents()
        time.sleep(0.01)
    qt.processEvents()
    assert not instance.processing
    assert instance.current_status == "Idle"
    assert captured["key"] == "ctrl+v"
    assert captured["text"] == "Проверка VoicePaste."
    assert clipboard["text"] == "previous clipboard"
    part = captured["request"]["contents"][1]
    with wave.open(io.BytesIO(part.inline_data.data), "rb") as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()) == (16000, 1, 2, 2)


def test_worker_status_updates_only_on_gui_thread(tray, monkeypatch):
    instance, qt = tray
    threads = []
    monkeypatch.setattr(instance, "_update_icon", lambda: threads.append(QtCore.QThread.currentThread()))
    worker = threading.Thread(target=instance._set_status, args=("Transcribing",))
    worker.start()
    worker.join()
    assert threads == []
    qt.processEvents()
    assert threads == [qt.thread()]


def test_no_second_recording_during_processing(tray):
    instance, _ = tray
    instance.processing = True
    instance._on_hold_start()
    assert not instance.recording
    instance.processing = False


def test_cancel_keeps_original_settings(tray, monkeypatch):
    monkeypatch.setattr(ui_settings, "get_api_key", lambda: None)
    original = settings.Settings(hotkey="ctrl+shift")
    dialog = ui_settings.SettingsDialog(original)
    dialog._on_hotkey_captured("alt+f12")
    dialog.model_combo.setCurrentIndex(1)
    dialog.reject()
    assert original.hotkey == "ctrl+shift"
    assert original.gemini_model == settings.DEFAULT_GEMINI_MODEL


def test_credential_failure_is_not_silently_accepted(monkeypatch):
    def fail(*args): raise RuntimeError("credential storage unavailable")
    monkeypatch.setattr(settings.keyring, "set_password", fail)
    with pytest.raises(RuntimeError, match="unavailable"):
        settings.set_api_key("test-only")


@pytest.mark.parametrize("start", [0, 2])
def test_fallback_wraps_after_errors_and_empty_reply_then_inserts_once(tray, monkeypatch, start):
    instance, _ = tray
    models = [model for _, model in settings.GEMINI_MODEL_CHOICES]
    instance.settings.gemini_model = models[start]
    expected = models[start:] + models[:start]
    calls, closed, inserted, errors = [], [], [], []
    outcomes = [RuntimeError("429 quota exceeded"), RuntimeError("404 unavailable"), "  ", "Ответ"]
    class Transcriber:
        def __init__(self, api_key, model):
            self.model = model
            self.client = SimpleNamespace(close=lambda: closed.append(model))
        def transcribe(self, audio, max_retries):
            assert audio == b"same WAV" and max_retries == 1
            calls.append(self.model)
            result = outcomes[len(calls)-1]
            if isinstance(result, Exception):
                raise result
            return result
    monkeypatch.setattr(vp, "GeminiTranscriber", Transcriber)
    monkeypatch.setattr(vp, "insert_text", lambda text: inserted.append(text))
    instance.transcribe_error_signal.connect(errors.append)
    instance._process_audio(b"same WAV")
    assert calls == expected and closed == expected
    assert inserted == ["Ответ"] and errors == []
    assert instance.settings.gemini_model == models[start]
    assert instance.current_status == "Idle"


def test_all_models_fail_show_one_error_without_pasting(tray, monkeypatch):
    instance, _ = tray
    calls, errors = [], []
    def unavailable(**kwargs):
        calls.append(kwargs["model"])
        raise TimeoutError("Connection timed out")
    monkeypatch.setattr(vp, "GeminiTranscriber", unavailable)
    monkeypatch.setattr(vp, "insert_text", lambda _: pytest.fail("Must not paste on failure"))
    instance.transcribe_error_signal.connect(errors.append)
    instance._process_audio(b"WAV")
    assert len(calls) == len(set(calls)) == len(settings.GEMINI_MODEL_CHOICES)
    assert len(errors) == 1 and errors[0].startswith("Все модели")
    assert all(model in errors[0] for model in calls)
    assert instance.current_status == "Idle"
