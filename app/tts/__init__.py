"""Offline text-to-speech. Several engines; the app picks the best one that is installed.

  kokoro  - Kokoro-82M (Apache-2.0). Best quality. EN (US/UK), Hindi, Spanish, French,
            Italian, Portuguese. Male + female voices. CPU real-time; GPU optional.
  piper   - Piper (engine GPL-3.0 / MIT legacy; each voice has its own licence).
            40+ languages. Drop .onnx + .onnx.json voice files into models/piper/.
  sapi    - Windows built-in voices via pyttsx3 (fallback, not open-source voices).
  espeak  - eSpeak NG (GPL-3.0). 100+ languages, robotic sound. Last-resort fallback.
"""
import re
import subprocess
from pathlib import Path

from ..config import AUDIO_RATE
from ..ffmpeg_utils import ffmpeg_bin
from . import kokoro_engine, piper_engine, sapi_engine, espeak_engine

ENGINES = {e.NAME: e for e in (kokoro_engine, piper_engine, sapi_engine, espeak_engine)}

# Rough synthesis speed: seconds of compute per second of audio on a typical 4-core laptop CPU.
CPU_COST = {"kokoro": 0.35, "piper": 0.08, "sapi": 0.1, "espeak": 0.02}


def status():
    out = []
    for name, e in ENGINES.items():
        ok, info = e.available()
        out.append({"name": name, "label": e.LABEL, "licence": e.LICENCE, "available": ok,
                    "info": info, "voices": e.voices() if ok else []})
    return out


def default_engine():
    for name, e in ENGINES.items():
        if e.available()[0]:
            return name
    return None


def clean_for_speech(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    text = text.replace("&", " and ").replace("%", " percent").replace("₹", " rupees ")
    return text


def synthesize(engine, text, voice, lang, speed, out_wav):
    """Synthesize text and normalise to mono 48 kHz 16-bit WAV. Returns duration in seconds."""
    e = ENGINES.get(engine)
    if e is None or not e.available()[0]:
        raise RuntimeError(f"Voice engine '{engine}' is not installed. See README > Voices.")
    out_wav = Path(out_wav)
    raw = out_wav.with_suffix(".raw.wav")
    text = clean_for_speech(text)
    if not text:
        raise ValueError("empty text")
    e.synth(text, voice, lang, float(speed or 1.0), raw)
    subprocess.run([ffmpeg_bin(), "-y", "-loglevel", "error", "-i", str(raw),
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-ar", str(AUDIO_RATE), "-ac", "1", "-sample_fmt", "s16", str(out_wav)], check=True)
    raw.unlink(missing_ok=True)
    return wav_duration(out_wav)


def wav_duration(path):
    import wave
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())
