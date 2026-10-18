"""Local web server. Open http://localhost:8000 on the laptop, or the Wi-Fi address it prints
(e.g. http://192.168.1.20:8000) on your phone. All rendering happens on the laptop."""
import socket
import sys
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, render_template, abort, Response
from werkzeug.utils import secure_filename

from . import jobs, project as P, tts
from .config import HOST, PORT, ROOT
from .ffmpeg_utils import best_encoder, ENCODERS
from .ppt_builder import build_pptx
from .ppt_import import import_pptx
from .script_writer import draft_all, script_text
from .video import render_video, estimate

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}

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
                   encoder=ENCODERS[best_encoder()][0], phone_url=url, qr_svg=qr)


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
    try:
        tts.synthesize(v["engine"] or tts.default_engine(), text[:600], v.get("voice"), v.get("lang"), v.get("speed", 1), out)
    except Exception as e:
        abort(400, str(e))
    return jsonify(url=f"/files/{pid}/audio/preview.wav?v={uuid.uuid4().hex[:6]}")


@app.get("/api/projects/<pid>/estimate")
def est(pid):
    return jsonify(estimate(_proj(pid)))


@app.post("/api/projects/<pid>/render")
def render(pid):
    proj = _proj(pid)
    if not any((s.get("script") or "").strip() for s in proj["slides"]):
        abort(400, "No narration yet — click 'Write narration' first.")

    def work(progress, cancelled):
        build_pptx(proj)
        r = render_video(proj, progress, cancelled)
        return {"video": f"/files/{pid}/out/video.mp4", "srt": f"/files/{pid}/out/subtitles.srt",
                "pptx": f"/files/{pid}/out/presentation.pptx",
                "seconds": round(r["seconds"]), "render_seconds": round(r["render_seconds"])}

    return jsonify(jobs.start(pid, work) | {"cancel": None})


@app.get("/api/projects/<pid>/job")
def job(pid):
    return jsonify(jobs.status(pid))


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
    print("\n  Design to Cost — Presentation & Video Studio")
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
