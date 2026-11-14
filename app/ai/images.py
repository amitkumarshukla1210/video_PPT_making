"""Picture creator: Stable Diffusion (LCM, 4 steps) on OpenVINO, using the Intel/AMD/NVIDIA GPU when
OpenVINO can, otherwise the CPU. Runs in its own environment (.venv-image), installed with
install_once.bat images. Model: rupeshs/LCM-dreamshaper-v7-openvino (CreativeML OpenRAIL-M:
commercial use allowed, with the licence's use restrictions)."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from ..config import ROOT

MODEL = os.environ.get("DTC_IMAGE_MODEL", "rupeshs/LCM-dreamshaper-v7-openvino")
WORKER = Path(__file__).with_name("image_worker.py")
SIZES = {"16:9": (768, 432), "9:16": (432, 768), "1:1": (512, 512)}


def _python():
    for p in (ROOT / ".venv-image" / "Scripts" / "python.exe", ROOT / ".venv-image" / "bin" / "python"):
        if p.exists():
            return str(p)
    return None


def _model_cached():
    return (ROOT / "models" / "hf" / "hub" / ("models--" + MODEL.replace("/", "--"))).exists()


def status():
    if not _python():
        return {"available": False, "info": "Picture creator: run install_once.bat images (about 3 GB, one time)"}
    if not _model_cached():
        return {"available": False, "info": "Picture model not downloaded yet: run install_once.bat images"}
    return {"available": True, "info": f"{MODEL.split('/')[-1]} on OpenVINO"}


def generate(prompts, aspect="16:9", seed=None, steps=4, progress=lambda done, total: None):
    """Make one PNG per prompt. Returns a list of PNG bytes."""
    w, h = SIZES.get(aspect, SIZES["16:9"])
    with tempfile.TemporaryDirectory() as td:
        outs = [str(Path(td) / f"img_{i}.png") for i in range(len(prompts))]
        job = Path(td) / "job.json"
        job.write_text(json.dumps({"model": MODEL, "width": w, "height": h, "steps": steps, "seed": seed,
                                   "items": [{"prompt": p, "out": o} for p, o in zip(prompts, outs)]}), encoding="utf-8")
        env = {**os.environ, "HF_HUB_OFFLINE": "1"}
        proc = subprocess.Popen([_python() or sys.executable, str(WORKER), str(job)], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", env=env)
        log = []
        for line in proc.stdout:
            log.append(line)
            if line.startswith("PROGRESS"):
                _, d, t = line.split()
                progress(int(d), int(t))
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError("Picture creation failed:\n" + "".join(log[-12:]))
        return [Path(o).read_bytes() for o in outs]
