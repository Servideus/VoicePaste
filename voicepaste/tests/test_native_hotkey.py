import time
from voicepaste.hotkeys import HotkeyManager, _vk_from_key


def test_digit_uses_main_keyboard_virtual_key():
    assert _vk_from_key("1") == ord("1")


def test_native_hotkey_can_be_reenabled():
    # Only register a rare combination. Do not synthesize user keystrokes.
    manager = HotkeyManager("ctrl+alt+shift+f24", lambda: None, lambda: None)
    try:
        for _ in range(2):
            manager.enable()
            deadline = time.monotonic() + 2
            while manager._hwnd is None and time.monotonic() < deadline:
                time.sleep(0.01)
            assert manager._hwnd is not None
            assert not manager._use_keyboard_fallback
            manager.disable()
            assert manager._thread is not None and not manager._thread.is_alive()
    finally:
        manager.disable()
