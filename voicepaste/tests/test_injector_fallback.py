import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_injector_fallback_sendinput(monkeypatch):
    from voicepaste import injector as inj

    # Make clipboard path fail
    monkeypatch.setattr(inj.pyperclip, "copy", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("clipboard fail")))
    monkeypatch.setattr(inj.pyperclip, "paste", lambda: "prev")

    sent: dict[str, int] = {"calls": 0}

    def fake_send_unicode_input(text: str):
        sent["calls"] += 1

    monkeypatch.setattr(inj, "send_unicode_input", fake_send_unicode_input)

    used = inj.insert_text("hello")
    assert used == "SendInput"
    assert sent["calls"] == 1
