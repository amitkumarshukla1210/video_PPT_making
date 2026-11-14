"""Talks to Ollama (https://ollama.com, MIT licence), which runs an AI model on this laptop.

Default model: llama3.2:3b (Llama 3.2 Community Licence: commercial use allowed). If it is not
downloaded, a suitable model already in Ollama is used instead (e.g. qwen3.5:4b or qwen3:8b,
Apache-2.0). Force one with the environment variable DTC_LLM_MODEL."""
import json
import os
import re
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("DTC_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
MODEL = os.environ.get("DTC_LLM_MODEL", "llama3.2:3b")
FORCED = "DTC_LLM_MODEL" in os.environ
# used, in this order, when MODEL is not downloaded (smaller = faster on a laptop)
FALLBACKS = ("llama3.2", "qwen3.5:4b", "qwen3:4b", "qwen2.5:3b", "qwen2.5:7b", "qwen3.5", "qwen3:8b", "qwen3",
             "qwen2.5", "gemma3", "llama3.1", "llama3", "mistral", "phi4", "granite3")
_active = None


class LLMError(RuntimeError):
    pass


def _request(path, payload=None, timeout=5):
    """HTTP call to Ollama. Replaced in tests."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(OLLAMA_URL + path, data=data, headers={"Content-Type": "application/json"},
                                 method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def status():
    try:
        tags = _request("/api/tags", timeout=2)
    except (urllib.error.URLError, OSError, ValueError):
        return {"available": False, "model": MODEL,
                "info": "Ollama is not running. Install it once (install_once.bat ai) and keep it running."}
    global _active
    names = [m.get("name", "") for m in tags.get("models", [])]
    model = pick_model(names)
    if not model:
        return {"available": False, "model": MODEL, "models": names,
                "info": f"Ollama is running but the model {MODEL} is not downloaded. Run: ollama pull {MODEL}"}
    _active = model
    return {"available": True, "model": model, "models": names, "info": f"{model} via Ollama"}


def pick_model(names):
    """The configured model if downloaded, else the first suitable model already in Ollama."""
    if MODEL in names or f"{MODEL}:latest" in names:
        return MODEL
    if FORCED:
        return None
    chat = [n for n in names if "embed" not in n.lower()]
    for want in FALLBACKS:
        for n in chat:
            if n == want or n.startswith(want if ":" in want else want + ":") or n.startswith(want + "."):
                return n
    return None


def _model():
    return _active or status().get("model") or MODEL


_THINK = re.compile(r"<think>.*?</think>", re.S)


def generate(prompt, system="", json_mode=False, temperature=0.4, timeout=900):
    # think=False: Qwen 3 and similar models answer directly instead of "thinking" first (older Ollama ignores it)
    payload = {"model": _model(), "prompt": prompt, "system": system, "stream": False, "think": False,
               "options": {"temperature": temperature}}
    if json_mode:
        payload["format"] = "json"
    try:
        out = _request("/api/generate", payload, timeout=timeout)
    except (urllib.error.URLError, OSError) as e:
        raise LLMError(f"The local AI (Ollama) could not be reached: {e}") from e
    text = _THINK.sub("", (out or {}).get("response", "")).strip()
    if not text.strip():
        raise LLMError("The local AI returned an empty answer.")
    return text


def generate_json(prompt, system="", **kw):
    """Ask for JSON and parse it, tolerating code fences or text around the object."""
    text = generate(prompt, system, json_mode=True, **kw)
    try:
        return json.loads(text)
    except ValueError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except ValueError:
                pass
    raise LLMError("The local AI did not return valid JSON. Try again, or use the simple narration writer.")
