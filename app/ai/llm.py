"""Talks to Ollama (https://ollama.com, MIT licence), which runs an AI model on this laptop.

Default model: llama3.2:3b (Llama 3.2 Community Licence: commercial use allowed). Change it with the
environment variable DTC_LLM_MODEL, e.g. "qwen2.5:7b" (Apache-2.0) on a faster laptop."""
import json
import os
import re
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("DTC_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
MODEL = os.environ.get("DTC_LLM_MODEL", "llama3.2:3b")


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
    names = [m.get("name", "") for m in tags.get("models", [])]
    if MODEL not in names and f"{MODEL}:latest" not in names:
        return {"available": False, "model": MODEL, "models": names,
                "info": f"Ollama is running but the model {MODEL} is not downloaded. Run: ollama pull {MODEL}"}
    return {"available": True, "model": MODEL, "models": names, "info": f"{MODEL} via Ollama"}


def generate(prompt, system="", json_mode=False, temperature=0.4, timeout=900):
    payload = {"model": MODEL, "prompt": prompt, "system": system, "stream": False,
               "options": {"temperature": temperature}}
    if json_mode:
        payload["format"] = "json"
    try:
        out = _request("/api/generate", payload, timeout=timeout)
    except (urllib.error.URLError, OSError) as e:
        raise LLMError(f"The local AI (Ollama) could not be reached: {e}") from e
    text = (out or {}).get("response", "")
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
