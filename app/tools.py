"""Creative tools (left menu › Tools): Video, Image, Audio, Character, World — all offline, no API key.

  • Image     — pictures from a prompt (local picture creator), with styles and shapes; kept in My media
  • Video     — picture → short animated clip (camera push, words, music) using the motion engine
  • Audio     — voice-over from text (any installed voice, your cloned voice), music by mood and length,
                sound effects
  • Character — save a person once (name, look, optional photo and voice) and reuse them as @Name
  • World     — save a place once (description, picture) and reuse it as @Place
Everything is stored in the app folder under my_media/ (kept by updates and backups)."""
import json
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from .config import ROOT, FPS

MEDIA = ROOT / "my_media"
KINDS = ("images", "audio", "videos")
REF_KINDS = ("characters", "worlds")

STYLES = {
    "none": ("No style", ""),
    "cinematic": ("Cinematic film", "cinematic film still, dramatic light, shallow depth of field, film grain"),
    "photo": ("Photo", "professional photograph, natural light, sharp focus"),
    "product": ("Product shot", "product photography on a seamless background, soft studio lighting"),
    "corporate": ("Corporate", "modern corporate photo, bright, clean, professional"),
    "anime": ("Anime", "anime illustration, clean lines, vibrant colours"),
    "3d": ("3D render", "3D render, soft studio light, high detail"),
    "watercolor": ("Watercolour", "watercolour painting, soft edges, paper texture"),
    "noir": ("Film noir", "black and white film noir, hard shadows, moody"),
}


def _dir(kind):
    d = MEDIA / kind
    d.mkdir(parents=True, exist_ok=True)
    return d


def _stamp(prefix, ext):
    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}{ext}"


def safe_name(name):
    if not re.fullmatch(r"[\w.\-]+", name or "") or ".." in name:
        raise ValueError("bad file name")
    return name


# ---------- picture index: which characters / places each picture shows (my_media/index.json) ----------
def _index_file():
    MEDIA.mkdir(parents=True, exist_ok=True)
    return MEDIA / "index.json"


def _index():
    f = _index_file()
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except ValueError:
        return {}


def _save_index(idx):
    f = _index_file()
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(idx, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def all_tags():
    return [i["tag"] for k in REF_KINDS for i in refs(k)]


def tags_in(text):
    """The saved @Name / @Place tags used in a text, in order of appearance."""
    known = {t.lower(): t for t in all_tags()}
    out = []
    for m in re.findall(r"@\w+", text or ""):
        t = known.get(m.lower())
        if t and t not in out:
            out.append(t)
    return out


def _name_part(tags):
    """'Shurpanakha' or 'Ram-Sita' for file names (letters and digits only)."""
    return "-".join(re.sub(r"[^\w]", "", t.lstrip("@")) for t in tags[:3]) or "img"


def picture_info(name):
    return _index().get(name, {})


def set_picture(name, **info):
    idx = _index()
    entry = idx.setdefault(name, {"created": time.strftime("%Y-%m-%d %H:%M")})
    if "tags" in info:
        known = {t.lower(): t for t in all_tags()}
        info["tags"] = [known.get(str(t).lower(), str(t)) for t in info["tags"] if str(t).strip()]
    entry.update(info)
    _save_index(idx)
    return entry


def media_list(kind):
    if kind not in KINDS:
        raise ValueError(kind)
    files = sorted(_dir(kind).glob("*"), key=lambda f: f.stat().st_mtime, reverse=True)
    idx = _index() if kind == "images" else {}
    out = []
    for f in files:
        if f.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".wav", ".mp3", ".mp4"):
            continue
        item = {"name": f.name, "url": f"/media/{kind}/{f.name}", "size_kb": round(f.stat().st_size / 1024),
                "date": time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime))}
        if kind == "images":
            info = idx.get(f.name, {})
            item.update(tags=info.get("tags", []), prompt=info.get("prompt", ""))
        out.append(item)
    return out


def delete_media(kind, name):
    media_path(kind, name).unlink()
    if kind == "images":
        idx = _index()
        if idx.pop(name, None) is not None:
            _save_index(idx)


def media_path(kind, name):
    if kind not in KINDS:
        raise ValueError(kind)
    p = _dir(kind) / safe_name(name)
    if not p.exists():
        raise FileNotFoundError(name)
    return p


# ---------- characters and worlds: saved once, used as @Name ----------
def _ref_file(kind):
    if kind not in REF_KINDS:
        raise ValueError(kind)
    MEDIA.mkdir(parents=True, exist_ok=True)
    return MEDIA / f"{kind}.json"


def refs(kind):
    f = _ref_file(kind)
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    except ValueError:
        return []


def refs_with_counts(kind):
    """The saved characters / worlds, each with how many pictures are tagged with it."""
    counts = {}
    for info in _index().values():
        for t in info.get("tags", []):
            counts[t.lower()] = counts.get(t.lower(), 0) + 1
    return [dict(i, pictures=counts.get(i["tag"].lower(), 0)) for i in refs(kind)]


def _save_refs(kind, items):
    f = _ref_file(kind)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def tag_of(name):
    return "@" + re.sub(r"[^\w]", "", name.title()) if name else ""


def save_ref(kind, name, description, voice=None, image=None, rid=None):
    name, description = str(name or "").strip()[:60], str(description or "").strip()[:600]
    if not name or not description:
        raise ValueError("Give it a name and a description.")
    items = refs(kind)
    tag = tag_of(name)
    if any(i["tag"].lower() == tag.lower() and i["id"] != rid for i in items + refs(_other(kind))):
        raise ValueError(f"{tag} is already used. Choose another name.")
    item = next((i for i in items if i["id"] == rid), None) if rid else None
    if not item:
        item = {"id": uuid.uuid4().hex[:8], "created": time.strftime("%Y-%m-%d %H:%M")}
        items.append(item)
    old_tag = item.get("tag")
    item.update(name=name, tag=tag, description=description)
    if old_tag and old_tag != tag:                  # renamed: its pictures follow
        idx = _index()
        for info in idx.values():
            info["tags"] = [tag if t == old_tag else t for t in info.get("tags", [])]
        _save_index(idx)
    if voice is not None:
        item["voice"] = voice
    if image is not None:
        item["image"] = image
    _save_refs(kind, items)
    return item


def _other(kind):
    return "worlds" if kind == "characters" else "characters"


def delete_ref(kind, rid):
    _save_refs(kind, [i for i in refs(kind) if i["id"] != rid])


def set_ref_image(kind, rid, image):
    items = refs(kind)
    for i in items:
        if i["id"] == rid:
            i["image"] = image
    _save_refs(kind, items)


def expand(text):
    """Replace @Name / @Place with the saved description, so every picture of them looks alike."""
    if not text or "@" not in text:
        return text
    table = {i["tag"].lower(): i for k in REF_KINDS for i in refs(k)}

    def sub(m):
        i = table.get(m.group(0).lower())
        return f"{i['name']} ({i['description']})" if i else m.group(0)
    return re.sub(r"@\w+", sub, text)


# ---------- Image ----------
def create_images(prompt, style="none", aspect="16:9", n=1, progress=lambda f, m: None, prefix=None, tags=None):
    """Pictures from a prompt. They are named after the characters / places in it (Shurpanakha_….png) and
    tagged with them, so they can be found and reused later."""
    from .ai import images
    if not images.status()["available"]:
        raise RuntimeError(images.status()["info"])
    tags = list(tags) if tags is not None else tags_in(prompt)
    prefix = prefix or _name_part(tags)
    full = expand(prompt.strip())
    extra = STYLES.get(style, STYLES["none"])[1]
    if extra:
        full = f"{full}, {extra}"
    n = max(1, min(8, int(n or 1)))
    progress(0.02, f"Drawing {n} picture(s)…" if images.warm() else
             "Starting the picture creator (about a minute; the very first time on this laptop 2–3 minutes)")
    pngs = images.generate([full] * n, aspect, progress=lambda d, t: progress(d / max(t, 1), f"Picture {min(d + 1, t)} of {t}"))
    names = []
    for png in pngs:
        name = _stamp(prefix, ".png")
        (_dir("images") / name).write_bytes(png)
        set_picture(name, tags=tags, prompt=prompt.strip()[:600], style=style, aspect=aspect)
        names.append(name)
    return {"images": names, "prompt": full, "tags": tags}


def save_upload(file_storage):
    ext = Path(file_storage.filename or "").suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        raise ValueError("Use a PNG, JPG or WEBP picture.")
    stem = re.sub(r"[^\w-]", "", Path(file_storage.filename or "").stem)[:30] or "upload"
    name = _stamp(stem, ext)
    file_storage.save(_dir("images") / name)
    set_picture(name, tags=[], prompt="")
    return name


# ---------- Audio ----------
def voice_over(text, engine, voice, lang, speed=1.0):
    from . import tts
    text = expand_voice_text(text)
    if not text.strip():
        raise ValueError("Write the text first.")
    eng = engine or tts.default_engine()
    if not eng:
        raise RuntimeError("No voice engine installed. Run install_once.bat.")
    ref = None
    if eng == "clone":
        from .speech_api import my_voice_sample
        ref = my_voice_sample()
        if not ref:
            raise RuntimeError("Record your voice sample once in Presentation › Voice clone.")
    name = _stamp("voice", ".wav")
    tts.synthesize(eng, text[:5000], voice, lang, float(speed or 1.0), _dir("audio") / name, ref=str(ref) if ref else None)
    return name


def expand_voice_text(text):
    # in spoken text, @Name is just the name
    table = {i["tag"].lower(): i["name"] for k in REF_KINDS for i in refs(k)}
    return re.sub(r"@\w+", lambda m: table.get(m.group(0).lower(), m.group(0)[1:]), text or "")


def music(mood, seconds=30):
    from .ai import library
    from .ffmpeg_utils import ffmpeg_bin
    if mood not in library.MOODS:
        raise ValueError("Unknown mood")
    seconds = max(5, min(600, int(seconds or 30)))
    name = _stamp(f"music_{mood}", ".wav")
    fade = min(3, seconds / 4)
    subprocess.run([ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-stream_loop", "-1",
                    "-i", str(library.music_file(mood)), "-t", str(seconds),
                    "-af", f"afade=t=in:d=0.5,afade=t=out:st={seconds - fade}:d={fade}", str(_dir("audio") / name)],
                   check=True, capture_output=True)
    return name


def sfx_copy(name):
    from .ai import library
    out = _stamp(f"sfx_{name}", ".wav")
    shutil.copyfile(library.sfx_file(name), _dir("audio") / out)
    return out


# ---------- Video: picture → animated clip ----------
def image_clip(image_name, title="", subtitle="", look="cinematic", seconds=6, mood="cinematic",
               progress=lambda f, m: None, cancelled=lambda: False, fx="drift"):
    """A picture becomes a short animated shot: camera push-in, the words rising over it, music under it."""
    from . import motion
    from .ai import library
    from .ffmpeg_utils import ffmpeg_bin, encoder_args
    src = media_path("images", image_name)
    seconds = max(3, min(30, float(seconds or 6)))
    proj = {"id": "tools", "look": look if look in motion.LOOKS else "cinematic", "logo": None,
            "title": title, "subtitle": "", "presenter": "", "company": "", "contact": ""}
    scene = {"kind": "content", "title": title.strip(), "notes": subtitle.strip(), "script": "",
             "image": str(src.resolve()),                     # absolute path: read straight from My media
             "fx": fx if fx in motion.FX else "drift"}
    sc = motion.Scene(proj, scene, 1, 1, seconds, 0.3, max(seconds - 1.2, 0.5))
    n = int(seconds * FPS)
    name = _stamp("clip", ".mp4")
    out = _dir("videos") / name
    cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{motion.W}x{motion.H}", "-r", str(FPS), "-i", "-"]
    if mood in library.MOODS:
        cmd += ["-i", str(library.music_file(mood)), "-map", "0:v", "-map", "1:a",
                "-af", f"afade=t=out:st={seconds - 1.2:.2f}:d=1.2", "-c:a", "aac", "-b:a", "160k"]
    cmd += [*encoder_args(), "-r", str(FPS), "-t", f"{seconds:.2f}", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for f in range(n):
            if cancelled():
                proc.kill()
                out.unlink(missing_ok=True)
                raise RuntimeError("Cancelled")
            if f % FPS == 0:
                progress(f / n, f"Animating {f // FPS + 1} / {int(seconds)} s")
            proc.stdin.write(sc.frame(f / FPS).tobytes())
        proc.stdin.close()
    except BrokenPipeError:
        pass
    err = proc.stderr.read().decode("utf-8", "replace")
    if proc.wait() != 0:
        out.unlink(missing_ok=True)
        raise RuntimeError("Making the clip failed:\n" + err[-800:])
    return name
