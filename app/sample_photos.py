"""Simple sample pictures, drawn offline, for the previews and thumbnails of picture presets
(the user replaces them with their own photo)."""
import math
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

W, H = 1600, 900


def _sky(top, bottom):
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        a = y / H
        d.line((0, y, W, y), fill=tuple(int(t + (b - t) * a) for t, b in zip(top, bottom)))
    return im, d


@lru_cache(maxsize=8)
def sample(kind="portrait"):
    if kind == "city":
        im, d = _sky((24, 30, 70), (240, 130, 90))
        for k in range(28):
            x = k * 60 - 20
            h = 200 + int(260 * abs(math.sin(k * 1.7)))
            d.rectangle((x, H - h, x + 54, H), fill=(18, 20, 34))
            for wy in range(H - h + 20, H - 20, 34):
                if (wy + k) % 3:
                    d.rectangle((x + 10, wy, x + 22, wy + 14), fill=(250, 200, 110))
    elif kind == "product":
        im, d = _sky((236, 238, 242), (200, 205, 214))
        d.ellipse((560, 720, 1040, 790), fill=(170, 175, 185))
        d.rounded_rectangle((680, 260, 920, 760), radius=40, fill=(31, 95, 168))
        d.rectangle((740, 200, 860, 270), fill=(20, 30, 50))
        d.rounded_rectangle((700, 420, 900, 560), radius=10, fill=(240, 244, 250))
        d.rectangle((720, 470, 880, 490), fill=(224, 123, 31))
    elif kind == "landscape":
        im, d = _sky((40, 80, 150), (250, 200, 140))
        d.ellipse((1050, 180, 1250, 380), fill=(255, 220, 140))
        d.polygon([(0, H), (420, 360), (820, H)], fill=(60, 64, 90))
        d.polygon([(500, H), (980, 300), (1500, H)], fill=(44, 46, 70))
        d.polygon([(0, H), (0, 760), (W, 700), (W, H)], fill=(30, 60, 50))
    elif kind == "food":
        im, d = _sky((60, 40, 30), (120, 80, 50))
        d.ellipse((450, 180, 1150, 860), fill=(245, 242, 236))
        d.ellipse((560, 290, 1040, 750), fill=(214, 96, 58))
        for k in range(9):
            a = k * 0.7
            cx, cy = 800 + int(150 * math.cos(a)), 520 + int(150 * math.sin(a))
            d.ellipse((cx - 34, cy - 34, cx + 34, cy + 34), fill=(250, 210, 90) if k % 2 else (80, 150, 70))
    else:   # portrait: a person against a soft studio background
        im, d = _sky((70, 90, 130), (200, 170, 150))
        d.ellipse((610, 640, 990, 1200), fill=(40, 44, 60))          # shoulders
        d.ellipse((690, 300, 910, 560), fill=(214, 170, 140))        # face
        d.pieslice((670, 250, 930, 520), 180, 360, fill=(36, 30, 32))  # hair
        d.rectangle((760, 540, 840, 640), fill=(200, 156, 128))      # neck
    return im.filter(ImageFilter.GaussianBlur(1.2))
