"""Turn what you bring (PowerPoint, pictures, PDF, Word, text, an HTML file or a web link) into the
slides of a project, ready for a script. Everything runs on this laptop; a web link is only fetched
from that address, nothing is sent anywhere."""
import html
import re
import urllib.request
import uuid
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from .project import add_content_slide, folder

PICTURE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
TEXT_EXT = {".txt", ".md"}
HTML_EXT = {".html", ".htm"}
DOC_EXT = {".pdf", ".docx", ".pptx"} | TEXT_EXT | HTML_EXT
MAX_PAGES = 60
MAX_CHARS = 60_000
MAX_DOWNLOAD = 5 * 1024 * 1024


# ---------- reading text ----------
class _Html(HTMLParser):
    """Keeps the title, headings, paragraphs and list items; skips scripts, menus and footers."""
    SKIP = {"script", "style", "noscript", "nav", "footer", "header", "svg", "form", "aside"}
    BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "td", "blockquote", "dd", "dt", "pre", "div", "section", "article"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.title = ""
        self.in_title = False
        self.blocks = []        # (tag, text)
        self.buf = []
        self.tag = "p"

    def _flush(self):
        t = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        if t:
            self.blocks.append((self.tag, t))
        self.buf = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "title":
            self.in_title = True
        elif tag in self.BLOCK or tag == "br":
            self._flush()
            if tag in self.BLOCK:
                self.tag = tag

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag == "title":
            self.in_title = False
        elif tag in self.BLOCK:
            self._flush()
            self.tag = "p"

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skip:
            self.buf.append(data)


def html_sections(text):
    p = _Html()
    p.feed(text)
    p.close()
    p._flush()
    sections, cur = [], None
    for tag, t in p.blocks:
        if tag in ("h1", "h2", "h3"):
            cur = {"title": t[:90], "text": []}
            sections.append(cur)
        elif len(t) > 25 or tag == "li":
            if cur is None:
                cur = {"title": html.unescape(p.title.strip())[:90] or "Overview", "text": []}
                sections.append(cur)
            cur["text"].append(t)
    return html.unescape(p.title.strip()), [s for s in sections if s["text"]]


def text_sections(text):
    """Plain text / Markdown: '#' lines or short lines followed by a blank line start a section."""
    sections, cur = [], None
    for block in re.split(r"\n\s*\n", text.replace("\r", "")):
        lines = [ln.strip() for ln in block.strip().split("\n") if ln.strip()]
        if not lines:
            continue
        first = lines[0]
        heading = first.startswith("#") or (len(lines) == 1 and len(first) < 70 and not first.endswith("."))
        if heading:
            cur = {"title": first.lstrip("#").strip()[:90], "text": []}
            sections.append(cur)
            lines = lines[1:]
        if lines:
            if cur is None:
                cur = {"title": "Overview", "text": []}
                sections.append(cur)
            cur["text"] += [ln.lstrip("-*• ").strip() for ln in lines]
    return [s for s in sections if s["text"]]


def docx_sections(path):
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as z:
        root = ElementTree.fromstring(z.read("word/document.xml"))
    sections, cur = [], None
    for p in root.iter(f"{{{ns['w']}}}p"):
        t = "".join(x.text or "" for x in p.iter(f"{{{ns['w']}}}t")).strip()
        if not t:
            continue
        style = p.find("w:pPr/w:pStyle", ns)
        sval = (style.get(f"{{{ns['w']}}}val") if style is not None else "") or ""
        if sval.lower().startswith(("heading", "title")):
            cur = {"title": t[:90], "text": []}
            sections.append(cur)
        else:
            if cur is None:
                cur = {"title": "Overview", "text": []}
                sections.append(cur)
            cur["text"].append(t)
    return [s for s in sections if s["text"]]


def fetch_url(url):
    if not re.match(r"^https?://", url or "", re.I):
        raise ValueError("The link must start with http:// or https://")
    req = urllib.request.Request(url, headers={"User-Agent": "DesignToCost-Studio/1.5 (offline video maker)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        ctype = r.headers.get("content-type", "")
        data = r.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError("That page is too large (over 5 MB).")
    charset = (re.search(r"charset=([\w-]+)", ctype) or [None, "utf-8"])[1]
    return data.decode(charset, errors="replace"), ctype


def _bullets(lines, n=5):
    """Short on-slide points from the section text."""
    out = []
    for ln in lines:
        for s in re.split(r"(?<=[.!?])\s+", ln):
            s = s.strip()
            if 12 <= len(s) <= 160:
                out.append(s.rstrip("."))
            if len(out) >= n:
                return out
    return out


def sections_to_text(sections):
    return "\n\n".join(f"## {s['title']}\n" + "\n".join(s["text"]) for s in sections)[:MAX_CHARS]


# ---------- building slides ----------
def add_pictures(proj, paths):
    base = folder(proj["id"])
    for p in sorted(paths, key=lambda p: Path(p).name.lower()):
        add_content_slide(proj, _title_from(Path(p).name), "", str(Path(p).relative_to(base)).replace("\\", "/"))
    return len(paths)


def _title_from(name):
    stem = re.sub(r"^\d+[\s_.-]*", "", Path(name).stem)
    stem = re.sub(r"[_-]+", " ", stem).strip()
    stem = re.sub(r"^(shot|doc) [0-9a-f]{6} ", "", stem)
    return stem[:1].upper() + stem[1:] if stem else "Picture"


def add_pdf(proj, path):
    """Each page becomes a slide: the page picture, and its text as notes for the script."""
    import pypdfium2 as pdfium
    base = folder(proj["id"])
    doc = pdfium.PdfDocument(str(path))
    n = 0
    try:
        for i in range(min(len(doc), MAX_PAGES)):
            page = doc[i]
            w = page.get_width()
            img = page.render(scale=max(1.0, 1600 / max(w, 1))).to_pil()
            name = f"uploads/page_{i + 1:02d}_{uuid.uuid4().hex[:4]}.png"
            img.convert("RGB").save(base / name)
            text = page.get_textpage().get_text_range().replace("\r", "")
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            title = (lines[0] if lines else f"Page {i + 1}")[:90]
            s = add_content_slide(proj, title, "", name)
            s["source_text"] = "\n".join(lines[1:])[:3000]
            n += 1
    finally:
        doc.close()
    return n


def add_sections(proj, sections, max_slides=20):
    """Text sources without AI: one slide per section, with short points."""
    n = 0
    for s in sections[:max_slides]:
        sl = add_content_slide(proj, s["title"], "\n".join(_bullets(s["text"])))
        sl["source_text"] = "\n".join(s["text"])[:3000]
        n += 1
    return n


def add_scenes(proj, scenes):
    """Slides from AI scenes: title, on-slide points, narration and a picture prompt."""
    for sc in scenes:
        sl = add_content_slide(proj, sc["title"] or "Scene", "\n".join(sc.get("points") or []))
        sl["script"] = sc["line"]
        sl["image_prompt"] = sc.get("image", "")
    return len(scenes)


def read_text_source(kind, path=None, url=None, text=None):
    """Returns (title, sections) for a document, web page or pasted text."""
    if kind == "url":
        body, ctype = fetch_url(url)
        if "html" in ctype or "<html" in body[:2000].lower():
            return html_sections(body)
        return "", text_sections(body)
    if kind == "text":
        return "", text_sections(text or "")
    ext = Path(path).suffix.lower()
    if ext in HTML_EXT:
        return html_sections(Path(path).read_text(encoding="utf-8", errors="replace"))
    if ext == ".docx":
        return "", docx_sections(path)
    return "", text_sections(Path(path).read_text(encoding="utf-8", errors="replace"))
