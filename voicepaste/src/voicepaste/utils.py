import os
import time
from pathlib import Path
from typing import Tuple


APP_NAME = "VoicePaste"


def appdata_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    p = Path(base) / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def localappdata_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    p = Path(base) / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def logs_dir() -> Path:
    p = localappdata_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def ms() -> int:
    return int(time.time() * 1000)


def format_hotkey_str(mods: set[str], key: str | None = None) -> str:
    """Format hotkey like 'ctrl+shift+f1' or 'tab'."""
    order = ["ctrl", "shift", "alt", "windows"]
    mods_l = [m.lower() for m in mods]
    out = [m for m in order if m in mods_l]
    if key:
        out.append(key.lower())
    return "+".join(out) if out else (key.lower() if key else "")


def parse_hotkey(s: str) -> Tuple[set[str], str | None]:
    """Parse hotkey string into (modifiers, key).
    Supports letters, digits, f1..f24, and names: tab, enter, esc, space,
    arrows, home/end, page up/down, insert/delete/backspace, print screen.
    Modifiers: ctrl/shift/alt/windows(win).
    """
    parts = [p.strip().lower() for p in s.split("+") if p.strip()]
    mod_aliases = {"ctrl": "ctrl", "control": "ctrl", "shift": "shift", "alt": "alt", "win": "windows", "windows": "windows"}
    specials = {
        "tab": "tab", "enter": "enter", "return": "enter", "esc": "esc", "escape": "esc",
        "space": "space", "backspace": "backspace", "delete": "delete", "del": "delete", "insert": "insert", "ins": "insert",
        "home": "home", "end": "end", "left": "left", "right": "right", "up": "up", "down": "down",
        "pageup": "page up", "page_up": "page up", "pgup": "page up", "page up": "page up",
        "pagedown": "page down", "page_down": "page down", "pgdn": "page down", "page down": "page down",
        "printscreen": "print screen", "printscr": "print screen", "prtsc": "print screen",
    }
    mods: set[str] = set()
    key: str | None = None
    for p in parts:
        if p in mod_aliases:
            mods.add(mod_aliases[p])
            continue
        if len(p) >= 2 and p[0] == "f" and p[1:].isdigit():
            n = int(p[1:])
            if 1 <= n <= 24:
                key = f"f{n}"
                continue
        if p in specials:
            key = specials[p]
            continue
        if len(p) == 1 and p.isalnum():
            key = p
            continue
        # ignore unknown pieces
    return mods, key


def parse_hotkey_str(s: str) -> set[str]:
    """Backward compatibility: return only modifiers."""
    mods, _ = parse_hotkey(s)
    return mods

