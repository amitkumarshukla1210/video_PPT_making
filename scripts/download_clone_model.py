"""Downloads the Chatterbox Multilingual voice-clone model once (about 3 GB) into models/hf.
Run by: setup_windows.bat clone   (inside .venv-clone)."""
import os
from pathlib import Path

os.environ.setdefault("HF_HOME", str(Path(__file__).resolve().parent.parent / "models" / "hf"))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from chatterbox.mtl_tts import ChatterboxMultilingualTTS  # noqa: E402

ChatterboxMultilingualTTS.from_pretrained(device="cpu")
print("Voice clone model ready.")
