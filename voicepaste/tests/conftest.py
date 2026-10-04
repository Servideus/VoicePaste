import os
import sys
from pathlib import Path
import tempfile

# Keep tests away from personal settings, logs and the interactive desktop.
_profile = tempfile.TemporaryDirectory(prefix="voicepaste-tests-")
os.environ["APPDATA"] = _profile.name
os.environ["LOCALAPPDATA"] = _profile.name
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def pytest_sessionstart(session):
    # Ensure absolute imports from voicepaste/ work when running tests from repo root
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

