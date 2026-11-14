"""End-to-end tests for the offline-first Video & Voice Studio in Chromium.

Every test gets fresh browser storage. The localhost voice server is mocked; no hosted voice service
is used. The optional ffmpeg.wasm core is served from tests/.cache for conversion tests.
"""
import io
import json
import math
import re
import struct
import subprocess
import sys
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pw = pytest.importorskip("playwright.sync_api")

from app.ffmpeg_utils import ffmpeg_bin  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = ROOT / "tests" / ".cache" / "ffmpeg-core" / "package" / "dist" / "esm"
CDN_CORE = re.compile(r"https://cdn\.jsdelivr\.net/npm/@ffmpeg/core@[^/]+/dist/esm/(ffmpeg-core\.(js|wasm))")
TEMPLATES = ["inspiration", "trailer", "explainer", "product", "documentary"]


# server & browser fixtures (base_url, browser): tests/conftest.py


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
  window.__toasts = [];   // every message the page shows, for clear test failures
  document.addEventListener('DOMContentLoaded', () => {
    const t = document.querySelector('#toast');
    if (t) new MutationObserver(() => window.__toasts.push(t.textContent)).observe(t, { childList: true, characterData: true, subtree: true });
  });
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
        self.ai_calls = []
        self.long_scenes = 0
        self.cdn_requests = []
        self.page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
        self.page.on("console", lambda m: self.errors.append(f"console: {m.text} ({m.location.get('url', '')})") if m.type == "error" else None)
        settings = {"theme": "light"}
        init = SPEECH_STUB + f"if (!localStorage.getItem('dtc.studio.settings')) localStorage.setItem('dtc.studio.settings', {json.dumps(json.dumps(settings))});"
        if block_native_mp4:
            init += "const _its = MediaRecorder.isTypeSupported.bind(MediaRecorder); MediaRecorder.isTypeSupported = (t) => !t.startsWith('video/mp4') && _its(t);"
        self.ctx.add_init_script(init)
        self.voice_seconds = voice_seconds
        self.silent_voice = silent_voice
        self.ctx.route("http://localhost:8080/**", self._tts)
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
        if "/v1/ai/" in req.url or "/v1/images/" in req.url or "/v1/library" in req.url:
            return self._local_ai(route, cors)
        body = json.loads(req.post_data or "{}")
        self.tts_calls.append(body)
        secs = self.voice_seconds or min(3.0, 0.6 + 0.25 * len(body.get("input", "").split()))
        return route.fulfill(status=200, headers=cors, content_type="audio/wav",
                             body=wav_bytes(secs, amp=0.0 if self.silent_voice else 0.3))

    def _local_ai(self, route, cors):
        """Stand-in for the app's local AI endpoints (scene writer, picture creator, music library)."""
        import base64
        from PIL import Image
        url = route.request.url
        self.ai_calls.append((url.split("8080")[1], json.loads(route.request.post_data or "{}") if route.request.method == "POST" else None))
        if url.endswith("/v1/ai/status"):
            data = {"llm": {"available": True, "info": "fake"}, "images": {"available": True, "info": "fake"}}
        elif url.endswith("/v1/ai/scenes") and json.loads(route.request.post_data or "{}").get("background"):
            self.long_scenes = json.loads(route.request.post_data)["scenes"]
            return route.fulfill(status=202, headers=cors, content_type="application/json", body=json.dumps({"job": {"state": "running"}}))
        elif url.endswith("/v1/ai/jobs/scenes"):
            n = self.long_scenes
            data = {"state": "done", "result": {"script": "\n\n".join(f"# Scene {k}\nLine {k}." for k in range(1, n + 1)),
                                                "scenes": [{"title": f"Scene {k}", "line": f"Line {k}.", "image": f"picture {k}"} for k in range(1, n + 1)]}}
        elif url.endswith("/v1/ai/scenes"):
            data = {"script": "# Opening\nEvery product starts with an idea.\n\n# The turn\nCost becomes part of design.",
                    "scenes": [{"title": "Opening", "line": "Every product starts with an idea.", "image": "a design studio at dawn"},
                               {"title": "The turn", "line": "Cost becomes part of design.", "image": "engineers around a table"}]}
        elif url.endswith("/v1/images/generations"):
            buf = io.BytesIO()
            Image.new("RGB", (768, 432), (200, 120, 40)).save(buf, "PNG")
            data = {"data": [{"b64_json": base64.b64encode(buf.getvalue()).decode()}]}
        elif url.endswith("/v1/library"):
            data = {"music": [{"id": "corporate", "label": "Corporate — bright and positive"}], "sfx": []}
        elif "/v1/library/music/" in url:
            return route.fulfill(status=200, headers=cors, content_type="audio/wav", body=wav_bytes(4.0, freq=220, amp=0.4, rate=44100))
        else:
            return route.fulfill(status=404, headers=cors, body="")
        return route.fulfill(status=200, headers=cors, content_type="application/json", body=json.dumps(data))

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
        if fmt == "mp3" or (fmt == "mp4" and not self.page.evaluate("() => MediaRecorder.isTypeSupported('video/mp4')")):
            self.page.once("dialog", lambda dialog: dialog.accept())
        self.page.click("#exportBtn")
        self.page.wait_for_selector("#downloadLink", timeout=timeout)
        with self.page.expect_download() as d:
            self.page.click("#downloadLink")
        return d.value

    def toast(self, containing=None):
        """Text of the message box; with `containing`, wait until that message is shown (messages replace each other)."""
        if containing:
            try:
                self.page.wait_for_function("t => window.__toasts.some(x => x.includes(t))", arg=containing, timeout=15000)
            except Exception:
                raise AssertionError(f"message {containing!r} never shown; messages were {self.page.evaluate('window.__toasts')}, "
                                     f"console: {self.errors}") from None
            return next(x for x in self.page.evaluate("window.__toasts") if containing in x)
        else:
            self.page.wait_for_selector("#toast:not([hidden])")
        return self.page.text_content("#toast")

    def close(self):
        self.ctx.close()


@pytest.fixture
def studio(browser, base_url, request):
    opts = getattr(request, "param", {}) or {}
    s = Studio(browser, base_url, **opts)
    yield s
    errors = s.errors
    s.close()
    assert not errors, f"console errors: {errors}"


def media_seconds(path, stream=None):
    """Decoded length (WebM from MediaRecorder has no duration in its header, so decode it)."""
    cmd = [ffmpeg_bin(), "-hide_banner", "-i", str(path)]
    if stream:
        cmd += ["-map", stream]
    r = subprocess.run(cmd + ["-f", "null", "-"], capture_output=True, text=True)
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
    version = (ROOT / "VERSION").read_text().strip()
    p.wait_for_function("v => document.querySelector('#appVersion').textContent.includes(v)", arg=version)
    # headings are left-aligned
    assert p.evaluate("() => getComputedStyle(document.querySelector('h2')).textAlign") in ("left", "start")
    assert p.locator("#demoBtn").is_visible()
    assert "Not included offline" in p.text_content(".side-unavailable")
    assert not p.locator("#settingsBtn, input[type=password], [data-secret-field]").count()


def test_main_creation_prompt_builds_a_branded_project(browser, base_url, tmp_path, monkeypatch):
    from app import project as project_store

    monkeypatch.setattr(project_store, "PROJECTS_DIR", tmp_path / "projects")
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(f"{base_url}/")
        page.wait_for_selector("#app:not(.hidden)")
        assert page.title() == "Design to Cost — Presentation & Video Studio"
        assert page.locator(".brand .name").inner_text() == "Design to Cost"
        brief = "Explain how material choices affect the cost of our new product."
        page.fill("#creationPrompt", brief)
        page.click("#createForm button[type=submit]")
        page.wait_for_function("() => document.querySelectorAll('#slides .slide').length === 3")
        content = page.locator("#slides .slide:not(.cover)").first
        assert content.locator("input[data-k=title]").input_value() == "Explain how material choices affect the cost of our new product"
        assert content.locator("textarea[data-k=notes]").input_value() == brief
        assert content.locator("textarea[data-k=script]").input_value()
        assert page.locator(".sidebar-link[href='/studio/']").count() == 1
        assert not errors, errors
    finally:
        page.close()


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
    secs, info = media_seconds(out, "0:v:0")
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
    assert p.locator("#engine").locator("option").evaluate_all("(options) => options.map((option) => option.value)") == ["webspeech", "local"]


def test_narrated_sample_uses_original_picture_and_local_voice_in_video(studio, tmp_path):
    p = studio.page
    p.click("#demoBtn")
    p.wait_for_function("() => document.querySelectorAll('#scenes .scene').length === 3")
    p.wait_for_selector("#scenes .scene:first-child .thumb img")
    assert studio.project()["title"] == "Cost clarity — sample"
    assert studio.project()["scenes"][0]["background"]["kind"] == "image"
    p.wait_for_selector("#downloadLink", timeout=120_000)
    assert len(studio.tts_calls) == 3
    with p.expect_download() as download:
        p.click("#downloadLink")
    out = tmp_path / "sample.webm"
    download.value.save_as(out)
    seconds, info = media_seconds(out, "0:v:0")
    assert out.stat().st_size > 10_000
    assert seconds >= 8
    assert "Audio: opus" in info


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
    p.focus("#redoBtn")
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
    assert "not valid JSON" in studio.toast(containing="not valid JSON")
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
    secs, info = media_seconds(out, "0:v:0")     # the video track (newer FFmpeg reports the shortest track overall)
    assert "Video: h264" in info
    assert 2.5 < secs < 4.0, secs
    _, info = media_seconds(out)
    assert "Audio: aac" in info
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


def test_ai_writes_scenes_from_an_idea_and_creates_pictures(studio):
    p = studio.page
    p.click("#aiBox summary")
    p.fill("#aiIdea", "How designing with live material prices cut product cost")
    p.select_option("#aiLength", "custom")
    p.fill("#aiScenes", "2")
    p.click("#aiScenesBtn")
    p.wait_for_function("() => document.querySelector('#aiStudioStatus').textContent.includes('picture(s) created')", timeout=30000)
    proj = studio.project()
    assert [s["title"] for s in proj["scenes"]] == ["Opening", "The turn"]
    assert [s["imagePrompt"] for s in proj["scenes"]] == ["a design studio at dawn", "engineers around a table"]
    assert all(s["background"]["kind"] == "image" and s["background"]["mediaId"] for s in proj["scenes"])
    calls = [c[0] for c in studio.ai_calls]
    assert calls.count("/v1/images/generations") == 2
    sent = [c[1] for c in studio.ai_calls if c[0] == "/v1/ai/scenes"][0]
    assert sent["scenes"] == 2 and "material prices" in sent["idea"]
    prompts = [c[1]["prompt"] for c in studio.ai_calls if c[0] == "/v1/images/generations"]
    assert prompts == ["a design studio at dawn", "engineers around a table"]
    p.wait_for_selector("#scenes .scene:first-child .thumb img")
    # one more picture for a single scene, from an edited prompt
    box = studio.scenes().nth(1).locator("input[data-k=imagePrompt]")
    box.fill("a modern factory floor")
    studio.scenes().nth(1).locator("[data-act=picture]").click()
    p.wait_for_function("() => document.querySelector('#aiStudioStatus').textContent.includes('1 picture(s) created')")
    assert [c[1]["prompt"] for c in studio.ai_calls if c[0] == "/v1/images/generations"][-1] == "a modern factory floor"


def test_music_library_from_the_local_app(studio):
    p = studio.page
    p.wait_for_function("() => document.querySelectorAll('#libMood option').length > 1")
    p.select_option("#libMood", "corporate")
    p.click("#libUse")
    p.wait_for_function("() => document.querySelector('#musicName').textContent.includes('Corporate')")
    assert studio.project()["music"]["mediaId"]


def test_long_cinematic_video_from_a_prompt(studio):
    p = studio.page
    p.click("#aiBox summary")
    p.fill("#aiIdea", "An 3-minute cinematic story about designing with the full cost in view")
    p.select_option("#aiLength", "22")
    p.set_checked("#aiPictures", False)
    p.click("#aiScenesBtn")
    p.wait_for_function("() => document.querySelectorAll('#scenes .scene').length === 22", timeout=30000)
    proj = studio.project()
    assert proj["scenes"][21]["imagePrompt"] == "picture 22"
    assert 60 < studio.timeline()["total"] < 600              # long, and still within the 10-minute limit
    p.select_option("#aiLength", "custom")
    assert p.is_visible("#aiScenesField")
