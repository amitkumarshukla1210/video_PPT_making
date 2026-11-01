"""Run long tasks (video render) in a background thread; the web page polls the status."""
import threading
import time
import traceback

_jobs = {}
_lock = threading.Lock()


def start(pid, fn):
    """fn(progress, cancelled) -> dict. Only one job per project at a time."""
    with _lock:
        job = _jobs.get(pid)
        if job and job["state"] == "running":
            return job
        job = {"state": "running", "stage": "Starting", "fraction": 0.0, "message": "",
               "started": time.time(), "result": None, "error": None, "cancel": False}
        _jobs[pid] = job

    def progress(stage, frac, msg):
        job.update(stage=stage, fraction=float(frac), message=msg)

    def run():
        try:
            job["result"] = fn(progress, lambda: job["cancel"])
            job["state"] = "done"
        except Exception as e:  # shown in the UI
            from .video import Cancelled
            if isinstance(e, Cancelled):
                job["state"], job["error"] = "cancelled", "Cancelled"
            else:
                job["state"], job["error"] = "error", f"{e}"
                traceback.print_exc()

    threading.Thread(target=run, daemon=True).start()
    return job


def status(pid):
    job = _jobs.get(pid)
    if not job:
        return {"state": "idle"}
    out = {k: v for k, v in job.items() if k not in ("cancel",)}
    out["elapsed"] = round(time.time() - job["started"])
    return out


def cancel(pid):
    if pid in _jobs:
        _jobs[pid]["cancel"] = True
