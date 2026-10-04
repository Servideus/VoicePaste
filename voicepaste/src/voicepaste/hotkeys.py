from __future__ import annotations

import threading
import time
from typing import Callable, Optional, Tuple, Set

from loguru import logger

from .utils import parse_hotkey

# Optional imports (fallback to keyboard if pywin32 path fails)
try:
    import win32con
    import win32gui
    import win32api
except Exception:  # pragma: no cover - environment dependent
    win32con = None  # type: ignore
    win32gui = None  # type: ignore
    win32api = None  # type: ignore

try:
    import keyboard  # fallback
except Exception:  # pragma: no cover
    keyboard = None  # type: ignore


def _vk_from_key(key: Optional[str]) -> Optional[int]:
    if key is None:
        return None
    k = key.lower()
    # Letters/digits
    if len(k) == 1 and k.isalnum():
        if k.isdigit():
            return ord(k)
        return ord(k.upper())
    # Function keys f1..f24
    if k.startswith("f") and k[1:].isdigit():
        n = int(k[1:])
        if 1 <= n <= 24:
            return getattr(win32con, f"VK_F{n}", None)
    # Specials
    mapping = {
        "tab": win32con.VK_TAB if win32con else None,
        "enter": win32con.VK_RETURN if win32con else None,
        "esc": win32con.VK_ESCAPE if win32con else None,
        "space": win32con.VK_SPACE if win32con else None,
        "backspace": win32con.VK_BACK if win32con else None,
        "delete": win32con.VK_DELETE if win32con else None,
        "insert": win32con.VK_INSERT if win32con else None,
        "home": win32con.VK_HOME if win32con else None,
        "end": win32con.VK_END if win32con else None,
        "left": win32con.VK_LEFT if win32con else None,
        "right": win32con.VK_RIGHT if win32con else None,
        "up": win32con.VK_UP if win32con else None,
        "down": win32con.VK_DOWN if win32con else None,
        "page up": win32con.VK_PRIOR if win32con else None,
        "page down": win32con.VK_NEXT if win32con else None,
        "print screen": win32con.VK_SNAPSHOT if win32con else None,
    }
    return mapping.get(k)


def _mod_flags(mods: Set[str]) -> int:
    flags = 0
    if not win32con:
        return flags
    if "ctrl" in mods:
        flags |= win32con.MOD_CONTROL
    if "shift" in mods:
        flags |= win32con.MOD_SHIFT
    if "alt" in mods:
        flags |= win32con.MOD_ALT
    if "windows" in mods:
        flags |= win32con.MOD_WIN
    return flags


class HotkeyManager:
    """
    Global hold-to-talk using RegisterHotKey with a message loop thread.
    Falls back to `keyboard` when only modifiers are used or on failure.
    """

    def __init__(self, hotkey: str, on_start: Callable[[], None], on_stop: Callable[[], None]):
        self._hotkey_str = hotkey
        self._mods, self._key = parse_hotkey(hotkey)
        self._on_start = on_start
        self._on_stop = on_stop
        self._enabled = False
        self._is_down = False
        self._lock = threading.Lock()
        # Win32
        self._thread: Optional[threading.Thread] = None
        self._hwnd: Optional[int] = None
        self._hotkey_id: int = 0xBEEF
        self._use_keyboard_fallback: bool = False
        self._kb_hook = None

    def set_hotkey(self, hotkey: str):
        with self._lock:
            self._hotkey_str = hotkey
            self._mods, self._key = parse_hotkey(hotkey)
        if self._enabled:
            self.disable()
            self.enable()

    def enable(self):
        if self._enabled:
            return
        self._enabled = True
        # Pure-modifier holds are not supported by RegisterHotKey
        if not self._key or not win32con or not win32gui or not win32api:
            self._use_keyboard_fallback = True
            self._enable_keyboard()
            logger.info(f"Hotkey enabled (fallback): {self._hotkey_str}")
            return
        try:
            self._start_win32_loop()
            logger.info(f"Hotkey enabled: {self._hotkey_str}")
        except Exception as e:
            logger.error(f"Win32 hotkey failed, fallback to keyboard: {e}")
            self._use_keyboard_fallback = True
            self._enable_keyboard()

    def disable(self):
        if not self._enabled:
            return
        self._enabled = False
        if self._use_keyboard_fallback:
            try:
                if keyboard and self._kb_hook:
                    keyboard.unhook(self._kb_hook)
            except Exception:
                pass
            self._kb_hook = None
        else:
            try:
                if win32gui and self._hwnd:
                    win32gui.PostMessage(self._hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:
                pass
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)
        with self._lock:
            if self._is_down:
                self._is_down = False
                try:
                    self._on_stop()
                except Exception:
                    pass

    # Keyboard fallback (used for pure modifiers or when win32 path fails)
    def _enable_keyboard(self):
        if not keyboard:
            logger.error("keyboard module unavailable; hotkey disabled")
            return
        self._kb_hook = keyboard.hook(self._kb_handle)

    def _kb_mods_pressed(self) -> bool:
        if not keyboard:
            return False
        mapping = {"ctrl": "ctrl", "shift": "shift", "alt": "alt", "windows": "windows"}
        for m in self._mods:
            key = mapping.get(m, m)
            try:
                if not keyboard.is_pressed(key):
                    return False
            except Exception:
                return False
        return True

    def _kb_combo_down(self) -> bool:
        if self._mods and not self._kb_mods_pressed():
            return False
        if self._key:
            try:
                return bool(keyboard and keyboard.is_pressed(self._key))
            except Exception:
                return False
        return bool(self._mods)

    def _kb_handle(self, event):
        if not self._enabled:
            return
        down = self._kb_combo_down()
        with self._lock:
            if down and not self._is_down:
                self._is_down = True
                try:
                    self._on_start()
                except Exception as e:
                    logger.error(f"on_start error: {e}")
            elif not down and self._is_down:
                self._is_down = False
                try:
                    self._on_stop()
                except Exception as e:
                    logger.error(f"on_stop error: {e}")

    # Win32 RegisterHotKey path
    def _start_win32_loop(self) -> None:
        mods = _mod_flags(self._mods)
        vk = _vk_from_key(self._key)
        if vk is None:
            raise RuntimeError("No VK for key")

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == win32con.WM_HOTKEY and int(wparam) == self._hotkey_id:
                # Press detected
                self._on_press()
                return 0
            if msg == win32con.WM_CLOSE:
                try:
                    win32gui.UnregisterHotKey(hwnd, self._hotkey_id)
                except Exception:
                    pass
                win32gui.DestroyWindow(hwnd)
                return 0
            if msg == win32con.WM_DESTROY:
                win32gui.PostQuitMessage(0)
                return 0
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

        def thread_main():
            atom = None
            try:
                wc = win32gui.WNDCLASS()
                wc.lpfnWndProc = wndproc
                wc.lpszClassName = "VoicePasteHotkeyWnd"
                atom = win32gui.RegisterClass(wc)
                hwnd = win32gui.CreateWindow(atom, "", 0, 0, 0, 0, 0, 0, 0, 0, None)
                self._hwnd = hwnd
                win32gui.RegisterHotKey(hwnd, self._hotkey_id, mods, vk)
                win32gui.PumpMessages()
            except Exception as error:
                logger.warning(f"Win32 hotkey unavailable; using keyboard hook: {error}")
                if self._enabled:
                    self._use_keyboard_fallback = True
                    self._enable_keyboard()
            finally:
                try:
                    if self._hwnd and win32gui.IsWindow(self._hwnd):
                        win32gui.UnregisterHotKey(self._hwnd, self._hotkey_id)
                        win32gui.DestroyWindow(self._hwnd)
                except Exception:
                    pass
                self._hwnd = None
                if atom is not None:
                    try:
                        win32gui.UnregisterClass(atom, None)
                    except Exception:
                        pass

        self._thread = threading.Thread(target=thread_main, name="VP-Hotkey", daemon=True)
        self._thread.start()

    def _on_press(self):
        with self._lock:
            if self._is_down:
                return
            self._is_down = True
        try:
            self._on_start()
        except Exception as e:
            logger.error(f"on_start error: {e}")
        # Monitor release
        threading.Thread(target=self._monitor_release, daemon=True).start()

    def _monitor_release(self):
        # Wait until the combo (mods + key) is no longer pressed
        try:
            while True:
                time.sleep(0.01)
                if not self._is_combo_down_win32():
                    break
        except Exception:
            pass
        with self._lock:
            was = self._is_down
            self._is_down = False
        if was:
            try:
                self._on_stop()
            except Exception as e:
                logger.error(f"on_stop error: {e}")

    def _is_combo_down_win32(self) -> bool:
        if not win32api or not win32con:
            return False
        # Check modifiers
        def down(vk: int) -> bool:
            return (win32api.GetAsyncKeyState(vk) & 0x8000) != 0

        ok = True
        if "ctrl" in self._mods:
            ok = ok and (down(win32con.VK_LCONTROL) or down(win32con.VK_RCONTROL))
        if "shift" in self._mods:
            ok = ok and (down(win32con.VK_LSHIFT) or down(win32con.VK_RSHIFT))
        if "alt" in self._mods:
            ok = ok and (down(win32con.VK_LMENU) or down(win32con.VK_RMENU))
        if "windows" in self._mods:
            ok = ok and (down(win32con.VK_LWIN) or down(win32con.VK_RWIN))
        if not ok:
            return False
        vk = _vk_from_key(self._key)
        if vk is None:
            return False
        return down(vk)

