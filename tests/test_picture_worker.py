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


def test_errors_are_short_and_point_to_the_log(monkeypatch, tmp_path):
    bad = tmp_path / "worker.py"
    bad.write_text("import sys\nprint('Traceback (most recent call last):')\nprint('  lots of lines')\n"
                   "print('ERROR AttributeError: module transformers has no attribute X')\nsys.exit(1)\n")
    monkeypatch.setattr(images, "WORKER", bad)
    monkeypatch.setattr(images, "_python", lambda: sys.executable)
    monkeypatch.setattr(images, "LOG", tmp_path / "logs" / "picture_creator.log")
    with pytest.raises(RuntimeError) as e:
        images.generate(["a cat"])
    msg = str(e.value)
    assert "ERROR AttributeError" in msg and "Full log:" in msg
    assert "lots of lines" in (tmp_path / "logs" / "picture_creator.log").read_text()
    r = images.check()
    assert r["ok"] is False and "ERROR AttributeError" in r["report"] and "Model files downloaded" in r["report"]


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
    worker = tmp_path / "w.py"
    worker.write_text(
        "import json,sys\nfrom PIL import Image\njob=json.load(open(sys.argv[1]))\n"
        "assert job['width'] % 64 == 0 and job['height'] % 64 == 0, job\n"
        "[Image.new('RGB',(job['width'],job['height']),'blue').save(i['out']) for i in job['items']]\n")
    monkeypatch.setattr(images, "WORKER", worker)
    monkeypatch.setattr(images, "_python", lambda: sys.executable)
    monkeypatch.setattr(images, "LOG", tmp_path / "log.txt")
    import io
    for aspect in ("16:9", "9:16", "1:1"):
        png = images.generate(["x"], aspect)[0]
        assert Image.open(io.BytesIO(png)).size == images.SIZES[aspect]
