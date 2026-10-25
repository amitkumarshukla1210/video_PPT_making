"""A project is one folder under projects/ holding project.json plus uploads and outputs."""
import json
import re
import shutil
import threading
import time
import uuid
from pathlib import Path

from .config import PROJECTS_DIR

_lock = threading.Lock()


def _slide(kind, title="", notes="", image=None, script=""):
    return {"id": uuid.uuid4().hex[:8], "kind": kind, "title": title,
            "notes": notes, "image": image, "script": script, "clip": None, "clip_seconds": 0}


def new_project(name):
    pid = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "project"
    pid = f"{pid}-{uuid.uuid4().hex[:5]}"
    folder = PROJECTS_DIR / pid
    for sub in ("uploads", "audio", "frames", "out"):
        (folder / sub).mkdir(parents=True, exist_ok=True)
    data = {
        "id": pid,
        "name": name,
        "title": name,
        "subtitle": "Product walkthrough",
        "presenter": "",
        "company": "",
        "contact": "",
        "logo": None,
        "language": "en",
        "voice": {"engine": "", "voice": "", "lang": "en-us", "speed": 1.0},
        "music": {"file": None, "volume": 0.12},
        "voice_sample": None,
        "intro": True,
        "pip": {"enabled": False, "photo": None, "position": "br", "shape": "circle", "size": "m"},
        "created": time.strftime("%Y-%m-%d %H:%M"),
        "slides": [
            _slide("title", name, "Product walkthrough"),
            _slide("closing", "Thank you", "Questions & next steps"),
        ],
    }
    save(data)
    return data


def folder(pid):
    if not re.fullmatch(r"[a-z0-9-]+", pid or ""):
        raise ValueError("bad project id")
    return PROJECTS_DIR / pid


def load(pid):
    data = json.loads((folder(pid) / "project.json").read_text(encoding="utf-8"))
    data.setdefault("voice_sample", None)            # projects made before these features existed
    data.setdefault("intro", True)
    data.setdefault("pip", {"enabled": False, "photo": None, "position": "br", "shape": "circle", "size": "m"})
    return data


def save(data):
    path = folder(data["id"]) / "project.json"
    with _lock:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)


def list_projects():
    out = []
    for p in sorted(PROJECTS_DIR.glob("*/project.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            out.append({"id": d["id"], "name": d["name"], "created": d.get("created", ""),
                        "slides": len(d["slides"])})
        except Exception:
            continue
    return out


def delete(pid):
    shutil.rmtree(folder(pid), ignore_errors=True)


def add_content_slide(data, title, notes="", image=None):
    """Insert before the closing slide (if there is one)."""
    s = _slide("content", title, notes, image)
    idx = len(data["slides"])
    if data["slides"] and data["slides"][-1]["kind"] == "closing":
        idx -= 1
    data["slides"].insert(idx, s)
    return s


def title_from_filename(name):
    stem = Path(name).stem
    stem = re.sub(r"^\d+[\s_.-]*", "", stem)          # "01_cost-summary" -> "cost-summary"
    stem = re.sub(r"[_-]+", " ", stem).strip()
    return stem[:1].upper() + stem[1:] if stem else "Screen"
