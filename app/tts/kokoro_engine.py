"""Kokoro-82M via kokoro-onnx (MIT) — model weights Apache-2.0, commercial use allowed."""
import wave

import numpy as np

from ..config import MODELS_DIR

NAME = "kokoro"
LABEL = "Kokoro-82M (best quality)"
LICENCE = "Apache-2.0 (weights) / MIT (kokoro-onnx)"
DIR = MODELS_DIR / "kokoro"

# id, label, kokoro language code, gender
VOICES = [
    ("af_heart", "Heart — US English", "en-us", "female"),
    ("af_bella", "Bella — US English", "en-us", "female"),
    ("af_sarah", "Sarah — US English", "en-us", "female"),
    ("am_michael", "Michael — US English", "en-us", "male"),
    ("am_adam", "Adam — US English", "en-us", "male"),
    ("am_fenrir", "Fenrir — US English", "en-us", "male"),
    ("bf_emma", "Emma — UK English", "en-gb", "female"),
    ("bf_isabella", "Isabella — UK English", "en-gb", "female"),
    ("bm_george", "George — UK English", "en-gb", "male"),
    ("bm_lewis", "Lewis — UK English", "en-gb", "male"),
    ("hf_alpha", "Alpha — Hindi", "hi", "female"),
    ("hf_beta", "Beta — Hindi", "hi", "female"),
    ("hm_omega", "Omega — Hindi", "hi", "male"),
    ("hm_psi", "Psi — Hindi", "hi", "male"),
    ("ef_dora", "Dora — Spanish", "es", "female"),
    ("em_alex", "Alex — Spanish", "es", "male"),
    ("ff_siwis", "Siwis — French", "fr-fr", "female"),
    ("if_sara", "Sara — Italian", "it", "female"),
    ("im_nicola", "Nicola — Italian", "it", "male"),
    ("pf_dora", "Dora — Portuguese (BR)", "pt-br", "female"),
    ("pm_alex", "Alex — Portuguese (BR)", "pt-br", "male"),
]

_model = None


def _files():
    model = next((p for p in (DIR / "kokoro-v1.0.onnx", DIR / "kokoro-v1.0.fp16.onnx",
                              DIR / "kokoro-v1.0.int8.onnx") if p.exists()), None)
    voices = DIR / "voices-v1.0.bin"
    return model, voices if voices.exists() else None


def available():
    try:
        import kokoro_onnx  # noqa: F401
    except ImportError:
        return False, "pip package kokoro-onnx not installed"
    model, voices = _files()
    if not model or not voices:
        return False, "model files missing — run: python scripts/download_models.py"
    return True, f"{model.name} on {_provider()}"


def _provider():
    import onnxruntime as ort
    av = ort.get_available_providers()
    for p in ("CUDAExecutionProvider", "DmlExecutionProvider", "CoreMLExecutionProvider"):
        if p in av:
            return p
    return "CPUExecutionProvider"


def voices():
    return [{"id": v, "label": l, "lang": lang, "gender": g} for v, l, lang, g in VOICES]


def _load():
    global _model
    if _model is None:
        import onnxruntime as ort
        from kokoro_onnx import Kokoro
        model, voices_bin = _files()
        prov = _provider()
        providers = [prov, "CPUExecutionProvider"] if prov != "CPUExecutionProvider" else [prov]
        sess = ort.InferenceSession(str(model), providers=providers)
        _model = Kokoro.from_session(sess, str(voices_bin))
    return _model


def synth(text, voice, lang, speed, out_path):
    lang_for_voice = next((l for v, _, l, _ in VOICES if v == voice), None)
    samples, rate = _load().create(text, voice=voice or "af_heart", speed=speed,
                                   lang=lang_for_voice or lang or "en-us")
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
