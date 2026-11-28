"""Picture creator worker: graphics-card fallback to CPU, clear errors, the self-check report.
The real model is replaced by stand-ins (optimum.intel / openvino / torch), so this runs anywhere."""
import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from app.ai import image_worker, images  # noqa: E402


def fake_stack(monkeypatch, gpu_compile_fails=False, gpu_draw_fails=False, devices=("CPU", "GPU"), lcm_unet=False):
    calls = []

    class Pipe:
        kind = "sd"
        def __init__(self):
            self.device = "CPU"

        @classmethod
        def from_pretrained(cls, model, **kw):
            calls.append(("load", kw.get("compile")))
            p = cls()
            names = ["sample", "timestep", "encoder_hidden_states"] + (["timestep_cond"] if lcm_unet else [])
            p.unet = types.SimpleNamespace(
                config=types.SimpleNamespace(time_cond_proj_dim=None),
                model=types.SimpleNamespace(inputs=[types.SimpleNamespace(get_names=lambda n=n: {n}) for n in names]),
                register_to_config=lambda **kw: None)
            return p

        def to(self, dev):
            self.device = dev

        def reshape(self, **kw):
            pass

        def compile(self):
            calls.append(("compile", self.device))
            if self.device == "GPU" and gpu_compile_fails:
                raise RuntimeError("GPU plugin: out of memory")

        def __call__(self, **kw):
            calls.append(("draw", self.device))
            calls.append(("guidance", type(self).kind, kw["guidance_scale"]))
            if self.device == "GPU" and gpu_draw_fails:
                raise RuntimeError("GPU hang")
            return types.SimpleNamespace(images=[Image.new("RGB", (kw["width"], kw["height"]), "red")])

    class LcmPipe(Pipe):
        kind = "lcm"

    oi = types.ModuleType("optimum.intel")
    oi.OVStableDiffusionPipeline = Pipe
    oi.OVLatentConsistencyModelPipeline = LcmPipe

    class Shape(list):
        rank = types.SimpleNamespace(is_static=True, get_length=lambda: 4)

    class Inp:
        def __init__(self, name):
            self.name = name

        def get_any_name(self):
            return self.name

        def get_partial_shape(self):
            return Shape([2, 4, 72, 128])

    class XlPipe(Pipe):
        kind = "xl"

        def _reshape_unet(self, model, *a, **kw):        # like optimum-intel: doubles the batch for guidance
            model.inputs = [Inp("sample"), Inp("timestep")]
            return model

        def reshape(self, **kw):
            m = types.SimpleNamespace(reshape=lambda shapes: calls.append(
                ("unet batch", {i.get_any_name(): s[0] for i, s in shapes.items()})))
            self._reshape_unet(m, 1, kw["height"], kw["width"], 1, 77)
    oi.OVStableDiffusionXLPipeline = XlPipe
    ov = types.ModuleType("openvino")
    ov.Core = lambda: types.SimpleNamespace(available_devices=list(devices))
    torch = types.ModuleType("torch")
    torch.Generator = lambda: types.SimpleNamespace(manual_seed=lambda s: s)
    tf = types.ModuleType("transformers")
    tf.CLIPImageProcessor = object
    for name, mod in (("optimum", types.ModuleType("optimum")), ("optimum.intel", oi), ("openvino", ov),
                      ("torch", torch), ("transformers", tf)):
        monkeypatch.setitem(sys.modules, name, mod)
    return calls


def _job(tmp_path, n=2):
    return {"model": "m", "width": 64, "height": 64, "steps": 2, "seed": 1,
            "items": [{"prompt": f"p{k}", "out": str(tmp_path / f"o{k}.png")} for k in range(n)]}


def test_uses_the_graphics_card_when_it_works(monkeypatch, tmp_path, capsys):
    calls = fake_stack(monkeypatch)
    image_worker.run(_job(tmp_path))
    assert ("compile", "GPU") in calls and ("draw", "CPU") not in calls
    assert (tmp_path / "o1.png").exists() and "PROGRESS 2 2" in capsys.readouterr().out


def test_falls_back_to_cpu_when_the_graphics_card_cannot_load(monkeypatch, tmp_path, capsys):
    calls = fake_stack(monkeypatch, gpu_compile_fails=True)
    image_worker.run(_job(tmp_path))
    out = capsys.readouterr().out
    assert "WARN could not use GPU" in out and "model ready on CPU" in out
    assert ("draw", "CPU") in calls and (tmp_path / "o0.png").exists()


def test_falls_back_to_cpu_when_drawing_on_the_graphics_card_fails(monkeypatch, tmp_path, capsys):
    calls = fake_stack(monkeypatch, gpu_draw_fails=True)
    image_worker.run(_job(tmp_path, 1))
    assert "switching to CPU" in capsys.readouterr().out
    assert [c for c in calls if c[0] == "draw"][-1] == ("draw", "CPU") and (tmp_path / "o0.png").exists()


def test_check_prints_a_report(monkeypatch, capsys):
    fake_stack(monkeypatch, devices=("CPU",))
    image_worker.check("m")
    out = capsys.readouterr().out
    assert "CHECK python" in out and "CHECK OK" in out and "devices: CPU" in out


BAD_WORKER = """import sys
if sys.argv[1] == "--serve":
    for line in sys.stdin:
        if '"quit"' in line:
            break
        print('Traceback (most recent call last):')
        print('  lots of lines')
        print('ERROR AttributeError: module transformers has no attribute X')
        print('END', flush=True)
else:
    print('ERROR AttributeError: module transformers has no attribute X')
    sys.exit(1)
"""

GOOD_WORKER = """import json, sys
from PIL import Image
starts = 0
for line in sys.stdin:
    job = json.loads(line)
    if job.get('cmd') == 'quit':
        break
    assert job['width'] % 64 == 0 and job['height'] % 64 == 0, job
    assert job['cache']
    if starts == 0:
        print('INFO model ready on GPU in 1s')
    starts += 1
    for n, i in enumerate(job['items']):
        Image.new('RGB', (job['width'], job['height']), 'blue').save(i['out'])
        print(f"PROGRESS {n + 1} {len(job['items'])}")
    print(f'INFO jobs {starts}')
    print('DONE')
    print('END', flush=True)
"""


def _server(monkeypatch, tmp_path, code):
    w = tmp_path / "w.py"
    w.write_text(code)
    monkeypatch.setattr(images, "WORKER", w)
    monkeypatch.setattr(images, "_python", lambda: sys.executable)
    monkeypatch.setattr(images, "LOG", tmp_path / "logs" / "picture_creator.log")
    monkeypatch.setattr(images, "CACHE", tmp_path / "ov_cache")
    monkeypatch.setattr(images, "hd_ready", lambda: False)
    srv = images._Server()
    monkeypatch.setattr(images, "SERVER", srv)
    return srv


def test_errors_are_short_and_point_to_the_log(monkeypatch, tmp_path):
    srv = _server(monkeypatch, tmp_path, BAD_WORKER)
    try:
        with pytest.raises(RuntimeError) as e:
            images.generate(["a cat"])
        msg = str(e.value)
        assert "ERROR AttributeError" in msg and "Full log:" in msg
        assert "lots of lines" in (tmp_path / "logs" / "picture_creator.log").read_text()
        assert srv.alive()                                  # one bad job does not kill the picture creator
        r = images.check()
        assert r["ok"] is False and "ERROR AttributeError" in r["report"] and "Model files downloaded" in r["report"]
        assert not srv.alive()                              # the check frees the running one first
    finally:
        srv.stop()


def test_model_stays_loaded_between_pictures(monkeypatch, tmp_path):
    srv = _server(monkeypatch, tmp_path, GOOD_WORKER)
    try:
        assert not images.warm()
        images.generate(["one"])
        pid = srv.proc.pid
        assert images.warm()
        images.generate(["two", "three"], "9:16")
        assert srv.proc.pid == pid                          # same process: the model was not loaded again
        assert "INFO jobs 2" in (tmp_path / "logs" / "picture_creator.log").read_text()
        assert (tmp_path / "ov_cache").is_dir()
    finally:
        srv.stop()
    assert not images.warm()


def test_check_when_not_installed(monkeypatch):
    monkeypatch.setattr(images, "_python", lambda: None)
    r = images.check()
    assert r["ok"] is False and "install_once.bat images" in r["report"]


def test_draw_sizes_are_multiples_of_64_and_pictures_keep_their_shape(monkeypatch, tmp_path):
    for aspect, (w, h) in images.SIZES.items():
        dw, dh = images.draw_size(w, h)
        assert dw % 64 == 0 and dh % 64 == 0 and dw >= w and dh >= h and dh - h < 64 and dw - w < 64, aspect
    assert images.draw_size(768, 432) == (768, 448)
    # the worker draws 768x448, the app trims to exactly 768x432
    srv = _server(monkeypatch, tmp_path, GOOD_WORKER)
    import io
    try:
        for aspect in ("16:9", "9:16", "1:1"):
            png = images.generate(["x"], aspect, quality="fast")[0]
            assert Image.open(io.BytesIO(png)).size == images.SIZES[aspect]
    finally:
        srv.stop()


def test_serve_mode_reuses_the_model_and_only_reshapes(monkeypatch, tmp_path):
    calls = fake_stack(monkeypatch)
    state = {}
    image_worker.run(_job(tmp_path, 1), state)
    image_worker.run(_job(tmp_path, 1), state)              # same size: nothing to load
    job = _job(tmp_path, 1)
    job["width"], job["height"] = 128, 64
    image_worker.run(job, state)                            # new size: re-shape only
    assert [c for c in calls if c[0] == "load"] == [("load", False)]
    assert ("guidance", "sd", 1.5) in calls                  # plain SD pipeline for this model, gentle guidance
    assert calls.count(("compile", "GPU")) == 2 and state["size"] == (128, 64)


def test_missing_time_cond_proj_dim_is_filled_in_from_the_model(capsys):
    """optimum-intel sets time_cond_proj_dim=None for older LCM exports; diffusers then fails with
    'NoneType // int'. The worker reads the width of the model's timestep_cond input instead."""
    class Dim:
        is_static = True

        def get_length(self):
            return 256

    class Inp:
        def __init__(self, name):
            self.name = name

        def get_names(self):
            return {self.name}

        def get_partial_shape(self):
            return [None, Dim()]

    class Unet:
        def __init__(self):
            self.config = types.SimpleNamespace(time_cond_proj_dim=None)
            self.model = types.SimpleNamespace(inputs=[Inp("sample"), Inp("timestep_cond")])

        def register_to_config(self, **kw):
            for k, v in kw.items():
                setattr(self.config, k, v)

    pipe = types.SimpleNamespace(unet=Unet())
    image_worker.fix_lcm(pipe)
    assert pipe.unet.config.time_cond_proj_dim == 256 and "time_cond_proj_dim to 256" in capsys.readouterr().out
    pipe.unet.config.time_cond_proj_dim = 512
    image_worker.fix_lcm(pipe)                          # a model that has it keeps its own value
    assert pipe.unet.config.time_cond_proj_dim == 512
    image_worker.fix_lcm(types.SimpleNamespace())       # pipelines without a UNet are left alone


def test_lcm_unet_with_guidance_input_uses_the_lcm_pipeline(monkeypatch, tmp_path):
    calls = fake_stack(monkeypatch, lcm_unet=True)
    image_worker.run(_job(tmp_path, 1))
    assert ("guidance", "lcm", 8.0) in calls


def test_model_without_guidance_input_keeps_time_cond_proj_dim_empty():
    unet = types.SimpleNamespace(config=types.SimpleNamespace(time_cond_proj_dim=None),
                                 model=types.SimpleNamespace(inputs=[]), register_to_config=lambda **kw: 1 / 0)
    image_worker.fix_lcm(types.SimpleNamespace(unet=unet))       # must not set 256 (the real model has no input)
    assert unet.config.time_cond_proj_dim is None


def test_compat_patches_the_module_that_transformers_put_in_place(monkeypatch):
    """transformers 5 can replace its module in sys.modules while loading CLIPImageProcessor."""
    old, new = types.ModuleType("transformers"), types.ModuleType("transformers")

    class Lazy(types.ModuleType):
        def __getattr__(self, name):
            if name == "CLIPImageProcessor":
                sys.modules["transformers"] = new          # what the real lazy module does
                return "Proc"
            raise AttributeError(name)
    old.__class__ = Lazy
    monkeypatch.setitem(sys.modules, "transformers", old)
    image_worker.compat()
    assert sys.modules["transformers"].CLIPFeatureExtractor == "Proc" and old.CLIPFeatureExtractor == "Proc"


def test_model_is_opened_from_its_folder(monkeypatch, tmp_path):
    repo = tmp_path / "models" / "hf" / "hub" / ("models--" + images.MODEL.replace("/", "--"))
    (repo / "snapshots" / "abc").mkdir(parents=True)
    (repo / "snapshots" / "abc" / "model_index.json").write_text("{}")
    (repo / "refs").mkdir()
    (repo / "refs" / "main").write_text("abc")
    monkeypatch.setattr(images, "ROOT", tmp_path)
    assert images.model_path() == str(repo / "snapshots" / "abc")


def test_picture_creator_sends_no_usage_statistics():
    assert images.PRIVATE_ENV["OPENVINO_TELEMETRY_OPTOUT"] == "1" and images.PRIVATE_ENV["HF_HUB_DISABLE_TELEMETRY"] == "1"
    import os
    assert os.environ.get("OPENVINO_TELEMETRY_OPTOUT") == "1"      # set by importing the worker module


def _xl_folder(tmp_path):
    d = tmp_path / "xl"
    d.mkdir()
    (d / "model_index.json").write_text(json.dumps({"_class_name": "StableDiffusionXLPipeline"}))
    return str(d)


def test_film_quality_model_uses_the_xl_pipeline_without_guidance(monkeypatch, tmp_path):
    calls = fake_stack(monkeypatch)
    job = _job(tmp_path, 1)
    job["model"], job["width"], job["height"] = _xl_folder(tmp_path), 1024, 576
    state = {}
    image_worker.run(job, state)
    assert ("guidance", "xl", 0.0) in calls
    job["width"], job["height"] = 576, 1024                 # another shape: re-shaped, not re-loaded
    image_worker.run(job, state)
    assert len([c for c in calls if c[0] == "load"]) == 1
    assert Image.open(job["items"][0]["out"]).size == (576, 1024)
    # fixed size with a UNet batch of 1 (no guidance): low memory and fast on a graphics card
    batches = [c[1] for c in calls if c[0] == "unet batch"]
    assert len(batches) == 2 and all(b["sample"] == 1 and b["timestep"] == 2 for b in batches)
    assert not image_worker.is_xl(str(tmp_path))


def test_film_quality_is_used_when_downloaded(monkeypatch, tmp_path):
    monkeypatch.setattr(images, "ROOT", tmp_path)
    assert not images.hd_ready() and images.pick() == "fast" and images.pick("hd") == "fast"
    repo = images._repo(images.HD_MODEL) / "snapshots" / "r1"
    repo.mkdir(parents=True)
    assert not images.hd_ready()                            # download not finished yet
    (repo / "model_index.json").write_text("{}")
    assert images.hd_ready() and images.pick() == "hd" and images.pick("fast") == "fast"


def test_film_quality_pictures_are_1024_wide(monkeypatch, tmp_path):
    srv = _server(monkeypatch, tmp_path, GOOD_WORKER)
    monkeypatch.setattr(images, "hd_ready", lambda: True)
    import io
    try:
        png = images.generate(["x"], "16:9")[0]
        assert Image.open(io.BytesIO(png)).size == (1024, 576)
        assert Image.open(io.BytesIO(images.generate(["x"], "16:9", quality="fast")[0])).size == (768, 432)
    finally:
        srv.stop()


def test_prompt_keeps_the_subject_first_and_the_quality_words_in_reach():
    from app import tools
    p = tools.build_prompt("Ram by the river", "cinematic")
    assert p.startswith("Ram by the river, cinematic film still")
    assert p.count("cinematic film still") == 1 and "photorealistic" in p
    long = tools.build_prompt(" ".join(f"w{i}" for i in range(200)), "photo")
    assert len(long.split(", ")[0].split()) == tools.SUBJECT_WORDS and long.endswith("sharp focus, cinematic film still, photorealistic, detailed face")
    assert tools.build_prompt("a cat", "anime") == "a cat, anime illustration, clean lines, vibrant colours"


def test_film_quality_decoder_runs_in_full_precision():
    shared = {"CACHE_DIR": "c"}
    vae = types.SimpleNamespace(ov_config=shared, request="old")
    pipe = types.SimpleNamespace(dtc_kind="xl", vae_decoder=vae)
    image_worker.full_precision_vae(pipe)
    assert vae.ov_config == {"CACHE_DIR": "c", "INFERENCE_PRECISION_HINT": "f32"} and vae.request is None
    assert shared == {"CACHE_DIR": "c"}                     # the other parts keep the fast setting
    sd = types.SimpleNamespace(dtc_kind="sd", vae_decoder=types.SimpleNamespace(ov_config={}, request="r"))
    image_worker.full_precision_vae(sd)
    assert sd.vae_decoder.ov_config == {}


def test_black_picture_on_the_graphics_card_is_redrawn_on_cpu(monkeypatch, tmp_path, capsys):
    calls = fake_stack(monkeypatch)
    real_make = image_worker.make

    def make(pipe, *a):
        img = real_make(pipe, *a)
        return Image.new("RGB", img.size, "black") if pipe.device == "GPU" else img
    monkeypatch.setattr(image_worker, "make", make)
    job = _job(tmp_path, 1)
    image_worker.run(job)
    assert Image.open(job["items"][0]["out"]).getpixel((0, 0)) == (255, 0, 0)
    assert "came out black" in capsys.readouterr().out
    assert image_worker.is_black(Image.new("RGB", (8, 8), (3, 3, 3))) and not image_worker.is_black(Image.new("RGB", (8, 8), "red"))
