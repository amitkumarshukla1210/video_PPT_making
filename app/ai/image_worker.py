"""Stand-alone worker for the picture creator; runs inside .venv-image (OpenVINO + diffusers).

    python image_worker.py job.json      make the pictures in job.json
    python image_worker.py --check MODEL test the installation and print a report
job.json = {"model": "...", "width": 768, "height": 432, "steps": 4, "seed": null,
            "items": [{"prompt": "...", "out": "img_0.png"}]}
Prints "PROGRESS <done> <total>". Loads the model once for the batch. Uses the graphics card when OpenVINO
can; if the graphics card fails, it falls back to the processor (CPU) instead of giving up."""
import json
import os
import platform
import sys

os.environ.setdefault("OPENVINO_TELEMETRY_OPTOUT", "1")     # no usage statistics (Google Analytics) from OpenVINO
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("DO_NOT_TRACK", "1")
import time
import traceback

NEGATIVE = "text, letters, watermark, logo, signature, blurry, low quality, deformed"
STYLE = ", high detail, sharp focus"        # the user's prompt and chosen style decide the look


def compat():
    """transformers 5 removed CLIPFeatureExtractor, which the picture model's files still name.
    CLIPImageProcessor is its replacement (same class since transformers 4.25)."""
    import transformers
    proc = getattr(transformers, "CLIPImageProcessor", None)
    # transformers 5 can replace its module object in sys.modules while loading an attribute, so patch the module
    # that is current now (and the one we imported), not just the first reference.
    for mod in {id(m): m for m in (transformers, sys.modules.get("transformers")) if m is not None}.values():
        if proc is not None and "CLIPFeatureExtractor" not in vars(mod) and not hasattr(mod, "CLIPFeatureExtractor"):
            setattr(mod, "CLIPFeatureExtractor", proc)


def say(msg):
    print(msg, flush=True)


def unet_inputs(pipe):
    try:
        return {n for i in pipe.unet.model.inputs for n in i.get_names()}
    except Exception:                                # noqa: BLE001
        return set()


def fix_lcm(pipe):
    """An LCM UNet with a `timestep_cond` input but no `time_cond_proj_dim` in its config: optimum-intel sets it to
    None and drawing fails ("NoneType // int"). Read the width of that input and set it. Models without the input
    are left alone (they use the plain Stable Diffusion pipeline, see load())."""
    unet = getattr(pipe, "unet", None)
    if unet is None or getattr(unet.config, "time_cond_proj_dim", None):
        return
    try:
        for inp in unet.model.inputs:
            if "timestep_cond" in inp.get_names():
                last = inp.get_partial_shape()[-1]
                dim = last.get_length() if last.is_static else 256
                unet.register_to_config(time_cond_proj_dim=dim)
                say(f"INFO set the missing time_cond_proj_dim to {dim}")
    except Exception:                                # noqa: BLE001
        pass


# guidance per pipeline kind: LCM UNets with a guidance input were distilled for ~8; LCM weights exported as a
# plain Stable Diffusion UNet (no guidance input, e.g. rupeshs/LCM-dreamshaper-v7-openvino) need ~1.5 —
# higher values burn the colours (checked on the real model: 1.5 clean, 2.5 over-saturated).
# SDXL-Lightning ("xl") was distilled without guidance: 0 (no negative prompt pass, twice as fast).
GUIDANCE = {"lcm": 8.0, "sd": 1.5, "xl": 0.0}


def is_xl(model):
    """Stable Diffusion XL model folder? (model_index.json names the pipeline class)."""
    try:
        with open(os.path.join(model, "model_index.json"), encoding="utf-8") as f:
            return "XL" in json.load(f).get("_class_name", "")
    except (OSError, ValueError):
        return False


def _pipeline(model, cache):
    """The right pipeline for the model: XL for SDXL models; the LCM pipeline only when the UNet takes
    `timestep_cond`; otherwise plain Stable Diffusion."""
    from optimum.intel import OVStableDiffusionPipeline, OVLatentConsistencyModelPipeline
    cfg = {"CACHE_DIR": cache or ""}
    compat()                                         # again, after optimum/diffusers were imported
    if is_xl(model):
        from optimum.intel import OVStableDiffusionXLPipeline
        return OVStableDiffusionXLPipeline.from_pretrained(model, ov_config=cfg, compile=False), "xl"
    pipe = OVStableDiffusionPipeline.from_pretrained(model, ov_config=cfg, compile=False)
    if "timestep_cond" in unet_inputs(pipe):
        pipe = OVLatentConsistencyModelPipeline.from_pretrained(model, ov_config=cfg, compile=False)
        fix_lcm(pipe)
        return pipe, "lcm"
    return pipe, "sd"


def reshape(pipe, width, height):
    """Fix the picture size (static shapes: much less memory and faster, above all on a graphics card).
    optimum-intel doubles the UNet batch for guidance; SDXL-Lightning draws without guidance, so its UNet is set
    back to a batch of 1 (otherwise drawing fails: "model input [2,4,72,128] and tensor (1,4,72,128)")."""
    if getattr(pipe, "dtc_kind", "") != "xl":
        pipe.reshape(batch_size=1, height=height, width=width, num_images_per_prompt=1)
        return
    orig = pipe._reshape_unet

    def batch_one(model, *a, **kw):
        model = orig(model, *a, **kw)
        shapes = {}
        for inp in model.inputs:
            ps = inp.get_partial_shape()
            if ps.rank.is_static and ps.rank.get_length() > 1 and inp.get_any_name() != "timestep":
                ps[0] = 1
            shapes[inp] = ps
        model.reshape(shapes)
        return model
    pipe._reshape_unet = batch_one
    try:
        pipe.reshape(batch_size=1, height=height, width=width, num_images_per_prompt=1)
    finally:
        del pipe._reshape_unet


def full_precision_vae(pipe):
    """The SDXL picture decoder (VAE) overflows in half precision, which graphics cards use by default: every picture
    comes out black. Run that one part in full precision (f32); the rest stays fast."""
    vae = getattr(pipe, "vae_decoder", None)
    if vae is not None and getattr(pipe, "dtc_kind", "") == "xl":
        vae.ov_config = {**vae.ov_config, "INFERENCE_PRECISION_HINT": "f32"}   # its own copy, not the shared one
        vae.request = None


def is_black(img):
    """A failed drawing (NaN in half precision) comes out as a plain black picture."""
    lo, hi = zip(*img.convert("RGB").getextrema())
    return max(hi) <= 8


def load(model, width, height, prefer_gpu=True, cache=""):
    """Load and compile the pipeline: graphics card first, processor (CPU) if that fails.
    cache = folder where OpenVINO keeps the compiled model, so the next start takes seconds, not minutes."""
    import openvino as ov
    devices = ov.Core().available_devices
    say(f"INFO devices: {', '.join(devices)}")
    tries = (["GPU"] if prefer_gpu and any(d.startswith("GPU") for d in devices) else []) + ["CPU"]
    last = None
    for dev in tries:
        try:
            t = time.time()
            pipe, kind = _pipeline(model, cache)
            pipe.dtc_kind = kind
            full_precision_vae(pipe)
            if dev != "CPU":
                pipe.to(dev)
            reshape(pipe, width, height)
            pipe.compile()
            say(f"INFO model ready on {dev} in {time.time() - t:.0f}s ({kind} pipeline)")
            return pipe, dev
        except Exception as e:                       # noqa: BLE001 — try the next device
            last = e
            say(f"WARN could not use {dev}: {type(e).__name__}: {str(e)[:300]}")
    raise last


def make(pipe, prompt, width, height, steps, seed):
    import torch
    gen = torch.Generator().manual_seed(int(seed)) if seed is not None else None
    guidance = GUIDANCE.get(getattr(pipe, "dtc_kind", "sd"), 1.5)
    extra = {"negative_prompt": NEGATIVE} if guidance > 1 else {}
    return pipe(prompt=prompt + STYLE, width=width, height=height, num_inference_steps=int(steps or 4),
                guidance_scale=guidance, generator=gen, **extra).images[0]


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
        reshape(state["pipe"], w, h)
        state["pipe"].compile()
        state["size"] = (w, h)
        say(f"INFO re-shaped to {w}x{h} in {time.time() - t:.0f}s")
    items = job["items"]
    for n, it in enumerate(items):
        seed = int(job["seed"]) + n if job.get("seed") is not None else None
        try:
            img = make(state["pipe"], it["prompt"], w, h, job.get("steps"), seed)
            if is_black(img) and state["dev"] != "CPU":
                raise RuntimeError("the picture came out black")
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
