"""Draw each slide as a 1920x1080 PNG (Pillow) using the same layout as the .pptx.
This avoids needing PowerPoint or LibreOffice to turn slides into video frames."""
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from . import layout as L
from .config import (NAVY, BLUE, ORANGE, WHITE, LIGHT, GREY, VIDEO_W, VIDEO_H, FONT_CANDIDATES)
from .ppt_builder import logo_path
from .project import folder

PX = VIDEO_W / L.SLIDE_W   # pixels per inch (144)
PT = PX / 72               # pixels per point (2)


@lru_cache(maxsize=64)
def font(style, size_px):
    for path in FONT_CANDIDATES[style]:
        if path.exists():
            return ImageFont.truetype(str(path), int(size_px))
    return ImageFont.load_default(size=int(size_px))


def _b(box):
    x, y, w, h = box
    return int(x * PX), int(y * PX), int((x + w) * PX), int((y + h) * PX)


def _wrap(draw, text, fnt, width):
    lines = []
    for para in text.split("\n"):
        words, cur = para.split(), ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if draw.textlength(trial, font=fnt) <= width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def _text(draw, box, text, pt, color, style="regular", valign="top"):
    x0, y0, x1, y1 = _b(box)
    size = pt * PT
    while True:
        fnt = font(style, size)
        lines = _wrap(draw, text, fnt, x1 - x0)
        lh = size * 1.25
        if lh * len(lines) <= (y1 - y0) or size <= 12:
            break
        size *= 0.92
    total = lh * len(lines)
    y = y0 if valign == "top" else (y1 - total if valign == "bottom" else y0 + (y1 - y0 - total) / 2)
    for line in lines:
        draw.text((x0, y), line, font=fnt, fill=color)
        y += lh


def _paste_fit(canvas, path, box, border=None, shadow=False):
    with Image.open(path) as im:
        im = im.convert("RGBA")
        x, y, w, h = L.fit_box(im.width, im.height, box)
        x0, y0, w, h = int(x * PX), int(y * PX), int(w * PX), int(h * PX)
        im = im.resize((max(w, 1), max(h, 1)), Image.LANCZOS)
    if shadow:
        sh = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rectangle((20, 20, w + 20, h + 20), fill=(21, 34, 56, 70))
        sh = sh.filter(ImageFilter.GaussianBlur(10))
        canvas.alpha_composite(sh, (x0 - 14, y0 - 10))
    canvas.alpha_composite(im, (x0, y0))
    if border:
        ImageDraw.Draw(canvas).rectangle((x0, y0, x0 + w, y0 + h), outline=border, width=2)


def _logo(canvas, logo, box):
    d = ImageDraw.Draw(canvas)
    x0, y0, x1, y1 = _b(box)
    d.rounded_rectangle((x0, y0, x1, y1), radius=int((y1 - y0) * 0.18), fill=WHITE)
    x, y, w, h = box
    _paste_fit(canvas, logo, (x + 0.08, y + 0.08, w - 0.16, h - 0.16))


def _bullets(canvas, box, lines, pt):
    d = ImageDraw.Draw(canvas)
    x0, y0, x1, y1 = _b(box)
    d.rectangle((x0, y0, x1, y1), fill=LIGHT)
    d.rectangle((x0, y0, x0 + int(0.07 * PX), y1), fill=BLUE)
    left, right = x0 + int(0.3 * PX), x1 - int(0.2 * PX)
    size = pt * PT
    while True:
        fb, fr = font("bold", (pt + 2) * PT * size / (pt * PT)), font("regular", size)
        wrapped = [_wrap(d, l, fr, right - left - size * 1.2) for l in lines]
        height = size * 1.6 + sum(len(w) * size * 1.3 + size * 0.6 for w in wrapped)
        if height <= (y1 - y0) - 0.4 * PX or size <= 14:
            break
        size *= 0.92
    y = y0 + int(0.2 * PX)
    d.text((left, y), "Key points", font=fb, fill=BLUE)
    y += size * 1.6
    for wl in wrapped:
        y += size * 0.6
        sq = size * 0.38
        d.rectangle((left, y + size * 0.42, left + sq, y + size * 0.42 + sq), fill=ORANGE)
        for line in wl:
            d.text((left + size * 1.2, y), line, font=fr, fill=NAVY)
            y += size * 1.3


def render_slide(proj, s, number, out_path):
    base = folder(proj["id"])
    logo = logo_path(proj)
    canvas = Image.new("RGBA", (VIDEO_W, VIDEO_H), WHITE)
    d = ImageDraw.Draw(canvas)
    if s["kind"] in ("title", "closing"):
        d.rectangle((0, 0, VIDEO_W, VIDEO_H), fill=NAVY)
        d.rectangle(_b(L.COVER_BAND), fill=BLUE)
        d.rectangle(_b(L.COVER_BAR), fill=ORANGE)
        _logo(canvas, logo, L.COVER_LOGO)
        _text(d, L.COVER_TITLE, s["title"] or proj["title"], 44, WHITE, "bold", "bottom")
        _text(d, L.COVER_SUB, s["notes"] or "", 22, "#bcd3f0")
        meta = "  |  ".join(v for v in (proj.get("presenter"), proj.get("company"), proj.get("contact")) if v)
        if meta:
            _text(d, L.COVER_META, meta, 16, WHITE)
    else:
        d.rectangle(_b(L.HEADER), fill=NAVY)
        d.rectangle(_b(L.ACCENT), fill=ORANGE)
        _text(d, L.HEADER_TITLE, s["title"], 28, WHITE, "bold", "middle")
        _logo(canvas, logo, L.HEADER_LOGO)
        lines = L.bullets(s["notes"])
        img = base / s["image"] if s.get("image") else None
        if img and img.exists():
            _paste_fit(canvas, img, L.SHOT_WITH_NOTES if lines else L.SHOT_FULL, border="#c9d3e0", shadow=True)
            if lines:
                _bullets(canvas, L.NOTES_PANEL, lines, L.bullet_font_pt(lines))
        elif lines:
            _bullets(canvas, L.NOTES_FULL, lines, L.bullet_font_pt(lines, full_width=True))
        footer = proj.get("title", "") + (f"  |  {proj['company']}" if proj.get("company") else "")
        _text(d, (0.5, L.FOOTER_Y, 9, 0.35), footer, 10, GREY)
        fnt = font("bold", 10 * PT)
        num = str(number)
        d.text((int(12.83 * PX) - d.textlength(num, font=fnt), int(L.FOOTER_Y * PX)), num, font=fnt, fill=BLUE)
    canvas.convert("RGB").save(out_path, "PNG", optimize=False)
    return out_path
