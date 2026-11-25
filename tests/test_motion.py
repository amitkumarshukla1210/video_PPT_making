"""Motion graphics scenes: reading numbers, choosing the motion per scene, narration-anchored reveals,
frames that really move, and cuts on the music's beat."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import ImageChops  # noqa: E402

from app import project as P, tts, motion, maker  # noqa: E402
from app.main import app  # noqa: E402
from app.video import render_video, estimate, _beat_frames  # noqa: E402
from app.config import FPS  # noqa: E402
from tests.test_pipeline import _fake_screenshot, _duration  # noqa: E402

HAS_ESPEAK = "espeak" in [e["name"] for e in tts.status() if e["available"]]


@pytest.fixture
def proj():
    p = P.new_project("Motion test")
    p["voice"] = {"engine": "espeak", "voice": "en-us", "lang": "en-us", "speed": 1.0}
    yield p
    P.delete(p["id"])


@pytest.mark.parametrize("line, shown, label", [
    ("Supplier A: ₹ 1,250", "₹1,250", "Supplier A"),
    ("Machining time down to 18 minutes", "18 minutes", "Machining time down to"),
    ("BOM cost -12.5%", "−12.5%", "BOM cost"),
    ("$3.2 mn saved", "$3.2 mn", "saved"),
    ("Lead time 4 weeks", "4 weeks", "Lead time"),
])
def test_numbers_are_read_with_currency_and_units(line, shown, label):
    n = motion._number(line)
    assert motion._fmt(n, n["value"]) == shown and n["label"] == label


@pytest.mark.parametrize("line", ["Act before Q4 orders", "FY2024 savings", "Plan for 2025", "ISO9001 audit"])
def test_codes_and_years_are_not_numbers(line):
    assert motion._number(line) is None


def test_each_scene_gets_its_own_motion(proj):
    base = P.folder(proj["id"])
    _fake_screenshot(base / "uploads/a.png", "Dashboard", "#1f5fa8")
    one = P.add_content_slide(proj, "Steel", "Steel up 8% this quarter\nForex adds pressure")
    bars = P.add_content_slide(proj, "Quotes", "Supplier A: ₹ 1,250\nSupplier B: ₹ 1,120\nSupplier C: ₹ 1,310")
    pts = P.add_content_slide(proj, "Changes", "Die-cast housing\nFewer machined faces")
    pic = P.add_content_slide(proj, "Dashboard", "Live prices", "uploads/a.png")
    kinds = {s["id"]: motion.plan(proj, s)["type"] for s in proj["slides"]}
    assert kinds[proj["slides"][0]["id"]] == "title" and kinds[proj["slides"][-1]["id"]] == "title"
    assert [kinds[s["id"]] for s in (one, bars, pts, pic)] == ["counter", "bars", "points", "photo"]
    # every scene really moves: early and late frames differ, and none is blank
    for i, s in enumerate(proj["slides"]):
        a = motion.still(proj, s, i + 1, len(proj["slides"]), at=0.3, dur=6)
        b = motion.still(proj, s, i + 1, len(proj["slides"]), at=4.0, dur=6)
        assert a.size == (1920, 1080)
        assert ImageChops.difference(a, b).getbbox(), f"scene {i} does not move"
        assert len(b.resize((64, 36)).getcolors(4096) or []) > 3, f"scene {i} looks empty"


def test_cheapest_quote_is_highlighted(proj):
    s = P.add_content_slide(proj, "Supplier quotes", "Supplier A: ₹ 1,250\nSupplier B: ₹ 1,120\nSupplier C: ₹ 1,310")
    im = motion.still(proj, s, 2, 3, at=4.5, dur=6)
    orange = motion.ORANGE_
    rows = [y for y in range(300, 900, 4) if im.getpixel((1000, y)) == orange]
    assert rows, "no orange bar"
    # Supplier B is the second of three bars: its row sits in the middle of the chart
    ys = sorted({y for y in range(300, 900, 4) if im.getpixel((1000, y)) in (orange, motion.BLUE_)})
    assert ys[0] < min(rows) and max(rows) < ys[-1]


def test_points_appear_when_the_voice_says_them():
    script = "First we look at the price. Then the die-cast housing saves time. Finally fewer machined faces."
    t = motion.anchors(["Die-cast housing", "Fewer machined faces"], script, 0.6, 8.0)
    words = script.split()
    assert abs(t[0] - (0.6 + words.index("die-cast") / len(words) * 8.0 - 0.25)) < 0.01
    assert t[1] > t[0] + 1.0
    # no match: spread evenly, in order
    t2 = motion.anchors(["Alpha", "Beta", "Gamma"], "nothing matches here", 0.6, 6.0)
    assert t2 == sorted(t2) and t2[0] >= 0.35


@pytest.mark.skipif(not HAS_ESPEAK, reason="needs eSpeak NG")
def test_motion_video_cuts_on_the_beat(proj):
    s = P.add_content_slide(proj, "Quotes", "Supplier A: ₹ 1,250\nSupplier B: ₹ 1,120")
    s["script"] = "Supplier B is cheaper."
    for x in proj["slides"]:
        x["script"] = x["script"] or "Short line."
    proj = maker.prepare_video(proj, "youtube", "corporate", captions=False, motion="motion")
    beat = _beat_frames(proj)
    assert beat == round(60 / 100 * FPS)                      # corporate music: 100 bpm
    assert estimate(proj)["render_seconds"] > estimate(proj | {"motion": "classic"})["render_seconds"]
    r = render_video(proj)
    secs, info = _duration(r["video"])
    assert "1920x1080" in info and abs(secs - r["seconds"]) < 0.5
    tl = json.loads((P.folder(proj["id"]) / "out/timeline.json").read_text())
    for e in tl:
        frames = round((e["end"] - e["start"]) * FPS)
        assert frames % beat == 0, e
    assert _beat_frames(proj | {"motion": "classic"}) is None


def test_motion_setting_is_saved(proj):
    assert P.load(proj["id"])["motion"] == "classic"           # old projects keep their look
    c = app.test_client()
    assert c.put(f"/api/projects/{proj['id']}", json={"motion": "motion"}).get_json()["motion"] == "motion"
    assert c.put(f"/api/projects/{proj['id']}", json={"motion": "fancy"}).get_json()["motion"] == "motion"
    assert 'name="motion" value="motion" checked' in c.get("/make").get_data(as_text=True)
    assert 'id="motion"' in c.get("/").get_data(as_text=True)
