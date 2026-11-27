"""Local web server. Open http://localhost:8000 on the laptop, or the Wi-Fi address it prints
(e.g. http://192.168.1.20:8000) on your phone. All rendering happens on the laptop."""
import socket
import sys
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, render_template, abort, Response, redirect
from werkzeug.utils import secure_filename

from . import jobs, media, project as P, tts
from .config import HOST, PORT, MAX_VIDEO_SECONDS, APP_NAME, MODULE_NAME, ROOT
from .speech_api import bp as speech_bp
from .version import app_version
from .ai import llm, writer as ai_writer, dubbing, library
from . import maker, sources, inspirations, motion, tools
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
app.register_blueprint(speech_bp)
STUDIO_DIR = ROOT / "studio"


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
@app.errorhandler(405)
@app.errorhandler(409)
@app.errorhandler(413)
@app.errorhandler(500)
def _err(e):
    return jsonify(error=getattr(e, "description", str(e))), getattr(e, "code", 500)


@app.get("/")
def index():
    return render_template("index.html", version=app_version())


@app.get("/make")
def make_page():
    """Guided flow: source -> script -> voice -> video type."""
    return render_template("make.html", version=app_version(), page="make")


@app.get("/projects")
def projects_page():
    """My projects: every project with its videos, PowerPoint and subtitles."""
    return render_template("projects.html", version=app_version(), page="projects")


@app.get("/inspirations")
def inspirations_page():
    """100 example videos in 9 categories (incl. 12 viral picture presets), to start from."""
    return render_template("inspirations.html", version=app_version(), page="inspirations")


@app.get("/api/inspirations")
def inspirations_list():
    return jsonify(inspirations.catalogue() | {"looks": {k: v["label"] for k, v in motion.LOOKS.items()},
                                               "ai": llm.status()["available"]})


@app.get("/inspirations/thumb/<eid>.jpg")
def inspiration_thumb(eid):
    if eid not in inspirations.BY_ID:
        abort(404)
    return Response(inspirations.thumbnail(eid), mimetype="image/jpeg",
                    headers={"Cache-Control": "max-age=86400"})


@app.get("/inspirations/preview/<eid>.mp4")
def inspiration_preview(eid):
    """About 10 s animated preview with music; made on first play (10–20 s), then served from the cache."""
    if eid not in inspirations.BY_ID:
        abort(404)
    try:
        path = inspirations.preview(eid)
    except Exception as e:
        abort(500, str(e))
    return send_from_directory(path.parent, path.name, mimetype="video/mp4", max_age=86400)


@app.post("/api/inspirations/<eid>/use")
def inspiration_use(eid):
    """A new project from an example. With a topic and the local AI, the AI adapts it (background job)."""
    if eid not in inspirations.BY_ID:
        abort(404, "Unknown example")
    b = request.json or {}
    topic = str(b.get("topic") or "").strip()[:500]
    if inspirations.BY_ID[eid].get("preset"):
        abort(400, "Picture presets are used in Tools › Video with your own photo.")
    proj = inspirations.create(eid, str(b.get("name") or "").strip()[:80] or None)
    pid = proj["id"]
    if not topic:
        return jsonify(project=pid, job=False)
    if not llm.status()["available"]:
        return jsonify(project=pid, job=False, note="The local AI is not running, so the example was kept as it is. "
                                                    "Change the texts in step 2.")
    language = str(b.get("language") or "en")[:5]

    def work(progress, cancelled):
        p = inspirations.adapt(_proj(pid), eid, topic, language, lambda f, m: progress("Adapting the example", f, m))
        P.save(p)
        return {"slides": sum(s["kind"] == "content" for s in p["slides"])}

    jobs.start(f"{pid}:ai", work)
    return jsonify(project=pid, job=True)


# ---------- Tools: Video, Image, Audio, Character, World ----------
TOOL_PAGES = ("character", "image", "world", "audio", "video")     # the order a film is made in


@app.get("/tools")
@app.get("/tools/<tool>")
def tools_page(tool="character"):
    if tool not in TOOL_PAGES:
        abort(404)
    return render_template("tools.html", version=app_version(), page="tool-" + tool, tool=tool)


@app.get("/api/tools/state")
def tools_state():
    from .ai import images
    presets = {e["id"]: {"name": e["name"], "look": e["look"], "music": e["music"], **e["preset"]}
               for e in inspirations.EXAMPLES if e.get("preset")}
    return jsonify(presets=presets, fx=motion.FX,
                   styles={k: v[0] for k, v in tools.STYLES.items()}, looks={k: v["label"] for k, v in motion.LOOKS.items()},
                   moods={k: v["label"] for k, v in library.MOODS.items()}, sfx=library.SFX, engines=tts.status(),
                   default_engine=tts.default_engine(), images=images.status(),
                   characters=tools.refs_with_counts("characters"), worlds=tools.refs_with_counts("worlds"),
                   media={k: tools.media_list(k) for k in tools.KINDS})


@app.get("/media/<kind>/<name>")
def media_file(kind, name):
    try:
        path = tools.media_path(kind, name)
    except (ValueError, FileNotFoundError):
        abort(404)
    return send_from_directory(path.parent, path.name, as_attachment=request.args.get("dl") == "1")


@app.delete("/api/tools/media/<kind>/<name>")
def media_delete(kind, name):
    try:
        tools.delete_media(kind, name)
    except (ValueError, FileNotFoundError):
        abort(404)
    return jsonify(ok=True)


@app.put("/api/tools/media/images/<name>/tags")
def media_tags(name):
    """Which characters / places a picture shows (so it can be found and reused)."""
    try:
        tools.media_path("images", name)
    except (ValueError, FileNotFoundError):
        abort(404)
    tags = [str(t) for t in (request.json or {}).get("tags", [])][:10]
    return jsonify(tools.set_picture(name, tags=tags))


@app.post("/api/tools/<kind>/<rid>/portrait")
def ref_portrait(kind, rid):
    """Use one of My pictures as the character's portrait / the world's view."""
    if kind not in tools.REF_KINDS:
        abort(404)
    item = next((i for i in tools.refs(kind) if i["id"] == rid), None) or abort(404)
    name = str((request.json or {}).get("image") or "")
    try:
        tools.media_path("images", name)
    except (ValueError, FileNotFoundError):
        abort(400, "Choose one of your pictures")
    tools.set_ref_image(kind, rid, name)
    tags = tools.picture_info(name).get("tags", [])
    if item["tag"] not in tags:
        tools.set_picture(name, tags=tags + [item["tag"]])
    return jsonify(ok=True)


@app.post("/api/projects/<pid>/slides/<sid>/from_media")
def slide_from_media(pid, sid):
    """Use a picture from My media (e.g. a character picture) for a scene of a project."""
    proj = _proj(pid)
    s = next((x for x in proj["slides"] if x["id"] == sid), None) or abort(404)
    name = str((request.json or {}).get("name") or "")
    try:
        src = tools.media_path("images", name)
    except (ValueError, FileNotFoundError):
        abort(400, "Picture not found")
    import shutil
    dst = f"uploads/media_{uuid.uuid4().hex[:6]}{src.suffix.lower()}"
    shutil.copyfile(src, P.folder(pid) / dst)
    s["image"] = dst
    P.save(proj)
    return jsonify(proj)


@app.get("/api/tools/job")
def tools_job():
    return jsonify(jobs.status("tools"))


def _tool_job(fn):
    j = jobs.status("tools")
    if j.get("state") == "running":
        abort(409, "Another tool is still working. Wait until it is done.")
    return jsonify(jobs.start("tools", fn) | {"cancel": None})


@app.post("/api/tools/image")
def tool_image():
    b = request.json or {}
    prompt = str(b.get("prompt") or "").strip()[:1500]
    if not prompt:
        abort(400, "Describe the picture first.")
    from .ai import images
    if not images.status()["available"]:
        abort(400, images.status()["info"])
    return _tool_job(lambda progress, cancelled: tools.create_images(
        prompt, str(b.get("style") or "none"), str(b.get("aspect") or "16:9"), b.get("n") or 1,
        lambda f, m: progress("Creating pictures", f, m)))


@app.post("/api/tools/image/check")
def tool_image_check():
    """Picture creator self-test (versions, graphics card, model, one small picture) as a background job."""
    from .ai import images
    return _tool_job(lambda progress, cancelled: (progress("Checking the picture creator", 0.1,
                                                           "Loading the model (1–3 minutes the first time)"),
                                                  images.check())[1])


@app.post("/api/tools/upload")
def tool_upload():
    f = request.files.get("file")
    if not f:
        abort(400, "Choose a picture")
    try:
        return jsonify(name=tools.save_upload(f))
    except ValueError as e:
        abort(400, str(e))


@app.post("/api/tools/clip")
def tool_clip():
    b = request.json or {}
    try:
        tools.media_path("images", str(b.get("image") or ""))
    except (ValueError, FileNotFoundError):
        abort(400, "Choose a picture first.")
    return _tool_job(lambda progress, cancelled: {"video": tools.image_clip(
        b["image"], str(b.get("title") or "")[:120], str(b.get("subtitle") or "")[:200], str(b.get("look") or "cinematic"),
        b.get("seconds") or 6, str(b.get("music") or "cinematic"), lambda f, m: progress("Making the clip", f, m), cancelled,
        fx=str(b.get("fx") or "drift"))})


@app.post("/api/tools/voice")
def tool_voice():
    b = request.json or {}
    try:
        name = tools.voice_over(str(b.get("text") or "")[:5000], b.get("engine"), b.get("voice"), b.get("lang"),
                                b.get("speed") or 1.0)
    except (ValueError, RuntimeError) as e:
        abort(400, str(e))
    return jsonify(name=name, url=f"/media/audio/{name}")


@app.post("/api/tools/music")
def tool_music():
    b = request.json or {}
    try:
        name = tools.music(str(b.get("mood") or ""), b.get("seconds") or 30)
    except ValueError as e:
        abort(400, str(e))
    return jsonify(name=name, url=f"/media/audio/{name}")


@app.post("/api/tools/sfx/<name>")
def tool_sfx(name):
    if name not in library.SFX:
        abort(404)
    out = tools.sfx_copy(name)
    return jsonify(name=out, url=f"/media/audio/{out}")


@app.post("/api/tools/<kind>")
def ref_save(kind):
    if kind not in tools.REF_KINDS:
        abort(404)
    b = request.json or {}
    try:
        item = tools.save_ref(kind, b.get("name"), b.get("description"), b.get("voice"), b.get("image"), b.get("id"))
    except ValueError as e:
        abort(400, str(e))
    return jsonify(item)


@app.delete("/api/tools/<kind>/<rid>")
def ref_delete(kind, rid):
    if kind not in tools.REF_KINDS:
        abort(404)
    tools.delete_ref(kind, rid)
    return jsonify(ok=True)


@app.post("/api/tools/<kind>/<rid>/picture")
def ref_picture(kind, rid):
    """A portrait of the character / a view of the world, made from its description."""
    if kind not in tools.REF_KINDS:
        abort(404)
    item = next((i for i in tools.refs(kind) if i["id"] == rid), None) or abort(404)
    from .ai import images
    if not images.status()["available"]:
        abort(400, images.status()["info"])
    style = "portrait photo, looking at the camera, soft light" if kind == "characters" else "wide establishing shot, cinematic"

    def work(progress, cancelled):
        r = tools.create_images(f"{item['description']}, {style}", "none", "16:9", 1,
                                lambda f, m: progress("Creating the picture", f, m), tags=[item["tag"]])
        tools.set_ref_image(kind, rid, r["images"][0])
        return {"image": r["images"][0]}
    return _tool_job(work)


@app.get("/api/my_projects")
def my_projects():
    return jsonify(maker.library_list())


@app.post("/api/projects/<pid>/source")
def add_source(pid):
    """Step 1 of Make a video: read the PPT / pictures / document / link / text / idea (background job)."""
    _proj(pid)
    f = request.form
    kind = f.get("kind", "")
    if kind not in maker.KINDS:
        abort(400, "Choose what to make the video from")
    allowed = {"pptx": {".pptx"}, "pictures": IMAGE_EXT, "document": sources.DOC_EXT}.get(kind, set())
    saved = [str(P.folder(pid) / _save_upload(pid, x, allowed, "doc")) for x in request.files.getlist("files")]
    if kind in ("pptx", "pictures", "document") and not saved:
        abort(400, "Add at least one file")
    if kind == "url" and not f.get("url", "").strip():
        abort(400, "Paste the web link")
    if kind in ("text", "idea") and not f.get("text", "").strip():
        abort(400, "Write or paste the text first")
    use_ai = f.get("ai", "1") == "1"
    if kind == "idea" and not llm.status()["available"]:
        abort(400, llm.status()["info"])
    try:
        scenes = max(2, min(ai_writer.MAX_SCENES, int(f.get("scenes") or 8)))
    except ValueError:
        scenes = 8

    def work(progress, cancelled):
        return maker.build_from_source(pid, kind, saved, f.get("url", "").strip(), f.get("text", ""), scenes,
                                       f.get("language") or "en", f.get("video_type") or "corporate", use_ai,
                                       f.get("pictures") == "1", f.get("style", ""), progress, cancelled)

    return jsonify(jobs.start(f"{pid}:ai", work) | {"cancel": None})


@app.post("/api/projects/<pid>/pictures")
def ai_pictures(pid):
    """Create a picture (local AI) for every slide that has none."""
    _proj(pid)

    def work(progress, cancelled):
        proj = _proj(pid)
        n = maker.make_pictures(proj, progress, cancelled)
        fresh = _proj(pid)
        for s in fresh["slides"]:
            new = next((x for x in proj["slides"] if x["id"] == s["id"]), None)
            if new and new.get("image") and not s.get("image"):
                s["image"] = new["image"]
        P.save(fresh)
        return {"pictures": n}

    return jsonify(jobs.start(f"{pid}:ai", work) | {"cancel": None})


@app.post("/api/projects/<pid>/make_video")
def make_video(pid):
    """Step 4 of Make a video: render, then the chosen format (YouTube, Reel, corporate, square)."""
    proj = _proj(pid)
    b = request.json or {}
    vtype = b.get("type", "corporate")
    if vtype not in maker.VIDEO_TYPES:
        abort(400, "Unknown video type")
    if not any((s.get("script") or "").strip() or s.get("clip") for s in proj["slides"]):
        abort(400, "No narration yet — go back to step 2 and write the script.")
    if estimate(proj)["video_seconds"] > MAX_VIDEO_SECONDS * 1.1:
        abort(400, f"The video would be longer than {MAX_VIDEO_SECONDS // 60} minutes. Shorten the script first.")
    if b.get("look") in motion.LOOKS:
        proj["look"] = b["look"]
    proj = maker.prepare_video(proj, vtype, str(b.get("music") or "auto"), bool(b.get("captions", True)),
                               b.get("motion"))

    def work(progress, cancelled):
        r = maker.make_video(proj, vtype, bool(b.get("captions", True)), progress, cancelled)
        return r | {"video": f"/files/{pid}/out/{r['file']}", "pptx": f"/files/{pid}/out/presentation.pptx",
                    "srt": f"/files/{pid}/out/subtitles.srt"}

    return jsonify(jobs.start(pid, work) | {"cancel": None})


@app.get("/studio")
def studio_redirect():
    return redirect("/studio/", code=301)        # relative asset paths need the trailing slash


@app.get("/studio/")
def studio_home():
    """Video & Voice Studio (static page, also hostable on GitHub Pages)."""
    return send_from_directory(STUDIO_DIR, "studio.html")


@app.get("/studio/VERSION")
def studio_version():
    return Response(app_version(), mimetype="text/plain")


@app.get("/studio/<path:sub>")
def studio_files(sub):
    return send_from_directory(STUDIO_DIR, sub)


@app.get("/api/system")
def system():
    import qrcode
    import qrcode.image.svg
    url = f"http://{lan_ip()}:{PORT}"
    qr = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage).to_string(encoding="unicode")
    return jsonify(version=app_version(), engines=tts.status(), default_engine=tts.default_engine(),
                   encoder=ENCODERS[best_encoder()][0], phone_url=url, qr_svg=qr,
                   max_seconds=MAX_VIDEO_SECONDS, presets={k: v[0] for k, v in PRESETS.items()},
                   ai=ai_status(), languages=ai_writer.LANGS)


def ai_status():
    from .ai import stt, images
    return {"llm": llm.status(), "stt": stt.status(), "images": images.status()}


@app.get("/api/library")
def library_list():
    return jsonify(library.catalogue())


@app.get("/library/<kind>/<name>.wav")
def library_file(kind, name):
    """Preview / download a library sound (made on first use, then cached)."""
    try:
        path = library.music_file(name) if kind == "music" else library.sfx_file(name) if kind == "sfx" else None
    except KeyError:
        path = None
    if not path:
        abort(404)
    return send_from_directory(path.parent, path.name, mimetype="audio/wav")


@app.post("/api/projects/<pid>/music_library")
def music_from_library(pid):
    """Use a library music bed as the project's background music."""
    proj = _proj(pid)
    mood = (request.json or {}).get("mood")
    if mood not in library.MOODS:
        abort(400, "Unknown music mood")
    maker.use_library_music(proj, mood)
    P.save(proj)
    return jsonify(proj)


@app.post("/api/projects/<pid>/ai_script")
def ai_script(pid):
    """Local AI writes corporate narration from the slides (runs in the background)."""
    _proj(pid)
    b = request.json or {}
    if not llm.status()["available"]:
        abort(400, llm.status()["info"])

    def work(progress, cancelled):
        proj = _proj(pid)
        n = ai_writer.write_narration(proj, b.get("language") or proj.get("language") or "en",
                                      bool(b.get("overwrite")), lambda f, m: progress("AI narration", f, m))
        fresh = _proj(pid)                       # keep edits made meanwhile to other fields
        for s, new in zip(fresh["slides"], proj["slides"]):
            if s["id"] == new["id"]:
                s["script"] = new["script"]
        P.save(fresh)
        return {"written": n}

    return jsonify(jobs.start(f"{pid}:ai", work) | {"cancel": None})


@app.post("/api/projects/<pid>/dub")
def dub(pid):
    """Translated copy of the project in another language (runs in the background)."""
    proj = _proj(pid)
    lang = str((request.json or {}).get("language") or "hi")[:2].lower()
    if lang not in ai_writer.LANGS:
        abort(400, "Unknown language")
    if not llm.status()["available"]:
        abort(400, llm.status()["info"])
    if not any((s.get("script") or "").strip() for s in proj["slides"]):
        abort(400, "Write the narration first; the dub translates it.")
    try:
        dubbing.pick_voice(proj, lang)
    except RuntimeError as e:
        abort(400, str(e))

    def work(progress, cancelled):
        d = dubbing.make_dub(_proj(pid), lang, lambda f, m: progress("Dubbing", f, m))
        return {"project": d["id"], "name": d["name"]}

    return jsonify(jobs.start(f"{pid}:ai", work) | {"cancel": None})


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
    if body.get("motion") in ("motion", "classic"):
        proj["motion"] = body["motion"]
    if body.get("look") in motion.LOOKS:
        proj["look"] = body["look"]
    for flag in ("clean_audio", "sfx"):
        if flag in body:
            proj[flag] = bool(body[flag])
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
    return jsonify(jobs.status(pid) | {"export": jobs.status(f"{pid}:export"), "ai": jobs.status(f"{pid}:ai")})


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
    print(f"\n  {APP_NAME} — {MODULE_NAME}   version {app_version()}")
    print("  ------------------------------------------------")
    print(f"  On this laptop : http://localhost:{PORT}")
    print(f"  On your phone  : {url}   (same Wi-Fi)")
    print(f"  Voice engine   : {tts.default_engine() or 'NONE — run install_once.bat'}")
    print(f"  Video encoder  : {ENCODERS[best_encoder()][0]}")
    print("  Close this window to stop the app.\n")
    sys.stdout.flush()
    serve(app, host=HOST, port=PORT, threads=8, max_request_body_size=app.config["MAX_CONTENT_LENGTH"])


if __name__ == "__main__":
    run()
