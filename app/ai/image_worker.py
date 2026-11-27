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


def fix_lcm(pipe):
    """Older OpenVINO exports of LCM models have no `time_cond_proj_dim` in the UNet config; optimum-intel then
    sets it to None and drawing fails ("NoneType // int" in get_guidance_scale_embedding). The value is the width
    of the model's `timestep_cond` input (256 for LCM DreamShaper): read it from the model, set it in the config."""
    unet = getattr(pipe, "unet", None)
    if unet is None or getattr(unet.config, "time_cond_proj_dim", None):
        return
    dim = 256
    try:
        for inp in unet.model.inputs:
            if "timestep_cond" in inp.get_names():
                last = inp.get_partial_shape()[-1]
                if last.is_static:
                    dim = last.get_length()
    except Exception:                                # noqa: BLE001 — keep the LCM default
        pass
    unet.register_to_config(time_cond_proj_dim=dim)
    say(f"INFO set the missing time_cond_proj_dim to {dim}")


def load(model, width, height, prefer_gpu=True, cache=""):
    """Load and compile the pipeline: graphics card first, processor (CPU) if that fails.
    cache = folder where OpenVINO keeps the compiled model, so the next start takes seconds, not minutes."""
    from optimum.intel import OVLatentConsistencyModelPipeline
    import openvino as ov
    devices = ov.Core().available_devices
    say(f"INFO devices: {', '.join(devices)}")
    tries = (["GPU"] if prefer_gpu and any(d.startswith("GPU") for d in devices) else []) + ["CPU"]
    last = None
    for dev in tries:
        try:
            t = time.time()
            pipe = OVLatentConsistencyModelPipeline.from_pretrained(model, ov_config={"CACHE_DIR": cache or ""},
                                                                    compile=False)
            fix_lcm(pipe)
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


def run(job, state=None):
    """Make the pictures of one job. With `state` (the --serve mode) the loaded model is kept for the next job;
    only a new picture size needs a (cached, quick) re-compile."""
    compat()
    state = state if state is not None else {}
    w, h = (max(64, -(-int(v) // 64) * 64) for v in (job["width"], job["height"]))   # the model needs multiples of 64
    cache = job.get("cache", "")
    if state.get("pipe") is None or state.get("model") != job["model"]:
        state["pipe"], state["dev"] = load(job["model"], w, h, cache=cache)
        state.update(model=job["model"], size=(w, h))
    elif state.get("size") != (w, h):
        t = time.time()
        state["pipe"].reshape(batch_size=1, height=h, width=w, num_images_per_prompt=1)
        state["pipe"].compile()
        state["size"] = (w, h)
        say(f"INFO re-shaped to {w}x{h} in {time.time() - t:.0f}s")
    items = job["items"]
    for n, it in enumerate(items):
        seed = int(job["seed"]) + n if job.get("seed") is not None else None
        try:
            img = make(state["pipe"], it["prompt"], w, h, job.get("steps"), seed)
        except Exception as e:                       # noqa: BLE001 — the graphics card failed while drawing
            if state["dev"] == "CPU":
                raise
            say(f"WARN drawing on {state['dev']} failed ({type(e).__name__}: {str(e)[:200]}); switching to CPU")
            state["pipe"], state["dev"] = load(job["model"], w, h, prefer_gpu=False, cache=cache)
            img = make(state["pipe"], it["prompt"], w, h, job.get("steps"), seed)
        img.save(it["out"])
        say(f"PROGRESS {n + 1} {len(items)}")


def serve():
    """Stay running: one JSON job per line on stdin; answers with PROGRESS lines, then DONE or ERROR, then END.
    Stops on {"cmd": "quit"} or when the app closes (stdin ends)."""
    state = {}
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            job = json.loads(raw)
            if job.get("cmd") == "quit":
                break
            run(job, state)
            say("DONE")
        except Exception as e:                       # noqa: BLE001 — report, keep serving
            traceback.print_exc(file=sys.stdout)
            say(f"ERROR {type(e).__name__}: {e}")
        say("END")


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
    pipe, dev = load(model, 256, 256, cache=sys.argv[3] if len(sys.argv) > 3 else "")
    img = make(pipe, "a red apple on a wooden table", 256, 256, 2, 1)
    say(f"CHECK test picture {img.size[0]}x{img.size[1]} on {dev} in {time.time() - t:.0f}s")
    say("CHECK OK — the picture creator works")


def main():
    try:
        if sys.argv[1] == "--serve":
            serve()
            return
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
