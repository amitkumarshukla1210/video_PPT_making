"""Stand-alone worker for the voice clone (Chatterbox Multilingual, MIT licence).

It runs inside its own Python environment (.venv-clone) because Chatterbox needs PyTorch and
pinned libraries that would clash with the main app. The app calls:

    python clone_worker.py job.json

job.json = {"ref": "my_voice.wav", "lang": "en", "exaggeration": 0.45, "cfg": 0.5,
            "items": [{"text": "...", "out": "slide_000.raw.wav"}, ...]}
Prints "PROGRESS <done> <total>" lines so the app can show progress.
Loads the model once for the whole batch. Needs no internet after the first download.
"""
import json
import os
import re
import sys
import wave
from pathlib import Path

MAX_CHARS = 280   # Chatterbox sounds best on short chunks


def chunks(text):
    parts = [p.strip() for p in re.split(r"(?<=[.!?।;:])\s+", text) if p.strip()]
    out, cur = [], ""
    for p in parts:
        if len(cur) + len(p) + 1 <= MAX_CHARS:
            cur = f"{cur} {p}".strip()
        else:
            if cur:
                out.append(cur)
            while len(p) > MAX_CHARS:                 # very long sentence: split at a comma or space
                cut = max(p.rfind(",", 0, MAX_CHARS), p.rfind(" ", 0, MAX_CHARS))
                cut = cut if cut > 40 else MAX_CHARS
                out.append(p[:cut].strip(" ,"))
                p = p[cut:].strip(" ,")
            cur = p
    if cur:
        out.append(cur)
    return out


def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    hf_home = Path(os.environ.get("HF_HOME", ""))
    if (hf_home / "hub" / "models--ResembleAI--chatterbox").exists():
        os.environ["HF_HUB_OFFLINE"] = "1"            # already downloaded: never touch the internet

    import numpy as np
    import torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"DEVICE {device}", flush=True)
    model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    model.prepare_conditionals(job["ref"], exaggeration=job.get("exaggeration", 0.45))

    items = job["items"]
    gap = np.zeros(int(model.sr * 0.18), dtype=np.float32)
    for n, item in enumerate(items):
        pieces = []
        for c in chunks(item["text"]):
            wav = model.generate(c, language_id=job.get("lang", "en"), audio_prompt_path=None,
                                 exaggeration=job.get("exaggeration", 0.45), cfg_weight=job.get("cfg", 0.5))
            pieces += [wav.squeeze(0).cpu().numpy().astype(np.float32), gap]
        audio = np.concatenate(pieces) if pieces else gap
        pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
        with wave.open(item["out"], "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(model.sr)
            w.writeframes(pcm.tobytes())
        print(f"PROGRESS {n + 1} {len(items)}", flush=True)


if __name__ == "__main__":
    main()
