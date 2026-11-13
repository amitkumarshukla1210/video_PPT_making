"""AI writing jobs on top of llm.py: corporate narration from slides, translation for dubbing,
and scene scripts + picture prompts for the Studio. Every function checks the AI's answer and
never invents slides; numbers and names must come from the user's own content."""
from . import llm

LANGS = {"en": "English", "hi": "Hindi", "ar": "Arabic", "da": "Danish", "de": "German", "el": "Greek",
         "es": "Spanish", "fi": "Finnish", "fr": "French", "he": "Hebrew", "it": "Italian", "ja": "Japanese",
         "ko": "Korean", "ms": "Malay", "nl": "Dutch", "no": "Norwegian", "pl": "Polish", "pt": "Portuguese",
         "ru": "Russian", "sv": "Swedish", "sw": "Swahili", "tr": "Turkish", "zh": "Chinese",
         "mr": "Marathi", "gu": "Gujarati", "ta": "Tamil", "te": "Telugu", "bn": "Bengali"}
CHUNK = 8   # slides per AI request; keeps answers short enough for a 3B model

SYSTEM_NARRATOR = (
    "You write voice-over scripts for corporate presentation videos. Tone: clear, confident, "
    "professional, friendly; short spoken sentences; no marketing hype; no emojis; no stage directions. "
    "Use ONLY the facts, numbers and names given in the slides. Never invent figures. Answer in JSON only.")


def lang_name(code):
    return LANGS.get((code or "en")[:2].lower(), "English")


def _slide_brief(i, s):
    kind = {"title": "Title slide", "closing": "Closing slide"}.get(s["kind"], "Slide")
    parts = [f"{i}. {kind}: {s.get('title') or ''}".strip()]
    if s.get("notes"):
        parts.append(f"   Points: {' | '.join(l.strip() for l in s['notes'].splitlines() if l.strip())}")
    if s.get("script"):
        parts.append(f"   Current narration: {s['script']}")
    return "\n".join(parts)


def write_narration(proj, language="en", overwrite=False, progress=lambda f, m: None):
    """Fill slide scripts with AI narration. Returns the number of slides written."""
    slides = proj["slides"]
    todo = [i for i, s in enumerate(slides) if overwrite or not (s.get("script") or "").strip()]
    if not todo:
        return 0
    deck = "\n".join(f"{i + 1}. {s.get('title', '')}" for i, s in enumerate(slides))
    about = ", ".join(v for v in (proj.get("title"), proj.get("subtitle"), proj.get("company")) if v)
    presenter = proj.get("presenter") or ""
    written = 0
    for c in range(0, len(todo), CHUNK):
        part = todo[c:c + CHUNK]
        progress(c / len(todo), f"AI writing narration for slides {part[0] + 1}–{part[-1] + 1} of {len(slides)}")
        brief = "\n".join(_slide_brief(i + 1, slides[i]) for i in part)
        prompt = (
            f"Presentation: {about}.\n" + (f"Presenter: {presenter}.\n" if presenter else "") +
            f"All slide titles, for flow:\n{deck}\n\n"
            f"Write the narration in {lang_name(language)} for these slides:\n{brief}\n\n"
            "Rules: title slide = a 2-sentence welcome naming the topic"
            + (" and the presenter" if presenter else "") + "; content slide = 2-4 sentences (40-70 words) that "
            "explain the points in plain words, linking to the previous slide where natural, do not read the bullets "
            "word for word; closing slide = a short thank-you and next step. "
            'Return JSON: {"slides": [{"n": <slide number>, "script": "<narration>"}]}')
        data = llm.generate_json(prompt, SYSTEM_NARRATOR)
        by_n = {}
        for item in data.get("slides", []) if isinstance(data, dict) else []:
            try:
                by_n[int(item.get("n"))] = str(item.get("script") or "").strip()
            except (TypeError, ValueError):
                continue
        for i in part:
            text = by_n.get(i + 1, "")
            if len(text.split()) >= 4:
                slides[i]["script"] = text
                written += 1
    progress(1, f"AI wrote narration for {written} slide(s)")
    return written


def translate(texts, language, progress=lambda f, m: None):
    """Translate a list of narration texts. Empty texts stay empty. Returns a list of the same length."""
    out = list(texts)
    idx = [i for i, t in enumerate(texts) if (t or "").strip()]
    target = lang_name(language)
    for c in range(0, len(idx), CHUNK):
        part = idx[c:c + CHUNK]
        progress(c / max(1, len(idx)), f"Translating into {target}: {c + len(part)}/{len(idx)}")
        items = "\n".join(f'{k + 1}. {texts[i]}' for k, i in enumerate(part))
        prompt = (f"Translate each numbered voice-over text into natural spoken {target} for a corporate video. "
                  "Keep numbers, product names and company names exactly. Keep the meaning; no additions.\n\n"
                  f"{items}\n\n"
                  'Return JSON: {"items": [{"n": <number>, "text": "<translation>"}]}')
        data = llm.generate_json(prompt, "You are a professional translator. Answer in JSON only.", temperature=0.2)
        got = {}
        for item in data.get("items", []) if isinstance(data, dict) else []:
            try:
                got[int(item.get("n"))] = str(item.get("text") or "").strip()
            except (TypeError, ValueError):
                continue
        for k, i in enumerate(part):
            if not got.get(k + 1):
                raise llm.LLMError(f"The local AI skipped text {i + 1}. Please try the translation again.")
            out[i] = got[k + 1]
    return out


def scenes_from_prompt(idea, template="inspiration", scenes=5, language="en", style=""):
    """A Studio script ('# Title' + one spoken line per scene) plus one picture prompt per scene."""
    scenes = max(2, min(12, int(scenes or 5)))
    prompt = (
        f"Idea for a short {template} video: {idea}\n"
        f"Write {scenes} scenes in {lang_name(language)}. Each scene: a short on-screen title (max 6 words), "
        "a spoken line (1-2 sentences, max 30 words), and an English picture prompt for an image generator "
        f"(cinematic, concrete subject, setting, light; no text in the image{'; style: ' + style if style else ''}). "
        'Return JSON: {"scenes": [{"title": "...", "line": "...", "image": "..."}]}')
    data = llm.generate_json(prompt, "You are a film scriptwriter for short corporate and cinematic videos. Answer in JSON only.",
                             temperature=0.7)
    out = []
    for sc in data.get("scenes", []) if isinstance(data, dict) else []:
        title = str(sc.get("title") or "").strip()
        line = str(sc.get("line") or "").strip()
        if line:
            out.append({"title": title, "line": line, "image": str(sc.get("image") or title or line).strip()})
    if len(out) < 2:
        raise llm.LLMError("The local AI did not return usable scenes. Try a more specific idea.")
    script = "\n\n".join(f"# {s['title']}\n{s['line']}" if s["title"] else s["line"] for s in out)
    return {"script": script, "scenes": out}
