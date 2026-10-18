"""One-time download of the offline voice models (needs internet ONCE; afterwards everything is offline).

  python scripts/download_models.py            Kokoro full quality (~340 MB)
  python scripts/download_models.py --small    Kokoro int8, faster on old laptops (~115 MB)
  python scripts/download_models.py --piper    also a few Piper voices for extra languages
"""
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KOKORO = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
PIPER = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"

# Piper voices: check each voice's MODEL_CARD on huggingface.co/rhasspy/piper-voices before monetised use.
PIPER_VOICES = [
    "en/en_US/ryan/high/en_US-ryan-high",
    "en/en_US/amy/medium/en_US-amy-medium",
    "hi/hi_IN/pratham/medium/hi_IN-pratham-medium",
    "hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium",
    "de/de_DE/thorsten/high/de_DE-thorsten-high",
    "ar/ar_JO/kareem/medium/ar_JO-kareem-medium",
]


def fetch(url, dest):
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  ✔ already have {dest.name}")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"  ↓ {dest.name}")
    try:
        with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while chunk := r.read(1 << 20):
                f.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r    {done / 1e6:6.1f} / {total / 1e6:.1f} MB", end="", flush=True)
        print()
        tmp.replace(dest)
        return True
    except Exception as e:
        print(f"\n  ✘ could not download {dest.name}: {e}")
        tmp.unlink(missing_ok=True)
        return False


def main():
    args = set(sys.argv[1:])
    print("Kokoro voice model:")
    model = "kokoro-v1.0.int8.onnx" if "--small" in args else "kokoro-v1.0.onnx"
    ok = fetch(KOKORO + model, ROOT / "models/kokoro" / model)
    ok &= fetch(KOKORO + "voices-v1.0.bin", ROOT / "models/kokoro/voices-v1.0.bin")
    if "--piper" in args:
        print("Piper voices (optional):")
        for v in PIPER_VOICES:
            name = v.rsplit("/", 1)[1]
            if fetch(PIPER + v + ".onnx", ROOT / "models/piper" / f"{name}.onnx"):
                fetch(PIPER + v + ".onnx.json", ROOT / "models/piper" / f"{name}.onnx.json")
    print("\nDone." if ok else "\nSome downloads failed — check your internet and run this again.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
