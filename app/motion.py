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

from PIL import Image, ImageDraw, ImageFilter

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
    label = (line[:m.start()] + " " + line[m.end():]).strip(" :-–—,.")
    label = re.sub(r"\s{2,}", " ", label)
    decimals = len(m.group("num").split(".")[1]) if "." in m.group("num") else 0
    return {"value": -val if neg else val, "pre": pre, "suf": suf, "label": label or line.strip(),
            "decimals": decimals, "signed": bool(m.group("sign")), "text": line}


def plan(proj, s):
    """Which motion language this scene uses, and its data."""
    points = L.bullets(s.get("notes"), limit=6)
    image = s.get("image") if s.get("image") and (folder(proj["id"]) / s["image"]).exists() else None
    if s["kind"] in ("title", "closing"):
        return {"type": "title", "points": points}
    nums = [n for n in (_number(p) for p in points) if n]
    if image:
        return {"type": "photo", "points": points, "image": image}
    if len(nums) >= 2 and len(nums) >= len(points) - 1:
        return {"type": "bars", "bars": nums[:6], "points": [p for p in points if not _number(p)]}
    if len(nums) == 1:
        return {"type": "counter", "number": nums[0], "points": [p for p in points if p != nums[0]["text"]]}
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


def _fmt(n, v):
    s = f"{abs(v):,.{n['decimals']}f}"
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
        self.logo = _Logo(proj)
        self.small_logo = self.logo.sized(54)
        self.title = (s.get("title") or "").strip()
        self.points = self.p.get("points") or []
        self.when = anchors(self.points, s.get("script"), lead_in, spoken, start=0.9)
        self.bg = self._background()
        if self.p["type"] == "photo":
            with Image.open(folder(proj["id"]) / self.p["image"]) as im:
                self.photo = im.convert("RGB")

    # static background: drawn once
    def _background(self):
        dark = self.p["type"] == "title"
        im = Image.new("RGB", (W, H), NAVY_ if dark else BG)
        d = ImageDraw.Draw(im)
        if dark:
            for k in range(9):      # soft diagonal light, like a lit stage
                d.polygon([(W * 0.45 + k * 90, 0), (W * 0.62 + k * 90, 0), (W * 0.32 + k * 90, H), (W * 0.15 + k * 90, H)],
                          fill=mix(NAVY_, BLUE_, 0.10 + 0.02 * (k % 3)))
            im = im.filter(ImageFilter.GaussianBlur(40))
        else:
            d.rectangle((0, 0, W, 10), fill=NAVY_)
            if self.small_logo:
                im.paste(self.small_logo, (W - MARGIN - self.small_logo.width, H - 54 - 40), self.small_logo)
            f = font("regular", 26)
            d.text((MARGIN, H - 40 - 34), f"{self.index:02d} / {self.total:02d}", font=f, fill=GREY_)
        return im

    def frame(self, t):
        im = self.bg.copy()
        d = ImageDraw.Draw(im)
        getattr(self, "_" + self.p["type"])(im, d, t)
        if self.p["type"] != "title":      # a thin line runs across the top during the scene: the frame never freezes
            d.rectangle((0, 10, int(W * clamp(t / max(self.dur, 0.1))), 16), fill=ORANGE_)
        k = prog(t, self.dur - EXIT, EXIT)          # push-out into the next scene
        if k > 0:
            im = Image.blend(im, self.bg, in_out(k))
        return im

    # — title: kinetic words + drawing accent bar + logo pop
    def _title(self, im, d, t):
        closing = self.s["kind"] == "closing"
        if not hasattr(self, "_big_logo"):
            self._big_logo = self.logo.sized(120)
        logo = self._big_logo
        if logo:
            a = out_back(prog(t, 0.05, 0.6))
            if a > 0.02:
                lw, lh = max(1, int(logo.width * a)), max(1, int(logo.height * a))
                small = logo if (lw, lh) == logo.size else logo.resize((lw, lh), Image.BILINEAR)
                card = Image.new("RGB", (lw + 40, lh + 30), WHITE_)
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
                    d.text((x, y + (1 - p) * 60), word, font=f, fill=mix(NAVY_, WHITE_, p))
                x += d.textlength(word + " ", font=f)
                n += 1
            y += size * 1.12
        bar = out_cubic(prog(t, 0.55 + n * 0.07, 0.7))
        d.rectangle((MARGIN, y + 24, MARGIN + int(bar * 420), y + 34), fill=ORANGE_)
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
                           fill=mix(NAVY_, (205, 218, 236), p))

    # — heading shared by content scenes: wipes in from the left
    def _heading(self, im, d, t, max_w=W - 2 * MARGIN):
        f, size = _fit_font(d, self.title, "bold", 72, max_w)
        p = out_cubic(prog(t, 0.0, 0.55))
        tw = int(d.textlength(self.title, font=f))
        layer = Image.new("RGB", (tw + 10, int(size * 1.35)), BG)
        ImageDraw.Draw(layer).text((0, 0), self.title, font=f, fill=INK)
        vis = int(layer.width * p)
        if vis > 0:
            im.paste(layer.crop((0, 0, vis, layer.height)), (MARGIN, 96))
        d.rectangle((MARGIN, 96 + size * 1.3, MARGIN + int(out_cubic(prog(t, 0.25, 0.6)) * 140), 96 + size * 1.3 + 8),
                    fill=ORANGE_)
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
            d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=BLUE_ if k else ORANGE_)
            if number and pop > 0.6:
                fn = font("bold", 30)
                s = str(k + 1)
                d.text((cx - d.textlength(s, font=fn) / 2, cy - 19), s, font=fn, fill=WHITE_)
            a = out_cubic(p)
            lines = _wrap(d, pt, f, max_w - 90, 2)
            for j, line in enumerate(lines):
                d.text((x + 90 + (1 - a) * 50, y + j * size * 1.2), line, font=f, fill=mix(BG, INK, a))
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
                d.text((MARGIN, y + 40 + j * 80 + (1 - a) * 30), l, font=f, fill=mix(BG, INK, a))
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
        color = ORANGE_ if n["value"] >= 0 else BLUE_
        d.text((MARGIN - 6, y + 10), txt, font=f, fill=mix(BG, color, out_cubic(prog(t, 0.4, 0.3))))
        fl = font("regular", 48)
        a = out_cubic(prog(t, 0.9, 0.5))
        for j, line in enumerate(_wrap(d, n["label"], fl, W * 0.5, 2)):
            d.text((MARGIN, y + 10 + nsize * 1.3 + j * 60 + (1 - a) * 20), line, font=fl, fill=mix(BG, INK, a))
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
        costy = re.search(r"cost|price|quote|rate|spend|₹|\$|€|£|rs\b|inr", (self.title + " " +
                          " ".join(b["text"] for b in bars)).lower())
        pick = min if costy else max
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
                d.text((MARGIN + (1 - a) * -30, ly + j * fl.size * 1.15), line, font=fl, fill=mix(BG, INK, a))
            bw = int((x1 - x0) * abs(b["value"]) / top * g)
            bh = int(row * 0.5)
            by = int(y + row * 0.45 - bh / 2)
            d.rectangle((x0, by, x0 + int(x1 - x0), by + bh), fill=mix(BG, (230, 236, 244), a))
            if bw > 0:
                d.rectangle((x0, by, x0 + bw, by + bh), fill=ORANGE_ if k == best else BLUE_)
            if g > 0.02:
                d.text((x0 + bw + 20, by + bh / 2 - fv.size * 0.62), _fmt(b, b["value"] * g), font=fv, fill=INK)
        if self.points:
            fp = font("regular", 36)
            a = out_cubic(prog(t, 0.6 + len(bars) * 0.14 + 0.8, 0.5))
            d.text((MARGIN, H - 150 + (1 - a) * 20), " · ".join(self.points)[:120], font=fp, fill=mix(BG, GREY_, a))

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
            sh = Image.new("RGB", (cw + 60, ch + 60), BG)
            ImageDraw.Draw(sh).rectangle((30, 40, cw + 30, ch + 40), fill=mix(BG, (170, 182, 200), a))
            sh = sh.filter(ImageFilter.GaussianBlur(18)) if not hasattr(self, "_shadow") else self._shadow
            if a >= 1:
                self._shadow = sh
            im.paste(sh, (cx0 - 30, cy0 - 30 + lift))
            frame = pic.crop((ox, oy, ox + cw, oy + ch))
            if a < 1:
                frame = Image.blend(Image.new("RGB", frame.size, BG), frame, a)
            im.paste(frame, (cx0, cy0 + lift))
        if side:
            f, size = _fit_font(d, self.title, "bold", 64, ax0 - MARGIN - 60)
            lines = _wrap(d, self.title, f, ax0 - MARGIN - 60, 3)
            a = out_cubic(prog(t, 0.3, 0.6))
            y = 130
            for line in lines:
                d.text((MARGIN - (1 - a) * 40, y), line, font=f, fill=mix(BG, INK, a))
                y += size * 1.15
            d.rectangle((MARGIN, y + 14, MARGIN + int(out_cubic(prog(t, 0.5, 0.6)) * 140), y + 22), fill=ORANGE_)
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
