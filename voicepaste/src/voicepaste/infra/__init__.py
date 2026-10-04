from __future__ import annotations

# Thin re-exports to preserve current imports while exposing a modular layout
from voicepaste.audio_recorder import AudioRecorder  # noqa: F401
from voicepaste.gemini import GeminiTranscriber  # noqa: F401
from voicepaste.hotkeys import HotkeyManager  # noqa: F401
from voicepaste.injector import insert_text  # noqa: F401
from voicepaste.settings import Settings, get_api_key, set_api_key  # noqa: F401

