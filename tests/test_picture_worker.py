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


def fake_stack(monkeypatch, gpu_compile_fails=False, gpu_draw_fails=False, devices=("CPU", "GPU")):
    calls = []

    class Pipe:
        def __init__(self):
            self.device = "CPU"

        @classmethod
        def from_pretrained(cls, model, **kw):
            calls.append(("load", kw.get("compile")))
            return cls()

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
            if self.device == "GPU" and gpu_draw_fails:
                raise RuntimeError("GPU hang")
            return types.SimpleNamespace(images=[Image.new("RGB", (kw["width"], kw["height"]), "red")])

    oi = types.ModuleType("optimum.intel")
    oi.OVLatentConsistencyModelPipeline = Pipe
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
    assert calls[-1] == ("draw", "CPU") and (tmp_path / "o0.png").exists()


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
            png = images.generate(["x"], aspect)[0]
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
