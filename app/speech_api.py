"""OpenAI-compatible speech endpoint backed by the app's offline engines (Kokoro / Piper / eSpeak / Windows).

    POST /v1/audio/speech   {"input": "...", "voice": "kokoro:af_heart", "speed": 1.0, "response_format": "wav"|"mp3"}
    GET  /v1/audio/voices   {"voices": [{"id": "kokoro:af_heart", "name": ..., "lang": ..., "gender": ...}]}

Used by the Video & Voice Studio page (studio/studio.html), also when that page is hosted on
GitHub Pages: the browser may call http://localhost from an https page, so CORS and
Private-Network-Access headers are sent for allowed origins (localhost, LAN, *.github.io, or
the list in DTC_CORS_ORIGINS)."""
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
STOCK = ("kokoro", "piper", "sapi", "espeak")   # the clone engine needs a per-project sample, so not offered here


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
    return out


@bp.get("/v1/audio/voices")
def voices():
    return jsonify(voices=_voices(), default_engine=tts.default_engine())


def _resolve(voice):
    """'engine:voice' -> (engine, voice id, lang). Accepts OpenAI names and bare voice ids too."""
    voice = (voice or "").strip()
    if ":" in voice:
        engine, vid = voice.split(":", 1)
    else:
        engine, vid = tts.default_engine(), OPENAI_NAMES.get(voice.lower(), voice)
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
        return _error(503, "No offline voice engine is installed. Run setup_windows.bat.", "server_error")
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "speech.wav"
        try:
            tts.synthesize(engine, text, vid, lang, speed, wav)
        except Exception as e:  # engine failures are reported, not crashed on
            return _error(500, f"{engine} failed: {e}", "server_error")
        if fmt == "mp3":
            mp3 = Path(td) / "speech.mp3"
            subprocess.run([ffmpeg_bin(), "-loglevel", "error", "-y", "-i", str(wav), "-b:a", "128k", str(mp3)], check=True)
            return Response(mp3.read_bytes(), mimetype="audio/mpeg")
        return Response(wav.read_bytes(), mimetype="audio/wav")
