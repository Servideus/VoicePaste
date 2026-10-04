"""Sequential, resumable benchmark through the actual VoicePaste transcriber."""
import argparse
import hashlib
import json
import random
import re
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "voicepaste/src"))
from loguru import logger
from voicepaste.gemini import GeminiTranscriber
from voicepaste.settings import GEMINI_MODEL_CHOICES, get_api_key

DIRECTORY = ROOT / "benchmark/2026-10-04"
NUMBERS = {
    "четыреста восемьдесят один": "481",
    "две тысячи пятьсот": "2500",
    "двенадцатого": "12",
    "двенадцатое": "12",
    "пятнадцать часов тридцать минут": "1530",
    "пятнадцать тридцать": "1530",
    "два": "2", "двух": "2", "три": "3", "трех": "3",
}
FACTS = {
    "short": [r"запись голоса", r"вставку текста"],
    "instructions": [r"не отправ", r"марии", r"с четверга на пятницу",
                     r"1530", r"не удал", r"резервн"],
    "facts": [r"481", r"2500", r"12 октября", r"не соглас", r"не подтверж",
              r"серге", r"2 кабел", r"не 3"],
}


def normalize(text):
    text = text.lower().replace("ё", "е")
    text = re.sub(r"15\s*[:.]\s*30|15\s*часов\s*30\s*минут", "1530", text)
    text = re.sub(r"2\s+500", "2500", text)
    for phrase, number in NUMBERS.items():
        text = re.sub(r"\b" + phrase + r"\b", number, text)
    return " ".join(re.findall(r"[а-яa-z0-9]+", text))


def edits(reference, output):
    row = list(range(len(output) + 1))
    for i, word in enumerate(reference, 1):
        new = [i]
        for j, other in enumerate(output, 1):
            new.append(min(new[-1] + 1, row[j] + 1, row[j-1] + (word != other)))
        row = new
    return row[-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", default="screen")
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--models", help="Comma-separated IDs; default is every menu model")
    parser.add_argument("--transcribe-mode", choices=("smart", "verbatim"), default="smart")
    args = parser.parse_args()
    if args.transcribe_mode == "verbatim":
        from voicepaste import gemini
        original_post = gemini.httpx.post
        def verbatim_post(url, **kwargs):
            kwargs["json"]["generation_config"]["transcription_config"]["mode"] = {"type": "verbatim"}
            return original_post(url, **kwargs)
        gemini.httpx.post = verbatim_post
    corpus = json.loads((DIRECTORY / "corpus.json").read_text(encoding="utf-8-sig"))
    models = args.models.split(",") if args.models else [m for _, m in GEMINI_MODEL_CHOICES]
    path = DIRECTORY / "results.jsonl"
    previous = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    completed = {(r["phase"], r["round"], r["sample"], r["model"]) for r in previous}
    key = get_api_key()
    if not key:
        raise RuntimeError("No stored Gemini key")
    logger.remove()
    for repeat in range(args.rounds):
        for index, sample in enumerate(corpus):
            sample_id = sample["Id"]
            audio_path = DIRECTORY / "audio" / f"{sample_id}.wav"
            audio = audio_path.read_bytes()
            with wave.open(str(audio_path)) as wav:
                duration = wav.getnframes() / wav.getframerate()
            order = list(models)
            random.Random(20261004 + repeat * 10 + index).shuffle(order)
            for model in order:
                if (args.phase, repeat, sample_id, model) in completed:
                    continue
                result = {"phase": args.phase, "round": repeat, "sample": sample_id,
                          "model": model, "audio_seconds": round(duration, 3),
                          "transcribe_mode": args.transcribe_mode if model == "gemini-3.5-transcribe" else None,
                          "audio_sha256": hashlib.sha256(audio).hexdigest()}
                transcriber = None
                start = time.perf_counter()
                try:
                    transcriber = GeminiTranscriber(api_key=key, model=model, timeout_sec=30)
                    original = transcriber._generate_with_timeout
                    def capture(kwargs):
                        response = original(kwargs)
                        result["resolved_model"] = response.model_version
                        result["thinking_tokens"] = getattr(response.usage_metadata, "thoughts_token_count", None)
                        return response
                    transcriber._generate_with_timeout = capture
                    text = transcriber.transcribe(audio, max_retries=1)
                    result["seconds"] = round(time.perf_counter() - start, 3)
                    result["text"] = text
                    reference = normalize(sample["Text"]).split()
                    normalized = normalize(text)
                    result["word_errors"] = edits(reference, normalized.split())
                    result["reference_words"] = len(reference)
                    result["wer"] = round(result["word_errors"] / len(reference), 4)
                    result["missing_facts"] = [fact for fact in FACTS[sample_id] if not re.search(fact, normalized)]
                    result["ok"] = bool(text.strip())
                except Exception as error:
                    result.update(ok=False, seconds=round(time.perf_counter() - start, 3),
                                  error=f"{type(error).__name__}: {str(error)[:500]}")
                finally:
                    if transcriber:
                        transcriber.client.close()
                with path.open("a", encoding="utf-8") as output:
                    output.write(json.dumps(result, ensure_ascii=False) + "\n")
                print(json.dumps({k: result[k] for k in ("model", "sample", "seconds", "ok")}
                                 | {k: result[k] for k in ("wer", "missing_facts", "error") if k in result},
                                 ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
