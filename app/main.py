"""Local web server. Open http://localhost:8000 on the laptop, or the Wi-Fi address it prints
(e.g. http://192.168.1.20:8000) on your phone. All rendering happens on the laptop."""
import socket
import sys
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, render_template, abort, Response
from werkzeug.utils import secure_filename

from . import jobs, media, project as P, tts
from .config import HOST, PORT, MAX_VIDEO_SECONDS, APP_NAME, MODULE_NAME
from .ffmpeg_utils import best_encoder, ENCODERS
from .ppt_builder import build_pptx
from .ppt_import import import_pptx
from .script_writer import draft_all, script_text
from .video import render_video, estimate, export, PRESETS

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm", ".aac", ".opus", ".mp4", ".3gp", ".amr"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".3gp", ".avi"}

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024   # 1 GB uploads


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))   # no packet is sent; just picks the Wi-Fi interface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def _save_upload(pid, f, allowed, prefix):
    ext = Path(f.filename or "").suffix.lower()
    if ext not in allowed:
        abort(400, f"File type {ext or '?'} not allowed")
    name = f"uploads/{prefix}_{uuid.uuid4().hex[:6]}_{secure_filename(Path(f.filename).stem)[:40]}{ext}"
    f.save(P.folder(pid) / name)
    return name


def _proj(pid):
    try:
        return P.load(pid)
    except (FileNotFoundError, ValueError):
        abort(404, "Project not found")


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(500)
def _err(e):
    return jsonify(error=getattr(e, "description", str(e))), getattr(e, "code", 500)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/system")
def system():
    import qrcode
    import qrcode.image.svg
    url = f"http://{lan_ip()}:{PORT}"
    qr = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage).to_string(encoding="unicode")
    return jsonify(engines=tts.status(), default_engine=tts.default_engine(),
                   encoder=ENCODERS[best_encoder()][0], phone_url=url, qr_svg=qr,
                   max_seconds=MAX_VIDEO_SECONDS, presets={k: v[0] for k, v in PRESETS.items()})


@app.get("/api/projects")
def projects():
    return jsonify(P.list_projects())


@app.post("/api/projects")
def create():
    name = (request.json or {}).get("name", "").strip() or "Design to Cost"
    proj = P.new_project(name)
    proj["voice"]["engine"] = tts.default_engine() or ""
    P.save(proj)
    return jsonify(proj)


@app.get("/api/projects/<pid>")
def get(pid):
    return jsonify(_proj(pid))


@app.put("/api/projects/<pid>")
def update(pid):
    proj = _proj(pid)
    body = request.json or {}
    for k in ("name", "title", "subtitle", "presenter", "company", "contact", "language"):
        if k in body:
            proj[k] = str(body[k])
    if "voice" in body:
        proj["voice"].update({k: body["voice"][k] for k in ("engine", "voice", "lang", "speed") if k in body["voice"]})
    if "music" in body and "volume" in body["music"]:
        proj["music"]["volume"] = float(body["music"]["volume"])
    if "intro" in body:
        proj["intro"] = bool(body["intro"])
    if "pip" in body:
        pip = proj.setdefault("pip", {"enabled": False, "photo": None, "position": "br", "shape": "circle", "size": "m"})
        b = body["pip"]
        if "enabled" in b:
            pip["enabled"] = bool(b["enabled"])
        if b.get("position") in ("br", "tr"):
            pip["position"] = b["position"]
        if b.get("shape") in ("circle", "rounded"):
            pip["shape"] = b["shape"]
        if b.get("size") in ("s", "m", "l"):
            pip["size"] = b["size"]
    if "slides" in body:
        old = {s["id"]: s for s in proj["slides"]}
        new = []
        for s in body["slides"]:
            o = old.get(s.get("id"))
            if not o:
                continue
            for k in ("title", "notes", "script"):
                if k in s:
                    o[k] = str(s[k])
            new.append(o)
        proj["slides"] = new
    P.save(proj)
    return jsonify(proj)


@app.delete("/api/projects/<pid>")
def remove(pid):
    P.delete(pid)
    return jsonify(ok=True)


@app.post("/api/projects/<pid>/screens")
def add_screens(pid):
    proj = _proj(pid)
    files = request.files.getlist("files")
    for f in sorted(files, key=lambda f: f.filename or ""):
        name = _save_upload(pid, f, IMAGE_EXT, "shot")
        P.add_content_slide(proj, P.title_from_filename(f.filename), "", name)
    if not files:
        P.add_content_slide(proj, request.form.get("title", "New slide"), request.form.get("notes", ""))
    P.save(proj)
    return jsonify(proj)


@app.post("/api/projects/<pid>/slides/<sid>/image")
def slide_image(pid, sid):
    proj = _proj(pid)
    s = next((s for s in proj["slides"] if s["id"] == sid), None) or abort(404)
    s["image"] = _save_upload(pid, request.files["file"], IMAGE_EXT, "shot")
    P.save(proj)
    return jsonify(proj)


@app.post("/api/projects/<pid>/slides/<sid>/clip")
def slide_clip(pid, sid):
    """Your own recording for this slide (phone camera, webcam or a file)."""
    proj = _proj(pid)
    s = next((s for s in proj["slides"] if s["id"] == sid), None) or abort(404)
    raw = _save_upload(pid, request.files["file"], VIDEO_EXT, "rec")
    dst = f"uploads/clip_{sid}_{uuid.uuid4().hex[:4]}.mp4"
    try:
        secs = media.normalize_clip(P.folder(pid) / raw, P.folder(pid) / dst)
    except Exception as e:
        abort(400, str(e))
    finally:
        (P.folder(pid) / raw).unlink(missing_ok=True)
    proj = _proj(pid)                      # re-read: the conversion may take a while
    s = next((s for s in proj["slides"] if s["id"] == sid), None) or abort(404)
    s["clip"], s["clip_seconds"] = dst, round(secs, 2)
    P.save(proj)
    return jsonify(proj)


@app.delete("/api/projects/<pid>/slides/<sid>/clip")
def slide_clip_delete(pid, sid):
    proj = _proj(pid)
    s = next((s for s in proj["slides"] if s["id"] == sid), None) or abort(404)
    s["clip"], s["clip_seconds"] = None, 0
    P.save(proj)
    return jsonify(proj)


@app.post("/api/projects/<pid>/pip_photo")
def pip_photo(pid):
    proj = _proj(pid)
    if "file" not in request.files:
        proj.setdefault("pip", {})["photo"] = None
    else:
        raw = _save_upload(pid, request.files["file"], IMAGE_EXT, "me")
        dst = f"uploads/presenter_{uuid.uuid4().hex[:4]}.jpg"
        media.normalize_photo(P.folder(pid) / raw, P.folder(pid) / dst)
        pip = proj.setdefault("pip", {"position": "br", "shape": "circle", "size": "m"})
        pip["photo"], pip["enabled"] = dst, True
    P.save(proj)
    return jsonify(proj)


@app.post("/api/projects/<pid>/voice_sample")
def voice_sample(pid):
    """10–30 s of YOUR voice for the voice clone. Consent is required."""
    proj = _proj(pid)
    if "file" not in request.files:
        proj["voice_sample"] = None
        P.save(proj)
        return jsonify(proj)
    if request.form.get("consent") != "yes":
        abort(400, "Please confirm the sample is your own voice (or you have the speaker's written permission).")
    raw = _save_upload(pid, request.files["file"], AUDIO_EXT | VIDEO_EXT, "sample")
    dst = f"uploads/voice_sample_{uuid.uuid4().hex[:4]}.wav"
    try:
        secs = media.normalize_voice_sample(P.folder(pid) / raw, P.folder(pid) / dst)
    except Exception as e:
        abort(400, str(e))
    finally:
        (P.folder(pid) / raw).unlink(missing_ok=True)
    proj["voice_sample"], proj["voice_sample_seconds"] = dst, round(secs, 1)
    proj["voice"]["engine"] = "clone" if tts.ENGINES["clone"].available()[0] else proj["voice"]["engine"]
    P.save(proj)
    return jsonify(proj)


@app.post("/api/projects/<pid>/import_pptx")
def import_ppt(pid):
    proj = _proj(pid)
    f = request.files["file"]
    if Path(f.filename or "").suffix.lower() != ".pptx":
        abort(400, "Please upload a .pptx file (save .ppt as .pptx first)")
    path = P.folder(pid) / "uploads" / f"import_{uuid.uuid4().hex[:6]}.pptx"
    f.save(path)
    n = import_pptx(proj, path)
    P.save(proj)
    return jsonify(proj | {"imported": n})


@app.post("/api/projects/<pid>/logo")
def logo(pid):
    proj = _proj(pid)
    proj["logo"] = _save_upload(pid, request.files["file"], IMAGE_EXT, "logo")
    P.save(proj)
    return jsonify(proj)


@app.delete("/api/projects/<pid>/logo")
def logo_reset(pid):
    proj = _proj(pid)
    proj["logo"] = None
    P.save(proj)
    return jsonify(proj)


@app.post("/api/projects/<pid>/music")
def music(pid):
    proj = _proj(pid)
    if "file" in request.files:
        proj["music"]["file"] = _save_upload(pid, request.files["file"], AUDIO_EXT, "music")
    else:
        proj["music"]["file"] = None
    P.save(proj)
    return jsonify(proj)


@app.post("/api/projects/<pid>/script")
def script(pid):
    proj = _proj(pid)
    draft_all(proj, overwrite=bool((request.json or {}).get("overwrite")))
    P.save(proj)
    return jsonify(proj)


@app.get("/api/projects/<pid>/script.txt")
def script_download(pid):
    proj = _proj(pid)
    return Response(script_text(proj), mimetype="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{pid}-script.txt"'})


@app.post("/api/projects/<pid>/pptx")
def pptx(pid):
    proj = _proj(pid)
    build_pptx(proj)
    return jsonify(url=f"/files/{pid}/out/presentation.pptx")


@app.post("/api/projects/<pid>/preview_voice")
def preview_voice(pid):
    proj = _proj(pid)
    body = request.json or {}
    v = proj["voice"] | {k: body[k] for k in ("engine", "voice", "lang", "speed") if body.get(k)}
    text = body.get("text") or "Welcome to Design to Cost. This is how the narration will sound."
    out = P.folder(pid) / "audio" / "preview.wav"
    ref = str(P.folder(pid) / proj["voice_sample"]) if proj.get("voice_sample") else None
    try:
        tts.synthesize(v["engine"] or tts.default_engine(), text[:600], v.get("voice"), v.get("lang"),
                       v.get("speed", 1), out, ref=ref)
    except Exception as e:
        abort(400, str(e))
    return jsonify(url=f"/files/{pid}/audio/preview.wav?v={uuid.uuid4().hex[:6]}")


@app.get("/api/projects/<pid>/estimate")
def est(pid):
    return jsonify(estimate(_proj(pid)))


@app.post("/api/projects/<pid>/render")
def render(pid):
    proj = _proj(pid)
    if not any((s.get("script") or "").strip() or s.get("clip") for s in proj["slides"]):
        abort(400, "No narration yet — click 'Write narration' first, or record yourself on a slide.")
    if estimate(proj)["video_seconds"] > MAX_VIDEO_SECONDS * 1.1:
        abort(400, f"The video would be longer than {MAX_VIDEO_SECONDS // 60} minutes. Shorten the narration first.")

    def work(progress, cancelled):
        build_pptx(proj)
        r = render_video(proj, progress, cancelled)
        return {"video": f"/files/{pid}/out/video.mp4", "srt": f"/files/{pid}/out/subtitles.srt",
                "pptx": f"/files/{pid}/out/presentation.pptx",
                "seconds": round(r["seconds"]), "render_seconds": round(r["render_seconds"])}

    return jsonify(jobs.start(pid, work) | {"cancel": None})


@app.post("/api/projects/<pid>/export")
def export_start(pid):
    proj = _proj(pid)
    b = request.json or {}
    preset = b.get("preset", "reels")
    if preset not in PRESETS:
        abort(400, "Unknown format")
    a, z = b.get("slide_from"), b.get("slide_to")

    def work(progress, cancelled):
        r = export(proj, preset, a, z, bool(b.get("burn_subs")), progress, cancelled)
        return {"file": f"/files/{pid}/out/{r['file'].name}", "label": r["label"], "seconds": r["seconds"],
                "note": r.get("note")}

    return jsonify(jobs.start(f"{pid}:export", work) | {"cancel": None})


@app.get("/api/projects/<pid>/job")
def job(pid):
    return jsonify(jobs.status(pid) | {"export": jobs.status(f"{pid}:export")})


@app.post("/api/projects/<pid>/cancel")
def cancel(pid):
    jobs.cancel(pid)
    return jsonify(ok=True)


@app.get("/files/<pid>/<path:sub>")
def files(pid, sub):
    if sub.split("/")[0] not in ("uploads", "out", "audio", "frames"):
        abort(404)
    return send_from_directory(P.folder(pid), sub, as_attachment=request.args.get("dl") == "1")


def run():
    from waitress import serve
    url = f"http://{lan_ip()}:{PORT}"
    print(f"\n  {APP_NAME} — {MODULE_NAME}")
    print("  ------------------------------------------------")
    print(f"  On this laptop : http://localhost:{PORT}")
    print(f"  On your phone  : {url}   (same Wi-Fi)")
    print(f"  Voice engine   : {tts.default_engine() or 'NONE — run setup_windows.bat'}")
    print(f"  Video encoder  : {ENCODERS[best_encoder()][0]}")
    print("  Close this window to stop the app.\n")
    sys.stdout.flush()
    serve(app, host=HOST, port=PORT, threads=8, max_request_body_size=app.config["MAX_CONTENT_LENGTH"])


if __name__ == "__main__":
    run()
