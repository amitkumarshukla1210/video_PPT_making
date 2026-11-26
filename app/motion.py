"""Motion graphics: animated scenes instead of still slides (Make a video › "Motion graphics").

Each scene picks a motion language from its own content, so the film is about *this* material:
  • title / closing   → kinetic title: the words rise in one by one, the accent bar draws, the logo pops
  • one number        → a big counter that counts up (e.g. "Steel price +8%")
  • several numbers   → a bar chart that grows, values counting with it (suppliers, cost drivers)
  • a picture         → the picture is revealed and slowly pushed in (camera move); points beside it
  • points only       → the points come in one by one *when the voice says them*
Every scene ends with a short push-out, so cuts feel continuous. Frames are drawn with Pillow and
streamed straight into FFmpeg (no temporary images), at 1920x1080, 30 fps.

Ideas (motion per content type, reveals anchored to the narration's words, cuts on the music's beat)
follow the approach of huashu-motion (MIT, github.com/alchaincyf/huashu-motion); the code is our own."""
import math
import re
import subprocess

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from . import layout as L
from .config import NAVY, BLUE, ORANGE, WHITE, GREY, VIDEO_W, VIDEO_H, FPS
from .ffmpeg_utils import ffmpeg_bin
from .ppt_builder import logo_path
from .project import folder
from .slide_render import font

W, H = VIDEO_W, VIDEO_H
BG = (246, 248, 251)
EXIT = 0.38          # seconds of push-out at the end of each scene
MARGIN = 120


def _rgb(hex_):
    hex_ = hex_.lstrip("#")
    return tuple(int(hex_[i:i + 2], 16) for i in (0, 2, 4))


NAVY_, BLUE_, ORANGE_, WHITE_, GREY_ = map(_rgb, (NAVY, BLUE, ORANGE, WHITE, GREY))
INK = NAVY_


# ---------- easing ----------
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def out_cubic(p):
    p = clamp(p)
    return 1 - (1 - p) ** 3


def in_out(p):
    p = clamp(p)
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def out_back(p, s=1.6):
    p = clamp(p)
    return 1 + (s + 1) * (p - 1) ** 3 + s * (p - 1) ** 2


def mix(c1, c2, a):
    a = clamp(a)
    return tuple(int(round(x + (y - x) * a)) for x, y in zip(c1, c2))


def prog(t, start, dur):
    return clamp((t - start) / dur) if dur > 0 else float(t >= start)


# ---------- looks (palettes) ----------
LOOKS = {
    # name: label, colours. "dark" = content scenes on a dark ground; "letterbox" = cinema bars;
    # "statement" = scenes with only a title become one big centred line
    "corporate": {"label": "Corporate — Design to Cost colours", "BG": (246, 248, 251), "INK": NAVY_, "ACC": ORANGE_,
                  "ACC2": BLUE_, "MUTED": GREY_, "DARK": NAVY_, "LIGHT": WHITE_, "SUB": (205, 218, 236),
                  "TRACK": (230, 236, 244), "SHADOW": (170, 182, 200), "letterbox": False, "statement": False},
    "cinematic": {"label": "Cinematic — dark, gold, cinema bars", "BG": (14, 15, 20), "INK": (238, 233, 222),
                  "ACC": (214, 170, 90), "ACC2": (110, 128, 160), "MUTED": (130, 130, 140), "DARK": (8, 9, 12),
                  "LIGHT": (245, 239, 228), "SUB": (190, 178, 155), "TRACK": (38, 40, 48), "SHADOW": (0, 0, 0),
                  "letterbox": True, "statement": True},
    "bold": {"label": "Bold social — black, yellow, pink", "BG": (16, 16, 16), "INK": (255, 255, 255),
             "ACC": (255, 214, 0), "ACC2": (255, 64, 129), "MUTED": (150, 150, 150), "DARK": (16, 16, 16),
             "LIGHT": (255, 255, 255), "SUB": (255, 214, 0), "TRACK": (45, 45, 45), "SHADOW": (0, 0, 0),
             "letterbox": False, "statement": True},
    "warm": {"label": "Warm — cream and terracotta", "BG": (250, 244, 235), "INK": (62, 42, 32), "ACC": (214, 96, 58),
             "ACC2": (52, 118, 108), "MUTED": (140, 120, 105), "DARK": (62, 42, 32), "LIGHT": (250, 244, 235),
             "SUB": (232, 210, 190), "TRACK": (238, 226, 212), "SHADOW": (200, 180, 160),
             "letterbox": False, "statement": True},
}


# camera effects for picture scenes (Tools › Video and the "Viral presets" in Inspirations)
FX = {
    "drift": "Dreamy drift — slow push-in",
    "zoom_punch": "Zoom punch — hits on every beat",
    "pull_back": "Pull-back reveal",
    "spin_in": "Spin-in",
    "glitch": "Glitch — colour split on the beat",
    "shake": "Camera shake",
    "polaroid": "Polaroid drop",
    "split_reveal": "Split reveal — three panels",
    "vhs": "VHS retro tape",
    "flash_cuts": "Flash cuts — new framing every beat",
    "duotone": "Duotone poster",
    "countdown": "3 · 2 · 1 countdown",
}


def look_of(proj):
    return LOOKS.get(proj.get("look") or "corporate", LOOKS["corporate"])


# ---------- reading the slide ----------
NUM = re.compile(r"(?<![A-Za-z\d])(?P<pre>[₹$€£]\s?|rs\.?\s?|inr\s?|usd\s?|eur\s?)?(?P<sign>[+\-−])?(?P<num>\d[\d,]*(?:\.\d+)?)"
                 r"\s?(?P<suf>%|x\b|k\b|mn\b|bn\b|m\b|cr\b|crores?\b|lakhs?\b|l\b|pcs\b|kg\b|mm\b|"
                 r"hours?\b|hrs?\b|minutes?\b|mins?\b|seconds?\b|secs?\b|days?\b|weeks?\b|months?\b)?(?![A-Za-z\d])",
                 re.I)


def _number(line):
    """(value, prefix, suffix, label) for the first number in a line, or None."""
    m = NUM.search(line)
    if not m or not re.search(r"\d", m.group("num")):
        return None
    try:
        val = float(m.group("num").replace(",", ""))
    except ValueError:
        return None
    if 1900 <= val <= 2100 and not m.group("suf") and not m.group("pre"):
        return None                                     # a year, not a value
    neg = m.group("sign") in ("-", "−")
    pre = (m.group("pre") or "").strip()
    suf = (m.group("suf") or "").strip()
    before, after = line[:m.start()].strip(" :-–—,."), line[m.end():].strip(" :-–—,.")
    # number in the middle of a sentence: keep the whole sentence, it reads naturally under the number
    label = line.strip() if before and after and len(after.split()) > 1 else f"{before} {after}".strip()
    label = re.sub(r"\s{2,}", " ", label)
    decimals = len(m.group("num").split(".")[1]) if "." in m.group("num") else 0
    return {"value": -val if neg else val, "pre": pre, "suf": suf, "label": label,
            "decimals": decimals, "signed": bool(m.group("sign")), "text": line, "bare": not label}


def plan(proj, s):
    """Which motion language this scene uses, and its data."""
    points = L.bullets(s.get("notes"), limit=6)
    if s.get("_photo") is not None:                 # a picture given directly (previews of picture presets)
        image = "sample"
    else:
        image = s.get("image") if s.get("image") and (folder(proj["id"]) / s["image"]).exists() else None
    if s["kind"] in ("title", "closing"):
        return {"type": "title", "points": points}
    nums = [n for n in (_number(p) for p in points) if n]
    if image and (s.get("fx") or (look_of(proj)["statement"] and not nums)):
        return {"type": "film", "points": points, "image": image}      # full-screen shot, words over it
    if image:
        return {"type": "photo", "points": points, "image": image}
    # a chart only compares like with like: at least two numbers in the same unit (₹, %, minutes…)
    unit = lambda n: (n["pre"].lower().strip(), n["suf"].lower().rstrip("s"))      # noqa: E731
    same = [n for n in nums if unit(n) == unit(nums[0])] if nums else []
    if len(same) >= 2 and len(nums) >= len(points) - 1:
        rest = [p for p in points if not any(p == n["text"] for n in same)]
        return {"type": "bars", "bars": same[:6], "points": rest}
    if nums:
        return {"type": "counter", "number": nums[0], "points": [p for p in points if p != nums[0]["text"]]}
    if not points and (look_of(proj)["statement"] or not (s.get("script") or "").strip()):
        return {"type": "statement", "points": []}
    return {"type": "points", "points": points}


def anchors(points, script, lead_in, spoken, start=0.5):
    """When each point should appear: the moment the narration says it (its first meaningful word),
    or evenly spread over the narration when no word matches."""
    words = [re.sub(r"\W", "", w.lower()) for w in (script or "").split()]
    n = max(len(words), 1)
    out, pos = [], 0
    for k, p in enumerate(points):
        keys = [re.sub(r"\W", "", w.lower()) for w in p.split()]
        keys = [w for w in keys if len(w) >= 4] or [w for w in keys if w]
        hit = next((i for i in range(pos, len(words)) if words[i] in keys), None)
        if hit is not None and spoken > 0:
            pos = hit + 1
            out.append(lead_in + hit / n * spoken - 0.25)
        else:
            span = max(spoken * 0.8, 0.6 * len(points))
            out.append(lead_in + start + span * k / max(len(points), 1))
    # keep order and at least 0.25 s apart, never before the scene has settled
    fixed, last = [], 0.35
    for t in out:
        t = max(t, last + 0.25, 0.35)
        fixed.append(t)
        last = t
    return fixed


# ---------- drawing helpers ----------
def _fit_font(d, text, style, size, max_w, min_size=24):
    while size > min_size and d.textlength(text, font=font(style, size)) > max_w:
        size = int(size * 0.92)
    return font(style, size), size


def _wrap(d, text, fnt, max_w, max_lines=3):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if d.textlength(trial, font=fnt) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,") + "…"
    return lines


def _indian(x, decimals):
    """12,34,567 — lakh / crore grouping for rupee amounts."""
    whole, _, frac = f"{x:.{decimals}f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
        whole = head + "," + tail
    return whole + ("." + frac if frac else "")


def _fmt(n, v):
    rupee = n["pre"].lower().strip(" .") in ("₹", "rs", "inr")
    s = _indian(abs(v), n["decimals"]) if rupee else f"{abs(v):,.{n['decimals']}f}"
    sign = ("−" if v < 0 else "+") if n["signed"] else ("−" if v < 0 else "")
    pre = n["pre"] if n["pre"] in ("₹", "$", "€", "£") else (n["pre"] + " " if n["pre"] else "")
    suf = n["suf"] if n["suf"] == "%" else (" " + n["suf"] if n["suf"] else "")
    return f"{sign}{pre}{s}{suf}"


class _Logo:
    def __init__(self, proj):
        try:
            with Image.open(logo_path(proj)) as im:
                self.im = im.convert("RGBA")
        except Exception:
            self.im = None

    def sized(self, h):
        if not self.im:
            return None
        w = max(1, int(self.im.width * h / self.im.height))
        return self.im.resize((w, int(h)), Image.LANCZOS)


# ---------- scenes ----------
class Scene:
    """Draws frame t (seconds) of one scene."""

    def __init__(self, proj, s, index, total, dur, lead_in, spoken):
        self.proj, self.s, self.index, self.total = proj, s, index, total
        self.dur, self.lead_in, self.spoken = dur, lead_in, spoken
        self.p = plan(proj, s)
        self.look = look_of(proj)
        for k in ("BG", "INK", "ACC", "ACC2", "MUTED", "DARK", "LIGHT", "SUB", "TRACK", "SHADOW"):
            setattr(self, k, self.look[k])
        self.logo = _Logo(proj)
        # the Design to Cost logo belongs on corporate videos; films and social videos show yours only if uploaded
        self.branded = (proj.get("look") or "corporate") == "corporate" or bool(proj.get("logo"))
        self.small_logo = self.logo.sized(54)
        self.title = (s.get("title") or "").strip()
        self.points = self.p.get("points") or []
        self.when = anchors(self.points, s.get("script"), lead_in, spoken, start=0.9)
        self.bg = self._background()
        if self.p["type"] in ("photo", "film"):
            if s.get("_photo") is not None:
                self.photo = s["_photo"].convert("RGB")
            else:
                with Image.open(folder(proj["id"]) / self.p["image"]) as im:
                    self.photo = im.convert("RGB")

    # static background: drawn once
    def _background(self):
        dark = self.p["type"] in ("title", "statement", "film")
        im = Image.new("RGB", (W, H), self.DARK if dark else self.BG)
        d = ImageDraw.Draw(im)
        if dark:
            for k in range(9):      # soft diagonal light, like a lit stage
                d.polygon([(W * 0.45 + k * 90, 0), (W * 0.62 + k * 90, 0), (W * 0.32 + k * 90, H), (W * 0.15 + k * 90, H)],
                          fill=mix(self.DARK, self.ACC2, 0.10 + 0.02 * (k % 3)))
            im = im.filter(ImageFilter.GaussianBlur(40))
        else:
            d.rectangle((0, 0, W, 10), fill=self.DARK)
            if self.branded:
                if self.small_logo:
                    im.paste(self.small_logo, (W - MARGIN - self.small_logo.width, H - 54 - 40), self.small_logo)
                f = font("regular", 26)
                d.text((MARGIN, H - 40 - 34), f"{self.index:02d} / {self.total:02d}", font=f, fill=self.MUTED)
        return im

    def frame(self, t):
        im = self.bg.copy()
        d = ImageDraw.Draw(im)
        getattr(self, "_" + self.p["type"])(im, d, t)
        if self.p["type"] not in ("title", "statement", "film"):   # a thin line runs across the top: never frozen
            d.rectangle((0, 10, int(W * clamp(t / max(self.dur, 0.1))), 16), fill=self.ACC)
        if self.look["letterbox"]:                           # cinema bars
            d.rectangle((0, 0, W, 104), fill=(0, 0, 0))
            d.rectangle((0, H - 104, W, H), fill=(0, 0, 0))
        k = prog(t, self.dur - EXIT, EXIT)          # push-out into the next scene
        if k > 0:
            im = Image.blend(im, self.bg, in_out(k))
        return im

    # — title: kinetic words + drawing accent bar + logo pop
    def _title(self, im, d, t):
        closing = self.s["kind"] == "closing"
        if not hasattr(self, "_big_logo"):
            self._big_logo = self.logo.sized(120)
        logo = self._big_logo if self.branded else None
        if logo:
            a = out_back(prog(t, 0.05, 0.6))
            if a > 0.02:
                lw, lh = max(1, int(logo.width * a)), max(1, int(logo.height * a))
                small = logo if (lw, lh) == logo.size else logo.resize((lw, lh), Image.BILINEAR)
                card = Image.new("RGB", (lw + 40, lh + 30), self.LIGHT)
                card.paste(small, (20, 15), small)
                im.paste(card, (MARGIN + int((logo.width - lw) / 2), 150 + int((logo.height - lh) / 2)))
        title = self.title or self.proj.get("title", "")
        f, size = _fit_font(d, title, "bold", 112, W - 2 * MARGIN)
        lines = _wrap(d, title, f, W - 2 * MARGIN, 2)
        y = 430 if len(lines) == 1 else 360
        n = 0
        for line in lines:
            x = MARGIN
            for word in line.split():
                p = out_cubic(prog(t, 0.35 + n * 0.07, 0.55))
                if p > 0:
                    d.text((x, y + (1 - p) * 60), word, font=f, fill=mix(self.DARK, self.LIGHT, p))
                x += d.textlength(word + " ", font=f)
                n += 1
            y += size * 1.12
        bar = out_cubic(prog(t, 0.55 + n * 0.07, 0.7))
        d.rectangle((MARGIN, y + 24, MARGIN + int(bar * 420), y + 34), fill=self.ACC)
        sub = self.s.get("notes") or ("" if closing else self.proj.get("subtitle", ""))
        sub = " · ".join(L.bullets(sub, 3)) if sub else ""
        meta = " · ".join(x for x in (self.proj.get("presenter"), self.proj.get("company"),
                                      self.proj.get("contact") if closing else "") if x)
        fs = font("regular", 44)
        for k, text in enumerate(x for x in (sub, meta) if x):
            p = out_cubic(prog(t, 0.9 + n * 0.07 + 0.2 * k, 0.6))
            if p > 0:
                for j, line in enumerate(_wrap(d, text, fs, W - 2 * MARGIN, 2)):
                    d.text((MARGIN, y + 70 + k * 110 + j * 54 + (1 - p) * 20), line, font=fs,
                           fill=mix(self.DARK, self.SUB, p))

    # — statement: one big centred line, word by word (trailers, music videos, social)
    def _statement(self, im, d, t):
        text = self.title or (self.s.get("script") or "").split(".")[0]
        f, size = _fit_font(d, text, "bold", 150, W - 2 * MARGIN, min_size=60)
        lines = _wrap(d, text, f, W - 2 * MARGIN, 3)
        y = H / 2 - len(lines) * size * 0.6 - 40
        n = 0
        for line in lines:
            words = line.split()
            x = (W - d.textlength(line, font=f)) / 2
            for k, word in enumerate(words):
                p = out_back(prog(t, 0.15 + n * 0.09, 0.45), 1.2)
                if p > 0:
                    hi = k == len(words) - 1 and line is lines[-1]       # last word: accent colour
                    d.text((x, y + (1 - min(p, 1)) * 70), word, font=f,
                           fill=mix(self.DARK, self.ACC if hi else self.LIGHT, min(p, 1)))
                x += d.textlength(word + " ", font=f)
                n += 1
            y += size * 1.15
        said = " ".join((self.s.get("script") or "").split()[:14])
        norm = lambda x: re.sub(r"\W+", " ", x.lower()).strip()      # noqa: E731
        if self.title and norm(said).startswith(norm(self.title)):      # don't repeat the title underneath it
            said = said[len(self.title):].lstrip(" .,:;!?—-")
        sub = (self.s.get("notes") or "").strip() or (said if self.title else "")
        if sub:
            fs = font("regular", 46)
            a = out_cubic(prog(t, 0.4 + n * 0.09, 0.6))
            for j, line in enumerate(_wrap(d, sub, fs, W - 4 * MARGIN, 2)):
                d.text(((W - d.textlength(line, font=fs)) / 2, y + 30 + j * 58 + (1 - a) * 20), line, font=fs,
                       fill=mix(self.DARK, self.SUB, a))
        w = int(out_cubic(prog(t, 0.3 + n * 0.09, 0.6)) * 260)
        d.rectangle(((W - w) / 2, y + 12, (W + w) / 2, y + 18), fill=self.ACC)

    # — film: the picture fills the screen, a slow push-in, the words rise over a dark gradient
    def _film(self, im, d, t):
        self._shot(im, t, self.s.get("fx") or "drift")
        if not hasattr(self, "_shade"):           # dark gradient at the bottom so the words read on any picture
            g = Image.linear_gradient("L").resize((W, H)).point(lambda v: int(max(0, v - 90) * 1.6))
            self._shade = (Image.new("RGB", (W, H), self.DARK), g)
        im.paste(self._shade[0], (0, 0), self._shade[1])
        text = self.title
        f, size = _fit_font(d, text, "bold", 110, W - 2 * MARGIN, min_size=50)
        lines = _wrap(d, text, f, W - 2 * MARGIN, 2)
        y = H - 170 - len(lines) * size * 1.12 - (60 if self.points or self.s.get("notes") else 0)
        n = 0
        for li, line in enumerate(lines):
            x = MARGIN
            words = line.split()
            for k, word in enumerate(words):
                p = out_cubic(prog(t, 0.35 + n * 0.08, 0.5))
                if p > 0:
                    hi = li == len(lines) - 1 and k == len(words) - 1
                    d.text((x, y + (1 - p) * 50), word, font=f, fill=mix(self.DARK, self.ACC if hi else self.LIGHT, p))
                x += d.textlength(word + " ", font=f)
                n += 1
            y += size * 1.12
        sub = " · ".join(self.points) if self.points else ""
        if sub:
            fs = font("regular", 44)
            a = out_cubic(prog(t, 0.6 + n * 0.08, 0.5))
            d.text((MARGIN, y + 20 + (1 - a) * 16), sub[:110], font=fs, fill=mix(self.DARK, self.SUB, a))

    # — the picture of a film scene, with its camera effect ("viral presets")
    def _fit(self, z, dx=0.0, dy=0.0, src=None):
        """The picture filling the frame at zoom z, shifted by dx/dy pixels."""
        src = src or self.photo
        sc = max(W / src.width, H / src.height) * z
        rw, rh = int(src.width * sc) + 1, int(src.height * sc) + 1
        key = (id(src), rw, rh)
        if getattr(self, "_cache", (None,))[0] != key:
            self._cache = (key, src.resize((rw, rh), Image.BILINEAR))
        x0 = int(clamp((rw - W) / 2 - dx, 0, rw - W))
        y0 = int(clamp((rh - H) / 2 - dy, 0, rh - H))
        return self._cache[1].crop((x0, y0, x0 + W, y0 + H))

    def _beat(self, t, every=0.6):
        """0..1 pulse that jumps to 1 on every beat and fades quickly."""
        return math.exp(-((t % every) / every) * 6)

    def _shot(self, im, t, fx):
        D = self.dur
        fade = out_cubic(prog(t, 0, 0.45))
        flash = 0.0
        if fx == "zoom_punch":                                   # punch-in on every beat
            b = self._beat(t)
            shot = self._fit(1.04 + 0.14 * b + 0.04 * prog(t, 0, D))
            flash = 0.35 * b if t > 0.3 else 0
        elif fx == "pull_back":                                  # starts close, pulls back to reveal
            shot = self._fit(1.0 + 0.9 * (1 - in_out(prog(t, 0, D * 0.75))))
        elif fx == "spin_in":                                    # spins and grows in from the centre
            p = out_back(prog(t, 0, 1.1), 1.2)
            base = self._fit(1.0 + 0.04 * prog(t, 0, D))
            k = max(0.05, min(1.0, 0.3 + 0.7 * p))
            small = base.resize((max(1, int(W * k)), max(1, int(H * k))), Image.BILINEAR).rotate(
                (1 - min(p, 1)) * 40, resample=Image.BILINEAR, expand=False, fillcolor=self.DARK)
            shot = Image.new("RGB", (W, H), self.DARK)
            shot.paste(small, ((W - small.width) // 2, (H - small.height) // 2))
        elif fx == "glitch":                                     # colour split and torn lines on the beat
            shot = self._fit(1.06 + 0.03 * prog(t, 0, D))
            b = self._beat(t, 0.8)
            if b > 0.35:
                k = int(24 * b)
                r, g, bl = shot.split()
                shot = Image.merge("RGB", (ImageChops.offset(r, k, 0), g, ImageChops.offset(bl, -k, 0)))
                n = int(t * 30)
                for j in range(4):
                    y = (n * 97 + j * 211) % (H - 60)
                    band = shot.crop((0, y, W, y + 40 + j * 6))
                    shot.paste(ImageChops.offset(band, ((n + j) % 5 - 2) * 30, 0), (0, y))
        elif fx == "shake":                                      # handheld camera shake, settling down
            a = 26 * (1 - 0.7 * prog(t, 0, D))
            shot = self._fit(1.12, a * math.sin(t * 37), a * 0.7 * math.cos(t * 29))
        elif fx == "polaroid":                                   # the photo drops in as a polaroid
            p = out_back(prog(t, 0.1, 0.9), 1.1)
            bg = Image.new("RGB", (W, H), self.BG if self.BG != self.DARK else (40, 40, 46))
            if not hasattr(self, "_pola"):
                ph = ImageOps.fit(self.photo, (760, 620), Image.BILINEAR)
                card = Image.new("RGB", (820, 800), (250, 250, 246))
                card.paste(ph, (30, 30))
                self._pola = card
            ang = -14 + 10 * min(p, 1)
            card = self._pola.rotate(ang, resample=Image.BILINEAR, expand=True, fillcolor=bg.getpixel((0, 0)))
            y = int(-card.height + (H / 2 - card.height / 2 + card.height) * min(p, 1.05)) - 40
            bg.paste(card, ((W - card.width) // 2 + 260, y))
            shot = bg
        elif fx == "split_reveal":                               # three panels slide in, one after another
            base = self._fit(1.05 + 0.04 * prog(t, 0, D))
            shot = Image.new("RGB", (W, H), self.DARK)
            pw = W // 3
            for k in range(3):
                p = out_cubic(prog(t, 0.15 + k * 0.22, 0.6))
                dy = int((1 - p) * H * (1 if k % 2 else -1))
                shot.paste(base.crop((k * pw, 0, (k + 1) * pw if k < 2 else W, H)), (k * pw, dy))
        elif fx == "vhs":                                        # retro tape look with a date stamp
            shot = self._fit(1.04, 3 * math.sin(t * 11), 0)
            shot = Image.blend(shot, Image.new("RGB", (W, H), (60, 20, 70)), 0.18)
            if not hasattr(self, "_lines"):
                ln = Image.new("L", (W, H), 0)
                dd = ImageDraw.Draw(ln)
                for y in range(0, H, 6):
                    dd.line((0, y, W, y), fill=60)
                self._lines = ln
            shot.paste((0, 0, 0), (0, 0), self._lines)
            dd = ImageDraw.Draw(shot)
            fnt = font("bold", 46)
            dd.text((80, 70), "PLAY ▶" if int(t * 2) % 2 == 0 else "PLAY", font=fnt, fill=(240, 240, 240))
            dd.text((W - 520, H - 130), "JAN 01 1999  12:00", font=fnt, fill=(240, 240, 240))
        elif fx == "flash_cuts":                                 # cut to a closer framing on every beat
            beat = int(t / 0.6)
            frames = [(1.02, 0, 0), (1.25, -220, -80), (1.12, 200, 60), (1.4, 0, -120)]
            z, dx, dy = frames[beat % len(frames)]
            shot = self._fit(z, dx, dy)
            flash = 0.5 * self._beat(t) if t > 0.3 else 0
        elif fx == "duotone":                                    # two-colour poster look, slow push
            if not hasattr(self, "_duo"):
                self._duo = ImageOps.colorize(ImageOps.grayscale(self.photo), self.DARK, self.ACC)
            shot = self._fit(1.03 + 0.07 * in_out(prog(t, 0, D)), src=self._duo)
        elif fx == "countdown":                                  # 3 · 2 · 1, then the reveal
            shot = self._fit(1.0 + 0.08 * in_out(prog(t, 0, D)))
            if t < 2.4:
                shot = Image.blend(shot, Image.new("RGB", (W, H), self.DARK), 0.7)
                dd = ImageDraw.Draw(shot)
                n = 3 - int(t / 0.8)
                p = out_back(prog(t % 0.8, 0, 0.35), 1.4)
                fnt = font("bold", int(420 * max(p, 0.1)))
                txt = str(n)
                dd.text(((W - dd.textlength(txt, font=fnt)) / 2, H / 2 - fnt.size * 0.62), txt, font=fnt, fill=self.ACC)
            elif t < 2.55:
                flash = 0.8
        else:                                                    # "drift": slow push-in and drift (default)
            p = in_out(prog(t, 0, D))
            shot = self._fit(1.0 + 0.08 * p, 120 * (1 - p) - 60, 0)
        if flash > 0:
            shot = Image.blend(shot, Image.new("RGB", (W, H), (255, 255, 255)), min(flash, 0.9))
        im.paste(Image.blend(Image.new("RGB", (W, H), self.DARK), shot, fade) if fade < 1 else shot)

    # — heading shared by content scenes: wipes in from the left
    def _heading(self, im, d, t, max_w=W - 2 * MARGIN):
        f, size = _fit_font(d, self.title, "bold", 72, max_w)
        p = out_cubic(prog(t, 0.0, 0.55))
        tw = int(d.textlength(self.title, font=f))
        layer = Image.new("RGB", (tw + 10, int(size * 1.35)), self.BG)
        ImageDraw.Draw(layer).text((0, 0), self.title, font=f, fill=self.INK)
        vis = int(layer.width * p)
        if vis > 0:
            im.paste(layer.crop((0, 0, vis, layer.height)), (MARGIN, 96))
        d.rectangle((MARGIN, 96 + size * 1.3, MARGIN + int(out_cubic(prog(t, 0.25, 0.6)) * 140), 96 + size * 1.3 + 8),
                    fill=self.ACC)
        return 96 + size * 1.3 + 60

    def _point_list(self, im, d, t, x, y, max_w, size=46, gap=34, times=None, number=True):
        f = font("regular", size)
        times = times or self.when
        for k, (pt, at) in enumerate(zip(self.points, times)):
            p = prog(t, at, 0.45)
            if p <= 0:
                y += size * 1.3 + gap
                continue
            r = 30 if number else 12
            pop = out_back(prog(t, at, 0.4))
            cx, cy = x + (r if number else 30), y + size * 0.62
            rr = max(1, int(r * pop))
            d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=self.ACC2 if k else self.ACC)
            if number and pop > 0.6:
                fn = font("bold", 30)
                s = str(k + 1)
                d.text((cx - d.textlength(s, font=fn) / 2, cy - 19), s, font=fn, fill=self.LIGHT)
            a = out_cubic(p)
            lines = _wrap(d, pt, f, max_w - 90, 2)
            for j, line in enumerate(lines):
                d.text((x + 90 + (1 - a) * 50, y + j * size * 1.2), line, font=f, fill=mix(self.BG, self.INK, a))
            y += size * 1.2 * len(lines) + gap
        return y

    # — points: appear when the voice says them
    def _points(self, im, d, t):
        y = self._heading(im, d, t)
        if not self.points:      # nothing but a title: let the spoken words carry it as a big quote
            line = (self.s.get("script") or "").split(".")[0][:140]
            f = font("light", 60)
            for j, l in enumerate(_wrap(d, line, f, W - 2 * MARGIN, 3)):
                a = out_cubic(prog(t, 0.6 + 0.15 * j, 0.6))
                d.text((MARGIN, y + 40 + j * 80 + (1 - a) * 30), l, font=f, fill=mix(self.BG, self.INK, a))
            return
        size = 50 if len(self.points) <= 4 else 42
        self._point_list(im, d, t, MARGIN, y + 10, W - 2 * MARGIN, size=size)

    # — counter: one big number that counts up
    def _counter(self, im, d, t):
        y = self._heading(im, d, t)
        n = self.p["number"]
        p = out_cubic(prog(t, 0.45, 1.4))
        txt = _fmt(n, n["value"] * p)
        f, nsize = _fit_font(d, _fmt(n, n["value"]), "bold", 230, W * 0.5 - MARGIN)
        color = self.ACC if n["value"] >= 0 else self.ACC2
        d.text((MARGIN - 6, y + 10), txt, font=f, fill=mix(self.BG, color, out_cubic(prog(t, 0.4, 0.3))))
        fl = font("regular", 48)
        a = out_cubic(prog(t, 0.9, 0.5))
        for j, line in enumerate(_wrap(d, n["label"], fl, W * 0.5, 2)):
            d.text((MARGIN, y + 10 + nsize * 1.3 + j * 60 + (1 - a) * 20), line, font=fl, fill=mix(self.BG, self.INK, a))
        if self.points:
            times = anchors(self.points, self.s.get("script"), self.lead_in, self.spoken, start=1.6)
            self._point_list(im, d, t, int(W * 0.6), y + 30, int(W * 0.4) - MARGIN, size=40, times=times)

    # — bars: a chart that grows
    def _bars(self, im, d, t):
        y0 = self._heading(im, d, t)
        bars = self.p["bars"]
        top = max(abs(b["value"]) for b in bars) or 1
        label_w = int(W * 0.30)
        x0, x1 = MARGIN + label_w + 30, W - MARGIN - 220
        avail = H - y0 - 150
        row = min(130, avail / len(bars))
        fl = font("regular", int(min(44, row * 0.38)))
        fv = font("bold", int(min(50, row * 0.42)))
        # prices and costs: the lowest is the one to notice (best quote); otherwise the largest
        text = (self.title + " " + " ".join(b["text"] for b in bars)).lower()
        costy = re.search(r"cost|price|quote|\brate|spend|₹|\$|€|£|\brs\b|\binr\b", text)   # not "hrs"
        versus = re.search(r"supplier|vendor|quote|brand|ours|competitor|option|offer", text)
        pick = min if costy and versus else max          # comparing offers: cheapest; a breakdown: biggest
        best = pick(range(len(bars)), key=lambda k: bars[k]["value"])
        y0 += max(0, (avail - row * len(bars)) * 0.35)        # sit the chart in the middle, not at the top
        for k, b in enumerate(bars):
            y = y0 + k * row
            start = 0.4 + k * 0.14
            a = out_cubic(prog(t, start, 0.5))
            g = out_cubic(prog(t, start + 0.1, 1.0))
            lines = _wrap(d, b["label"], fl, label_w, 2)
            ly = y + row * 0.45 - len(lines) * fl.size * 0.6
            for j, line in enumerate(lines):
                d.text((MARGIN + (1 - a) * -30, ly + j * fl.size * 1.15), line, font=fl, fill=mix(self.BG, self.INK, a))
            bw = int((x1 - x0) * abs(b["value"]) / top * g)
            bh = int(row * 0.5)
            by = int(y + row * 0.45 - bh / 2)
            d.rectangle((x0, by, x0 + int(x1 - x0), by + bh), fill=mix(self.BG, self.TRACK, a))
            if bw > 0:
                d.rectangle((x0, by, x0 + bw, by + bh), fill=self.ACC if k == best else self.ACC2)
            if g > 0.02:
                d.text((x0 + bw + 20, by + bh / 2 - fv.size * 0.62), _fmt(b, b["value"] * g), font=fv, fill=self.INK)
        if self.points:
            fp = font("regular", 36)
            a = out_cubic(prog(t, 0.6 + len(bars) * 0.14 + 0.8, 0.5))
            d.text((MARGIN, H - 150 + (1 - a) * 20), " · ".join(self.points)[:120], font=fp, fill=mix(self.BG, self.MUTED, a))

    # — photo / screenshot: shown whole on a card, revealed, then a slow push-in; points beside it
    def _photo(self, im, d, t):
        side = bool(self.points)
        ax0, ay0, ax1, ay1 = (int(W * 0.42), 110, W - MARGIN, H - 150) if side else (MARGIN, 210, W - MARGIN, H - 130)
        aw, ah = ax1 - ax0, ay1 - ay0
        src = self.photo
        z = 1.0 + 0.05 * in_out(prog(t, 0.3, self.dur))          # camera push-in over the whole scene
        base = min(aw / src.width, ah / src.height)
        rw, rh = max(1, int(src.width * base * z)), max(1, int(src.height * base * z))
        if getattr(self, "_cache", (None,))[0] != (rw, rh):
            self._cache = ((rw, rh), src.resize((rw, rh), Image.BILINEAR))
        pic = self._cache[1]
        # the card stays the fitted size; the picture moves inside it (a push-in, not a jump)
        cw, ch = int(src.width * base), int(src.height * base)
        cx0, cy0 = ax0 + (aw - cw) // 2, ay0 + (ah - ch) // 2
        ox, oy = (rw - cw) // 2, (rh - ch) // 2
        a = out_cubic(prog(t, 0.1, 0.7))
        if a > 0:
            lift = int((1 - a) * 60)
            sh = Image.new("RGB", (cw + 60, ch + 60), self.BG)
            ImageDraw.Draw(sh).rectangle((30, 40, cw + 30, ch + 40), fill=mix(self.BG, self.SHADOW, a))
            sh = sh.filter(ImageFilter.GaussianBlur(18)) if not hasattr(self, "_shadow") else self._shadow
            if a >= 1:
                self._shadow = sh
            im.paste(sh, (cx0 - 30, cy0 - 30 + lift))
            frame = pic.crop((ox, oy, ox + cw, oy + ch))
            if a < 1:
                frame = Image.blend(Image.new("RGB", frame.size, self.BG), frame, a)
            im.paste(frame, (cx0, cy0 + lift))
        if side:
            f, size = _fit_font(d, self.title, "bold", 64, ax0 - MARGIN - 60)
            lines = _wrap(d, self.title, f, ax0 - MARGIN - 60, 3)
            a = out_cubic(prog(t, 0.3, 0.6))
            y = 130
            for line in lines:
                d.text((MARGIN - (1 - a) * 40, y), line, font=f, fill=mix(self.BG, self.INK, a))
                y += size * 1.15
            d.rectangle((MARGIN, y + 14, MARGIN + int(out_cubic(prog(t, 0.5, 0.6)) * 140), y + 22), fill=self.ACC)
            self._point_list(im, d, t, MARGIN, y + 60, ax0 - MARGIN - 70, size=38, gap=24, number=False)
        else:
            self._heading(im, d, t)


def render_scene(proj, s, index, total, n_frames, lead_in, spoken, out_mp4, enc, cancelled=lambda: False):
    """Draw every frame of one animated scene and encode it with FFmpeg (frames are piped, not saved)."""
    sc = Scene(proj, s, index, total, n_frames / FPS, lead_in, spoken)
    cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", *enc, "-g", str(FPS * 2), "-r", str(FPS), str(out_mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for f in range(n_frames):
            if cancelled():
                proc.kill()
                return False
            proc.stdin.write(sc.frame(f / FPS).tobytes())
        proc.stdin.close()
    except BrokenPipeError:
        pass
    err = proc.stderr.read().decode("utf-8", "replace")
    if proc.wait() != 0:
        raise RuntimeError("FFmpeg failed (motion scene):\n" + err[-1500:])
    return True


def still(proj, s, index=1, total=1, at=2.5, dur=6.0):
    """One frame, for previews and tests."""
    return Scene(proj, s, index, total, dur, 0.6, dur - 1.5).frame(at)
