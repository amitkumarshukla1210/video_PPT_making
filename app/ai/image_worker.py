"""Stand-alone worker for the picture creator; runs inside .venv-image (OpenVINO + diffusers).

    python image_worker.py job.json
job.json = {"model": "...", "width": 768, "height": 432, "steps": 4, "seed": null,
            "items": [{"prompt": "...", "out": "img_0.png"}]}
Prints "PROGRESS <done> <total>". Loads the model once for the batch."""
import json
import sys

NEGATIVE = "text, letters, watermark, logo, signature, blurry, low quality, deformed"
STYLE = ", professional corporate photography, cinematic lighting, high detail"


def main():
    job = json.load(open(sys.argv[1], encoding="utf-8"))
    from optimum.intel import OVLatentConsistencyModelPipeline
    import openvino as ov

    pipe = OVLatentConsistencyModelPipeline.from_pretrained(job["model"], ov_config={"CACHE_DIR": ""})
    devices = ov.Core().available_devices
    if any(d.startswith("GPU") for d in devices):
        try:
            pipe.to("GPU")
        except Exception:
            pass   # stay on CPU
    pipe.reshape(batch_size=1, height=job["height"], width=job["width"], num_images_per_prompt=1)
    pipe.compile()
    import torch
    items = job["items"]
    for n, it in enumerate(items):
        gen = torch.Generator().manual_seed(int(job["seed"]) + n) if job.get("seed") is not None else None
        img = pipe(prompt=it["prompt"] + STYLE, negative_prompt=NEGATIVE, width=job["width"], height=job["height"],
                   num_inference_steps=int(job.get("steps") or 4), guidance_scale=8.0, generator=gen).images[0]
        img.save(it["out"])
        print(f"PROGRESS {n + 1} {len(items)}", flush=True)


if __name__ == "__main__":
    main()
