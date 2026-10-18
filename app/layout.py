"""One slide layout shared by the PowerPoint builder and the video frame renderer,
so the .pptx and the MP4 look the same. Units are inches on a 13.333 x 7.5 (16:9) slide."""
import re

SLIDE_W, SLIDE_H = 13.333, 7.5

HEADER = (0, 0, SLIDE_W, 1.0)
ACCENT = (0, 1.0, SLIDE_W, 0.06)
HEADER_TITLE = (0.5, 0.14, 10.6, 0.75)
HEADER_LOGO = (11.35, 0.17, 1.65, 0.66)          # white card in the header, logo inside
FOOTER_Y = 7.02
BODY_TOP, BODY_H = 1.35, 5.45
SHOT_WITH_NOTES = (0.5, BODY_TOP, 8.45, BODY_H)
SHOT_FULL = (0.5, BODY_TOP, 12.33, BODY_H)
NOTES_PANEL = (9.25, BODY_TOP, 3.58, BODY_H)
NOTES_FULL = (0.5, BODY_TOP, 12.33, BODY_H)

COVER_LOGO = (0.6, 0.55, 2.3, 1.0)
COVER_BAR = (0.6, 2.35, 0.12, 2.3)
COVER_TITLE = (0.95, 2.2, 11.4, 1.35)
COVER_SUB = (0.95, 3.55, 11.4, 0.7)
COVER_META = (0.95, 4.3, 11.4, 0.5)
COVER_BAND = (0, 6.95, SLIDE_W, 0.55)


def bullets(notes, limit=7):
    """Turn free-text notes into short bullet lines."""
    notes = (notes or "").strip()
    if not notes:
        return []
    lines = [l.strip(" -•*\t") for l in notes.splitlines() if l.strip(" -•*\t")]
    if len(lines) == 1:
        lines = [s.strip() for s in re.split(r"(?<=[.!?;])\s+", lines[0]) if s.strip()]
    return lines[:limit]


def bullet_font_pt(lines, full_width=False):
    chars = sum(len(l) for l in lines)
    if full_width:
        return 24 if chars < 250 else 20 if chars < 450 else 16
    return 16 if chars < 180 else 14 if chars < 320 else 12


def fit_box(img_w, img_h, box):
    """Largest rectangle with the image's aspect ratio centred inside box."""
    x, y, w, h = box
    scale = min(w / img_w, h / img_h)
    fw, fh = img_w * scale, img_h * scale
    return x + (w - fw) / 2, y + (h - fh) / 2, fw, fh
