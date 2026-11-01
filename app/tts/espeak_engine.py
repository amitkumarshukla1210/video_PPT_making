"""eSpeak NG command line (GPL-3.0). Robotic, but tiny and covers 100+ languages."""
import shutil
import subprocess
from pathlib import Path

NAME = "espeak"
LABEL = "eSpeak NG (basic, many languages)"
LICENCE = "GPL-3.0 (program); generated audio is yours"

VOICES = [("en-us", "English US", "male"), ("en-us+f3", "English US", "female"),
          ("en-gb", "English UK", "male"), ("en-gb+f3", "English UK", "female"),
          ("hi", "Hindi", "male"), ("hi+f3", "Hindi", "female"),
          ("de", "German", "male"), ("fr", "French", "male"), ("es", "Spanish", "male"),
          ("ar", "Arabic", "male"), ("ru", "Russian", "male"), ("zh", "Chinese (Mandarin)", "male"),
          ("ja", "Japanese", "male"), ("ta", "Tamil", "male"), ("te", "Telugu", "male"),
          ("mr", "Marathi", "male"), ("bn", "Bengali", "male"), ("gu", "Gujarati", "male")]


def _bin():
    for name in ("espeak-ng", "espeak"):
        p = shutil.which(name)
        if p:
            return p
    for p in (Path(r"C:\Program Files\eSpeak NG\espeak-ng.exe"), Path(r"C:\Program Files (x86)\eSpeak NG\espeak-ng.exe")):
        if p.exists():
            return str(p)
    return None


def available():
    return (True, _bin()) if _bin() else (False, "espeak-ng not installed (optional)")


def voices():
    return [{"id": v, "label": f"{l} ({g})", "lang": v.split("+")[0], "gender": g} for v, l, g in VOICES]


def synth(text, voice, lang, speed, out_path):
    subprocess.run([_bin(), "-v", voice or "en-us", "-s", str(int(165 * speed)), "-w", str(out_path), text],
                   check=True, capture_output=True)
