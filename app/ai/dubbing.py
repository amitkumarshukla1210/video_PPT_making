"""Dubbing: a translated copy of a Presentation project, voiced in the chosen language.
The copy is a normal project, so you can read and correct the translation before rendering."""
import copy
import shutil

from .. import project as P, tts
from . import writer


def pick_voice(proj, language):
    """Engine + voice for `language`: your cloned voice if you have a sample, else a stock voice."""
    lang = (language or "en")[:2].lower()
    clone = tts.ENGINES["clone"]
    if proj.get("voice_sample") and clone.available()[0] and any(v["id"] == lang for v in clone.voices()):
        return {"engine": "clone", "voice": lang, "lang": lang}
    for name in ("kokoro", "piper", "sapi", "espeak"):
        e = tts.ENGINES[name]
        if not e.available()[0]:
            continue
        current = proj.get("voice", {})
        voices = [v for v in e.voices() if (v.get("lang") or "").lower().startswith(lang)]
        if voices:
            same_gender = [v for v in voices if v.get("gender") and v.get("gender") == _gender(current)]
            v = (same_gender or voices)[0]
            return {"engine": name, "voice": v["id"], "lang": v["lang"]}
    raise RuntimeError(f"No installed voice speaks {writer.lang_name(lang)}. Record your voice sample for the "
                       "voice clone (it speaks 23 languages), or install Piper voices for that language.")


def _gender(voice):
    for e in tts.ENGINES.values():
        try:
            for v in e.voices() if e.available()[0] else []:
                if v["id"] == voice.get("voice"):
                    return v.get("gender", "")
        except Exception:
            continue
    return ""


def make_dub(proj, language, progress=lambda f, m: None):
    """Create and return the translated project."""
    lang = (language or "hi")[:2].lower()
    voice = pick_voice(proj, lang)
    texts = [s.get("script") or "" for s in proj["slides"]]
    titles = [s.get("title") or "" for s in proj["slides"]]
    progress(0.05, f"Translating the narration into {writer.lang_name(lang)}")
    new_scripts = writer.translate(texts, lang, lambda f, m: progress(0.05 + f * 0.6, m))
    progress(0.7, "Translating slide titles")
    new_titles = writer.translate(titles, lang)
    src = P.folder(proj["id"])
    dub = P.new_project(f"{proj['name']} ({writer.lang_name(lang)})")
    dst = P.folder(dub["id"])
    if (src / "uploads").exists():
        shutil.copytree(src / "uploads", dst / "uploads", dirs_exist_ok=True)
    data = copy.deepcopy(proj)
    data["id"], data["name"], data["created"] = dub["id"], dub["name"], dub["created"]
    data["title"] = new_titles[0] or proj.get("title", "")
    data["language"] = lang
    data["voice"] = {**proj.get("voice", {}), **voice}
    data["dubbed_from"] = proj["id"]
    for s, script, title in zip(data["slides"], new_scripts, new_titles):
        s["script"], s["title"] = script, title or s["title"]
        # a recording speaks the original language; the dub uses the translated voice-over instead
        s["clip"], s["clip_seconds"] = None, 0
    P.save(data)
    progress(1, f"Created “{data['name']}”")
    return data
