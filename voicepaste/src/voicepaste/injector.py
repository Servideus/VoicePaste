from __future__ import annotations

import ctypes
import time
from typing import Optional, Literal

import pyperclip
from loguru import logger
import keyboard


# WinAPI constants for SendInput
ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_ushort),
                ("wParamH", ctypes.c_ushort)]


class INPUT(ctypes.Structure):
    class _I(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

    _anonymous_ = ("i",)
    _fields_ = [("type", ctypes.c_ulong), ("i", _I)]


INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004


def send_unicode_input(text: str):
    # Send Unicode chars directly to the foreground window
    inputs = []
    encoded = text.encode("utf-16-le")
    for offset in range(0, len(encoded), 2):
        code_unit = int.from_bytes(encoded[offset:offset + 2], "little")
        # Key down
        ki_down = KEYBDINPUT(0, code_unit, KEYEVENTF_UNICODE, 0, 0)
        inputs.append(INPUT(type=INPUT_KEYBOARD, ki=ki_down))
        # Key up
        ki_up = KEYBDINPUT(0, code_unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0)
        inputs.append(INPUT(type=INPUT_KEYBOARD, ki=ki_up))

    n = len(inputs)
    if n == 0:
        return
    arr = (INPUT * n)(*inputs)
    sent = ctypes.windll.user32.SendInput(n, arr, ctypes.sizeof(INPUT))
    if sent != n:
        raise OSError(f"SendInput inserted {sent} of {n} events (blocked or elevated target)")


def insert_text(text: str) -> Literal["Clipboard", "SendInput", "None"]:
    if not text:
        return "None"
    logger.info("Insert text via clipboard")
    # Clipboard path
    try:
        prev = None
        try:
            prev = pyperclip.paste()
        except Exception:
            prev = None
        pyperclip.copy(text)
        time.sleep(0.05)
        keyboard.send("ctrl+v")
        time.sleep(0.05)
        if prev is not None:
            pyperclip.copy(prev)
        logger.info("injector=Clipboard")
        return "Clipboard"
    except Exception as e:
        logger.error(f"Clipboard paste failed: {e}")

    # Fallback to SendInput Unicode
    logger.info("Insert text via SendInput fallback")
    try:
        send_unicode_input(text)
        logger.info("injector=SendInput")
        return "SendInput"
    except Exception as e:
        logger.error(f"SendInput failed: {e}")
        return "None"
