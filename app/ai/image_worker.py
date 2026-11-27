"""Stand-alone worker for the picture creator; runs inside .venv-image (OpenVINO + diffusers).

    python image_worker.py job.json      make the pictures in job.json
    python image_worker.py --check MODEL test the installation and print a report
job.json = {"model": "...", "width": 768, "height": 432, "steps": 4, "seed": null,
            "items": [{"prompt": "...", "out": "img_0.png"}]}
Prints "PROGRESS <done> <total>". Loads the model once for the batch. Uses the graphics card when OpenVINO
can; if the graphics card fails, it falls back to the processor (CPU) instead of giving up."""
import json
import platform
import sys
import time
import traceback

NEGATIVE = "text, letters, watermark, logo, signature, blurry, low quality, deformed"
STYLE = ", high detail, sharp focus"        # the user's prompt and chosen style decide the look


def compat():
    """transformers 5 removed CLIPFeatureExtractor, which the picture model's files still name.
    CLIPImageProcessor is its replacement (same class since transformers 4.25)."""
    import transformers
    if not hasattr(transformers, "CLIPFeatureExtractor") and hasattr(transformers, "CLIPImageProcessor"):
        transformers.CLIPFeatureExtractor = transformers.CLIPImageProcessor


def say(msg):
    print(msg, flush=True)


def load(model, width, height, prefer_gpu=True):
    """Load and compile the pipeline: graphics card first, processor (CPU) if that fails."""
    from optimum.intel import OVLatentConsistencyModelPipeline
    import openvino as ov
    devices = ov.Core().available_devices
    say(f"INFO devices: {', '.join(devices)}")
    tries = (["GPU"] if prefer_gpu and any(d.startswith("GPU") for d in devices) else []) + ["CPU"]
    last = None
    for dev in tries:
        try:
            t = time.time()
            pipe = OVLatentConsistencyModelPipeline.from_pretrained(model, ov_config={"CACHE_DIR": ""}, compile=False)
            if dev != "CPU":
                pipe.to(dev)
            pipe.reshape(batch_size=1, height=height, width=width, num_images_per_prompt=1)
            pipe.compile()
            say(f"INFO model ready on {dev} in {time.time() - t:.0f}s")
            return pipe, dev
        except Exception as e:                       # noqa: BLE001 — try the next device
            last = e
            say(f"WARN could not use {dev}: {type(e).__name__}: {str(e)[:300]}")
    raise last


def make(pipe, prompt, width, height, steps, seed):
    import torch
    gen = torch.Generator().manual_seed(int(seed)) if seed is not None else None
    return pipe(prompt=prompt + STYLE, negative_prompt=NEGATIVE, width=width, height=height,
                num_inference_steps=int(steps or 4), guidance_scale=8.0, generator=gen).images[0]


def run(job):
    compat()
    w, h = (max(64, -(-int(v) // 64) * 64) for v in (job["width"], job["height"]))   # the model needs multiples of 64
    pipe, dev = load(job["model"], w, h)
    items = job["items"]
    for n, it in enumerate(items):
        seed = int(job["seed"]) + n if job.get("seed") is not None else None
        try:
            img = make(pipe, it["prompt"], w, h, job.get("steps"), seed)
        except Exception as e:                       # noqa: BLE001 — the graphics card failed while drawing
            if dev == "CPU":
                raise
            say(f"WARN drawing on {dev} failed ({type(e).__name__}: {str(e)[:200]}); switching to CPU")
            pipe, dev = load(job["model"], w, h, prefer_gpu=False)
            img = make(pipe, it["prompt"], w, h, job.get("steps"), seed)
        img.save(it["out"])
        say(f"PROGRESS {n + 1} {len(items)}")


def check(model):
    """Installation report: versions, devices, model loading and one small test picture."""
    import importlib.metadata as md
    say(f"CHECK python {platform.python_version()} on {platform.system()} {platform.release()}")
    for pkg in ("transformers", "diffusers", "optimum", "optimum-intel", "openvino", "torch", "huggingface-hub"):
        try:
            say(f"CHECK {pkg} {md.version(pkg)}")
        except md.PackageNotFoundError:
            say(f"CHECK {pkg} NOT INSTALLED")
    compat()
    t = time.time()
    pipe, dev = load(model, 256, 256)
    img = make(pipe, "a red apple on a wooden table", 256, 256, 2, 1)
    say(f"CHECK test picture {img.size[0]}x{img.size[1]} on {dev} in {time.time() - t:.0f}s")
    say("CHECK OK — the picture creator works")


def main():
    try:
        if sys.argv[1] == "--check":
            check(sys.argv[2])
        else:
            run(json.load(open(sys.argv[1], encoding="utf-8")))
    except Exception as e:                           # noqa: BLE001 — report clearly, then fail
        traceback.print_exc()
        say(f"ERROR {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
