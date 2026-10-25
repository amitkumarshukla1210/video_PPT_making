"""Slides + narration (+ your own presenter clips) -> MP4 (H.264/AAC, 1920x1080, soft subtitles) + .srt.

Pipeline: draw slide PNGs -> voice-over per slide (TTS / cloned voice / your clip's own sound,
cached) -> one frame-exact audio track -> one short video clip per slide (dip-to-navy fade,
presenter bubble overlaid when the slide has a recording) -> logo intro/outro -> join clips
without re-encoding -> mux audio (+ ducked music) and subtitles.
Exports (Reels 9:16, square 1:1, short clips) are cut from that 16:9 master."""
import hashlib
import json
import math
import re
import subprocess
import time
import wave

from PIL import Image, ImageDraw

from . import tts, media
from .config import (AUDIO_RATE, FPS, LEAD_IN, TAIL_OUT, FADE, NAVY, WHITE, VIDEO_W, VIDEO_H,
                     MAX_VIDEO_SECONDS, APP_NAME)
from .ffmpeg_utils import ffmpeg_bin, encoder_args, best_encoder, encode_cost, still_filter, ENCODERS
from .ppt_builder import logo_path
from .project import folder
from .slide_render import render_slide, bubble_mode, bubble_mask, font

MIN_SLIDE = 3.0      # seconds, for slides without narration
WORDS_PER_SEC = 2.4  # typical corporate narration pace at speed 1.0
STING = 3.0          # logo intro / outro length, seconds
CLIP_COST = 3.5      # overlaying a presenter video costs ~3.5x a still slide


class Cancelled(Exception):
    pass


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("FFmpeg failed:\n" + (r.stderr or "")[-1500:])


def _voice(proj, needed=True):
    v = dict(proj.get("voice") or {})
    if not v.get("engine") or v["engine"] not in tts.ENGINES or not tts.ENGINES[v["engine"]].available()[0]:
        v["engine"] = tts.default_engine()
    if not v["engine"] and needed:
        raise RuntimeError("No voice engine installed. Run setup_windows.bat (downloads Kokoro voices).")
    return v


def _ref(proj):
    return str(folder(proj["id"]) / proj["voice_sample"]) if proj.get("voice_sample") else None


def _slide_seconds(s, speed):
    if s.get("clip"):
        return float(s.get("clip_seconds") or 0) + LEAD_IN + TAIL_OUT
    words = len((s.get("script") or "").split())
    return max(words / WORDS_PER_SEC / speed + LEAD_IN + TAIL_OUT, MIN_SLIDE) if words else MIN_SLIDE


def estimate(proj):
    """Estimated final video length and render time (seconds) before rendering."""
    v = _voice(proj, needed=False)
    engine = v.get("engine") or "kokoro"
    speed = float(v.get("speed") or 1.0)
    intro = STING * 2 if proj.get("intro", True) else 0
    per_slide = [_slide_seconds(s, speed) for s in proj["slides"]]
    video_len = sum(per_slide) + intro
    narration = sum(len((s.get("script") or "").split()) / WORDS_PER_SEC / speed
                    for s in proj["slides"] if not s.get("clip"))
    clip_len = sum(t for t, s in zip(per_slide, proj["slides"]) if s.get("clip"))
    t_tts = narration * tts.cost_per_second(engine) + (20 if engine == "clone" else 0)   # + model load
    t_video = ((video_len - clip_len) + clip_len * CLIP_COST) * encode_cost() * 0.7 \
        + len(per_slide) * 0.6 + video_len * 0.02
    return {"video_seconds": round(video_len), "max_seconds": MAX_VIDEO_SECONDS,
            "over_limit": video_len > MAX_VIDEO_SECONDS,
            "render_seconds": round(t_tts + t_video + 3), "tts_seconds": round(t_tts),
            "encode_seconds": round(t_video), "engine": engine,
            "encoder": ENCODERS[best_encoder()][0], "slides": len(per_slide),
            "per_slide": [round(t, 1) for t in per_slide]}


def _hash(*parts):
    return hashlib.sha1(json.dumps(parts, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _split_caption(text, max_words=12):
    sentences = [s.strip() for s in re.split(r"(?<=[.!?।])\s+", re.sub(r"\s+", " ", text).strip()) if s.strip()]
    out = []
    for s in sentences:
        words = s.split()
        chunks = max(1, math.ceil(len(words) / max_words))
        size = math.ceil(len(words) / chunks)
        out += [" ".join(words[i:i + size]) for i in range(0, len(words), size)]
    return out


def _ts(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(cues, path):
    lines = []
    for i, (a, b, text) in enumerate(cues, 1):
        lines += [str(i), f"{_ts(a)} --> {_ts(b)}", text, ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def _sting_png(proj, path, outro=False):
    """Navy card with the logo and the title — the frame for the animated intro / outro."""
    im = Image.new("RGB", (VIDEO_W, VIDEO_H), NAVY)
    d = ImageDraw.Draw(im)
    size = 300
    with Image.open(logo_path(proj)) as lg:
        lg = lg.convert("RGBA")
        lg.thumbnail((size, size), Image.LANCZOS)
        card = Image.new("RGBA", (lg.width + 60, lg.height + 60), (0, 0, 0, 0))
        ImageDraw.Draw(card).rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=36, fill=WHITE)
        card.alpha_composite(lg, (30, 30))
    im.paste(card, ((VIDEO_W - card.width) // 2, 300 - card.height // 2 + 80), card)
    title = (proj.get("company") or APP_NAME) if outro else (proj.get("title") or APP_NAME)
    sub = proj.get("contact") or "" if outro else proj.get("subtitle") or ""
    for text, pt, color, y in ((title, 64, WHITE, 640), (sub, 32, "#bcd3f0", 740)):
        if text:
            f = font("bold" if pt > 40 else "regular", pt)
            d.text(((VIDEO_W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=color)
    d.rectangle(((VIDEO_W - 160) // 2, 840, (VIDEO_W + 160) // 2, 848), fill="#e07b1f")
    im.save(path)


def render_video(proj, progress=lambda stage, frac, msg: None, cancelled=lambda: False):
    base = folder(proj["id"])
    frames, audio, out = base / "frames", base / "audio", base / "out"
    for d in (frames, audio, out):
        d.mkdir(exist_ok=True)
    slides = proj["slides"]
    needs_tts = any((s.get("script") or "").strip() and not s.get("clip") for s in slides)
    v = _voice(proj, needed=needs_tts)
    n = len(slides)
    t0 = time.time()
    if estimate(proj)["video_seconds"] > MAX_VIDEO_SECONDS * 1.1:      # stop early, before any voice work
        raise RuntimeError(f"The video would be about {estimate(proj)['video_seconds'] / 60:.0f} minutes — the limit is "
                           f"{MAX_VIDEO_SECONDS // 60} minutes. Shorten the narration or remove slides.")

    def check():
        if cancelled():
            raise Cancelled()

    # 1) slide images (+ where the presenter bubble sits)
    modes, inners = [], []
    for i, s in enumerate(slides):
        check()
        progress("Drawing slides", i / n, f"Slide {i + 1}/{n}")
        mode = bubble_mode(proj, s)
        modes.append(mode)
        inners.append(render_slide(proj, s, i + 1, frames / f"slide_{i:03d}.png", mode))

    # 2) sound per slide: your recording's own audio, or the voice-over (cached by text + voice)
    durations = [0.0] * n
    todo = []
    for i, s in enumerate(slides):
        wav = audio / f"slide_{i:03d}.wav"
        stamp = wav.with_suffix(".key")
        text = (s.get("script") or "").strip()
        if s.get("clip"):
            key = _hash("clip", s["clip"])
            if not (wav.exists() and stamp.exists() and stamp.read_text() == key):
                progress("Voice-over", i / n, f"Taking sound from your recording, slide {i + 1}")
                media.clip_audio(base / s["clip"], wav)
                stamp.write_text(key)
        elif text:
            key = _hash(text, v, proj.get("voice_sample") if v["engine"] == "clone" else None)
            if not (wav.exists() and stamp.exists() and stamp.read_text() == key):
                todo.append((i, text, wav, stamp, key))
                continue
        else:
            continue
        durations[i] = tts.wav_duration(wav)
    if todo:
        check()
        progress("Voice-over", 0, f"Speaking {len(todo)} slide(s) with {tts.ENGINES[v['engine']].LABEL}")
        tts.synthesize_many(v["engine"], [(t, w) for _, t, w, _, _ in todo], v.get("voice"), v.get("lang"),
                            v.get("speed", 1.0), _ref(proj),
                            progress=lambda d, tot: progress("Voice-over", d / tot, f"Spoken {d}/{tot} slides"),
                            cancelled=cancelled)
        check()
        for i, _, wav, stamp, key in todo:
            stamp.write_text(key)
            durations[i] = tts.wav_duration(wav)

    # 3) frame-exact timeline, one audio track, subtitles — and the 15-minute limit
    progress("Timeline", 0, "Building audio track and subtitles")
    seg_frames = [math.ceil((max(d + LEAD_IN + TAIL_OUT, MIN_SLIDE) if d else MIN_SLIDE) * FPS) for d in durations]
    sting = proj.get("intro", True)
    sting_frames = int(STING * FPS) if sting else 0
    total = (sum(seg_frames) + 2 * sting_frames) / FPS
    if total > MAX_VIDEO_SECONDS:
        raise RuntimeError(f"The video would be {total / 60:.1f} minutes — the limit is "
                           f"{MAX_VIDEO_SECONDS // 60} minutes. Shorten the narration or remove slides.")
    narration = out / "narration.wav"
    cues, timeline, t = [], [], sting_frames / FPS
    with wave.open(str(narration), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(AUDIO_RATE)
        w.writeframes(b"\0\0" * round(sting_frames / FPS * AUDIO_RATE))
        for i, (d, nf) in enumerate(zip(durations, seg_frames)):
            seg_samples = round(nf / FPS * AUDIO_RATE)
            written = 0
            if d:
                lead = round(LEAD_IN * AUDIO_RATE)
                w.writeframes(b"\0\0" * lead)
                with wave.open(str(audio / f"slide_{i:03d}.wav"), "rb") as r:
                    data = r.readframes(r.getnframes())
                data = data[: (seg_samples - lead) * 2]
                w.writeframes(data)
                written = lead + len(data) // 2
                caps = _split_caption(slides[i].get("script") or "")
                total_chars = sum(len(c) for c in caps) or 1
                ct = t + LEAD_IN
                for c in caps:
                    dur = d * len(c) / total_chars
                    cues.append((ct, ct + dur - 0.05, c))
                    ct += dur
            w.writeframes(b"\0\0" * max(seg_samples - written, 0))
            timeline.append({"slide": i + 1, "title": slides[i]["title"], "start": round(t, 3),
                             "end": round(t + nf / FPS, 3)})
            t += nf / FPS
        w.writeframes(b"\0\0" * round(sting_frames / FPS * AUDIO_RATE))
    srt = out / "subtitles.srt"
    write_srt(cues, srt)
    (out / "timeline.json").write_text(json.dumps(timeline, indent=1, ensure_ascii=False), encoding="utf-8")

    # 4) one video clip per slide
    enc = encoder_args()
    clips = []
    navy = "0x" + NAVY.lstrip("#")
    q = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y"]
    if sting:
        for name, outro in (("intro", False), ("outro", True)):
            png = frames / f"{name}.png"
            _sting_png(proj, png, outro)
            zoom = f"zoompan=z='1+0.04*on/{sting_frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={VIDEO_W}x{VIDEO_H}:fps={FPS}"
            fades = f"fade=t=in:st=0:d=0.8:color={navy},fade=t=out:st={STING - FADE:.2f}:d={FADE}:color={navy}"
            _run(q + ["-i", str(png), "-frames:v", str(sting_frames),
                      "-vf", f"loop=loop={sting_frames - 1}:size=1:start=0,{zoom},format=yuv420p,{fades}",
                      *enc, "-g", str(FPS * 2), "-r", str(FPS), str(frames / f"{name}.mp4")])
    if sting:
        clips.append(frames / "intro.mp4")
    pip = proj.get("pip") or {}
    for i, nf in enumerate(seg_frames):
        check()
        dur = nf / FPS
        elapsed = time.time() - t0
        progress("Encoding video", i / n, f"Slide {i + 1}/{n}  ({ENCODERS[best_encoder()][0]}, {elapsed:.0f}s elapsed)")
        clip = frames / f"clip_{i:03d}.mp4"
        fades = [f"fade=t=in:st=0:d={FADE}:color={navy}"] if (i > 0 or sting) else []
        if i < n - 1 or sting:
            fades.append(f"fade=t=out:st={dur - FADE:.3f}:d={FADE}:color={navy}")
        png = str(frames / f"slide_{i:03d}.png")
        if modes[i] == "clip":
            ix, iy, size = inners[i]
            mask = frames / f"mask_{size}_{pip.get('shape', 'circle')}.png"
            if not mask.exists():
                bubble_mask(size, pip.get("shape", "circle")).save(mask)
            m = "min(iw,ih)"
            graph = (f"[0:v]{still_filter(nf)}[bg];"
                     f"[1:v]crop=w='{m}':h='{m}':x='(iw-{m})/2':y='(ih-{m})/4',scale={size}:{size},setsar=1,"
                     f"fps={FPS},tpad=start_duration={LEAD_IN}:start_mode=clone:stop_mode=clone:stop_duration={dur:.2f},"
                     f"format=rgba[c];"
                     f"[2:v]format=gray,loop=loop={nf - 1}:size=1:start=0,setpts=N/{FPS}/TB[m];"
                     f"[c][m]alphamerge[cm];"
                     f"[bg][cm]overlay={ix}:{iy}:format=auto,format=yuv420p" + ("," + ",".join(fades) if fades else "") + "[v]")
            _run(q + ["-i", png, "-i", str(base / slides[i]["clip"]), "-i", str(mask),
                      "-filter_complex", graph, "-map", "[v]", "-frames:v", str(nf),
                      *enc, "-g", str(FPS * 2), "-r", str(FPS), "-an", str(clip)])
        else:
            _run(q + ["-i", png, "-frames:v", str(nf), "-vf", still_filter(nf, ",".join(fades)),
                      *enc, "-g", str(FPS * 2), "-r", str(FPS), str(clip)])
        clips.append(clip)
    if sting:
        clips.append(frames / "outro.mp4")

    # 5) join + mux
    check()
    progress("Final mix", 0.2, "Joining clips, adding audio and subtitles")
    listfile = frames / "clips.txt"
    listfile.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    silent = frames / "video_only.mp4"
    _run(q + ["-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(silent)])

    final = out / "video.mp4"
    music = (proj.get("music") or {})
    music_file = base / music["file"] if music.get("file") else None
    has_music = bool(music_file and music_file.exists())
    cmd = q + ["-i", str(silent), "-i", str(narration)]
    if has_music:
        cmd += ["-stream_loop", "-1", "-i", str(music_file)]
    if cues:
        cmd += ["-i", str(srt)]
    if has_music:
        vol = float(music.get("volume") or 0.12)
        cmd += ["-filter_complex",
                f"[2:a]aformat=channel_layouts=stereo,volume={vol},afade=t=out:st={max(total - 4, 0):.2f}:d=4[m];"
                "[1:a]aformat=channel_layouts=stereo,asplit[n1][n2];"
                "[m][n2]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[duck];"
                "[n1][duck]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    if cues:
        cmd += ["-map", f"{3 if has_music else 2}:s", "-c:s", "mov_text",
                "-metadata:s:s:0", "language=" + _iso3(v.get("lang") if v.get("engine") else "en")]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(AUDIO_RATE), "-t", f"{total:.3f}",
            "-movflags", "+faststart", str(final)]
    _run(cmd)
    for c in clips:
        c.unlink(missing_ok=True)
    silent.unlink(missing_ok=True)
    progress("Done", 1, f"Video ready: {total / 60:.1f} min, rendered in {time.time() - t0:.0f}s")
    return {"video": final, "srt": srt, "seconds": total, "render_seconds": time.time() - t0}


# ---------- exports from the 16:9 master ----------
PRESETS = {
    "youtube": ("YouTube 16:9 1080p", 1920, 1080),
    "reels": ("Instagram Reels / Shorts 9:16", 1080, 1920),
    "square": ("Square 1:1 (LinkedIn / Instagram feed)", 1080, 1080),
}


def export(proj, preset="reels", slide_from=None, slide_to=None, burn_subs=False,
           progress=lambda stage, frac, msg: None, cancelled=lambda: False):
    """Re-frame the master video (and optionally cut slides slide_from..slide_to into a short clip)."""
    base = folder(proj["id"])
    out = base / "out"
    master = out / "video.mp4"
    if not master.exists():
        raise RuntimeError("Render the video first.")
    label, W, H = PRESETS[preset]
    timeline = json.loads((out / "timeline.json").read_text(encoding="utf-8"))
    start, end = 0.0, media.duration(master)
    name = preset
    if slide_from:
        a = max(1, int(slide_from))
        b = min(len(timeline), int(slide_to or a))
        start, end = timeline[a - 1]["start"], timeline[b - 1]["end"]
        name = f"{preset}_slides_{a}-{b}"
    if W == 1920:
        vf = f"scale={W}:{H}"
    else:
        # blurred, zoomed copy fills the background; the slide video sits in the middle at full width
        vf = (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
              f"gblur=sigma=30,eq=brightness=-0.08[bg];[b]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2")
    if burn_subs and (out / "subtitles.srt").exists():
        srt = (out / "subtitles.srt").as_posix().replace(":", "\\:")
        size = 14 if W == 1920 else 12
        vf += (f",subtitles='{srt}':force_style='FontName=Segoe UI,FontSize={size},PrimaryColour=&H00FFFFFF,"
               f"BackColour=&H99382215,BorderStyle=3,Outline=1,Shadow=0,MarginV={40 if H > W else 30}'")
    dst = out / f"{name}.mp4"
    progress("Exporting", 0.1, f"{label}: {end - start:.0f} s")
    cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
           "-i", str(master), "-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]", "-map", "0:a",
           *encoder_args(), "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(dst)]
    try:
        _run(cmd)
    except RuntimeError:
        if not burn_subs:
            raise
        return export(proj, preset, slide_from, slide_to, False, progress, cancelled) | {
            "note": "Subtitles could not be burned in on this PC; exported without them (the .srt still works)."}
    progress("Done", 1, f"{label} ready")
    return {"file": dst, "seconds": round(end - start, 1), "label": label}


def _iso3(lang):
    return {"en": "eng", "hi": "hin", "es": "spa", "fr": "fra", "it": "ita", "pt": "por", "de": "deu",
            "ar": "ara", "ru": "rus", "zh": "zho", "ja": "jpn"}.get((lang or "en")[:2], "und")
