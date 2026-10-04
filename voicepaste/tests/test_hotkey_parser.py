import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from voicepaste.utils import parse_hotkey, format_hotkey_str


def test_parse_hotkey_basic():
    mods, key = parse_hotkey("ctrl+shift+tab")
    assert mods == {"ctrl", "shift"}
    assert key == "tab"


def test_parse_hotkey_function_key():
    mods, key = parse_hotkey("alt+f12")
    assert mods == {"alt"}
    assert key == "f12"


def test_format_hotkey_roundtrip():
    mods = {"windows", "ctrl"}
    key = "a"
    s = format_hotkey_str(mods, key)
    assert s == "ctrl+windows+a"
