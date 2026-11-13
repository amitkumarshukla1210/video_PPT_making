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


MAX_SCENES = 60          # ~8 minutes at ~8 s per scene; the Studio's limit is 10 minutes
SCENE_CHUNK = 8          # scenes per AI request for long videos


def _scene_items(data):
    out = []
    for sc in data.get("scenes", []) if isinstance(data, dict) else []:
        title = str(sc.get("title") or "").strip()
        line = str(sc.get("line") or "").strip()
        if line:
            out.append({"title": title, "line": line, "image": str(sc.get("image") or title or line).strip()})
    return out


def scenes_from_prompt(idea, template="inspiration", scenes=5, language="en", style="", progress=lambda f, m: None):
    """A Studio script ('# Title' + one spoken line per scene) plus one picture prompt per scene.
    Long videos (more than SCENE_CHUNK scenes): the AI first writes a story outline, then the scenes
    in parts, each part seeing the outline and the previous scene, so the story stays consistent."""
    scenes = max(2, min(MAX_SCENES, int(scenes or 5)))
    system = ("You are a film scriptwriter for cinematic and corporate videos. Strong visual storytelling, "
              "a clear arc (hook, build-up, turning point, resolution, call to action). Answer in JSON only.")
    look = f"; visual style for every picture: {style}" if style else ""
    scene_rules = (f"Each scene: a short on-screen title (max 6 words), a spoken line in {lang_name(language)} "
                   "(1-2 sentences, max 30 words), and an English picture prompt for an image generator "
                   f"(cinematic, concrete subject, setting, camera angle, light; no text in the image{look}). ")
    if scenes <= SCENE_CHUNK:
        prompt = (f"Idea for a short {template} video: {idea}\nWrite {scenes} scenes. " + scene_rules +
                  'Return JSON: {"scenes": [{"title": "...", "line": "...", "image": "..."}]}')
        out = _scene_items(llm.generate_json(prompt, system, temperature=0.7))
    else:
        progress(0.02, f"Planning the story: {scenes} scenes")
        plan = llm.generate_json(
            f"Idea for a {template} video of {scenes} scenes: {idea}\n"
            f"Write a story outline: exactly {scenes} numbered beats, one short sentence each, forming one arc "
            "(hook, build-up, turning point, resolution, call to action). Keep one consistent main character, "
            "place and look throughout." + (f" Visual style: {style}." if style else "") +
            ' Return JSON: {"beats": ["...", "..."]}', system, temperature=0.7)
        beats = [str(b).strip() for b in (plan.get("beats") or []) if str(b).strip()] if isinstance(plan, dict) else []
        if len(beats) < scenes // 2:
            raise llm.LLMError("The local AI could not plan the story. Try again, or a shorter video.")
        beats = (beats + beats[-1:] * scenes)[:scenes]
        outline = "\n".join(f"{k + 1}. {b}" for k, b in enumerate(beats))
        out = []
        for c in range(0, scenes, SCENE_CHUNK):
            part = list(range(c, min(scenes, c + SCENE_CHUNK)))
            progress(0.05 + 0.95 * c / scenes, f"Writing scenes {part[0] + 1}–{part[-1] + 1} of {scenes}")
            prev = f'Previous scene: "{out[-1]["line"]}"\n' if out else ""
            prompt = (f"Video idea: {idea}\nFull outline:\n{outline}\n\n{prev}"
                      f"Write scenes {part[0] + 1} to {part[-1] + 1} only, one per outline beat, continuing smoothly. "
                      + scene_rules +
                      'Return JSON: {"scenes": [{"title": "...", "line": "...", "image": "..."}]}')
            got = _scene_items(llm.generate_json(prompt, system, temperature=0.7))
            if not got:
                raise llm.LLMError(f"The local AI skipped scenes {part[0] + 1}–{part[-1] + 1}. Please try again.")
            out += got[:len(part)]
    if len(out) < 2:
        raise llm.LLMError("The local AI did not return usable scenes. Try a more specific idea.")
    script = "\n\n".join(f"# {s['title']}\n{s['line']}" if s["title"] else s["line"] for s in out)
    return {"script": script, "scenes": out}
