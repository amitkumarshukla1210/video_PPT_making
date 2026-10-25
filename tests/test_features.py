"""Presenter-in-corner, logo intro/outro, social exports, 15-minute limit and the voice-clone plumbing."""
import json
import subprocess
import sys
import textwrap
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app import media, project as P, tts                       # noqa: E402
from app.config import MAX_VIDEO_SECONDS                        # noqa: E402
from app.ffmpeg_utils import ffmpeg_bin                         # noqa: E402
from app.script_writer import draft_all                         # noqa: E402
from app.tts import clone_engine                                # noqa: E402
from app.video import render_video, export, estimate            # noqa: E402
from tests.test_pipeline import _fake_screenshot, _duration     # noqa: E402


@pytest.fixture
def proj():
    p = P.new_project("Feature Test")
    p["voice"] = {"engine": tts.default_engine(), "voice": "", "lang": "en-us", "speed": 1.0}
    yield p
    P.delete(p["id"])


def _phone_clip(path, secs=3):
    subprocess.run([ffmpeg_bin(), "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=720x1280:r=30:d={secs}",
                    "-f", "lavfi", "-i", f"sine=f=300:d={secs}", "-shortest", "-c:v", "libvpx", "-c:a", "libopus",
                    str(path)], check=True)


def test_presenter_clip_photo_intro_and_exports(proj):
    base = P.folder(proj["id"])
    _fake_screenshot(base / "uploads/a.png", "Dashboard", "#152238")
    P.add_content_slide(proj, "Commodity impact", "Steel up 8%\nForex adds 2.1%", "uploads/a.png")
    s = P.add_content_slide(proj, "My explanation", "I explain this myself", "uploads/a.png")
    _phone_clip(base / "uploads/raw.webm")            # browser recordings have no duration in the header
    s["clip_seconds"] = media.normalize_clip(base / "uploads/raw.webm", base / "uploads/clip.mp4")
    s["clip"] = "uploads/clip.mp4"
    assert 2.5 < s["clip_seconds"] < 3.5
    im = Image.new("RGB", (600, 900), "#9a7b5c")
    ImageDraw.Draw(im).ellipse((150, 200, 450, 550), fill="#e8c4a0")
    im.save(base / "uploads/me.jpg")
    media.normalize_photo(base / "uploads/me.jpg", base / "uploads/photo.jpg")
    proj["pip"] = {"enabled": True, "photo": "uploads/photo.jpg", "position": "br", "shape": "circle", "size": "m"}
    draft_all(proj)

    r = render_video(proj)
    dur, info = _duration(r["video"])
    assert abs(dur - r["seconds"]) < 0.5
    timeline = json.loads((base / "out/timeline.json").read_text())
    assert len(timeline) == 4 and timeline[0]["start"] == 3.0          # after the 3 s logo intro
    # the recording's own sound is used on its slide
    assert abs((timeline[2]["end"] - timeline[2]["start"]) - (s["clip_seconds"] + 1.5)) < 0.2

    for preset, size in (("reels", "1080x1920"), ("square", "1080x1080")):
        e = export(proj, preset)
        assert size in _duration(e["file"])[1]
    short = export(proj, "reels", 3, 3, burn_subs=True)
    assert abs(short["seconds"] - (timeline[2]["end"] - timeline[2]["start"])) < 0.1


def test_fifteen_minute_limit(proj):
    P.add_content_slide(proj, "Very long", "x")
    proj["slides"][1]["script"] = "word " * int(MAX_VIDEO_SECONDS * 2.4 * 1.3)
    est = estimate(proj)
    assert est["over_limit"] and est["video_seconds"] > MAX_VIDEO_SECONDS
    with pytest.raises(RuntimeError, match="limit is 15 minutes"):
        render_video(proj)


def test_voice_sample_too_short_is_rejected(tmp_path):
    src = tmp_path / "short.wav"
    subprocess.run([ffmpeg_bin(), "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=220:d=2", str(src)], check=True)
    with pytest.raises(ValueError, match="10–30 seconds"):
        media.normalize_voice_sample(src, tmp_path / "out.wav")


def test_clone_engine_batch_plumbing(tmp_path, monkeypatch):
    """Runs the real batch / progress / post-processing code with a stand-in worker
    (the real Chatterbox model cannot be downloaded in CI)."""
    fake = tmp_path / "fake_worker.py"
    fake.write_text(textwrap.dedent('''
        import json, sys, wave, math, struct
        job = json.load(open(sys.argv[1], encoding="utf-8"))
        assert job["ref"].endswith("ref.wav") and job["lang"] == "hi"
        for n, it in enumerate(job["items"]):
            with wave.open(it["out"], "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
                w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 10))) for i in range(24000)))
            print(f"PROGRESS {n + 1} {len(job['items'])}", flush=True)
    '''))
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"x")
    monkeypatch.setattr(clone_engine, "WORKER", fake)
    monkeypatch.setattr(clone_engine, "_python", lambda: sys.executable)
    seen = []
    outs = [tmp_path / "a.wav", tmp_path / "b.wav"]
    durs = tts.synthesize_many("clone", [("नमस्ते", outs[0]), ("Second slide.", outs[1])], "hi", "hi", 1.25,
                               ref=str(ref), progress=lambda d, t: seen.append((d, t)))
    assert seen == [(1, 2), (2, 2)]
    assert all(abs(d - 0.8) < 0.1 for d in durs)                 # 1 s of audio sped up 1.25x
    with wave.open(str(outs[0])) as w:
        assert w.getframerate() == 48000
