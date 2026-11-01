"""End-to-end tests for the Video & Voice Studio page (studio/studio.html) in Chromium.

Every test gets a fresh browser context (empty localStorage / IndexedDB). ElevenLabs and the local
voice server are mocked with Playwright route interception: no real or paid API is ever called.
The ffmpeg.wasm core is served from tests/.cache (downloaded once with `npm pack`), never from a CDN.
"""
import io
import json
import math
import os
import re
import struct
import subprocess
import sys
import threading
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pw = pytest.importorskip("playwright.sync_api")

from app.ffmpeg_utils import ffmpeg_bin  # noqa: E402
from app.main import app  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = ROOT / "tests" / ".cache" / "ffmpeg-core" / "package" / "dist" / "esm"
CDN_CORE = re.compile(r"https://cdn\.jsdelivr\.net/npm/@ffmpeg/core@[^/]+/dist/esm/(ffmpeg-core\.(js|wasm))")
MOCK_TTS = "http://tts.mock"
TEMPLATES = ["inspiration", "trailer", "explainer", "product", "documentary"]


# ---------- server & browser ----------
@pytest.fixture(scope="session")
def base_url():
    from werkzeug.serving import make_server
    srv = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture(scope="session")
def browser():
    with pw.sync_playwright() as p:
        exe = "/opt/pw-browsers/chromium"
        b = p.chromium.launch(executable_path=exe if os.path.exists(exe) else None,
                              args=["--autoplay-policy=no-user-gesture-required"])
        yield b
        b.close()


def wav_bytes(seconds, freq=300.0, amp=0.3, rate=24000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        n = int(seconds * rate)
        w.writeframes(b"".join(struct.pack("<h", int(32767 * amp * math.sin(2 * math.pi * freq * i / rate))) for i in range(n)))
    return buf.getvalue()


SPEECH_STUB = """
  window.__spoken = [];
  const s = window.speechSynthesis;
  if (s) {
    s.speak = (u) => { window.__spoken.push(u.text); setTimeout(() => u.onend && u.onend(), 10); };
    s.cancel = () => {};
  }
"""


class Studio:
    """A fresh page with mocks. Always re-query elements: the scene list is re-rendered on change."""

    def __init__(self, browser, base_url, viewport=None, voice_seconds=None, silent_voice=False, block_native_mp4=False):
        self.ctx = browser.new_context(viewport=viewport or {"width": 1366, "height": 900}, accept_downloads=True)
        self.page = self.ctx.new_page()
        self.errors = []
        self.tts_calls = []
        self.eleven_calls = []
        self.cdn_requests = []
        self.page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
        self.page.on("console", lambda m: self.errors.append(f"console: {m.text}") if m.type == "error" else None)
        settings = {"localUrl": MOCK_TTS, "theme": "light"}
        init = SPEECH_STUB + f"if (!localStorage.getItem('dtc.studio.settings')) localStorage.setItem('dtc.studio.settings', {json.dumps(json.dumps(settings))});"
        if block_native_mp4:
            init += "const _its = MediaRecorder.isTypeSupported.bind(MediaRecorder); MediaRecorder.isTypeSupported = (t) => !t.startsWith('video/mp4') && _its(t);"
        self.ctx.add_init_script(init)
        self.voice_seconds = voice_seconds
        self.silent_voice = silent_voice
        self.ctx.route(f"{MOCK_TTS}/**", self._tts)
        self.ctx.route("https://api.elevenlabs.io/**", self._eleven)
        self.ctx.route(CDN_CORE, self._core)
        self.page.goto(f"{base_url}/studio/")
        self.page.wait_for_selector("body[data-ready=true]")

    # --- mocks ---
    def _tts(self, route):
        req = route.request
        if req.method == "OPTIONS":
            return route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*"})
        cors = {"Access-Control-Allow-Origin": "*"}
        if req.url.endswith("/v1/audio/voices"):
            return route.fulfill(status=200, headers=cors, content_type="application/json",
                                 body=json.dumps({"voices": [{"id": "kokoro:af_heart", "name": "Heart", "lang": "en-us", "gender": "female"},
                                                             {"id": "kokoro:am_adam", "name": "Adam", "lang": "en-us", "gender": "male"}]}))
        body = json.loads(req.post_data or "{}")
        self.tts_calls.append(body)
        secs = self.voice_seconds or min(3.0, 0.6 + 0.25 * len(body.get("input", "").split()))
        return route.fulfill(status=200, headers=cors, content_type="audio/wav",
                             body=wav_bytes(secs, amp=0.0 if self.silent_voice else 0.3))

    eleven_mode = "invalid_key"

    def _eleven(self, route):
        self.eleven_calls.append(route.request.url)
        if self.eleven_mode == "invalid_key":
            return route.fulfill(status=401, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"},
                                 body=json.dumps({"detail": {"status": "invalid_api_key", "message": "Invalid API key"}}))
        return route.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"}, body=json.dumps({"voices": []}))

    def _core(self, route):
        name = CDN_CORE.match(route.request.url).group(1)
        self.cdn_requests.append(name)
        f = CORE_DIR / name
        if not f.exists():
            return route.abort()
        return route.fulfill(status=200, body=f.read_bytes(),
                             headers={"Content-Type": "application/wasm" if name.endswith("wasm") else "text/javascript",
                                      "Access-Control-Allow-Origin": "*"})

    # --- helpers ---
    def project(self):
        return self.page.evaluate("() => JSON.parse(JSON.stringify(window.__studio.store.project))")

    def timeline(self):
        return self.page.evaluate("() => window.__studio.buildTimeline()")

    def scenes(self):
        return self.page.locator("#scenes .scene")

    def write_and_split(self, text):
        self.page.fill("#script", text)
        self.page.click("#splitBtn")
        self.page.wait_for_function("n => document.querySelectorAll('#scenes .scene').length === n", arg=text.count("\n\n") + 1)

    def use_local_engine(self):
        self.page.select_option("#engine", "local")
        self.page.wait_for_function("() => document.querySelectorAll('#voiceSelect option').length >= 2")

    def set_lengths(self, seconds):
        for i, s in enumerate(seconds):
            box = self.scenes().nth(i).locator("input[data-k=seconds]")
            box.fill(str(s))
            box.dispatch_event("change")

    def cards(self, on):
        for sel in ("#titleCard", "#endCard"):
            self.page.set_checked(sel, on)

    def export(self, fmt, timeout=120_000):
        self.page.select_option("#exportFormat", fmt)
        self.page.click("#exportBtn")
        self.page.wait_for_selector("#downloadLink", timeout=timeout)
        with self.page.expect_download() as d:
            self.page.click("#downloadLink")
        return d.value

    def toast(self):
        self.page.wait_for_selector("#toast:not([hidden])")
        return self.page.text_content("#toast")

    def close(self):
        self.ctx.close()


@pytest.fixture
def studio(browser, base_url, request):
    opts = getattr(request, "param", {}) or {}
    s = Studio(browser, base_url, **opts)
    yield s
    errors = list(s.errors)
    s.close()
    assert not errors, f"console errors: {errors}"


def media_seconds(path):
    """Decoded length (WebM from MediaRecorder has no duration in its header, so decode it)."""
    r = subprocess.run([ffmpeg_bin(), "-hide_banner", "-i", str(path), "-f", "null", "-"], capture_output=True, text=True)
    times = re.findall(r"time=(\d+):(\d+):([\d.]+)", r.stderr)
    assert times, r.stderr[-800:]
    h, m, s = times[-1]
    return int(h) * 3600 + int(m) * 60 + float(s), r.stderr


def needs_core():
    if not (CORE_DIR / "ffmpeg-core.wasm").exists():
        pytest.skip("ffmpeg.wasm core not cached; run: npm pack @ffmpeg/core@0.12.10 into tests/.cache/ffmpeg-core")


# ---------- tests ----------
def test_page_loads_and_is_accessible(studio):
    p = studio.page
    assert p.title() == "Design to Cost — Video & Voice Studio"
    assert p.locator("#templates [role=radio]").count() == 5
    assert p.locator("#templates [aria-checked=true]").count() == 1
    for h in ("Script", "Scenes", "Voice", "Music", "Export"):
        assert p.locator(f"h2:has-text('{h}')").count() == 1
    # every button has a name for screen readers
    unnamed = p.evaluate("""() => [...document.querySelectorAll('button')].filter(b => b.offsetParent &&
        !(b.getAttribute('aria-label') || b.textContent.trim())).length""")
    assert unnamed == 0
    # headings are left-aligned
    assert p.evaluate("() => getComputedStyle(document.querySelector('h2')).textAlign") in ("left", "start")


@pytest.mark.parametrize("template", TEMPLATES)
def test_every_template_exports_a_10_second_video(studio, template, tmp_path):
    p = studio.page
    p.click(f"[data-tpl={template}]")
    studio.write_and_split("First scene for the test.\n\nSecond scene closes it.")
    studio.set_lengths([5, 5])
    studio.cards(False)
    studio.use_local_engine()
    assert abs(studio.timeline()["total"] - 10) < 0.01
    d = studio.export("webm")
    out = tmp_path / d.suggested_filename
    d.save_as(out)
    assert out.stat().st_size > 10_000
    secs, info = media_seconds(out)
    assert 9.0 <= secs <= 11.5, secs
    assert "Video: vp" in info and "Audio: opus" in info
    assert len(studio.tts_calls) == 2


def test_ten_minute_limit_blocks_export(studio):
    p = studio.page
    studio.write_and_split("One.\n\nTwo.")
    studio.set_lengths([300, 299])
    p.wait_for_function("() => document.querySelector('#exportBtn').disabled")
    text = p.text_content("#limitText")
    assert "Too long" in text and "blocked" in text
    assert p.get_attribute("#meter", "aria-valuenow") == str(round(studio.timeline()["total"]))
    studio.set_lengths([200, 100])
    p.wait_for_function("() => !document.querySelector('#exportBtn').disabled")
    assert "left" in p.text_content("#limitText")


def test_engine_switch_and_voice_list(studio):
    p = studio.page
    studio.use_local_engine()
    options = p.locator("#voiceSelect option").all_text_contents()
    assert any("Heart" in o for o in options) and any("Adam" in o for o in options)
    assert studio.project()["voice"]["engine"] == "local"
    p.select_option("#voiceSelect", "kokoro:am_adam")
    assert studio.project()["voice"]["voiceId"] == "kokoro:am_adam"
    p.select_option("#engine", "webspeech")
    p.wait_for_function("() => document.querySelector('#engineNote').textContent.includes('previewed')")
    assert p.is_visible("#pitchField") and not p.is_visible("#stabilityField")
    p.select_option("#engine", "elevenlabs")
    assert p.is_visible("#stabilityField") and p.is_visible("#similarityField")


def test_invalid_elevenlabs_key_shows_error_and_falls_back(studio):
    p = studio.page
    p.click("#settingsBtn")
    p.fill("#elevenKey", "sk_wrong_key")
    p.click("#saveSettings")
    p.select_option("#engine", "elevenlabs")
    assert "rejected" in studio.toast()
    studio.write_and_split("Hello from the fallback voice.")
    # the voice list failed, so give the scene a voice id directly and preview it
    p.evaluate("() => window.__studio.store.update(p => { p.voice.voiceId = 'abc'; })")
    p.click("#scenes .scene [data-act=say]")
    p.wait_for_function("() => window.__spoken.length > 0")
    assert "browser voice instead" in p.text_content("#toast")
    assert p.evaluate("() => window.__spoken[0]") == "Hello from the fallback voice."
    assert studio.eleven_calls and all("api.elevenlabs.io" in u for u in studio.eleven_calls)
    # the key is kept only in this browser's settings, never in the project
    assert "sk_wrong_key" not in json.dumps(studio.project())
    studio.errors[:] = [e for e in studio.errors if "401" not in e]   # the browser logs the mocked 401 itself


def test_scene_add_edit_reorder_delete_undo_redo(studio):
    p = studio.page
    studio.write_and_split("Alpha.\n\nBravo.\n\nCharlie.")
    texts = lambda: [s["text"] for s in studio.project()["scenes"]]  # noqa: E731
    p.click("#addSceneBtn")
    assert len(texts()) == 4
    studio.scenes().nth(3).locator("textarea").fill("Delta.")
    assert texts()[3] == "Delta."
    studio.scenes().nth(0).locator("input[data-k=title]").fill("Opening")
    assert studio.project()["scenes"][0]["title"] == "Opening"
    studio.scenes().nth(2).locator("[data-act=up]").click()
    assert texts() == ["Alpha.", "Charlie.", "Bravo.", "Delta."]
    studio.scenes().nth(0).locator("[data-act=del]").click()
    assert texts() == ["Charlie.", "Bravo.", "Delta."]
    p.click("#undoBtn")
    assert texts() == ["Alpha.", "Charlie.", "Bravo.", "Delta."]
    p.click("body")
    p.keyboard.press("Control+z")
    assert texts() == ["Alpha.", "Bravo.", "Charlie.", "Delta."]
    p.keyboard.press("Control+y")
    assert texts() == ["Alpha.", "Charlie.", "Bravo.", "Delta."]
    p.click("#redoBtn")
    assert texts() == ["Charlie.", "Bravo.", "Delta."]
    # the background colour and transition per scene
    studio.scenes().nth(0).locator("select[data-k=transition]").select_option("zoom")
    assert studio.project()["scenes"][0]["transition"]["type"] == "zoom"


def test_srt_matches_the_voice_timing(studio, tmp_path):
    p = studio.page
    studio.voice_seconds = 2.0
    studio.write_and_split("The first caption sentence. A second one follows.\n\nScene two speaks here.")
    studio.use_local_engine()
    p.click("#genVoicesBtn")
    p.wait_for_function("() => document.querySelector('#progressText').textContent.includes('ready')")
    with p.expect_download() as d:
        p.click("#srtBtn")
    srt = Path(d.value.path()).read_text(encoding="utf-8")
    blocks = [b for b in srt.strip().split("\n\n") if b]
    tl = studio.timeline()
    assert len(blocks) == len(tl["captions"])
    first = blocks[0].split("\n")
    assert first[0] == "1"
    start = tl["items"][1]["voiceStart"]          # after the title card
    h, m, s = first[1].split(" --> ")[0].split(":")
    assert abs(int(h) * 3600 + int(m) * 60 + float(s.replace(",", ".")) - start) < 0.002
    assert first[2] == "The first caption sentence."
    last_end = blocks[-1].split("\n")[1].split(" --> ")[1]
    h, m, s = last_end.split(":")
    assert int(h) * 3600 + int(m) * 60 + float(s.replace(",", ".")) <= tl["items"][2]["voiceEnd"] + 0.002


@pytest.mark.parametrize("studio", [{"silent_voice": True, "voice_seconds": 3.0}], indirect=True)
def test_music_is_ducked_under_the_voice(studio, tmp_path):
    p = studio.page
    music = tmp_path / "music.wav"
    music.write_bytes(wav_bytes(4.0, freq=220, amp=0.5, rate=44100))
    studio.write_and_split("Only one scene with a voice.")
    studio.use_local_engine()
    p.set_input_files("#musicFile", str(music))
    p.wait_for_function("() => document.querySelector('#musicName').textContent.includes('music.wav')")
    d = studio.export("wav")
    out = tmp_path / "mix.wav"
    d.save_as(out)
    tl = studio.timeline()
    v = tl["items"][1]
    with wave.open(str(out)) as w:
        rate = w.getframerate()
        frames = w.readframes(w.getnframes())
    samples = struct.unpack(f"<{len(frames) // 2}h", frames)[0::2]   # left channel

    def rms(a, b):
        seg = samples[int(a * rate):int(b * rate)]
        return math.sqrt(sum(x * x for x in seg) / max(1, len(seg)))

    before = rms(0.5, v["voiceStart"] - 0.5)              # title card, music at full level
    during = rms(v["voiceStart"] + 0.5, v["voiceEnd"] - 0.5)   # silent voice, music ducked
    assert before > 1000
    assert 0.2 < during / before < 0.4, (before, during)


def test_project_save_and_open_round_trip(studio, tmp_path):
    p = studio.page
    img = tmp_path / "bg.png"
    from PIL import Image
    Image.new("RGB", (320, 180), (31, 95, 168)).save(img)
    p.fill("#projectTitle", "Round trip")
    studio.write_and_split("Keep me.\n\nAnd me.")
    studio.scenes().nth(0).locator("input[data-k=media]").set_input_files(str(img))
    p.wait_for_function("() => window.__studio.store.project.scenes[0].background.kind === 'image'")
    p.click("[data-tpl=trailer]")
    before = studio.project()
    with p.expect_download() as d:
        p.click("#saveBtn")
    saved = tmp_path / "project.json"
    d.value.save_as(saved)
    data = json.loads(saved.read_text())
    assert data["media"] and all(v.startswith("data:image/png") for v in data["media"].values())
    p.once("dialog", lambda dlg: dlg.accept())
    p.click("#newBtn")
    assert studio.project()["scenes"] == []
    p.set_input_files("#openFile", str(saved))
    p.wait_for_function("() => window.__studio.store.project.title === 'Round trip'")
    after = studio.project()
    assert [s["text"] for s in after["scenes"]] == [s["text"] for s in before["scenes"]]
    assert after["template"] == "trailer"
    assert after["scenes"][0]["background"]["mediaId"] == before["scenes"][0]["background"]["mediaId"]
    p.wait_for_selector("#scenes .scene:first-child .thumb img")
    # a broken file gives a clear message and keeps the project
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    p.set_input_files("#openFile", str(bad))
    assert "not valid JSON" in studio.toast()
    assert studio.project()["title"] == "Round trip"


def test_autosave_survives_reload(studio):
    p = studio.page
    studio.write_and_split("Saved automatically.")
    p.wait_for_timeout(600)
    p.reload()
    p.wait_for_selector("body[data-ready=true]")
    assert studio.project()["scenes"][0]["text"] == "Saved automatically."


@pytest.mark.parametrize("studio", [{"block_native_mp4": True}], indirect=True)
def test_mp4_export_via_ffmpeg_wasm_is_lazy(studio, tmp_path):
    needs_core()
    p = studio.page
    studio.write_and_split("MP4 export scene.")
    studio.set_lengths([3])
    studio.cards(False)
    studio.use_local_engine()
    assert studio.cdn_requests == []                 # nothing downloaded until MP4 is chosen
    d = studio.export("mp4", timeout=240_000)
    assert d.suggested_filename.endswith(".mp4")
    out = tmp_path / "out.mp4"
    d.save_as(out)
    secs, info = media_seconds(out)
    assert "Video: h264" in info and "Audio: aac" in info
    assert 2.5 < secs < 4.0
    assert set(studio.cdn_requests) == {"ffmpeg-core.js", "ffmpeg-core.wasm"}
    assert "converted to MP4 with ffmpeg.wasm" in p.text_content("#results")


def test_mp4_export_native_when_supported(studio, tmp_path):
    p = studio.page
    if not p.evaluate("() => MediaRecorder.isTypeSupported('video/mp4')"):
        pytest.skip("this Chromium cannot record MP4 natively")
    studio.write_and_split("Native MP4.")
    studio.set_lengths([2])
    studio.cards(False)
    studio.use_local_engine()
    d = studio.export("mp4")
    out = tmp_path / "n.mp4"
    d.save_as(out)
    assert out.stat().st_size > 5000 and studio.cdn_requests == []


def test_audio_only_export_wav_and_mp3(studio, tmp_path):
    needs_core()
    p = studio.page
    p.click("[data-tpl=documentary]")
    assert p.input_value("#exportFormat") == "mp3"
    studio.write_and_split("An audio documentary opening.\n\nAnd a calm close.")
    studio.use_local_engine()
    d = studio.export("wav")
    wav = tmp_path / "a.wav"
    d.save_as(wav)
    with wave.open(str(wav)) as w:
        wav_secs = w.getnframes() / w.getframerate()
    assert abs(wav_secs - studio.timeline()["total"]) < 0.05
    d = studio.export("mp3", timeout=180_000)
    mp3 = tmp_path / "a.mp3"
    d.save_as(mp3)
    secs, info = media_seconds(mp3)
    assert "Audio: mp3" in info and abs(secs - wav_secs) < 0.2


@pytest.mark.parametrize("studio", [{"viewport": {"width": 390, "height": 844}}], indirect=True)
def test_mobile_layout(studio):
    p = studio.page
    studio.write_and_split("Phone layout check.\n\nSecond scene.")
    overflow = p.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 0, f"page scrolls sideways by {overflow}px"
    cols = p.evaluate("() => getComputedStyle(document.querySelector('.workspace')).gridTemplateColumns.split(' ').length")
    assert cols == 1
    box = p.locator("#scenes .scene").first.bounding_box()
    assert box["width"] <= 390
    assert p.is_visible("#exportBtn") or p.locator("#exportBtn").count() == 1


def test_dark_mode_and_keyboard_template_choice(studio):
    p = studio.page
    p.click("#themeBtn")
    assert p.evaluate("() => document.documentElement.dataset.theme") == "dark"
    bg = p.evaluate("() => getComputedStyle(document.body).backgroundColor")
    assert bg != "rgb(246, 248, 250)"
    p.focus("[data-tpl=explainer]")
    p.keyboard.press("ArrowRight")
    assert studio.project()["template"] == "product"
    assert p.evaluate("() => document.activeElement.dataset.tpl") == "product"
    p.click("#themeBtn")
    assert p.evaluate("() => document.documentElement.dataset.theme") == "light"


def test_voice_presets_and_per_scene_voice(studio):
    p = studio.page
    studio.use_local_engine()
    p.select_option("#voiceSelect", "kokoro:am_adam")
    p.fill("#presetName", "Calm Adam")
    p.click("#savePresetBtn")
    assert "Calm Adam" in p.text_content("#presets")
    studio.write_and_split("Scene with its own voice.")
    studio.scenes().nth(0).locator("select[data-k=voice]").select_option("Calm Adam")
    assert studio.project()["scenes"][0]["voice"]["voiceId"] == "kokoro:am_adam"
    p.select_option("#voiceSelect", "kokoro:af_heart")
    studio.scenes().nth(0).locator("[data-act=regen]").click()
    p.wait_for_function("() => document.querySelector('#toast').textContent.includes('regenerated')")
    assert studio.tts_calls[-1]["voice"] == "kokoro:am_adam"


def test_cancel_stops_a_running_export(studio):
    p = studio.page
    studio.write_and_split("Long enough to cancel.")
    studio.set_lengths([30])
    studio.use_local_engine()
    p.select_option("#exportFormat", "webm")
    p.click("#exportBtn")
    p.wait_for_function("() => document.querySelector('#progressText').textContent.startsWith('Recording')")
    p.click("#cancelBtn")
    p.wait_for_function("() => document.querySelector('#progressText').textContent === 'Cancelled.'")
    assert p.locator("#downloadLink").count() == 0
    assert not p.is_disabled("#exportBtn")
