"""Slides + narration -> MP4 (H.264/AAC, 1920x1080, soft subtitles) + .srt.

Pipeline: draw slide PNGs -> synthesize each slide's narration (cached) -> build one
frame-exact narration track -> encode one short clip per slide with a dip-to-navy fade ->
join clips without re-encoding -> mux audio (+ optional ducked music) and subtitles."""
import hashlib
import json
import math
import re
import subprocess
import time
import wave

from . import tts
from .config import (AUDIO_RATE, FPS, LEAD_IN, TAIL_OUT, FADE, NAVY)
from .ffmpeg_utils import ffmpeg_bin, encoder_args, best_encoder, encode_cost, still_filter, ENCODERS
from .project import folder
from .slide_render import render_slide

MIN_SLIDE = 3.0     # seconds, for slides without narration
WORDS_PER_SEC = 2.4  # typical corporate narration pace at speed 1.0


class Cancelled(Exception):
    pass


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("FFmpeg failed:\n" + (r.stderr or "")[-1500:])


def _voice(proj):
    v = dict(proj.get("voice") or {})
    if not v.get("engine") or not tts.ENGINES[v["engine"]].available()[0]:
        v["engine"] = tts.default_engine()
    if not v["engine"]:
        raise RuntimeError("No voice engine installed. Run setup_windows.bat (downloads Kokoro voices).")
    return v


def estimate(proj):
    """Estimated final video length and render time (seconds) before rendering."""
    v = proj.get("voice") or {}
    engine = v.get("engine") or tts.default_engine() or "kokoro"
    speed = float(v.get("speed") or 1.0)
    narration = 0.0
    for s in proj["slides"]:
        words = len((s.get("script") or "").split())
        narration += max(words / WORDS_PER_SEC / speed, 0) if words else 0
    n = len(proj["slides"])
    video_len = sum(
        max(len((s.get("script") or "").split()) / WORDS_PER_SEC / speed + LEAD_IN + TAIL_OUT, MIN_SLIDE)
        for s in proj["slides"])
    tts_cost = tts.CPU_COST.get(engine, 0.3)
    if engine == "kokoro":
        from .tts import kokoro_engine
        if kokoro_engine.available()[0] and kokoro_engine._provider() != "CPUExecutionProvider":
            tts_cost *= 0.25
    t_tts = narration * tts_cost
    t_video = video_len * encode_cost() * 0.7 + n * 0.6 + video_len * 0.02   # encode + slide drawing + mux
    return {"video_seconds": round(video_len), "render_seconds": round(t_tts + t_video + 3),
            "tts_seconds": round(t_tts), "encode_seconds": round(t_video), "engine": engine,
            "encoder": ENCODERS[best_encoder()][0], "slides": n}


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


def render_video(proj, progress=lambda stage, frac, msg: None, cancelled=lambda: False):
    base = folder(proj["id"])
    frames, audio, out = base / "frames", base / "audio", base / "out"
    for d in (frames, audio, out):
        d.mkdir(exist_ok=True)
    v = _voice(proj)
    slides = proj["slides"]
    n = len(slides)
    t0 = time.time()

    def check():
        if cancelled():
            raise Cancelled()

    # 1) slide images
    for i, s in enumerate(slides):
        check()
        progress("Drawing slides", i / n, f"Slide {i + 1}/{n}")
        render_slide(proj, s, i + 1, frames / f"slide_{i:03d}.png")

    # 2) narration per slide (re-used if text and voice did not change)
    durations = []
    for i, s in enumerate(slides):
        check()
        progress("Voice-over", i / n, f"Speaking slide {i + 1}/{n} with {v['engine']}")
        text = (s.get("script") or "").strip()
        wav = audio / f"slide_{i:03d}.wav"
        key = _hash(text, v)
        stamp = wav.with_suffix(".key")
        if not text:
            durations.append(0.0)
            continue
        if not (wav.exists() and stamp.exists() and stamp.read_text() == key):
            tts.synthesize(v["engine"], text, v.get("voice"), v.get("lang"), v.get("speed", 1.0), wav)
            stamp.write_text(key)
        durations.append(tts.wav_duration(wav))

    # 3) frame-exact timeline + one narration track + subtitles
    progress("Timeline", 0, "Building narration track and subtitles")
    seg_frames = [math.ceil((max(d + LEAD_IN + TAIL_OUT, MIN_SLIDE) if d else MIN_SLIDE) * FPS) for d in durations]
    narration = out / "narration.wav"
    cues, t = [], 0.0
    with wave.open(str(narration), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(AUDIO_RATE)
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
                caps = _split_caption(slides[i]["script"])
                total_chars = sum(len(c) for c in caps) or 1
                ct = t + LEAD_IN
                for c in caps:
                    dur = d * len(c) / total_chars
                    cues.append((ct, ct + dur - 0.05, c))
                    ct += dur
            w.writeframes(b"\0\0" * max(seg_samples - written, 0))
            t += nf / FPS
    srt = out / "subtitles.srt"
    write_srt(cues, srt)

    # 4) one clip per slide with dip-to-navy fade in/out
    enc = encoder_args()
    clips = []
    navy = "0x" + NAVY.lstrip("#")
    for i, nf in enumerate(seg_frames):
        check()
        dur = nf / FPS
        elapsed = time.time() - t0
        progress("Encoding video", i / n, f"Clip {i + 1}/{n}  ({ENCODERS[best_encoder()][0]}, {elapsed:.0f}s elapsed)")
        clip = frames / f"clip_{i:03d}.mp4"
        fades = [f"fade=t=in:st=0:d={FADE}:color={navy}"] if i > 0 else []
        if i < n - 1:
            fades.append(f"fade=t=out:st={dur - FADE:.3f}:d={FADE}:color={navy}")
        vf = still_filter(nf, ",".join(fades))
        _run([ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
              "-i", str(frames / f"slide_{i:03d}.png"), "-frames:v", str(nf), "-vf", vf,
              *enc, "-g", str(FPS * 2), "-r", str(FPS), str(clip)])
        clips.append(clip)

    # 5) join + mux
    check()
    progress("Final mix", 0.2, "Joining clips, adding audio and subtitles")
    listfile = frames / "clips.txt"
    listfile.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    silent = frames / "video_only.mp4"
    _run([ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
          "-i", str(listfile), "-c", "copy", str(silent)])

    total = sum(seg_frames) / FPS
    final = out / "video.mp4"
    cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(silent), "-i", str(narration)]
    music = (proj.get("music") or {})
    music_file = base / music["file"] if music.get("file") else None
    if music_file and music_file.exists():
        vol = float(music.get("volume") or 0.12)
        cmd += ["-stream_loop", "-1", "-i", str(music_file), "-i", str(srt),
                "-filter_complex",
                f"[2:a]aformat=channel_layouts=stereo,volume={vol},afade=t=out:st={max(total - 4, 0):.2f}:d=4[m];"
                "[1:a]aformat=channel_layouts=stereo,asplit[n1][n2];"
                "[m][n2]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[duck];"
                "[n1][duck]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]", "-map", "3:s"]
    else:
        cmd += ["-i", str(srt), "-map", "0:v", "-map", "1:a", "-map", "2:s"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(AUDIO_RATE), "-c:s", "mov_text",
            "-metadata:s:s:0", "language=" + _iso3(v.get("lang")), "-t", f"{total:.3f}",
            "-movflags", "+faststart", str(final)]
    _run(cmd)
    for c in clips:
        c.unlink(missing_ok=True)
    silent.unlink(missing_ok=True)
    progress("Done", 1, f"Video ready: {total / 60:.1f} min, rendered in {time.time() - t0:.0f}s")
    return {"video": final, "srt": srt, "seconds": total, "render_seconds": time.time() - t0}


def _iso3(lang):
    return {"en": "eng", "hi": "hin", "es": "spa", "fr": "fra", "it": "ita", "pt": "por", "de": "deu",
            "ar": "ara", "ru": "rus", "zh": "zho", "ja": "jpn"}.get((lang or "en")[:2], "und")
