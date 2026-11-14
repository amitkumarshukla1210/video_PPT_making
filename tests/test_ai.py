"""Local-AI features: AI narration from slides, dubbing, Whisper captions + noise cleanup, music library.
The AI models are replaced by stand-ins (Ollama, Whisper), so the tests run without downloads."""
import json
import re
import sys
import time
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import project as P, tts  # noqa: E402
from app.ai import library, llm, writer, dubbing, stt  # noqa: E402
from app.main import app  # noqa: E402


class FakeOllama:
    """Answers like Ollama: /api/tags lists the model; /api/generate returns JSON for our prompts."""

    def __init__(self):
        self.prompts = []

    def __call__(self, path, payload=None, timeout=5):
        if path == "/api/tags":
            return {"models": [{"name": llm.MODEL}]}
        self.prompts.append(payload["prompt"])
        p = payload["prompt"]
        if "Translate each numbered" in p:
            items = re.findall(r"^(\d+)\. (.*)$", p, re.M)
            return {"response": json.dumps({"items": [{"n": int(n), "text": f"[hi] {t}"} for n, t in items]})}
        if "Write the narration" in p:
            nums = [int(n) for n in re.findall(r"^(\d+)\. (?:Title slide|Closing slide|Slide):", p, re.M)]
            return {"response": json.dumps({"slides": [{"n": n, "script": f"AI narration for slide {n}, clear and professional."} for n in nums]})}
        m = re.search(r"exactly (\d+) numbered beats", p)
        if m:
            return {"response": json.dumps({"beats": [f"Beat {k + 1}" for k in range(int(m.group(1)))]})}
        m = re.search(r"Write scenes (\d+) to (\d+) only", p)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            return {"response": json.dumps({"scenes": [{"title": f"Scene {k}", "line": f"Spoken line {k}.", "image": f"picture {k}"}
                                                       for k in range(a, b + 1)]})}
        if "Write " in p and "scenes" in p:
            return {"response": json.dumps({"scenes": [{"title": "Opening", "line": "Every product starts with an idea.", "image": "a design studio at dawn"},
                                                       {"title": "The turn", "line": "Cost becomes part of design.", "image": "engineers around a table"}]})}
        return {"response": "{}"}


@pytest.fixture
def fake_llm(monkeypatch):
    f = FakeOllama()
    monkeypatch.setattr(llm, "_request", f)
    return f


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "PROJECTS_DIR", tmp_path)
    p = P.new_project("Design to Cost")
    P.add_content_slide(p, "Steel price impact", "Steel up 8%\nBOM up 2.1%")
    P.add_content_slide(p, "Supplier comparison", "Three suppliers\nBest landed cost")
    p["voice"] = {"engine": "espeak", "voice": "en-us", "lang": "en-us", "speed": 1.0}
    P.save(p)
    return p


def test_llm_status_when_ollama_is_off(monkeypatch):
    def down(*a, **k):
        raise OSError("connection refused")
    monkeypatch.setattr(llm, "_request", down)
    st = llm.status()
    assert st["available"] is False and "Ollama" in st["info"]


def test_llm_status_model_missing(monkeypatch):
    monkeypatch.setattr(llm, "_request", lambda *a, **k: {"models": [{"name": "other:1b"}]})
    assert "ollama pull" in llm.status()["info"]


def test_ai_writes_narration_for_every_slide_from_content(fake_llm, proj):
    n = writer.write_narration(proj, "en")
    assert n == 4
    assert all(s["script"].startswith("AI narration for slide") for s in proj["slides"])
    # the AI got the real slide content, the deck outline and the language
    joined = "\n".join(fake_llm.prompts)
    assert "Steel up 8%" in joined and "Supplier comparison" in joined and "in English" in joined


def test_ai_only_fills_empty_slides_unless_asked(fake_llm, proj):
    proj["slides"][1]["script"] = "My own words, keep them."
    writer.write_narration(proj, "hi")
    assert proj["slides"][1]["script"] == "My own words, keep them."
    assert "in Hindi" in fake_llm.prompts[0]


def test_large_decks_are_written_in_chunks(fake_llm, proj):
    for k in range(17):
        P.add_content_slide(proj, f"Slide {k}", "point")
    assert writer.write_narration(proj, "en") == len(proj["slides"])
    assert len(fake_llm.prompts) == 3      # 21 slides, 8 per request


def test_bad_ai_answer_gives_a_clear_error(monkeypatch, proj):
    monkeypatch.setattr(llm, "_request", lambda path, payload=None, timeout=5: {"response": "sorry, no JSON"})
    with pytest.raises(llm.LLMError, match="valid JSON"):
        writer.write_narration(proj, "en")


def test_dub_creates_translated_copy_with_hindi_voice(fake_llm, proj):
    for s in proj["slides"]:
        s["script"] = f"Narration of {s['title']}."
    P.save(proj)
    d = dubbing.make_dub(proj, "hi")
    assert d["id"] != proj["id"] and d["name"] == "Design to Cost (Hindi)"
    assert all(s["script"].startswith("[hi] Narration of") for s in d["slides"])
    assert d["voice"]["engine"] == "espeak" and d["voice"]["lang"].startswith("hi")
    assert P.load(d["id"])["dubbed_from"] == proj["id"]
    assert P.load(proj["id"])["slides"][1]["script"] == "Narration of Steel price impact."   # original untouched


def test_dub_prefers_my_cloned_voice(fake_llm, proj, monkeypatch):
    from app.tts import clone_engine
    monkeypatch.setattr(clone_engine, "_python", lambda: sys.executable)
    proj["voice_sample"] = "uploads/voice_sample_x.wav"
    assert dubbing.pick_voice(proj, "hi") == {"engine": "clone", "voice": "hi", "lang": "hi"}


def test_scene_writer_for_the_studio(fake_llm):
    out = writer.scenes_from_prompt("why design to cost matters", "trailer", 2)
    assert out["script"].startswith("# Opening\nEvery product")
    assert out["scenes"][1]["image"] == "engineers around a table"


def test_ai_endpoints_run_in_background(fake_llm, proj):
    c = app.test_client()
    r = c.post(f"/api/projects/{proj['id']}/ai_script", json={"language": "en"})
    assert r.status_code == 200
    for _ in range(100):
        j = c.get(f"/api/projects/{proj['id']}/job").get_json()["ai"]
        if j["state"] != "running":
            break
        time.sleep(0.05)
    assert j["state"] == "done" and j["result"]["written"] == 4
    assert P.load(proj["id"])["slides"][1]["script"].startswith("AI narration")
    r = c.post(f"/api/projects/{proj['id']}/dub", json={"language": "hi"})
    assert r.status_code == 200
    for _ in range(100):
        j = c.get(f"/api/projects/{proj['id']}/job").get_json()["ai"]
        if j["state"] != "running":
            break
        time.sleep(0.05)
    assert j["state"] == "done" and P.load(j["result"]["project"])["language"] == "hi"


def test_ai_endpoints_explain_when_ai_is_missing(monkeypatch, proj):
    monkeypatch.setattr(llm, "_request", lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    r = app.test_client().post(f"/api/projects/{proj['id']}/ai_script", json={})
    assert r.status_code == 400 and "Ollama" in r.get_json()["error"]


def test_music_library_beds_and_sound_effects(tmp_path, monkeypatch, proj):
    monkeypatch.setattr(library, "DIR", tmp_path / "lib")
    for mood in library.MOODS:
        path = library.music_file(mood)
        with wave.open(str(path)) as w:
            assert w.getnchannels() == 2 and w.getframerate() == 48000
            assert 50 < w.getnframes() / w.getframerate() < 130
    for name in library.SFX:
        assert library.sfx_file(name).stat().st_size > 1000
    c = app.test_client()
    assert {m["id"] for m in c.get("/api/library").get_json()["music"]} == set(library.MOODS)
    assert c.get("/library/music/corporate.wav").status_code == 200
    assert c.get("/library/music/nope.wav").status_code == 404
    p = c.post(f"/api/projects/{proj['id']}/music_library", json={"mood": "cinematic"}).get_json()
    assert p["music"]["file"].endswith("music_library_cinematic.wav") and p["music"]["library"] == "cinematic"


def test_loops_are_seamless():
    import numpy as np
    loop = library.compose("corporate", bars=4)
    jump = np.abs(loop[0] - loop[-1]).max()
    typical = np.abs(np.diff(loop[:, 0])).max()
    assert jump <= typical * 1.5


def test_recording_gets_noise_cleanup_whisper_captions_and_whoosh(proj, monkeypatch, tmp_path):
    """A slide with my recording: noise cleaned, captions from Whisper's timings, whoosh at cuts."""
    import subprocess
    from app.ffmpeg_utils import ffmpeg_bin
    from app import media
    from app.video import render_video
    base = P.folder(proj["id"])
    raw = base / "uploads/raw.webm"
    subprocess.run([ffmpeg_bin(), "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=3",
                    "-f", "lavfi", "-i", "sine=f=300:d=3", "-shortest", "-c:v", "libvpx", "-c:a", "libopus", str(raw)], check=True)
    s = proj["slides"][1]
    s["clip_seconds"] = media.normalize_clip(raw, base / "uploads/clip.mp4")
    s["clip"] = "uploads/clip.mp4"
    proj["slides"] = proj["slides"][:2]
    proj["slides"][0]["script"] = "Welcome."
    proj["intro"], proj["sfx"], proj["clean_audio"] = False, True, True
    calls = {}
    monkeypatch.setattr(stt, "status", lambda: {"available": True, "info": "fake"})
    monkeypatch.setattr(stt, "transcribe", lambda wav, lang=None: calls.setdefault("segs", [(0.2, 1.4, "Steel went up eight percent."), (1.6, 2.8, "So did our costs.")]))
    filters = []
    real_run = media._run
    monkeypatch.setattr(media, "_run", lambda cmd: (filters.append(" ".join(map(str, cmd))), real_run(cmd))[1])
    r = render_video(proj)
    assert any("afftdn" in f for f in filters)                      # noise cleanup used
    srt = Path(r["srt"]).read_text()
    assert "Steel went up eight percent." in srt and "So did our costs." in srt
    timeline = json.loads((base / "out/timeline.json").read_text())
    start2 = timeline[1]["start"]
    first_cue = re.search(r"(\d\d):(\d\d):(\d\d),(\d\d\d) --> .*\nSteel went up", srt)
    h, m, sec, ms = map(int, first_cue.groups())
    assert abs((h * 3600 + m * 60 + sec + ms / 1000) - (start2 + 0.6 + 0.2)) < 0.06   # Whisper timing, not a guess
    # a whoosh is mixed in around the slide change
    import numpy as np
    with wave.open(str(base / "out/narration.wav")) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(float)
        rate = w.getframerate()
    around = a[int((start2 - 0.3) * rate):int((start2 + 0.3) * rate)]
    assert np.sqrt((around ** 2).mean()) > 200
    assert (base / "audio/slide_001.captions.json").exists()      # cached for the next render


def test_long_cinematic_video_outline_then_parts(fake_llm):
    steps = []
    out = writer.scenes_from_prompt("a factory that learns to save", "trailer", 22, progress=lambda f, m: steps.append(m))
    assert len(out["scenes"]) == 22
    assert [sc["title"] for sc in out["scenes"]][:3] == ["Scene 1", "Scene 2", "Scene 3"]
    assert out["scenes"][-1]["line"] == "Spoken line 22."
    # 1 outline request + 3 parts of up to 8 scenes, each part sees the full outline and the previous line
    assert len(fake_llm.prompts) == 4
    assert "22. Beat 22" in fake_llm.prompts[2] and 'Previous scene: "Spoken line 8."' in fake_llm.prompts[2]
    assert steps[0].startswith("Planning the story") and "scenes 17–22 of 22" in steps[-1]
    assert writer.scenes_from_prompt("x", scenes=500)["scenes"] and len(fake_llm.prompts) > 4   # capped at 60


def test_long_scene_job_endpoint(fake_llm):
    c = app.test_client()
    r = c.post("/v1/ai/scenes", json={"idea": "long story", "scenes": 12, "background": True})
    assert r.status_code == 202
    for _ in range(100):
        j = c.get("/v1/ai/jobs/scenes").get_json()
        if j["state"] != "running":
            break
        time.sleep(0.05)
    assert j["state"] == "done" and len(j["result"]["scenes"]) == 12


def test_picture_creator_endpoint_with_stand_in_worker(tmp_path, monkeypatch):
    import base64
    import textwrap
    from app.ai import images
    fake = tmp_path / "fake_image_worker.py"
    fake.write_text(textwrap.dedent('''
        import json, sys
        from PIL import Image
        job = json.load(open(sys.argv[1], encoding="utf-8"))
        for n, it in enumerate(job["items"]):
            Image.new("RGB", (job["width"], job["height"]), (20, 90, 160)).save(it["out"])
            print(f"PROGRESS {n + 1} {len(job['items'])}", flush=True)
    '''))
    monkeypatch.setattr(images, "WORKER", fake)
    monkeypatch.setattr(images, "_python", lambda: sys.executable)
    monkeypatch.setattr(images, "_model_cached", lambda: True)
    c = app.test_client()
    assert c.get("/v1/ai/status").get_json()["images"]["available"] is True
    r = c.post("/v1/images/generations", json={"prompt": "a design studio at dawn", "aspect": "9:16"})
    assert r.status_code == 200
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(base64.b64decode(r.get_json()["data"][0]["b64_json"])))
    assert img.size == images.SIZES["9:16"]
    assert c.post("/v1/images/generations", json={}).status_code == 400


def test_picture_creator_explains_when_not_installed(monkeypatch):
    from app.ai import images
    monkeypatch.setattr(images, "_python", lambda: None)
    r = app.test_client().post("/v1/images/generations", json={"prompt": "x"})
    assert r.status_code == 503 and "install_once.bat images" in r.get_json()["error"]["message"]
