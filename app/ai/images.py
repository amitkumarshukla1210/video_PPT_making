"""Picture creator: Stable Diffusion (LCM, 4 steps) on OpenVINO, using the Intel/AMD/NVIDIA GPU when
OpenVINO can, otherwise the CPU. Runs in its own environment (.venv-image), installed with
install_once.bat images. Model: rupeshs/LCM-dreamshaper-v7-openvino (CreativeML OpenRAIL-M:
commercial use allowed, with the licence's use restrictions)."""
import atexit
import json
import os
import subprocess
import threading
import sys
import tempfile
from pathlib import Path

from ..config import ROOT

MODEL = os.environ.get("DTC_IMAGE_MODEL", "rupeshs/LCM-dreamshaper-v7-openvino")
WORKER = Path(__file__).with_name("image_worker.py")
SIZES = {"16:9": (768, 432), "9:16": (432, 768), "1:1": (512, 512)}     # the pictures you get


def draw_size(w, h):
    """The size the model draws at: Stable Diffusion needs multiples of 64 (768x432 fails inside the UNet,
    432/8 = 54 latent rows halve to 27, which does not match on the way back up). Drawn a bit larger,
    then trimmed to the exact shape."""
    up = lambda v: max(64, -(-v // 64) * 64)          # noqa: E731 — round up to a multiple of 64
    return up(w), up(h)


def _trim(png_bytes, w, h):
    """Centre-crop a drawn picture to the exact size asked for."""
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(png_bytes))
    if im.size == (w, h):
        return png_bytes
    x, y = (im.width - w) // 2, (im.height - h) // 2
    buf = io.BytesIO()
    im.crop((x, y, x + w, y + h)).save(buf, "PNG")
    return buf.getvalue()


def _python():
    for p in (ROOT / ".venv-image" / "Scripts" / "python.exe", ROOT / ".venv-image" / "bin" / "python"):
        if p.exists():
            return str(p)
    return None


def _model_cached():
    return (ROOT / "models" / "hf" / "hub" / ("models--" + MODEL.replace("/", "--"))).exists()


def model_path():
    """The downloaded model's folder on disk (models/hf/hub/…/snapshots/<rev>). Loading from the folder needs no
    Hugging Face lookup, so it also works offline and with any huggingface-hub version. Falls back to the name."""
    repo = ROOT / "models" / "hf" / "hub" / ("models--" + MODEL.replace("/", "--"))
    try:
        rev = (repo / "refs" / "main").read_text().strip()
        if (repo / "snapshots" / rev / "model_index.json").exists():
            return str(repo / "snapshots" / rev)
    except OSError:
        pass
    snaps = sorted((repo / "snapshots").glob("*/model_index.json")) if (repo / "snapshots").exists() else []
    return str(snaps[-1].parent) if snaps else MODEL


def status():
    if not _python():
        return {"available": False, "info": "Picture creator: run install_once.bat images (about 3 GB, one time)"}
    if not _model_cached():
        return {"available": False, "info": "Picture model not downloaded yet: run install_once.bat images"}
    return {"available": True, "info": f"{MODEL.split('/')[-1]} on OpenVINO"}


LOG = ROOT / "models" / "logs" / "picture_creator.log"
# offline and private: no usage statistics from OpenVINO (it would send to Google Analytics), Hugging Face or others
PRIVATE_ENV = {"OPENVINO_TELEMETRY_OPTOUT": "1", "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
               "HF_HUB_OFFLINE": "1", "PYTHONIOENCODING": "utf-8"}


def _run_worker(args, progress=lambda done, total: None, timeout=None):
    """Runs the worker in .venv-image; keeps its whole output in models/logs/picture_creator.log."""
    env = {**os.environ, **PRIVATE_ENV}
    proc = subprocess.Popen([_python() or sys.executable, str(WORKER), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", env=env)
    log = []
    for line in proc.stdout:
        log.append(line)
        if line.startswith("PROGRESS"):
            _, d, t = line.split()
            progress(int(d), int(t))
    proc.wait(timeout=timeout)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("".join(log), encoding="utf-8")
    return proc.returncode, log


def _explain(log):
    """A short, readable reason for the failure (the full text is in the log file)."""
    err = [l.strip() for l in log if l.startswith(("ERROR", "WARN"))]
    tail = [l.rstrip() for l in log[-6:]]
    return "\n".join(dict.fromkeys(err[-4:] + tail)) + f"\n\nFull log: {LOG}"


CACHE = ROOT / "models" / "ov_cache"       # OpenVINO keeps the compiled model here: next start in seconds
IDLE_SECONDS = 15 * 60                     # the picture creator closes itself after this long unused


class _Server:
    """The picture creator kept running between requests, so the model is loaded only once."""

    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self.timer = None

    def _start(self):
        env = {**os.environ, **PRIVATE_ENV}
        self.proc = subprocess.Popen([_python() or sys.executable, str(WORKER), "--serve"], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                     errors="replace", env=env, bufsize=1)

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        if self.alive():
            try:
                self.proc.stdin.write('{"cmd": "quit"}\n')
                self.proc.stdin.flush()
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()
        self.proc = None

    def _idle(self):
        with self.lock:
            self.stop()

    def job(self, job, progress):
        with self.lock:
            if self.timer:
                self.timer.cancel()
            fresh = not self.alive()
            if fresh:
                self._start()
            log = []
            try:
                self.proc.stdin.write(json.dumps(job) + "\n")
                self.proc.stdin.flush()
                for line in self.proc.stdout:
                    log.append(line)
                    if line.startswith("PROGRESS"):
                        _, d, t = line.split()
                        progress(int(d), int(t))
                    elif line.startswith("INFO model ready"):
                        progress(0, len(job["items"]))
                    if line.strip() == "END":
                        break
            except (BrokenPipeError, OSError):
                pass
            if not log or log[-1].strip() != "END":          # the process died
                self.stop()
                log.append("ERROR the picture creator stopped unexpectedly\n")
            LOG.parent.mkdir(parents=True, exist_ok=True)
            LOG.write_text("".join(log), encoding="utf-8")
            self.timer = threading.Timer(IDLE_SECONDS, self._idle)
            self.timer.daemon = True
            self.timer.start()
            return any(l.strip() == "DONE" for l in log), log


SERVER = _Server()
atexit.register(SERVER.stop)


def generate(prompts, aspect="16:9", seed=None, steps=4, progress=lambda done, total: None):
    """Make one PNG per prompt. Returns a list of PNG bytes. The first picture after starting the app loads the
    model (about a minute, more the very first time); later ones only draw."""
    w, h = SIZES.get(aspect, SIZES["16:9"])
    dw, dh = draw_size(w, h)
    with tempfile.TemporaryDirectory() as td:
        outs = [str(Path(td) / f"img_{i}.png") for i in range(len(prompts))]
        CACHE.mkdir(parents=True, exist_ok=True)
        ok, log = SERVER.job({"model": model_path(), "width": dw, "height": dh, "steps": steps, "seed": seed,
                              "cache": str(CACHE), "items": [{"prompt": p, "out": o} for p, o in zip(prompts, outs)]},
                             progress)
        if not ok:
            raise RuntimeError("Picture creation failed.\n" + _explain(log))
        return [_trim(Path(o).read_bytes(), w, h) for o in outs]


def warm():
    """True when the model is already loaded (the next picture starts at once)."""
    return SERVER.alive()


def check():
    """Test the installation: package versions, devices, loading the model, one small picture.
    Returns a plain-text report the user can copy."""
    head = [f"Picture creator check — model {MODEL}",
            f"Environment: {_python() or 'NOT INSTALLED (run install_once.bat images)'}",
            f"Model files downloaded: {'yes' if _model_cached() else 'NO (run install_once.bat images)'}"]
    if not _python():
        return {"ok": False, "report": "\n".join(head)}
    with SERVER.lock:                      # free the memory of a running picture creator before testing
        SERVER.stop()
    CACHE.mkdir(parents=True, exist_ok=True)
    code, log = _run_worker(["--check", model_path(), str(CACHE)], timeout=1800)
    lines = [l.rstrip() for l in log if l.startswith(("CHECK", "INFO", "WARN", "ERROR"))] or [l.rstrip() for l in log[-15:]]
    if code != 0:
        lines += ["", "Last lines:"] + [l.rstrip() for l in log[-8:]]
    return {"ok": code == 0, "report": "\n".join(head + [""] + lines + ["", f"Full log: {LOG}"])}
