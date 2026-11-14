"""Make a video (source -> script -> voice -> video type) and My projects."""
import io
import sys
import time
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from app import project as P, sources, maker  # noqa: E402
from app.ai import llm  # noqa: E402
from app.main import app  # noqa: E402
from tests.test_ai import FakeOllama  # noqa: E402
from tests.test_pipeline import _duration  # noqa: E402

HTML = """<html><head><title>Pump cost study</title><script>var x=1;</script></head><body>
<nav>Home | About</nav>
<h1>Why the pump was too expensive</h1><p>The housing was cast iron and machined on five faces, which made it slow.</p>
<ul><li>Steel price rose 8 percent this quarter.</li><li>Machining time was 42 minutes.</li></ul>
<h2>What we changed</h2><p>We moved to a die-cast aluminium housing with only two machined faces.</p>
<footer>Copyright</footer></body></html>"""


def _docx(path):
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = ('<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Supplier review</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Three suppliers were compared on landed cost and lead time.</w:t></w:r></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Decision</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Supplier B wins with the lowest landed cost and a 4 week lead time.</w:t></w:r></w:p>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f'<?xml version="1.0"?><w:document {w}><w:body>{body}</w:body></w:document>')


def _pdf(path):
    pages = [Image.new("RGB", (800, 600), c) for c in ("#1f5fa8", "#e07b1f")]
    pages[0].save(path, save_all=True, append_images=pages[1:])


@pytest.fixture
def client():
    app.config["TESTING"] = True
    made = []
    c = app.test_client()
    c.made = made
    yield c
    for pid in made:
        P.delete(pid)


def _new(c, name="Make test"):
    pid = c.post("/api/projects", json={"name": name}).get_json()["id"]
    c.made.append(pid)
    c.put(f"/api/projects/{pid}", json={"voice": {"engine": "espeak", "voice": "en-us", "lang": "en-us", "speed": 1.0}})
    return pid


def _wait(c, pid, key="ai", timeout=240):
    t = time.time()
    while time.time() - t < timeout:
        j = c.get(f"/api/projects/{pid}/job").get_json()
        j = j[key] if key else j
        if j["state"] in ("done", "error", "cancelled"):
            return j
        time.sleep(0.3)
    raise AssertionError("job did not finish")


# ---------- reading sources ----------
def test_html_sections_skip_menus_and_scripts():
    title, secs = sources.html_sections(HTML)
    assert title == "Pump cost study"
    assert [s["title"] for s in secs] == ["Why the pump was too expensive", "What we changed"]
    text = sources.sections_to_text(secs)
    assert "Steel price rose 8 percent" in text and "var x" not in text and "Copyright" not in text and "Home |" not in text


def test_text_and_docx_sections(tmp_path):
    secs = sources.text_sections("# Cost drivers\nSteel is up 8%.\nForex adds 2%.\n\nNext steps\n\nAsk suppliers for new quotes.")
    assert [s["title"] for s in secs] == ["Cost drivers", "Next steps"]
    _docx(tmp_path / "a.docx")
    d = sources.docx_sections(tmp_path / "a.docx")
    assert [s["title"] for s in d] == ["Supplier review", "Decision"] and "lowest landed cost" in d[1]["text"][0]


def test_url_must_be_http():
    with pytest.raises(ValueError, match="http"):
        sources.fetch_url("file:///etc/passwd")


# ---------- step 1: source -> scenes + script ----------
def test_document_upload_without_ai_makes_scenes_and_script(client, tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "status", lambda: {"available": False, "info": "off"})
    pid = _new(client)
    _pdf(tmp_path / "deck.pdf")
    _docx(tmp_path / "notes.docx")
    (tmp_path / "page.html").write_text(HTML, encoding="utf-8")
    files = [(open(tmp_path / n, "rb"), n) for n in ("deck.pdf", "notes.docx", "page.html")]
    r = client.post(f"/api/projects/{pid}/source", data={"kind": "document", "files": files, "ai": "1", "scenes": "8"},
                    content_type="multipart/form-data")
    assert r.status_code == 200
    j = _wait(client, pid)
    assert j["state"] == "done", j
    assert j["result"]["ai"] is False and j["result"]["slides"] == 2 + 2 + 2   # 2 PDF pages, 2 Word, 2 HTML sections
    proj = P.load(pid)
    content = [s for s in proj["slides"] if s["kind"] == "content"]
    assert content[0]["image"].startswith("uploads/page_01") and (P.folder(pid) / content[0]["image"]).exists()
    assert all(s["script"].strip() for s in proj["slides"])          # every scene has a first-draft script
    assert any("landed cost" in s["notes"] for s in content)
    assert proj["title"] == "Pump cost study"
    assert all("source_text" not in s for s in proj["slides"])


def test_link_with_local_ai_writes_scene_by_scene(client, monkeypatch):
    fake = FakeOllama()
    monkeypatch.setattr(llm, "_request", fake)
    monkeypatch.setattr(sources, "fetch_url", lambda url: (HTML, "text/html; charset=utf-8"))
    pid = _new(client)
    r = client.post(f"/api/projects/{pid}/source", data={"kind": "url", "url": "https://example.com/pump",
                                                          "video_type": "reel", "scenes": "5", "language": "en"})
    assert r.status_code == 200
    j = _wait(client, pid)
    assert j["state"] == "done", j
    assert j["result"]["ai"] is True
    doc_prompt = next(p for p in fake.prompts if "Document — Pump cost study" in p)
    assert "Steel price rose 8 percent" in doc_prompt and "Instagram" in doc_prompt and "max 18 words" in doc_prompt
    content = [s for s in P.load(pid)["slides"] if s["kind"] == "content"]
    assert [s["title"] for s in content] == ["Opening", "The turn"]
    assert content[0]["script"] == "Every product starts with an idea." and content[0]["image_prompt"]


def test_source_errors_are_clear(client, monkeypatch):
    monkeypatch.setattr(llm, "status", lambda: {"available": False, "info": "Ollama is not running."})
    pid = _new(client)
    assert "Add at least one file" in client.post(f"/api/projects/{pid}/source", data={"kind": "pptx"}).get_json()["error"]
    assert "web link" in client.post(f"/api/projects/{pid}/source", data={"kind": "url"}).get_json()["error"]
    r = client.post(f"/api/projects/{pid}/source", data={"kind": "idea", "text": "A cost story"})
    assert r.status_code == 400 and "Ollama" in r.get_json()["error"]
    bad = client.post(f"/api/projects/{pid}/source", data={"kind": "pictures", "files": [(io.BytesIO(b"x"), "a.exe")]},
                      content_type="multipart/form-data")
    assert bad.status_code == 400 and ".exe" in bad.get_json()["error"]


# ---------- step 4: video type -> finished video, kept in My projects ----------
def test_reel_and_corporate_videos_are_kept_in_my_projects(client, monkeypatch):
    monkeypatch.setattr(llm, "status", lambda: {"available": False, "info": "off"})
    pid = _new(client, "Reel test")
    r = client.post(f"/api/projects/{pid}/source", data={"kind": "text", "text": "# Steel\nSteel is up eight percent this quarter."})
    assert r.status_code == 200 and _wait(client, pid)["state"] == "done"
    proj = P.load(pid)
    for s in proj["slides"]:
        s["script"] = "Short line."                     # keep the test render fast
    P.save(proj)

    r = client.post(f"/api/projects/{pid}/make_video", json={"type": "reel", "captions": True, "music": "auto"})
    assert r.status_code == 200
    j = _wait(client, pid, key=None)
    assert j["state"] == "done", j
    res = j["result"]
    assert res["file"].startswith("reel_") and res["video"].endswith(res["file"])
    assert "1080x1920" in _duration(P.folder(pid) / "out" / res["file"])[1]
    assert P.load(pid)["music"]["library"] == "tech" and P.load(pid)["video_type"] == "reel"

    r = client.post(f"/api/projects/{pid}/make_video", json={"type": "corporate", "captions": False, "music": "none"})
    j = _wait(client, pid, key=None)
    assert j["state"] == "done", j
    assert P.load(pid)["intro"] is True and P.load(pid)["music"]["file"] is None
    assert "1920x1080" in _duration(P.folder(pid) / "out" / j["result"]["file"])[1]

    lib = {p["id"]: p for p in client.get("/api/my_projects").get_json()}[pid]
    labels = [f["label"] for f in lib["files"] if f["kind"] == "mp4"]
    assert "Corporate video" in labels and "Instagram Reel / YouTube Shorts" in labels
    assert lib["files"][0]["name"].startswith("corporate_")              # newest first
    assert client.get(lib["files"][0]["url"]).status_code == 200
    assert lib["slides"] == 1 and lib["modified"]


def test_make_video_checks(client):
    pid = _new(client)
    assert client.post(f"/api/projects/{pid}/make_video", json={"type": "tiktok"}).status_code == 400
    proj = P.load(pid)
    for s in proj["slides"]:
        s["script"] = ""
    P.save(proj)
    r = client.post(f"/api/projects/{pid}/make_video", json={"type": "youtube"})
    assert r.status_code == 400 and "narration" in r.get_json()["error"]


def test_pages_load(client):
    for path, text in (("/make", "Make a video"), ("/projects", "My projects"), ("/", "Make a video")):
        r = client.get(path)
        assert r.status_code == 200 and text in r.get_data(as_text=True)
    assert 'href="/#s-project"' in client.get("/make").get_data(as_text=True)     # sidebar links back to the workspace


def test_file_labels():
    assert maker._file_label("reel_2026-11-14_101010.mp4") == "Instagram Reel / YouTube Shorts"
    assert maker._file_label("video.mp4") == "Video (latest render)"
    assert maker._file_label("reels_slides_2-3.mp4") == "Short clip 9:16"
