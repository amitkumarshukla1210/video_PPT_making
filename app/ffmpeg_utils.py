"""Find FFmpeg, pick the fastest working H.264 encoder (GPU first, CPU fallback) and
measure how fast this laptop encodes, for the render-time estimate."""
import shutil
import subprocess
import tempfile
import time
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def ffmpeg_bin():
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg            # bundled ffmpeg.exe, installed by requirements.txt
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise RuntimeError("FFmpeg not found. Run setup_windows.bat again.") from e


ENCODERS = {
    # name: (label, args)
    "h264_nvenc": ("NVIDIA GPU (NVENC)", ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23", "-pix_fmt", "yuv420p"]),
    "h264_qsv": ("Intel GPU (Quick Sync)", ["-c:v", "h264_qsv", "-global_quality", "23", "-pix_fmt", "nv12"]),
    "h264_amf": ("AMD GPU (AMF)", ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "cqp", "-qp_i", "22", "-qp_p", "22", "-pix_fmt", "yuv420p"]),
    "libx264": ("CPU (x264)", ["-c:v", "libx264", "-preset", "superfast", "-tune", "stillimage", "-crf", "20", "-pix_fmt", "yuv420p"]),
}


def _works(name):
    cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
           "color=c=black:s=1280x720:d=0.3", *ENCODERS[name][1], "-f", "null", "-"]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=30).returncode == 0
    except Exception:
        return False


@lru_cache(maxsize=1)
def best_encoder():
    for name in ("h264_nvenc", "h264_qsv", "h264_amf"):
        if _works(name):
            return name
    return "libx264"


def encoder_args(name=None):
    return ENCODERS[name or best_encoder()][1]


def still_filter(frames, extra=""):
    """Decode the slide image once and repeat it (much faster than re-reading it every frame)."""
    from .config import FPS
    f = f"format=yuv420p,loop=loop={frames - 1}:size=1:start=0,setpts=N/{FPS}/TB"
    return f + ("," + extra if extra else "")


@lru_cache(maxsize=1)
def encode_cost():
    """Seconds of wall-clock needed per second of 1080p slide video on this machine."""
    from .config import VIDEO_W, VIDEO_H, FPS
    with tempfile.TemporaryDirectory() as td:
        png, out = Path(td) / "bench.png", Path(td) / "bench.mp4"
        q = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y"]
        try:
            subprocess.run(q + ["-f", "lavfi", "-i", f"testsrc2=s={VIDEO_W}x{VIDEO_H}", "-frames:v", "1", str(png)],
                           check=True, capture_output=True, timeout=60)
            t = time.time()
            subprocess.run(q + ["-i", str(png), "-frames:v", str(FPS * 3), "-vf", still_filter(FPS * 3, "fade=t=in:st=0:d=0.45"),
                                *encoder_args(), "-r", str(FPS), str(out)],
                           check=True, capture_output=True, timeout=120)
        except Exception:
            return 0.25
        return max((time.time() - t) / 3.0, 0.02)
