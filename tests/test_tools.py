"""Tools: Video (picture → clip), Image, Audio (voice-over, music, sound effects), Character and World (@Name)."""
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from app import tools, tts  # noqa: E402
from app.ai import images  # noqa: E402
from app.main import app  # noqa: E402
from tests.test_pipeline import _duration  # noqa: E402

HAS_ESPEAK = "espeak" in [e["name"] for e in tts.status() if e["available"]]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "MEDIA", tmp_path / "my_media")      # never touch the real My media
    return app.test_client()


def _png(color="#1f5fa8"):
    buf = io.BytesIO()
    Image.new("RGB", (800, 450), color).save(buf, "PNG")
    buf.seek(0)
    return buf


def test_pages_and_state(client):
    for t in ("video", "image", "audio", "character", "world"):
        r = client.get(f"/tools/{t}")
        assert r.status_code == 200 and f'data-tool="{t}"' in r.get_data(as_text=True)
    assert client.get("/tools/nope").status_code == 404
    st = client.get("/api/tools/state").get_json()
    assert {"cinematic", "photo", "anime"} <= set(st["styles"]) and "corporate" in st["moods"]
    assert set(st["media"]) == {"images", "audio", "videos"}
    assert 'href="/tools/character"' in client.get("/inspirations").get_data(as_text=True)     # in the left menu


def test_characters_and_worlds_fill_in_prompts(client):
    r = client.post("/api/tools/characters", json={"name": "Maya", "description": "woman, 30, red raincoat"})
    maya = r.get_json()
    assert maya["tag"] == "@Maya"
    client.post("/api/tools/worlds", json={"name": "Old City", "description": "narrow stone streets at night"})
    assert tools.expand("@maya walks through @OldCity") == \
        "Maya (woman, 30, red raincoat) walks through Old City (narrow stone streets at night)"
    assert tools.expand_voice_text("Hello @Maya") == "Hello Maya"
    # same tag twice is refused; missing description is refused
    assert client.post("/api/tools/worlds", json={"name": "maya", "description": "x"}).status_code == 400
    assert client.post("/api/tools/characters", json={"name": "Ravi"}).status_code == 400
    # edit keeps the id, delete removes
    client.post("/api/tools/characters", json={"id": maya["id"], "name": "Maya", "description": "woman, 31"})
    assert [c["description"] for c in tools.refs("characters")] == ["woman, 31"]
    client.delete(f"/api/tools/characters/{maya['id']}")
    assert tools.refs("characters") == []


def test_picture_to_clip(client):
    name = client.post("/api/tools/upload", data={"file": (_png(), "photo.png")},
                       content_type="multipart/form-data").get_json()["name"]
    assert client.post("/api/tools/upload", data={"file": (io.BytesIO(b"x"), "a.exe")},
                       content_type="multipart/form-data").status_code == 400
    clip = tools.image_clip(name, "The water is gone", "This winter", "cinematic", 3, "cinematic")
    secs, info = _duration(tools.media_path("videos", clip))
    assert abs(secs - 3) < 0.3 and "1920x1080" in info and "Audio: aac" in info
    listed = client.get("/api/tools/state").get_json()["media"]
    assert listed["videos"][0]["name"] == clip and listed["images"][0]["name"] == name
    assert client.get(f"/media/videos/{clip}").status_code == 200
    assert client.get("/media/videos/..%2Fsecret").status_code == 404
    assert client.delete(f"/api/tools/media/videos/{clip}").status_code == 200
    assert client.post("/api/tools/clip", json={"image": "missing.png"}).status_code == 400


def test_music_and_sound_effects(client):
    r = client.post("/api/tools/music", json={"mood": "calm", "seconds": 8}).get_json()
    secs, _ = _duration(tools.media_path("audio", r["name"]))
    assert abs(secs - 8) < 0.3
    assert client.post("/api/tools/music", json={"mood": "nope"}).status_code == 400
    r = client.post("/api/tools/sfx/whoosh").get_json()
    assert client.get(r["url"]).status_code == 200


@pytest.mark.skipif(not HAS_ESPEAK, reason="needs eSpeak NG")
def test_voice_over_reads_names(client):
    client.post("/api/tools/characters", json={"name": "Maya", "description": "woman"})
    r = client.post("/api/tools/voice", json={"text": "Hello, I am @Maya.", "engine": "espeak", "voice": "en-us",
                                              "lang": "en-us"}).get_json()
    secs, _ = _duration(tools.media_path("audio", r["name"]))
    assert secs > 0.5
    assert client.post("/api/tools/voice", json={"text": " "}).status_code == 400


def test_images_need_the_picture_creator(client, monkeypatch):
    monkeypatch.setattr(images, "status", lambda: {"available": False, "info": "run install_once.bat images"})
    r = client.post("/api/tools/image", json={"prompt": "a red car"})
    assert r.status_code == 400 and "install_once.bat images" in r.get_json()["error"]


def test_images_use_style_and_characters(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(images, "status", lambda: {"available": True, "info": "ok"})

    def gen(prompts, aspect="16:9", seed=None, steps=4, progress=lambda d, t: None):
        seen.update(prompts=prompts, aspect=aspect)
        return [_png().getvalue() for _ in prompts]
    monkeypatch.setattr(images, "generate", gen)
    tools.save_ref("characters", "Maya", "red raincoat")
    r = tools.create_images("@Maya in the rain", "anime", "9:16", 2)
    assert len(r["images"]) == 2 and seen["aspect"] == "9:16"
    assert seen["prompts"][0].startswith("Maya (red raincoat) in the rain") and "anime" in seen["prompts"][0]
