import ctypes
import pytest
from voicepaste import injector


def test_sendinput_layout_and_utf16(monkeypatch):
    calls = []
    def send(count, events, size):
        calls.append((count, size, [events[i].ki.wScan for i in range(count)]))
        return count
    monkeypatch.setattr(ctypes.windll.user32, "SendInput", send)
    injector.send_unicode_input("Я😀")
    assert ctypes.sizeof(injector.INPUT) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
    assert calls == [(6, ctypes.sizeof(injector.INPUT), [0x42F, 0x42F, 0xD83D, 0xD83D, 0xDE00, 0xDE00])]


def test_sendinput_failure_is_reported(monkeypatch):
    monkeypatch.setattr(ctypes.windll.user32, "SendInput", lambda *args: 0)
    with pytest.raises(OSError, match="0 of 2"):
        injector.send_unicode_input("a")
