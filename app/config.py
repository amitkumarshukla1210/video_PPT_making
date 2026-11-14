"""Central settings: folders, brand colours, fonts and video presets."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = ROOT / "projects"
MODELS_DIR = ROOT / "models"
DEFAULT_LOGO = ROOT / "app" / "static" / "logo_hd.png"   # Design to Cost logo; replace per project in the UI
APP_NAME = "Design to Cost"
MODULE_NAME = "Presentation & Video Studio"

# Hugging Face models (voice clone) are kept inside the app folder, never sent anywhere.
os.environ.setdefault("HF_HOME", str(MODELS_DIR / "hf"))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

HOST = os.environ.get("DTC_HOST", "0.0.0.0")  # 0.0.0.0 = reachable from phone on same Wi-Fi
PORT = int(os.environ.get("DTC_PORT", "8000"))

# Brand
NAVY = "#152238"
BLUE = "#1f5fa8"
ORANGE = "#e07b1f"
WHITE = "#ffffff"
LIGHT = "#eef3f9"
GREY = "#5b6575"
FONT_NAME = "Segoe UI"

# Video (master is YouTube 16:9 1080p; Reels / square are made from it)
VIDEO_W, VIDEO_H, FPS = 1920, 1080, 30
MAX_VIDEO_SECONDS = 15 * 60   # hard limit: 15 minutes
AUDIO_RATE = 48000
LEAD_IN = 0.6    # seconds of silence before narration on each slide
TAIL_OUT = 0.9   # seconds after narration before the transition
FADE = 0.45      # dip-to-navy transition length (each side)

# Fonts used when drawing slide images for the video (PowerPoint itself uses Segoe UI).
_WIN_FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
FONT_CANDIDATES = {
    "regular": [_WIN_FONTS / "segoeui.ttf", _WIN_FONTS / "Nirmala.ttf",
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                Path("/System/Library/Fonts/Supplemental/Arial.ttf")],
    "bold": [_WIN_FONTS / "segoeuib.ttf", _WIN_FONTS / "NirmalaB.ttf",
             Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
             Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")],
    "light": [_WIN_FONTS / "segoeuil.ttf", _WIN_FONTS / "segoeui.ttf",
              Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")],
}

for d in (PROJECTS_DIR, MODELS_DIR / "kokoro", MODELS_DIR / "piper"):
    d.mkdir(parents=True, exist_ok=True)
