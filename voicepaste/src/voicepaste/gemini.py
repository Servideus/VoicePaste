from __future__ import annotations

import time
import random
import base64
import httpx
from typing import Optional, Dict, Any

from loguru import logger

from google import genai
from google.genai import types

from .settings import DEFAULT_GEMINI_MODEL, normalize_gemini_model


PROMPT_RU = (
    "Распознай русскую речь в этом аудиофайле и сразу преобразуй её в аккуратный, связный письменный текст. "
    "Сохраняй факты и смысл, исправь орфографию и пунктуацию. Удали слова-паразиты и ложные старты (э, э-э, эм, ну, как бы, в общем, типа, вот, значит, получается, короче, то есть, собственно, скажем так, в принципе, и подобные слова) и повторы фраз. "
    "Разбей текст на логические абзацы. Верни только конечный текст без любых пояснений."
)


class GeminiTranscriber:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_GEMINI_MODEL,
        timeout_sec: float = 30.0,
    ):
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(timeout_sec * 1000),
                retry_options=types.HttpRetryOptions(attempts=1)),
        )
        self._api_key = api_key
        self._model = normalize_gemini_model(model)
        thinking = None
        if self._model in {"gemini-2.5-flash", "gemini-2.5-flash-lite"}:
            thinking = types.ThinkingConfig(thinking_budget=0)
        elif self._model != "gemini-3.5-transcribe":
            thinking = types.ThinkingConfig(thinking_level="minimal")
        self._config = types.GenerateContentConfig(temperature=0, thinking_config=thinking)
        self._timeout_sec = float(timeout_sec)

    def transcribe(self, audio_wav_bytes: bytes, max_retries: int = 3) -> str:
        audio_part = types.Part.from_bytes(data=audio_wav_bytes, mime_type="audio/wav")

        delay = 1.0
        last_exc: Optional[Exception] = None
        for attempt in range(1, max_retries + 1):
            try:
                if self._model == "gemini-3.5-transcribe":
                    return self._transcribe_special(audio_wav_bytes)
                t0 = time.perf_counter()
                kwargs: Dict[str, Any] = dict(model=self._model, contents=[PROMPT_RU, audio_part])
                if self._config is not None:
                    kwargs["config"] = self._config
                # Call with timeout. Some SDK versions support request_options, others don't.
                response = self._generate_with_timeout(kwargs)
                took_ms = int((time.perf_counter() - t0) * 1000)
                logger.info(f"Gemini transcribe ok in {took_ms} ms")
                usage = getattr(response, "usage_metadata", None)
                logger.info(f"thinking_tokens={getattr(usage, 'thoughts_token_count', None)}")
                text = getattr(response, "text", None)
                if not text:
                    # Some responses may have candidates
                    try:
                        # Fallback to candidates text if available
                        cand = response.candidates[0]
                        text = cand.content.parts[0].text
                    except Exception:
                        text = ""
                return text or ""
            except Exception as e:
                last_exc = e
                msg = str(e)
                retryable = (
                    any(code in msg for code in ["429", "500", "502", "503", "504"]) or
                    isinstance(e, (TimeoutError, httpx.TimeoutException))
                )
                logger.error(f"Gemini error (attempt {attempt}): {e}")
                if attempt < max_retries and retryable:
                    jitter = random.uniform(0.0, delay * 0.1)
                    time.sleep(delay + jitter)
                    delay *= 2
                    continue
                break
        # Out of retries
        if last_exc:
            raise last_exc
        return ""

    def _generate_with_timeout(self, kwargs: Dict[str, Any]):
        return self.client.models.generate_content(**kwargs)

    def _transcribe_special(self, wav_bytes: bytes) -> str:
        # Installed SDK uses the retired Interactions schema; use the current
        # documented REST schema without replacing the working SDK.
        response = httpx.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={"x-goog-api-key": self._api_key},
            json={
                "model": self._model,
                "input": [{"type": "audio", "mime_type": "audio/wav",
                           "data": base64.b64encode(wav_bytes).decode("ascii")}],
                "generation_config": {"transcription_config": {
                    "mode": {"type": "verbatim"}, "language_codes": ["ru-RU"]}},
                "store": False,
            },
            timeout=self._timeout_sec,
        )
        response.raise_for_status()
        return "\n".join(
            content["text"] for step in response.json().get("steps", [])
            if step.get("type") == "model_output"
            for content in step.get("content", [])
            if content.get("type") == "text" and content.get("text")
        )
