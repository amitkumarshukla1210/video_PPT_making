"""OpenAI-compatible speech endpoint used by the Video & Voice Studio."""
import io
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402


def client():
    app.testing = True
    return app.test_client()


def test_voices_list():
    r = client().get("/v1/audio/voices")
    assert r.status_code == 200
    data = r.get_json()
    assert data["voices"] and all(":" in v["id"] for v in data["voices"])


def test_speech_wav_and_mp3():
    c = client()
    r = c.post("/v1/audio/speech", json={"input": "Hello from the studio.", "voice": "alloy", "response_format": "wav"})
    assert r.status_code == 200 and r.mimetype == "audio/wav"
    with wave.open(io.BytesIO(r.data)) as w:
        assert w.getnframes() / w.getframerate() > 0.5
    r = c.post("/v1/audio/speech", json={"input": "Hello.", "voice": "espeak:en-us", "response_format": "mp3", "speed": 1.2})
    assert r.status_code == 200 and r.mimetype == "audio/mpeg" and len(r.data) > 1000


def test_speech_validation():
    c = client()
    assert c.post("/v1/audio/speech", json={}).status_code == 400
    assert c.post("/v1/audio/speech", json={"input": "x" * 6000}).status_code == 400
    assert c.post("/v1/audio/speech", json={"input": "hi", "speed": "fast"}).status_code == 400


def test_cors_and_private_network_headers():
    c = client()
    r = c.options("/v1/audio/speech", headers={"Origin": "https://someone.github.io",
                                               "Access-Control-Request-Private-Network": "true"})
    assert r.status_code == 204
    assert r.headers["Access-Control-Allow-Origin"] == "https://someone.github.io"
    assert r.headers["Access-Control-Allow-Private-Network"] == "true"
    r = c.options("/v1/audio/speech", headers={"Origin": "https://evil.example.com"})
    assert "Access-Control-Allow-Origin" not in r.headers


def test_studio_route_served():
    c = client()
    assert c.get("/studio").status_code == 301
    r = c.get("/studio/")
    assert r.status_code == 200 and b"Video &amp; Voice Studio" in r.data


def test_version_everywhere():
    c = client()
    v = (Path(__file__).resolve().parent.parent / "VERSION").read_text().strip()
    assert c.get("/api/system").get_json()["version"] == v
    assert c.get("/studio/VERSION").data.decode() == v
    assert f"v{v}".encode() in c.get("/").data
    assert f"## {v} " in (Path(__file__).resolve().parent.parent / "CHANGELOG.md").read_text()


def test_my_cloned_voice_is_offered_and_uses_my_sample(tmp_path, monkeypatch):
    """The Studio gets 'My cloned voice' from the local server once a sample was recorded (no API key)."""
    import json as _json
    import sys as _sys
    import textwrap
    from app import project as project_store
    from app.tts import clone_engine

    monkeypatch.setattr(project_store, "PROJECTS_DIR", tmp_path)
    c = client()
    # installed but no sample yet: not offered
    monkeypatch.setattr(clone_engine, "_python", lambda: _sys.executable)
    assert not any(v["engine"] == "clone" for v in c.get("/v1/audio/voices").get_json()["voices"])

    proj = tmp_path / "demo-1"
    (proj / "uploads").mkdir(parents=True)
    sample = proj / "uploads" / "voice_sample_ab12.wav"
    with wave.open(str(sample), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b"\0\0" * 24000 * 8)
    (proj / "project.json").write_text(_json.dumps({"id": "demo-1", "voice_sample": "uploads/voice_sample_ab12.wav"}))

    seen = {}
    fake = tmp_path / "fake_worker.py"
    fake.write_text(textwrap.dedent(f'''
        import json, sys, wave
        job = json.load(open(sys.argv[1], encoding="utf-8"))
        json.dump({{"ref": job["ref"], "lang": job["lang"]}}, open({str(tmp_path / "seen.json")!r}, "w"))
        for n, it in enumerate(job["items"]):
            with wave.open(it["out"], "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(b"\\x10\\x00" * 24000)
            print(f"PROGRESS {{n + 1}} {{len(job['items'])}}", flush=True)
    '''))
    monkeypatch.setattr(clone_engine, "WORKER", fake)

    voices = c.get("/v1/audio/voices").get_json()
    clone = [v for v in voices["voices"] if v["engine"] == "clone"]
    assert voices["clone"] == {"installed": True, "sample": True}
    assert any(v["id"] == "clone:hi" and "Hindi" in v["name"] for v in clone)
    r = c.post("/v1/audio/speech", json={"input": "नमस्ते, यह मेरी आवाज़ है।", "voice": "clone:hi"})
    assert r.status_code == 200 and r.mimetype == "audio/wav"
    seen = _json.loads((tmp_path / "seen.json").read_text())
    assert seen == {"ref": str(sample), "lang": "hi"}
