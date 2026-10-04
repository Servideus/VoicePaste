import sys
import pytest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class DummyResponse:
    def __init__(self, text: str):
        self.text = text


class DummyModels:
    def __init__(self, seq):
        self._seq = seq
        self._i = 0
        self.requests = []

    def generate_content(self, **kwargs):
        self.requests.append(kwargs)
        v = self._seq[self._i]
        self._i += 1
        if isinstance(v, Exception):
            raise v
        return DummyResponse(v)


class DummyClient:
    def __init__(self, seq):
        self.models = DummyModels(seq)


def test_gemini_retries(monkeypatch):
    from voicepaste import gemini as gm

    seq = [Exception("429 Too Many Requests"), Exception("500"), "OK"]

    client = DummyClient(seq)
    options = {}
    def fake_client(**kwargs):
        options.update(kwargs)
        return client
    monkeypatch.setattr(gm.genai, "Client", fake_client)
    monkeypatch.setattr(gm.time, "sleep", lambda _: None)

    t = gm.GeminiTranscriber(api_key="x")
    out = t.transcribe(b"RIFF....WAVE")
    assert out == "OK"
    assert options["http_options"].timeout == 30000
    assert options["http_options"].retry_options.attempts == 1
    assert len(client.models.requests) == 3
    assert all(request["model"] == gm.DEFAULT_GEMINI_MODEL for request in client.models.requests)


def test_auth_error_is_not_retried(monkeypatch):
    import pytest
    from voicepaste import gemini as gm
    client = DummyClient([Exception("403 permission denied")])
    monkeypatch.setattr(gm.genai, "Client", lambda **kwargs: client)
    with pytest.raises(Exception, match="403"):
        gm.GeminiTranscriber(api_key="test-only").transcribe(b"RIFF....WAVE")
    assert len(client.models.requests) == 1


def test_transcribe_model_uses_current_schema_and_only_output_text(monkeypatch):
    from voicepaste import gemini as gm
    client = DummyClient([])
    monkeypatch.setattr(gm.genai, "Client", lambda **kwargs: client)
    requests = []
    def post(url, **kwargs):
        requests.append(kwargs)
        return gm.httpx.Response(200, request=gm.httpx.Request("POST", url), json={
            "steps": [{"type": "model_output", "content": [
                {"type": "text", "text": "Готовый текст"}]},
                {"type": "other", "content": [{"type": "text", "text": "Не вставлять"}]}]})
    monkeypatch.setattr(gm.httpx, "post", post)
    transcriber = gm.GeminiTranscriber(api_key="test-only", model="gemini-3.5-transcribe")
    assert transcriber.transcribe(b"WAV") == "Готовый текст"
    assert requests[0]["json"]["store"] is False
    assert requests[0]["json"]["generation_config"]["transcription_config"] == {
        "mode": {"type": "verbatim"}, "language_codes": ["ru-RU"]}
    assert requests[0]["json"]["input"][0]["data"] == "V0FW"
    assert not client.models.requests


@pytest.mark.parametrize("model,level,budget", [
    ("gemini-3.6-flash", "MINIMAL", None),
    ("gemini-3.5-flash-lite", "MINIMAL", None),
    ("gemini-flash-lite-latest", "MINIMAL", None),
    ("gemini-3.5-transcribe", None, None),
])
def test_fast_thinking_respects_model_limits(monkeypatch, model, level, budget):
    from voicepaste import gemini as gm
    monkeypatch.setattr(gm.genai, "Client", lambda **kwargs: DummyClient([]))
    config = gm.GeminiTranscriber(api_key="test-only", model=model)._config.thinking_config
    if model == "gemini-3.5-transcribe":
        assert config is None
    else:
        assert config.thinking_level == level
        assert config.thinking_budget == budget
