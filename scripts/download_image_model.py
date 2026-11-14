"""One-time download of the picture-creator model (about 2.5 GB) into models/hf.
Run by: install_once.bat images (inside .venv-image)."""
import os
from pathlib import Path

os.environ.setdefault("HF_HOME", str(Path(__file__).resolve().parent.parent / "models" / "hf"))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from huggingface_hub import snapshot_download  # noqa: E402

model = os.environ.get("DTC_IMAGE_MODEL", "rupeshs/LCM-dreamshaper-v7-openvino")
print(f"Downloading the picture model {model} (one time, about 2.5 GB)...")
print("Saved to", snapshot_download(model))
