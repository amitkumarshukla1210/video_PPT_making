"""Guided "Make a video" flow: source -> scene-by-scene script -> voice -> video type.
Builds on the normal project, so every step can also be changed in the Presentation workspace."""
import shutil
import time
import uuid
from pathlib import Path

from . import project as P, sources
from .ai import llm, writer, library
from .ppt_builder import build_pptx
from .ppt_import import import_pptx
from .script_writer import draft_all
from .video import render_video, export, Cancelled

KINDS = ("pptx", "pictures", "document", "url", "text", "idea")
VIDEO_TYPES = {
    # type: (label, export preset or None for the 16:9 master, logo intro/outro, default music mood)
    "youtube": ("YouTube video · 16:9", None, False, "documentary"),
    "reel": ("Instagram Reel / YouTube Shorts · 9:16", "reels", False, "tech"),
    "corporate": ("Corporate video · 16:9 with logo intro and outro", None, True, "corporate"),
    "square": ("LinkedIn / Instagram feed · 1:1", "square", False, "corporate"),
}


def _ai_ready():
    return llm.status()["available"]


def build_from_source(pid, kind, files=(), url="", text="", scenes=8, language="en", video_type="corporate",
                      use_ai=True, pictures=False, style="", progress=lambda stage, f, m: None,
                      cancelled=lambda: False):
    """Fills the (new) project with slides from the source, writes the narration for every slide and,
    if asked, creates a picture for slides that have none. files = saved paths inside the project."""
    if kind not in KINDS:
        raise ValueError("Unknown source type")
    proj = P.load(pid)
    proj["language"] = language
    ai = use_ai and _ai_ready()
    say = lambda f, m: progress("Reading your source", f, m)      # noqa: E731
    say(0.02, "Reading…")
    title = ""
    if kind == "pptx":
        for f in files:
            import_pptx(proj, f)
    elif kind == "pictures":
        sources.add_pictures(proj, [Path(f) for f in files])
    elif kind == "idea":
        if not ai:
            raise RuntimeError("Writing from an idea needs the local AI (install_once.bat ai).")
        r = writer.scenes_from_prompt(text, video_type, scenes, language, style,
                                      lambda f, m: progress("AI script", f, m))
        sources.add_scenes(proj, [s | {"points": []} for s in r["scenes"]])
        title = r["scenes"][0]["title"] if r["scenes"] else ""
    else:
        sections = []
        for f in files:
            ext = Path(f).suffix.lower()
            if ext == ".pdf":
                sources.add_pdf(proj, f)
            elif ext == ".pptx":
                import_pptx(proj, f)
            else:
                t, sec = sources.read_text_source("file", path=f)
                title = title or t
                sections += sec
        if kind == "url":
            title, sections = sources.read_text_source("url", url=url)
        elif kind == "text":
            title, sections = sources.read_text_source("text", text=text)
        if kind in ("url", "text") and not sections:
            raise RuntimeError("No readable text was found there. Try another page or paste the text.")
        if sections:
            if ai:
                found = writer.scenes_from_document(sources.sections_to_text(sections), scenes, language, video_type,
                                                    title, style, lambda f, m: progress("AI script", f, m))
                sources.add_scenes(proj, found)
            else:
                sources.add_sections(proj, sections, max_slides=scenes)
    if cancelled():
        raise Cancelled()
    if title:
        proj["title"] = title[:90]
        if proj["slides"] and proj["slides"][0]["kind"] == "title":
            proj["slides"][0]["title"] = title[:90]
    if not any(s["kind"] == "content" for s in proj["slides"]):
        raise RuntimeError("Nothing usable was found in that source.")

    # narration for every slide that has none yet
    if ai:
        writer.write_narration(proj, language, False, lambda f, m: progress("AI script", f, m))
    draft_all(proj, overwrite=False)          # offline draft for anything still empty (and title/closing)

    if pictures:
        make_pictures(proj, progress, cancelled)
    for s in proj["slides"]:
        s.pop("source_text", None)
    P.save(proj)
    return {"slides": sum(s["kind"] == "content" for s in proj["slides"]), "ai": ai}


def make_pictures(proj, progress=lambda stage, f, m: None, cancelled=lambda: False, only_missing=True):
    from .ai import images
    if not images.status()["available"]:
        return 0
    todo = [s for s in proj["slides"] if s["kind"] == "content" and (not only_missing or not s.get("image"))]
    if not todo:
        return 0
    if cancelled():
        raise Cancelled()
    base = P.folder(proj["id"])
    prompts = [s.get("image_prompt") or f"{s['title']}, professional corporate photo, modern, clean" for s in todo]
    progress("Creating pictures", 0.0, f"Loading the picture model for {len(todo)} pictures")
    pngs = images.generate(prompts, "16:9", progress=lambda d, t: progress(
        "Creating pictures", d / max(t, 1), f"Picture {min(d + 1, t)} of {t}"))     # one model load for all
    for s, png in zip(todo, pngs):
        name = f"uploads/ai_{uuid.uuid4().hex[:6]}.png"
        (base / name).write_bytes(png)
        s["image"] = name
    return len(todo)


def use_library_music(proj, mood):
    dst = f"uploads/music_library_{mood}.wav"
    shutil.copyfile(library.music_file(mood), P.folder(proj["id"]) / dst)
    proj["music"]["file"] = dst
    proj["music"]["library"] = mood


def prepare_video(proj, video_type, music="auto", captions=True):
    if video_type not in VIDEO_TYPES:
        raise ValueError("Unknown video type")
    _, _, intro, mood = VIDEO_TYPES[video_type]
    proj["intro"] = intro or bool(proj.get("intro") and video_type != "reel")
    if music == "none":
        proj["music"]["file"] = None
    elif music in library.MOODS:
        use_library_music(proj, music)
    elif music == "auto" and not proj["music"].get("file"):
        use_library_music(proj, mood)
    proj["video_type"] = video_type
    proj["captions"] = bool(captions)
    P.save(proj)
    return proj


def make_video(proj, video_type, captions=True, progress=lambda stage, f, m: None, cancelled=lambda: False):
    """Renders the 16:9 master, then the chosen format. Each finished video is kept in out/ with its
    type and date in the name, so older videos stay available in My projects."""
    label, preset, _, _ = VIDEO_TYPES[video_type]
    build_pptx(proj)
    r = render_video(proj, progress, cancelled)
    out = P.folder(proj["id"]) / "out"
    if preset or captions:
        e = export(proj, preset or "youtube", None, None, captions, progress, cancelled)
        src = e["file"]
    else:
        src = out / "video.mp4"
    final = out / f"{video_type}_{time.strftime('%Y-%m-%d_%H%M%S')}.mp4"
    shutil.copyfile(src, final)
    return {"file": final.name, "label": label, "seconds": round(r["seconds"]),
            "render_seconds": round(r["render_seconds"])}


# ---------- My projects ----------
LABELS = {"video.mp4": "Video (latest render)", "youtube.mp4": "YouTube 16:9", "reels.mp4": "Reel / Shorts 9:16",
          "square.mp4": "Square 1:1"}


def _file_label(name):
    if name in LABELS:
        return LABELS[name]
    kind = name.split("_")[0]
    if kind in VIDEO_TYPES:
        return VIDEO_TYPES[kind][0].split(" · ")[0]
    if name.startswith("reels_slides_"):
        return "Short clip 9:16"
    if name.startswith("youtube_slides_"):
        return "Short clip 16:9"
    return name


def library_entry(pid):
    proj = P.load(pid)
    base = P.folder(pid)
    pj = base / "project.json"
    thumb = next((s["image"] for s in proj["slides"] if s.get("image")), None)
    if not thumb:
        frames = sorted((base / "frames").glob("*.png"))
        thumb = f"frames/{frames[0].name}" if frames else None
    files = []
    for f in sorted((base / "out").glob("*"), key=lambda f: f.stat().st_mtime, reverse=True):
        if f.suffix.lower() not in (".mp4", ".pptx", ".srt", ".mp3"):
            continue
        st = f.stat()
        files.append({"name": f.name, "url": f"/files/{pid}/out/{f.name}", "kind": f.suffix[1:].lower(),
                      "label": _file_label(f.name) if f.suffix == ".mp4" else
                      {"pptx": "PowerPoint", "srt": "Subtitles", "mp3": "Audio"}[f.suffix[1:].lower()],
                      "size_mb": round(st.st_size / 1e6, 1), "date": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))})
    return {"id": pid, "name": proj["name"], "title": proj.get("title", ""), "created": proj.get("created", ""),
            "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(pj.stat().st_mtime)),
            "slides": sum(s["kind"] == "content" for s in proj["slides"]),
            "thumb": f"/files/{pid}/{thumb}" if thumb else None,
            "video_type": proj.get("video_type"), "dubbed_from": proj.get("dubbed_from"), "files": files}


def library_list():
    out = []
    for p in P.list_projects():
        try:
            out.append(library_entry(p["id"]))
        except Exception:
            continue
    return out
