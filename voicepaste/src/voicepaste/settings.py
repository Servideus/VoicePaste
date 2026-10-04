from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from typing import Optional

import keyring

from .utils import appdata_dir


CONFIG_FILE = appdata_dir() / "config.json"
KEYRING_SERVICE = "VoicePaste"
KEYRING_USERNAME = "api_key"

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_MODEL_CHOICES: list[tuple[str, str]] = [
    # Measured medians: benchmark/2026-10-04/report.md; not live estimates.
    ("Gemini 3.5 Transcribe — verbatim (1,96 с)", "gemini-3.5-transcribe"),
    ("Gemini 3.5 Flash Lite (2,37 с)", "gemini-3.5-flash-lite"),
    ("Gemini 3.6 Flash (2,86 с)", "gemini-3.6-flash"),
    ("Gemini Flash Lite Latest — alias (2,90 с)", "gemini-flash-lite-latest"),
]
GEMINI_MODEL_IDS = {model_id for _, model_id in GEMINI_MODEL_CHOICES}


def normalize_gemini_model(value: str | None) -> str:
    if not value or value not in GEMINI_MODEL_IDS:
        return DEFAULT_GEMINI_MODEL
    return value


@dataclass
class Settings:
    hotkey: str = "ctrl+shift"
    gemini_model: str = DEFAULT_GEMINI_MODEL

    def normalize(self) -> None:
        self.gemini_model = normalize_gemini_model(self.gemini_model)

    @staticmethod
    def load() -> "Settings":
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    allowed = {f.name for f in fields(Settings)}
                    filtered = {k: v for k, v in data.items() if k in allowed}
                    settings = Settings(**filtered)
                    settings.normalize()
                    return settings
            except Exception:
                pass
        settings = Settings()
        settings.normalize()
        return settings

    def save(self) -> None:
        self.normalize()
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")


def get_api_key() -> Optional[str]:
    try:
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except Exception:
        return None


def set_api_key(value: Optional[str]) -> None:
    if value:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, value)
    else:
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
        except keyring.errors.PasswordDeleteError:
            pass
