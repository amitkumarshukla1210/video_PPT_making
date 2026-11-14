"""One-time download for the local AI (needs internet once): the Whisper 'small' captions model
(about 460 MB) into models/hf. The writer model is downloaded by Ollama itself (ollama pull)."""
import os
from pathlib import Path

os.environ.setdefault("HF_HOME", str(Path(__file__).resolve().parent.parent / "models" / "hf"))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from faster_whisper.utils import download_model  # noqa: E402

size = os.environ.get("DTC_WHISPER_MODEL", "small")
print(f"Downloading the Whisper '{size}' model for captions (one time)...")
print("Saved to", download_model(size))
