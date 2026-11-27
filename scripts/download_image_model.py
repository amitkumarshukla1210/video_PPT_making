"""One-time download of a picture-creator model into models/hf.
Run by: install_once.bat images (about 2.5 GB), install_once.bat hd (film quality, about 4.8 GB),
or the app's "Get film quality" button (inside .venv-image). Optional argument: the model name."""
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HOME", str(Path(__file__).resolve().parent.parent / "models" / "hf"))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from huggingface_hub import snapshot_download  # noqa: E402

model = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DTC_IMAGE_MODEL", "rupeshs/LCM-dreamshaper-v7-openvino")
print(f"Downloading the picture model {model} (one time)...", flush=True)
print("Saved to", snapshot_download(model, allow_patterns=["*.json", "*.xml", "*.bin", "*.txt"]), flush=True)
