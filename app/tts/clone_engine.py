"""Your own voice, cloned from a 10–30 second recording (Chatterbox Multilingual, MIT licence).
Runs in a separate Python environment (.venv-clone) — install with: setup_windows.bat clone"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from ..config import ROOT

NAME = "clone"
LABEL = "My cloned voice (Chatterbox)"
LICENCE = "MIT (Chatterbox code + weights); output carries an inaudible AI watermark"
NEEDS_SAMPLE = True
NATIVE_SPEED = False
WORKER = Path(__file__).with_name("clone_worker.py")

LANGS = {"en": "English", "hi": "Hindi", "ar": "Arabic", "da": "Danish", "de": "German", "el": "Greek",
         "es": "Spanish", "fi": "Finnish", "fr": "French", "he": "Hebrew", "it": "Italian",
         "ja": "Japanese", "ko": "Korean", "ms": "Malay", "nl": "Dutch", "no": "Norwegian",
         "pl": "Polish", "pt": "Portuguese", "ru": "Russian", "sv": "Swedish", "sw": "Swahili",
         "tr": "Turkish", "zh": "Chinese"}


def _python():
    for p in (ROOT / ".venv-clone" / "Scripts" / "python.exe", ROOT / ".venv-clone" / "bin" / "python"):
        if p.exists():
            return str(p)
    try:                                   # also fine if installed into the main environment
        import importlib.util
        if importlib.util.find_spec("chatterbox"):
            return sys.executable
    except Exception:
        pass
    return None


def available():
    py = _python()
    return (True, "ready" + (" (GPU)" if has_gpu() else " (CPU — slow, see estimate)")) if py else \
        (False, "not installed — run: setup_windows.bat clone")


def has_gpu():
    return shutil.which("nvidia-smi") is not None


def voices():
    return [{"id": k, "label": f"My voice — {v}", "lang": k, "gender": ""} for k, v in LANGS.items()]


def synth_batch(items, voice, lang, ref, progress=lambda done, total: None, cancelled=lambda: False):
    """items = [(text, raw_wav_path)]. One model load for the whole batch."""
    if not ref or not Path(ref).exists():
        raise RuntimeError("Record or upload a voice sample first (Voice section).")
    lang = (voice or lang or "en")[:2]
    if lang not in LANGS:
        lang = "en"
    with tempfile.TemporaryDirectory() as td:
        job = Path(td) / "job.json"
        job.write_text(json.dumps({"ref": str(ref), "lang": lang, "exaggeration": 0.45, "cfg": 0.5,
                                   "items": [{"text": t, "out": str(o)} for t, o in items]}), encoding="utf-8")
        proc = subprocess.Popen([_python(), str(WORKER), str(job)], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        log = []
        for line in proc.stdout:
            log.append(line)
            if line.startswith("PROGRESS"):
                _, done, total = line.split()
                progress(int(done), int(total))
            if cancelled():
                proc.kill()
                break
        proc.wait()
        if proc.returncode != 0 and not cancelled():
            raise RuntimeError("Voice clone failed:\n" + "".join(log[-15:]))


def synth(text, voice, lang, speed, out_path, ref=None):
    synth_batch([(text, out_path)], voice, lang, ref)
