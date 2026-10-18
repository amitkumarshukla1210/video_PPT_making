"""Windows built-in voices (Microsoft David / Zira, and Hindi Kalpana / Hemant if the Hindi
speech pack is installed) through pyttsx3. Used only as a fallback when Kokoro is not set up."""
import sys
import threading

NAME = "sapi"
LABEL = "Windows built-in voices (fallback)"
LICENCE = "pyttsx3 MPL-2.0; voices are Microsoft's (check their terms)"
_lock = threading.Lock()


def available():
    if sys.platform != "win32":
        return False, "Windows only"
    try:
        import pyttsx3  # noqa: F401
    except ImportError:
        return False, "pip package pyttsx3 not installed"
    return True, "SAPI5"


def _com_init():
    try:                              # SAPI runs on COM; each worker thread must initialise it
        import comtypes
        comtypes.CoInitialize()
    except Exception:
        pass


def voices():
    import pyttsx3
    _com_init()
    eng = pyttsx3.init()
    out = []
    for v in eng.getProperty("voices"):
        name = v.name or v.id
        gender = "female" if any(k in name for k in ("Zira", "Hazel", "Kalpana", "Heera", "Susan")) else "male"
        langs = [l.decode() if isinstance(l, bytes) else str(l) for l in (v.languages or [])]
        out.append({"id": v.id, "label": name, "lang": (langs[0] if langs else "").lower(), "gender": gender})
    eng.stop()
    return out


def synth(text, voice, lang, speed, out_path):
    import pyttsx3
    with _lock:                       # SAPI is not thread-safe
        _com_init()
        eng = pyttsx3.init()
        if voice:
            eng.setProperty("voice", voice)
        eng.setProperty("rate", int(175 * speed))
        eng.save_to_file(text, str(out_path))
        eng.runAndWait()
        eng.stop()
