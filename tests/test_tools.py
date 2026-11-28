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
    clip = tools.image_clip(name, "The water is gone", "This winter", "cinematic", 3, "cinematic", fx="glitch")
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

    def gen(prompts, aspect="16:9", seed=None, steps=None, progress=lambda d, t: None, quality=None):
        seen.update(prompts=prompts, aspect=aspect, quality=quality)
        return [_png().getvalue() for _ in prompts]
    monkeypatch.setattr(images, "generate", gen)
    tools.save_ref("characters", "Maya", "red raincoat")
    r = tools.create_images("@Maya in the rain", "anime", "9:16", 2, quality="fast")
    assert len(r["images"]) == 2 and seen["aspect"] == "9:16" and seen["quality"] == "fast"
    assert len(seen["prompts"]) == 1                    # drawn and saved one at a time
    assert seen["prompts"][0].startswith("Maya (red raincoat) in the rain") and "anime" in seen["prompts"][0]


def test_picture_worker_works_with_transformers_5(monkeypatch):
    """transformers 5 removed CLIPFeatureExtractor; the worker maps it to CLIPImageProcessor before loading."""
    import types
    from app.ai import image_worker
    fake = types.ModuleType("transformers")
    fake.CLIPImageProcessor = type("CLIPImageProcessor", (), {})
    monkeypatch.setitem(sys.modules, "transformers", fake)
    image_worker.compat()
    assert fake.CLIPFeatureExtractor is fake.CLIPImageProcessor
    assert "corporate" not in image_worker.STYLE                 # films are not forced into a corporate look
    req = (Path(__file__).resolve().parent.parent / "requirements-image.txt").read_text()
    assert "transformers>=4.45,<5" in req


def test_tools_follow_the_film_order(client):
    html = client.get("/tools").get_data(as_text=True)
    assert 'data-tool="character"' in html                         # Tools opens on step 1
    order = [html.index(f'data-t="{t}"') for t in ("character", "image", "world", "audio", "video")]
    assert order == sorted(order)
    side = [html.index(f'href="/tools/{t}"') for t in ("character", "image", "world", "audio", "video")]
    assert side == sorted(side)


def test_busy_tool_answers_in_plain_json(client, monkeypatch):
    from app import jobs
    monkeypatch.setattr(jobs, "status", lambda key: {"state": "running"})
    monkeypatch.setattr(images, "status", lambda: {"available": True, "info": "ok"})
    r = client.post("/api/tools/image", json={"prompt": "a cat"})
    assert r.status_code == 409 and r.is_json and "still working" in r.get_json()["error"]


def _fake_images(monkeypatch):
    monkeypatch.setattr(images, "status", lambda: {"available": True, "info": "ok"})
    monkeypatch.setattr(images, "warm", lambda: True)
    monkeypatch.setattr(images, "generate", lambda prompts, aspect="16:9", **kw: [_png().getvalue() for _ in prompts])


def test_pictures_are_named_and_tagged_after_their_characters(client, monkeypatch):
    _fake_images(monkeypatch)
    sh = tools.save_ref("characters", "Shurpanakha", "glamorous woman, black outfit")
    tools.save_ref("characters", "Ram", "prince with a bow")
    tools.save_ref("worlds", "Panchavati", "forest hermitage")
    r = tools.create_images("@shurpanakha meets @Ram at @Panchavati", "cinematic", "16:9", 2)
    assert all(n.startswith("Shurpanakha-Ram-Panchavati_") for n in r["images"])
    assert r["tags"] == ["@Shurpanakha", "@Ram", "@Panchavati"]
    plain = tools.create_images("a quiet river", "none", "16:9", 1)["images"][0]
    assert plain.startswith("img_")
    st = client.get("/api/tools/state").get_json()
    pics = {f["name"]: f for f in st["media"]["images"]}
    assert pics[r["images"][0]]["tags"] == ["@Shurpanakha", "@Ram", "@Panchavati"]
    assert "meets" in pics[r["images"][0]]["prompt"] and pics[plain]["tags"] == []
    assert {c["tag"]: c["pictures"] for c in st["characters"]} == {"@Shurpanakha": 2, "@Ram": 2}
    # tag an older picture by hand, make it the portrait, rename the character: the pictures follow
    assert client.put(f"/api/tools/media/images/{plain}/tags", json={"tags": ["@shurpanakha"]}).get_json()["tags"] == ["@Shurpanakha"]
    assert client.post(f"/api/tools/characters/{sh['id']}/portrait", json={"image": plain}).status_code == 200
    assert tools.refs("characters")[0]["image"] == plain
    client.post("/api/tools/characters", json={"id": sh["id"], "name": "Surpanakha", "description": "x"})
    assert tools.picture_info(plain)["tags"] == ["@Surpanakha"]
    # deleting a picture forgets its tags
    client.delete(f"/api/tools/media/images/{plain}")
    assert tools.picture_info(plain) == {}


def test_character_portrait_is_named_after_the_character(client, monkeypatch):
    _fake_images(monkeypatch)
    import time as _t
    sh = tools.save_ref("characters", "Shurpanakha", "glamorous woman")
    assert client.post(f"/api/tools/characters/{sh['id']}/picture").status_code == 200
    for _ in range(100):
        j = client.get("/api/tools/job").get_json()
        if j["state"] != "running":
            break
        _t.sleep(0.05)
    img = tools.refs("characters")[0]["image"]
    assert img.startswith("Shurpanakha_") and tools.picture_info(img)["tags"] == ["@Shurpanakha"]


def test_scene_can_use_a_saved_picture(client, monkeypatch, tmp_path):
    from app import project as P
    _fake_images(monkeypatch)
    tools.save_ref("characters", "Sita", "princess")
    name = tools.create_images("@Sita in a garden", "none", "16:9", 1)["images"][0]
    pid = client.post("/api/projects", json={"name": "Film"}).get_json()["id"]
    try:
        proj = P.load(pid)
        sid = proj["slides"][0]["id"]
        r = client.post(f"/api/projects/{pid}/slides/{sid}/from_media", json={"name": name})
        img = r.get_json()["slides"][0]["image"]
        assert img.startswith("uploads/media_") and (P.folder(pid) / img).exists()
        assert client.post(f"/api/projects/{pid}/slides/{sid}/from_media", json={"name": "../x"}).status_code == 400
    finally:
        P.delete(pid)


def test_pages_have_the_viewer_and_the_picker(client):
    tools_html = client.get("/tools/image").get_data(as_text=True)
    assert 'id="viewer"' in tools_html and 'id="imgFilters"' in tools_html
    assert 'id="picker"' in client.get("/make").get_data(as_text=True)


def test_upload_own_pictures_for_a_character(client):
    ram = tools.save_ref("characters", "Ram", "prince with a bow")
    files = [(_png(c), f"ram{k}.png") for k, c in enumerate(("#111111", "#222222", "#333333", "#444444"))]
    r = client.post(f"/api/tools/characters/{ram['id']}/upload", data={"files": files}, content_type="multipart/form-data")
    names = r.get_json()["images"]
    assert len(names) == 4 and all(n.startswith("ram") for n in names)
    assert all(tools.picture_info(n)["tags"] == ["@Ram"] for n in names)
    assert tools.refs("characters")[0]["image"] == names[0]                 # first one became the portrait
    assert tools.refs_with_counts("characters")[0]["pictures"] == 4
    assert client.post(f"/api/tools/characters/{ram['id']}/upload", data={}, content_type="multipart/form-data").status_code == 400
    bad = client.post(f"/api/tools/characters/{ram['id']}/upload", data={"files": [(io.BytesIO(b"x"), "a.exe")]},
                      content_type="multipart/form-data")
    assert bad.status_code == 400
