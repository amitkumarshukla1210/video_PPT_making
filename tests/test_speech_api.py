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
