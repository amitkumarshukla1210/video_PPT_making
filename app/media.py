"""Uploaded media: presenter video clips, voice samples and presenter photos are converted once
to a standard format so rendering is fast and predictable."""
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageOps

from .config import AUDIO_RATE, FPS
from .ffmpeg_utils import ffmpeg_bin


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("Could not read this file:\n" + (r.stderr or "")[-800:])
    return r


def duration(path):
    """Seconds, read from FFmpeg's header info (no ffprobe needed)."""
    r = subprocess.run([ffmpeg_bin(), "-hide_banner", "-i", str(path)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr or "")
    if not m:
        return 0.0
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def normalize_clip(src, dst):
    """Phone / webcam recording -> MP4, max 720p, 30 fps, AAC 48 kHz. Fixes rotation and
    browser recordings (WebM) that have no duration in their header."""
    _run([ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
          "-vf", f"scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,fps={FPS}",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "160k", "-ar", str(AUDIO_RATE), "-ac", "1", "-movflags", "+faststart", str(dst)])
    return duration(dst)


def clip_audio(src, dst_wav):
    """Presenter clip -> loudness-normalised mono WAV, the same format as the voice-over."""
    _run([ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-vn",
          "-af", "highpass=f=70,loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", str(AUDIO_RATE), "-ac", "1",
          "-sample_fmt", "s16", str(dst_wav)])


def normalize_voice_sample(src, dst_wav, max_seconds=30):
    """Voice sample for cloning -> 24 kHz mono WAV, trimmed, silence at the ends removed."""
    _run([ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-vn",
          "-af", "highpass=f=70,silenceremove=start_periods=1:start_threshold=-45dB,"
                 "areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                 "loudnorm=I=-18:TP=-2",
          "-t", str(max_seconds), "-ar", "24000", "-ac", "1", str(dst_wav)])
    secs = duration(dst_wav)
    if secs < 5:
        Path(dst_wav).unlink(missing_ok=True)
        raise ValueError(f"The sample is only {secs:.0f} s of speech. Please record 10–30 seconds.")
    return secs


def normalize_photo(src, dst):
    """Presenter photo -> square 800x800 JPEG centred slightly above the middle (where the face is)."""
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        side = min(im.size)
        left = (im.width - side) // 2
        top = max(0, int((im.height - side) * 0.3))
        im.crop((left, top, left + side, top + side)).resize((800, 800), Image.LANCZOS).save(dst, "JPEG", quality=92)
