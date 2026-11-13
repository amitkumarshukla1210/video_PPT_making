"""Music beds and sound effects composed by the app itself (numpy synthesis), so they are free of
copyright and licence questions — safe for monetised YouTube. Files are made once and cached in
models/library/. Every bed loops seamlessly; the video mixer lowers it under the voice."""
import wave

import numpy as np

from ..config import MODELS_DIR

SR = 48000
DIR = MODELS_DIR / "library"
VERSION = 1   # bump when the sound design changes, to rebuild cached files

MOODS = {
    "corporate": {"label": "Corporate — bright and positive", "bpm": 100, "templates": ["product", "explainer"]},
    "calm": {"label": "Calm — warm piano and pads", "bpm": 72, "templates": ["inspiration"]},
    "cinematic": {"label": "Cinematic — drums and big strings", "bpm": 84, "templates": ["trailer"]},
    "documentary": {"label": "Documentary — soft strings", "bpm": 64, "templates": ["documentary"]},
    "tech": {"label": "Tech — modern pulsing synth", "bpm": 118, "templates": []},
}
SFX = {
    "whoosh": "Whoosh (slide change)",
    "rise": "Rising swell (before a reveal)",
    "impact": "Deep impact (title hit)",
    "chime": "Soft chime (new point)",
    "click": "Click (UI)",
}

# chord progressions as MIDI notes (root position triads / sevenths)
PROGRESSIONS = {
    "corporate": [[48, 52, 55, 60], [43, 50, 55, 59], [45, 52, 57, 60], [41, 48, 53, 57]],      # C G Am F
    "calm": [[41, 48, 52, 57], [45, 52, 55, 60], [38, 50, 53, 57], [46, 50, 53, 57]],           # Fmaj7 Am7 Dm7 Bbmaj7
    "cinematic": [[38, 50, 53, 57], [34, 46, 50, 53], [41, 48, 53, 57], [36, 48, 52, 55]],      # Dm Bb F C
    "documentary": [[45, 52, 57, 60], [41, 48, 53, 57], [36, 48, 52, 55], [43, 50, 55, 59]],    # Am F C G
    "tech": [[40, 52, 55, 59], [36, 48, 52, 55], [43, 50, 55, 59], [38, 50, 54, 57]],           # Em C G D
}


def _hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _t(dur):
    return np.arange(int(dur * SR)) / SR


def _adsr(n, a=0.01, d=0.1, s=0.7, r=0.2):
    env = np.full(n, s, dtype=np.float32)
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    a, d = min(a, n), min(d, max(0, n - a))
    env[:a] = np.linspace(0, 1, a, endpoint=False)
    env[a:a + d] = np.linspace(1, s, d, endpoint=False)
    if r:
        env[-min(r, n):] *= np.linspace(1, 0, min(r, n))
    return env


def _pad(m, dur):
    t = _t(dur)
    f = _hz(m)
    x = sum(np.sin(2 * np.pi * f * k * (1 + dt) * t) / k ** 1.3
            for k in (1, 2, 3, 4) for dt in (-0.003, 0.003))
    return (x * _adsr(len(t), a=min(1.2, dur / 3), d=0.3, s=0.8, r=min(1.5, dur / 3)) * 0.12).astype(np.float32)


def _piano(m, dur, vel=1.0):
    t = _t(dur)
    f = _hz(m)
    x = sum(np.sin(2 * np.pi * f * k * t) * (0.6 ** (k - 1)) * np.exp(-t * (1.2 + k * 0.8)) for k in range(1, 7))
    return (x * _adsr(len(t), a=0.004, d=0.05, s=1.0, r=0.15) * 0.22 * vel).astype(np.float32)


def _pluck(m, dur, vel=1.0):
    t = _t(dur)
    f = _hz(m)
    x = sum(np.sign(np.sin(2 * np.pi * f * k * t)) * (0.5 ** k) for k in (1, 2)) * np.exp(-t * 9)
    return (x * 0.10 * vel).astype(np.float32)


def _bass(m, dur):
    t = _t(dur)
    f = _hz(m - 12)
    x = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)
    return (x * _adsr(len(t), a=0.01, d=0.2, s=0.6, r=0.1) * 0.22).astype(np.float32)


def _kick(level=0.5):
    t = _t(0.35)
    f = 45 + 80 * np.exp(-t * 18)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) * level).astype(np.float32)


def _hat(rng, level=0.06):
    n = rng.standard_normal(int(0.05 * SR)).astype(np.float32)
    n = np.diff(n, prepend=0)          # crude high-pass
    return n * np.exp(-_t(0.05) * 70) * level


def _timpani(level=0.45):
    t = _t(1.6)
    x = np.sin(2 * np.pi * 73 * t) + 0.4 * np.sin(2 * np.pi * 110 * t)
    return (x * np.exp(-t * 3) * level).astype(np.float32)


def _add(buf, x, at):
    i = int(at * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(x))
    buf[i:j] += x[: j - i]


def _reverb(x, mix=0.25):
    out = x.copy()
    for ms, g in ((47, 0.35), (83, 0.28), (131, 0.22), (197, 0.16), (271, 0.11)):
        d = int(ms / 1000 * SR)
        out[d:] += x[:-d] * g * mix * 3
    return out


def compose(mood, bars=16, seed=7):
    """Return a seamless stereo loop (float32 array, shape (n, 2)) for `mood`."""
    spec = MOODS[mood]
    beat = 60 / spec["bpm"]
    bar = beat * 4
    length = bars * bar
    tail = 3.0
    L = np.zeros(int((length + tail) * SR), dtype=np.float32)
    R = np.zeros_like(L)
    rng = np.random.default_rng(seed)
    prog = PROGRESSIONS[mood]
    for b in range(bars):
        chord = prog[b % len(prog)]
        t0 = b * bar
        pad = sum(_pad(m, bar + 0.6) for m in chord[1:])
        _add(L, pad, t0)
        _add(R, pad, t0 + 0.012)                    # small offset = width
        if mood in ("corporate", "tech", "cinematic", "calm"):
            bs = _bass(chord[0], bar if mood != "tech" else beat * 2)
            _add(L, bs, t0)
            _add(R, bs, t0)
            if mood == "tech":
                _add(L, bs, t0 + 2 * beat)
                _add(R, bs, t0 + 2 * beat)
        if mood == "corporate":
            for k in range(8):                       # 8th-note arpeggio
                m = chord[1:][k % 3] + 12
                x = _pluck(m, beat, 0.8 + 0.2 * (k % 2 == 0))
                _add(L if k % 2 else R, x, t0 + k * beat / 2)
            for k in range(4):
                _add(L, _kick(0.35), t0 + k * beat)
                _add(R, _kick(0.35), t0 + k * beat)
                h = _hat(rng)
                _add(L, h, t0 + k * beat + beat / 2)
                _add(R, h * 0.8, t0 + k * beat + beat / 2)
        elif mood == "tech":
            for k in range(16):                      # 16th-note arpeggio
                m = chord[1:][k % 3] + 12 + (12 if k % 8 == 7 else 0)
                x = _pluck(m, beat / 2, 0.7)
                _add(L if k % 2 else R, x, t0 + k * beat / 4)
            for k in range(4):
                _add(L, _kick(0.4), t0 + k * beat)
                _add(R, _kick(0.4), t0 + k * beat)
            for k in range(8):
                h = _hat(rng, 0.05)
                _add(L, h, t0 + k * beat / 2 + beat / 4)
                _add(R, h, t0 + k * beat / 2 + beat / 4)
        elif mood == "calm":
            for k, m in enumerate([chord[1], chord[2], chord[3], chord[2]]):
                x = _piano(m + 12, beat * 2.5, 0.9 if k == 0 else 0.7)
                _add(L, x, t0 + k * beat)
                _add(R, x * 0.9, t0 + k * beat + 0.006)
        elif mood == "documentary":
            if b % 2 == 0:
                x = _piano(chord[3] + 12, bar * 1.5, 0.6)
                _add(L, x, t0 + beat)
                _add(R, x, t0 + beat + 0.008)
        elif mood == "cinematic":
            _add(L, _timpani(), t0)
            _add(R, _timpani(), t0)
            if b % 4 == 3:
                for k in range(4):
                    _add(L, _timpani(0.25), t0 + 2 * beat + k * beat / 2)
                    _add(R, _timpani(0.25), t0 + 2 * beat + k * beat / 2)
            drone = _pad(chord[0] - 12, bar + 0.6) * 1.4
            _add(L, drone, t0)
            _add(R, drone, t0)
    L, R = _reverb(L), _reverb(R)
    n = int(length * SR)
    t = int(tail * SR)
    L[:t] += L[n:n + t]                              # wrap the tail: seamless loop
    R[:t] += R[n:n + t]
    out = np.stack([L[:n], R[:n]], axis=1)
    return out / (np.max(np.abs(out)) + 1e-9) * 0.7


def sfx(name):
    """Return a mono float32 sound effect."""
    rng = np.random.default_rng(3)
    if name == "whoosh":
        d = 0.7
        t = _t(d)
        noise = rng.standard_normal(len(t)).astype(np.float32)
        # moving band-pass by mixing two crude low-pass states driven by a sweep
        y = np.zeros_like(noise)
        a = 0.0
        cutoff = 0.02 + 0.25 * np.sin(np.pi * t / d) ** 2
        for i in range(len(noise)):
            a += cutoff[i] * (noise[i] - a)
            y[i] = a
        env = np.sin(np.pi * t / d) ** 1.5
        x = y * env
    elif name == "rise":
        d = 2.0
        t = _t(d)
        f = 180 * 2 ** (t / d * 2)
        x = (np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.3 * rng.standard_normal(len(t))) * (t / d) ** 2
    elif name == "impact":
        d = 1.8
        t = _t(d)
        f = 40 + 60 * np.exp(-t * 10)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.5) + 0.4 * rng.standard_normal(len(t)) * np.exp(-t * 25)
    elif name == "chime":
        d = 1.6
        t = _t(d)
        x = sum(np.sin(2 * np.pi * 1046.5 * k * t) * np.exp(-t * (2 + k)) / k for k in (1, 2.76, 5.4))
    elif name == "click":
        d = 0.06
        t = _t(d)
        x = np.sin(2 * np.pi * 2200 * t) * np.exp(-t * 120)
    else:
        raise KeyError(name)
    x = x.astype(np.float32)
    return x / (np.max(np.abs(x)) + 1e-9) * 0.8


def _write(path, data):
    data = np.clip(data, -1, 1)
    pcm = (data * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1 if data.ndim == 1 else data.shape[1])
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def music_file(mood):
    if mood not in MOODS:
        raise KeyError(mood)
    DIR.mkdir(parents=True, exist_ok=True)
    path = DIR / f"music_{mood}_v{VERSION}.wav"
    if not path.exists():
        tmp = path.with_suffix(".part")
        _write(tmp, np.concatenate([compose(mood)] * 2))        # about 1–1.5 minutes, loops on
        tmp.replace(path)
    return path


def sfx_file(name):
    if name not in SFX:
        raise KeyError(name)
    DIR.mkdir(parents=True, exist_ok=True)
    path = DIR / f"sfx_{name}_v{VERSION}.wav"
    if not path.exists():
        tmp = path.with_suffix(".part")
        _write(tmp, sfx(name))
        tmp.replace(path)
    return path


def catalogue():
    return {"music": [{"id": k, **v} for k, v in MOODS.items()],
            "sfx": [{"id": k, "label": v} for k, v in SFX.items()]}
