"""Offline text-to-speech. Several engines; the app picks the best one that is installed.

  kokoro  - Kokoro-82M (Apache-2.0). Best stock voices. EN (US/UK), Hindi, Spanish, French,
            Italian, Portuguese. Male + female. CPU real-time; GPU optional.
  clone   - Your own voice from a 10-30 s sample (Chatterbox Multilingual, MIT). 23 languages
            incl. Hindi. Separate environment; GPU strongly recommended.
  piper   - Piper (engine GPL-3.0; each voice has its own licence). 40+ languages.
  sapi    - Windows built-in voices via pyttsx3 (fallback, not open-source voices).
  espeak  - eSpeak NG (GPL-3.0). 100+ languages, robotic sound. Last-resort fallback.
"""
import re
import subprocess
from pathlib import Path

from ..config import AUDIO_RATE
from ..ffmpeg_utils import ffmpeg_bin
from . import kokoro_engine, clone_engine, piper_engine, sapi_engine, espeak_engine

ENGINES = {e.NAME: e for e in (kokoro_engine, clone_engine, piper_engine, sapi_engine, espeak_engine)}

# Rough synthesis speed: seconds of compute per second of audio on a typical 4-core laptop CPU.
CPU_COST = {"kokoro": 0.35, "clone": 4.0, "piper": 0.08, "sapi": 0.1, "espeak": 0.02}
GPU_COST = {"kokoro": 0.1, "clone": 0.5}


def status():
    out = []
    for name, e in ENGINES.items():
        ok, info = e.available()
        out.append({"name": name, "label": e.LABEL, "licence": e.LICENCE, "available": ok, "info": info,
                    "needs_sample": getattr(e, "NEEDS_SAMPLE", False), "voices": e.voices() if ok else []})
    return out


def default_engine():
    for name, e in ENGINES.items():
        if not getattr(e, "NEEDS_SAMPLE", False) and e.available()[0]:
            return name
    return None


def cost_per_second(engine):
    e = ENGINES.get(engine)
    gpu = False
    if engine == "kokoro" and e.available()[0]:
        gpu = kokoro_engine._provider() != "CPUExecutionProvider"
    elif engine == "clone":
        gpu = clone_engine.has_gpu()
    return GPU_COST[engine] if gpu and engine in GPU_COST else CPU_COST.get(engine, 0.3)


def clean_for_speech(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    text = text.replace("&", " and ").replace("%", " percent").replace("₹", " rupees ")
    return text


def _finish(raw, out_wav, speed, native_speed):
    """Normalise loudness, apply speed if the engine can't, and convert to mono 48 kHz 16-bit."""
    filters = []
    if not native_speed and abs(speed - 1.0) > 0.01:
        filters.append(f"atempo={max(0.5, min(2.0, speed)):.3f}")
    filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    subprocess.run([ffmpeg_bin(), "-y", "-loglevel", "error", "-i", str(raw), "-af", ",".join(filters),
                    "-ar", str(AUDIO_RATE), "-ac", "1", "-sample_fmt", "s16", str(out_wav)], check=True)
    Path(raw).unlink(missing_ok=True)
    return wav_duration(out_wav)


def _engine(engine):
    e = ENGINES.get(engine)
    if e is None or not e.available()[0]:
        raise RuntimeError(f"Voice engine '{engine}' is not installed. See README > Voices.")
    return e


def synthesize(engine, text, voice, lang, speed, out_wav, ref=None):
    """Synthesize one text. Returns duration in seconds."""
    return synthesize_many(engine, [(text, out_wav)], voice, lang, speed, ref)[0]


def synthesize_many(engine, items, voice, lang, speed, ref=None,
                    progress=lambda done, total: None, cancelled=lambda: False):
    """items = [(text, out_wav)]. Returns durations. Batch engines load their model only once."""
    e = _engine(engine)
    speed = float(speed or 1.0)
    jobs = []
    for text, out in items:
        text = clean_for_speech(text)
        if not text:
            raise ValueError("empty text")
        jobs.append((text, Path(out).with_suffix(".raw.wav"), Path(out)))
    if hasattr(e, "synth_batch"):
        e.synth_batch([(t, raw) for t, raw, _ in jobs], voice, lang, ref, progress, cancelled)
    else:
        for n, (t, raw, _) in enumerate(jobs):
            if cancelled():
                break
            e.synth(t, voice, lang, speed, raw)
            progress(n + 1, len(jobs))
    native = getattr(e, "NATIVE_SPEED", True)
    return [_finish(raw, out, speed, native) for _, raw, out in jobs if raw.exists()]


def wav_duration(path):
    import wave
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())
