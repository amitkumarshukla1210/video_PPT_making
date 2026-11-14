"""Shared fixtures for the browser tests: one local app server and one Chromium for the whole run."""
import os
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="session")
def base_url():
    from werkzeug.serving import make_server
    from app.main import app
    srv = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture(scope="session")
def browser():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        exe = "/opt/pw-browsers/chromium"
        b = p.chromium.launch(executable_path=exe if os.path.exists(exe) else None,
                              args=["--autoplay-policy=no-user-gesture-required"])
        yield b
        b.close()
