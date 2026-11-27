"""Browser tests: the Make a video wizard from pasted text to a finished Reel, My projects, and the
Studio opening in light mode even when Windows is set to dark mode."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
pytest.importorskip("playwright.sync_api")

from app import project as P, tts  # noqa: E402
from app.ai import llm, images  # noqa: E402


@pytest.fixture
def page(browser, base_url, monkeypatch):     # fixtures from tests/conftest.py
    monkeypatch.setattr(llm, "status", lambda: {"available": False, "model": "x", "info": "Ollama is not running."})
    monkeypatch.setattr(images, "status", lambda: {"available": False, "info": "not installed"})
    ctx = browser.new_context(viewport={"width": 1366, "height": 900}, color_scheme="dark")
    p = ctx.new_page()
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.base = base_url
    yield p
    ctx.close()
    assert not errors, errors


@pytest.mark.skipif("espeak" not in [e["name"] for e in tts.status() if e["available"]], reason="needs eSpeak NG")
def test_wizard_text_to_reel_and_my_projects(page):
    p = page
    p.goto(p.base + "/make")
    p.wait_for_selector("body[data-ready=true]")
    assert p.is_disabled("#useAi") and "Ollama is not running" in p.text_content("#aiNote")
    p.click("label.kind:has(input[value=text])")
    assert p.is_visible("#text") and not p.is_visible("#files")
    p.fill("#text", "# Steel price\nSteel is up eight percent.\n\n# Next step\nAsk suppliers for new quotes.")
    p.fill("#name", "Wizard e2e")
    p.select_option("#vtype1", "reel")
    p.click("#go1")

    p.wait_for_selector("#step2:not(.hidden)", timeout=60_000)
    pid = p.evaluate("() => new URLSearchParams(location.search).get('p')")
    try:
        titles = p.eval_on_selector_all(".scene input[data-k=title]", "els => els.map(e => e.value)")
        assert titles[1:3] == ["Steel price", "Next step"]
        assert "4 scenes" not in p.text_content("#scriptStats") and "2 scenes" in p.text_content("#scriptStats")
        for ta in p.query_selector_all(".scene textarea"):
            ta.fill("Short line.")
        p.fill(".scene:nth-child(2) input[data-k=title]", "Steel up 8%")
        p.click("#go2")

        p.wait_for_selector("#step3:not(.hidden)")
        assert P.load(pid)["slides"][1]["title"] == "Steel up 8%"           # saved
        p.select_option("#engine", "espeak")
        p.click("#go3")

        p.wait_for_selector("#step4:not(.hidden)")
        assert p.is_checked("input[name=vtype][value=reel]")              # chosen in step 1
        p.wait_for_function("() => document.querySelector('#estimate').textContent.includes('Video length')")
        p.click("#go4")
        p.wait_for_selector("#result:not(.hidden) video", timeout=240_000)
        assert "Reel: Instagram · Facebook" in p.text_content("#result h3")
        assert p.get_attribute("#result video", "class") == "vertical"

        # My projects shows it, plays it, and links back to the wizard
        p.click(".sidebar-link[href='/projects']")
        p.wait_for_selector("body[data-ready=true]")
        card = p.locator(f"article.proj[data-id='{pid}']")
        assert "Reel: Instagram · Facebook · YouTube Shorts" in card.text_content()
        card.locator("[data-play]").first.click()
        p.wait_for_selector(".file-video video.vertical")
        p.fill("#search", "no such project zzz")
        assert "No project matches" in p.text_content("#list")
        p.fill("#search", "wizard e2e")
        assert p.locator(f"article.proj[data-id='{pid}']").count() == 1
        p.locator(f"article.proj[data-id='{pid}'] a", has_text="Continue").click()
        p.wait_for_selector("#step2:not(.hidden)")
        assert p.input_value(".scene:nth-child(2) input[data-k=title]") == "Steel up 8%"
    finally:
        P.delete(pid)


def test_studio_opens_white_even_in_windows_dark_mode(page):
    p = page
    p.goto(p.base + "/studio/")
    p.wait_for_selector("body[data-ready=true]")
    assert p.evaluate("() => document.documentElement.dataset.theme") == "light"
    bg = p.evaluate("() => getComputedStyle(document.body).backgroundColor")
    r, g, b = [int(x) for x in bg[bg.index("(") + 1:bg.index(")")].split(",")[:3]]
    assert min(r, g, b) > 200, bg
    assert p.locator(".side-link[href='/make']").count() == 1 and p.locator(".side-link[href='/projects']").count() == 1


def test_inspirations_gallery_to_wizard(page):
    p = page
    p.goto(p.base + "/inspirations")
    p.wait_for_selector("body[data-ready=true]")
    assert p.locator(".ex").count() == 100
    p.click(".chip[data-cat=music_video]")
    assert p.locator(".ex").count() == 11
    assert all("Music Video" in t for t in p.locator(".ex .ex-cat").all_text_contents())    # category label on each
    with p.expect_response(lambda r: "/inspirations/preview/hype-beat.mp4" in r.url, timeout=60_000) as resp:
        p.click(".ex-thumb[data-preview=hype-beat]")                 # ▶ on the picture plays the preview
    assert resp.value.status in (200, 206) and resp.value.headers["content-type"] == "video/mp4"
    assert p.evaluate("() => getComputedStyle(document.querySelector('#useVideo')).transform") == "none"   # not mirrored
    p.click("#useCancel")
    p.click("[data-use=hype-beat]")
    assert "Music Video · 9:16" in p.text_content("#useCat")
    p.fill("#useName", "Hype e2e")
    p.click("#useGo")
    p.wait_for_selector("#step2:not(.hidden)", timeout=30_000)
    pid = p.evaluate("() => new URLSearchParams(location.search).get('p')")
    try:
        titles = p.eval_on_selector_all(".scene input[data-k=title]", "els => els.map(e => e.value)")
        assert titles[1:5] == ["Bold", "Loud", "Limited", "Yours"]
        p.click("#go2")
        p.wait_for_selector("#step3:not(.hidden)")
        p.click("#go3")
        p.wait_for_selector("#step4:not(.hidden)")
        p.wait_for_function("() => document.querySelector('#look').value === 'bold'")
        assert p.is_checked("input[name=vtype][value=reel]") and p.is_checked("input[name=motion][value=motion]")
    finally:
        P.delete(pid)


def test_viral_preset_opens_tools_video(page):
    p = page
    p.goto(p.base + "/inspirations?cat=viral")
    p.wait_for_selector("body[data-ready=true]")
    assert p.locator(".ex").count() == 12
    assert "Use with my photo" in p.text_content("[data-use=v-polaroid]")
    p.click("[data-use=v-polaroid]")
    assert p.is_hidden("#useTopic")
    p.click("#useGo")
    p.wait_for_url("**/tools/video?preset=v-polaroid")
    p.wait_for_selector("body[data-ready=true]")
    assert p.input_value("#clipFx") == "polaroid" and p.input_value("#clipLook") == "warm"
    assert p.input_value("#clipTitle") == "Best day ever"


def test_my_pictures_tags_viewer_and_scene_picker(page, tmp_path, monkeypatch):
    from PIL import Image as PILImage
    from app import tools
    monkeypatch.setattr(tools, "MEDIA", tmp_path / "media")
    tools.save_ref("characters", "Shurpanakha", "glamorous woman")
    tools.save_ref("characters", "Ram", "prince with a bow")
    names = []
    for k, color in enumerate(("#a0522d", "#1f5fa8", "#2e8b57")):
        name = f"pic{k}.png"
        PILImage.new("RGB", (768, 432), color).save(tools._dir("images") / name)
        tools.set_picture(name, tags=["@Shurpanakha"] if k < 2 else [], prompt=f"prompt {k}")
        names.append(name)
    p = page
    p.goto(p.base + "/tools/image")
    p.wait_for_selector("body[data-ready=true]")
    assert "@Shurpanakha 2" in p.text_content("#imgFilters") and "No name yet 1" in p.text_content("#imgFilters")
    p.click("#imgFilters [data-filter='@Shurpanakha']")
    assert p.locator("#imageList .pic").count() == 2
    # full screen: click, arrows, Esc
    p.click("#imageList .pic img >> nth=0")
    assert p.is_visible("#viewer") and "@Shurpanakha" in p.text_content("#viewTags") and p.text_content("#viewCount") == "1 / 2"
    p.keyboard.press("ArrowRight")
    assert p.text_content("#viewCount") == "2 / 2"
    p.keyboard.press("Escape")
    assert p.is_hidden("#viewer")
    # name the untagged picture
    p.click("#imgFilters [data-filter='untagged']")
    p.select_option("#imageList select[data-addtag]", "@Ram")
    p.wait_for_function("() => document.querySelector('#imgFilters').textContent.includes('@Ram 1')")
    assert tools.picture_info("pic2.png")["tags"] == ["@Ram"]
    # use a character picture in a scene of Make a video
    from app import project as P
    pid = P.new_project("Picker e2e")["id"]
    try:
        p.goto(p.base + f"/make?p={pid}&step=2")
        p.wait_for_selector("#step2:not(.hidden)")
        p.click(".scene:nth-child(1) [data-mypic]")
        p.wait_for_selector("#picker:not(.hidden)")
        p.click("#pickerFilters [data-ptag='@Ram']")
        assert p.locator("#pickerGrid .pick").count() == 1
        p.click("#pickerGrid .pick")
        p.wait_for_selector("#picker.hidden", state="attached")
        p.wait_for_selector(".scene:nth-child(1) .scene-pic img")
        assert P.load(pid)["slides"][0]["image"].startswith("uploads/media_")
    finally:
        P.delete(pid)
