"""Inspirations: 32 example videos in 8 categories, thumbnails, "use this example", AI adaptation."""
import io
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from app import project as P, inspirations as I, motion  # noqa: E402
from app.ai import llm  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client():
    c = app.test_client()
    c.made = []
    yield c
    for pid in c.made:
        P.delete(pid)


def test_32_examples_in_8_labelled_categories(client):
    cat = client.get("/api/inspirations").get_json()
    assert len(cat["examples"]) == 32 and len(cat["categories"]) == 8
    assert all(c["count"] == 4 for c in cat["categories"])
    labels = {c["label"] for c in cat["categories"]}
    assert {"Trending Templates", "Short Film", "Music Video", "UGC Ads", "Product Ads", "Film Trailer",
            "Social Content", "Explainer"} == labels
    for e in cat["examples"]:
        assert e["category_label"] in labels and e["format"] in ("16:9", "9:16", "1:1") and e["look"] in motion.LOOKS
    assert set(cat["looks"]) == {"corporate", "cinematic", "bold", "warm"}
    page = client.get("/inspirations").get_data(as_text=True)
    assert "32 example videos" in page and 'href="/inspirations"' in client.get("/").get_data(as_text=True)


def test_every_thumbnail_draws(client):
    for e in I.EXAMPLES:
        r = client.get(f"/inspirations/thumb/{e['id']}.jpg")
        assert r.status_code == 200 and r.mimetype == "image/jpeg"
        im = Image.open(io.BytesIO(r.data))
        assert im.size == (640, 360) and len(im.resize((32, 18)).getcolors(4096) or []) > 3
    assert client.get("/inspirations/thumb/nope.jpg").status_code == 404


def test_use_example_unchanged(client, monkeypatch):
    monkeypatch.setattr(llm, "status", lambda: {"available": False, "info": "off"})
    r = client.post("/api/inspirations/epic-trailer/use", json={"name": "My trailer"}).get_json()
    client.made.append(r["project"])
    assert r["job"] is False
    p = P.load(r["project"])
    assert p["name"] == "My trailer" and p["look"] == "cinematic" and p["motion"] == "motion"
    assert p["video_type"] == "youtube" and p["music"]["library"] == "cinematic" and p["intro"] is False
    content = [s for s in p["slides"] if s["kind"] == "content"]
    assert len(content) == 4 and content[0]["script"] and content[0]["image_prompt"]
    assert p["slides"][0]["title"] == "This winter" and p["slides"][-1]["title"] == "Kingdom of Sand"
    # a topic without the AI: kept as it is, with a note
    r = client.post("/api/inspirations/tip-15s/use", json={"topic": "sleep better"}).get_json()
    client.made.append(r["project"])
    assert r["job"] is False and "not running" in r["note"]


def test_music_video_has_no_voice_and_louder_music(client):
    r = client.post("/api/inspirations/city-beat/use", json={}).get_json()
    client.made.append(r["project"])
    p = P.load(r["project"])
    assert all(not s["script"] for s in p["slides"]) and p["music"]["volume"] == 0.55 and p["captions"] is False
    assert all(motion.plan(p, s)["type"] in ("statement", "title") for s in p["slides"])


def test_ai_adapts_example_to_my_topic(client, monkeypatch):
    prompts = []

    def fake(path, payload=None, timeout=5):
        if path == "/api/tags":
            return {"models": [{"name": llm.MODEL}]}
        prompts.append(payload["prompt"])
        return {"response": json.dumps({
            "open": ["The Bakery Wars", "This Diwali"], "close": ["Sweet Street", "Opening Friday"],
            "scenes": [{"title": f"Scene {k}", "points": [], "line": f"Line {k}.", "image": f"bakery shot {k}"}
                       for k in range(1, 5)]})}
    monkeypatch.setattr(llm, "_request", fake)
    r = client.post("/api/inspirations/epic-trailer/use", json={"topic": "a bakery opening for Diwali"}).get_json()
    client.made.append(r["project"])
    assert r["job"] is True
    for _ in range(100):
        j = client.get(f"/api/projects/{r['project']}/job").get_json()["ai"]
        if j["state"] != "running":
            break
        time.sleep(0.1)
    assert j["state"] == "done", j
    assert "a bakery opening for Diwali" in prompts[0] and "Keep exactly 4 scenes" in prompts[0]
    p = P.load(r["project"])
    assert [s["title"] for s in p["slides"]] == ["The Bakery Wars", "Scene 1", "Scene 2", "Scene 3", "Scene 4", "Sweet Street"]
    assert p["slides"][1]["script"] == "Line 1." and p["slides"][1]["image_prompt"] == "bakery shot 1"
    assert p["look"] == "cinematic"


def test_film_and_social_videos_are_not_branded():
    proj = {"id": "x", "look": "cinematic", "logo": None}
    sc = motion.Scene(proj, {"kind": "content", "title": "Run", "notes": "", "script": ""}, 1, 3, 4, 0.6, 0)
    assert sc.branded is False and sc.p["type"] == "statement"
    assert motion.Scene(proj | {"look": "corporate"}, {"kind": "content", "title": "Run", "notes": "", "script": ""},
                        1, 3, 4, 0.6, 0).branded is True


def test_rupees_use_indian_grouping():
    n = motion._number("Crew: ₹ 9,00,000")
    assert motion._fmt(n, n["value"]) == "₹9,00,000"
    n = motion._number("Budget $1,250,000")
    assert motion._fmt(n, n["value"]) == "$1,250,000"


def test_preview_video_plays_with_music(client, tmp_path):
    from tests.test_pipeline import _duration
    r = client.get("/inspirations/preview/spec-compare.mp4")
    assert r.status_code == 200 and r.mimetype == "video/mp4"
    f = tmp_path / "p.mp4"
    f.write_bytes(r.get_data())
    secs, info = _duration(f)
    want = (1 + min(3, len(I.BY_ID["spec-compare"]["scenes"]))) * I.PREVIEW_SCENE      # opening + up to 3 scenes
    assert abs(secs - want) < 0.5 and "640x360" in info and "Audio: aac" in info
    assert client.get("/inspirations/preview/nope.mp4").status_code == 404
    assert all(e["preview"].endswith(f"{e['id']}.mp4") for e in client.get("/api/inspirations").get_json()["examples"])


def test_hours_are_not_rupees():
    proj = {"id": "x", "look": "corporate"}
    s = {"kind": "content", "title": "Battery life", "notes": "Ours: 40 hrs\nBrand A: 28 hrs\nBrand B: 22 hrs",
         "script": "", "image": None}
    im = motion.still(proj, s, 1, 3, at=4.5, dur=6)
    orange = motion.ORANGE_
    ys = sorted({y for y in range(250, 900, 3) if im.getpixel((1000, y)) in (orange, motion.BLUE_)})
    first_orange = min(y for y in ys if im.getpixel((1000, y)) == orange)
    assert first_orange == ys[0]          # the longest battery life (Ours, first bar) is highlighted, not the shortest
