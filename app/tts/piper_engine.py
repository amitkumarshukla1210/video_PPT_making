"""Piper TTS: put voice files (<name>.onnx + <name>.onnx.json) in models/piper/.
Check each voice's MODEL_CARD licence before monetised use (most are CC0/CC-BY/MIT, a few are not)."""
import json
import wave

from ..config import MODELS_DIR

NAME = "piper"
LABEL = "Piper (40+ languages)"
LICENCE = "GPL-3.0 engine (piper1-gpl); per-voice licences"
DIR = MODELS_DIR / "piper"
_cache = {}


def available():
    try:
        import piper  # noqa: F401
    except ImportError:
        return False, "pip package piper-tts not installed (optional)"
    if not list(DIR.glob("*.onnx")):
        return False, "no voices in models/piper/ — run: python scripts/download_models.py --piper"
    return True, f"{len(list(DIR.glob('*.onnx')))} voice(s)"


def voices():
    out = []
    for onnx in sorted(DIR.glob("*.onnx")):
        lang, gender = onnx.stem.split("-")[0], ""
        meta = onnx.with_suffix(".onnx.json")
        if meta.exists():
            try:
                lang = json.loads(meta.read_text(encoding="utf-8")).get("language", {}).get("code", lang)
            except Exception:
                pass
        out.append({"id": onnx.stem, "label": onnx.stem, "lang": lang.replace("_", "-").lower(), "gender": gender})
    return out


def synth(text, voice, lang, speed, out_path):
    from piper import PiperVoice
    if voice not in _cache:
        _cache[voice] = PiperVoice.load(str(DIR / f"{voice}.onnx"))
    pv = _cache[voice]
    with wave.open(str(out_path), "wb") as wf:
        if hasattr(pv, "synthesize_wav"):          # piper-tts >= 1.3
            try:
                from piper import SynthesisConfig
                pv.synthesize_wav(text, wf, syn_config=SynthesisConfig(length_scale=1.0 / speed))
            except ImportError:
                pv.synthesize_wav(text, wf)
        else:                                      # piper-tts 1.2
            pv.synthesize(text, wf, length_scale=1.0 / speed)
