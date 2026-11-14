"""OpenAI-compatible speech endpoint backed by the app's offline engines (Kokoro / Piper / eSpeak / Windows).

    POST /v1/audio/speech   {"input": "...", "voice": "kokoro:af_heart", "speed": 1.0, "response_format": "wav"|"mp3"}
    GET  /v1/audio/voices   {"voices": [{"id": "kokoro:af_heart", "name": ..., "lang": ..., "gender": ...}]}

Used by the Video & Voice Studio page (studio/studio.html), also when that page is hosted on
GitHub Pages: the browser may call http://localhost from an https page, so CORS and
Private-Network-Access headers are sent for allowed origins (localhost, LAN, *.github.io, or
the list in DTC_CORS_ORIGINS)."""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from flask import Blueprint, Response, jsonify, request

from . import tts
from .ffmpeg_utils import ffmpeg_bin

bp = Blueprint("speech_api", __name__)
MAX_INPUT = 5000
# OpenAI voice names -> a sensible offline voice
OPENAI_NAMES = {"alloy": "af_heart", "nova": "af_bella", "shimmer": "bf_emma", "echo": "am_michael",
                "onyx": "am_adam", "fable": "bm_george"}
STOCK = ("kokoro", "piper", "sapi", "espeak")
# "My cloned voice": the Chatterbox clone, using the newest voice sample recorded in the Presentation app.


def my_voice_sample():
    """Newest voice sample that a Presentation project still uses, or None."""
    from .project import PROJECTS_DIR
    best = None
    for pj in PROJECTS_DIR.glob("*/project.json"):
        try:
            rel = json.loads(pj.read_text(encoding="utf-8")).get("voice_sample")
        except (OSError, ValueError):
            continue
        f = pj.parent / rel if rel else None
        if f and f.is_file() and (best is None or f.stat().st_mtime > best.stat().st_mtime):
            best = f
    return best


def _clone_ready():
    return tts.ENGINES["clone"].available()[0] and my_voice_sample() is not None


def _origin_allowed(origin):
    if not origin:
        return False
    extra = [o.strip() for o in os.environ.get("DTC_CORS_ORIGINS", "").split(",") if o.strip()]
    if "*" in extra or origin in extra:
        return True
    return bool(re.match(r"^https?://(localhost|127\.0\.0\.1|\[::1\]|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?$", origin)
                or re.match(r"^https://[a-z0-9-]+\.github\.io$", origin))


@bp.after_app_request
def _cors(resp):
    if not request.path.startswith("/v1/"):
        return resp
    origin = request.headers.get("Origin")
    if _origin_allowed(origin):
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        resp.headers["Access-Control-Max-Age"] = "600"
        if request.headers.get("Access-Control-Request-Private-Network") == "true":
            resp.headers["Access-Control-Allow-Private-Network"] = "true"
    return resp


@bp.route("/v1/audio/speech", methods=["OPTIONS"])
@bp.route("/v1/audio/voices", methods=["OPTIONS"])
def _preflight():
    return Response(status=204)


def _voices():
    out = []
    for name in STOCK:
        e = tts.ENGINES[name]
        if not e.available()[0]:
            continue
        for v in e.voices():
            out.append({"id": f"{name}:{v['id']}", "name": f"{v['label']} ({name})", "lang": v.get("lang", ""),
                        "gender": v.get("gender", ""), "engine": name})
    if _clone_ready():
        for v in tts.ENGINES["clone"].voices():
            out.append({"id": f"clone:{v['id']}", "name": v["label"], "lang": v["lang"], "gender": "", "engine": "clone"})
    return out


@bp.get("/v1/audio/voices")
def voices():
    return jsonify(voices=_voices(), default_engine=tts.default_engine(),
                   clone={"installed": tts.ENGINES["clone"].available()[0], "sample": my_voice_sample() is not None})


def _resolve(voice):
    """'engine:voice' -> (engine, voice id, lang). Accepts OpenAI names and bare voice ids too."""
    voice = (voice or "").strip()
    if ":" in voice:
        engine, vid = voice.split(":", 1)
    else:
        engine, vid = tts.default_engine(), OPENAI_NAMES.get(voice.lower(), voice)
    if engine == "clone" and _clone_ready():
        langs = {v["id"] for v in tts.ENGINES["clone"].voices()}
        vid = vid if vid in langs else "en"
        return "clone", vid, vid
    if engine not in STOCK or not tts.ENGINES[engine].available()[0]:
        engine = tts.default_engine()
    if not engine:
        return None, None, None
    known = {v["id"]: v for v in tts.ENGINES[engine].voices()}
    if vid not in known:
        vid = next(iter(known), "")
    return engine, vid, known.get(vid, {}).get("lang", "en-us")


def _error(status, message, code):
    return jsonify(error={"message": message, "type": code, "code": code}), status


@bp.post("/v1/audio/speech")
def speech():
    body = request.get_json(silent=True) or {}
    text = str(body.get("input") or "").strip()
    if not text:
        return _error(400, "'input' is required.", "invalid_request_error")
    if len(text) > MAX_INPUT:
        return _error(400, f"'input' is longer than {MAX_INPUT} characters; split it into scenes.", "invalid_request_error")
    try:
        speed = float(body.get("speed") or 1.0)
    except (TypeError, ValueError):
        return _error(400, "'speed' must be a number.", "invalid_request_error")
    speed = min(2.0, max(0.5, speed))
    fmt = str(body.get("response_format") or "wav").lower()
    if fmt not in ("wav", "mp3"):
        fmt = "wav"
    engine, vid, lang = _resolve(body.get("voice"))
    if not engine:
        return _error(503, "No offline voice engine is installed. Run install_once.bat.", "server_error")
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "speech.wav"
        try:
            ref = str(my_voice_sample()) if engine == "clone" else None
            tts.synthesize(engine, text, vid, lang, speed, wav, ref=ref)
        except Exception as e:  # engine failures are reported, not crashed on
            return _error(500, f"{engine} failed: {e}", "server_error")
        if fmt == "mp3":
            mp3 = Path(td) / "speech.mp3"
            subprocess.run([ffmpeg_bin(), "-loglevel", "error", "-y", "-i", str(wav), "-b:a", "128k", str(mp3)], check=True)
            return Response(mp3.read_bytes(), mimetype="audio/mpeg")
        return Response(wav.read_bytes(), mimetype="audio/wav")


# ---------- local AI for the Video & Voice Studio (same CORS rules as speech) ----------
@bp.route("/v1/ai/status", methods=["OPTIONS"])
@bp.route("/v1/ai/scenes", methods=["OPTIONS"])
@bp.route("/v1/images/generations", methods=["OPTIONS"])
def _preflight_ai():
    return Response(status=204)


@bp.get("/v1/ai/status")
def ai_status():
    from .ai import llm, images
    return jsonify(llm=llm.status(), images=images.status())


@bp.post("/v1/ai/scenes")
def ai_scenes():
    """Idea → scene script ('# Title' + spoken line per scene) and one picture prompt per scene."""
    from .ai import llm, writer
    b = request.get_json(silent=True) or {}
    idea = str(b.get("idea") or "").strip()
    if not idea:
        return _error(400, "Describe your idea first.", "invalid_request_error")
    if not llm.status()["available"]:
        return _error(503, llm.status()["info"], "server_error")
    args = (idea[:2000], str(b.get("template") or "inspiration"), b.get("scenes") or 5,
            str(b.get("language") or "en"), str(b.get("style") or "")[:200])
    if b.get("background"):          # long videos: run as a job, poll GET /v1/ai/jobs/scenes
        from . import jobs
        job = jobs.start("studio:scenes", lambda progress, cancelled: writer.scenes_from_prompt(
            *args, progress=lambda f, m: progress("Writing scenes", f, m)))
        return jsonify(job={k: v for k, v in job.items() if k != "cancel"}), 202
    try:
        out = writer.scenes_from_prompt(*args)
    except llm.LLMError as e:
        return _error(502, str(e), "server_error")
    return jsonify(out)


@bp.route("/v1/ai/jobs/scenes", methods=["OPTIONS"])
def _preflight_job():
    return Response(status=204)


@bp.get("/v1/ai/jobs/scenes")
def ai_scenes_job():
    from . import jobs
    return jsonify(jobs.status("studio:scenes"))


@bp.post("/v1/images/generations")
def image_generations():
    """OpenAI-style picture creation, offline: {"prompt", "n", "aspect"} → {"data": [{"b64_json"}]}"""
    import base64
    from .ai import images
    b = request.get_json(silent=True) or {}
    prompt = str(b.get("prompt") or "").strip()
    if not prompt:
        return _error(400, "'prompt' is required.", "invalid_request_error")
    if not images.status()["available"]:
        return _error(503, images.status()["info"], "server_error")
    n = max(1, min(4, int(b.get("n") or 1)))
    try:
        pngs = images.generate([prompt[:900]] * n, str(b.get("aspect") or "16:9"), b.get("seed"))
    except RuntimeError as e:
        return _error(500, str(e), "server_error")
    return jsonify(data=[{"b64_json": base64.b64encode(p).decode("ascii")} for p in pngs])


@bp.get("/v1/library")
def library_catalogue():
    from .ai import library
    return jsonify(library.catalogue())


@bp.get("/v1/library/<kind>/<name>.wav")
def library_sound(kind, name):
    from flask import send_file
    from .ai import library
    try:
        path = library.music_file(name) if kind == "music" else library.sfx_file(name) if kind == "sfx" else None
    except KeyError:
        path = None
    if not path:
        return _error(404, "Unknown sound.", "invalid_request_error")
    return send_file(path, mimetype="audio/wav")
