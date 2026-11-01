"""The software version. The single source of truth is the VERSION file in the app folder."""
from .config import ROOT


def app_version():
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip() or "dev"
    except OSError:
        return "dev"
