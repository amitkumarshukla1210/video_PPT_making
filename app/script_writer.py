"""Turn slide titles + notes into a first-draft narration (fully offline, rule-based).
The user then edits it in the UI. Stage 2 adds an optional local LLM (Ollama) rewrite."""
from . import layout as L

PHRASES = {
    "en": {
        "intro": "Welcome. In this walkthrough, I will show you {title}{sub}. "
                 "Let us look at how it helps us control cost from the design stage onwards.",
        "by": ", presented by {presenter}",
        "screen_only": "Here we see {title}. Take a moment to look at the key figures on the screen.",
        "first": "Let us start with {title}.",
        "next": ["Next, let us look at {title}.", "Moving on to {title}.", "Now we come to {title}."],
        "closing": "Thank you for watching this overview of {title}. "
                   "{notes} We would be happy to walk you through a live demo.",
    },
    "hi": {
        "intro": "नमस्कार। इस प्रस्तुति में हम {title}{sub} देखेंगे। "
                 "आइए देखें कि यह डिज़ाइन स्तर से ही लागत नियंत्रण में कैसे मदद करता है।",
        "by": ", प्रस्तुतकर्ता {presenter}",
        "screen_only": "यहाँ हम {title} देख रहे हैं। स्क्रीन पर मुख्य आँकड़ों पर ध्यान दें।",
        "first": "आइए {title} से शुरू करते हैं।",
        "next": ["अब देखते हैं {title}।", "आगे बढ़ते हैं {title} की ओर।"],
        "closing": "{title} का यह परिचय देखने के लिए धन्यवाद। {notes} लाइव डेमो के लिए हमसे संपर्क करें।",
    },
}


def _sentence(line):
    line = line.strip().rstrip(";,")
    if not line:
        return ""
    if line[-1] not in ".!?।":
        line += "."
    return line[0].upper() + line[1:]


def draft_script(proj, slide, index_in_content, lang=None):
    ph = PHRASES.get((lang or proj.get("language") or "en")[:2], PHRASES["en"])
    title = slide["title"].strip() or proj["title"]
    if slide["kind"] == "title":
        sub = ph["by"].format(presenter=proj["presenter"]) if proj.get("presenter") else ""
        return ph["intro"].format(title=title, sub=sub)
    if slide["kind"] == "closing":
        notes = _sentence(slide.get("notes", ""))
        return ph["closing"].format(title=proj["title"], notes=notes).replace("  ", " ")
    lines = L.bullets(slide.get("notes", ""), limit=20)
    if index_in_content == 0:
        opener = ph["first"].format(title=title)
    else:
        nxt = ph["next"]
        opener = nxt[index_in_content % len(nxt)].format(title=title)
    if not lines:
        return f"{opener} {ph['screen_only'].format(title=title)}"
    body = " ".join(_sentence(l) for l in lines)
    return f"{opener} {body}"


def draft_all(proj, overwrite=False):
    k = 0
    for s in proj["slides"]:
        if overwrite or not s.get("script", "").strip():
            s["script"] = draft_script(proj, s, k)
        if s["kind"] == "content":
            k += 1
    return proj


def script_text(proj):
    out = [f"NARRATION SCRIPT — {proj['title']}", ""]
    for i, s in enumerate(proj["slides"], 1):
        out += [f"[Slide {i}] {s['title']}", s.get("script", ""), ""]
    return "\n".join(out)
