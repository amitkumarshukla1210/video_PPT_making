"""Captions from your own recordings with faster-whisper (MIT; Whisper weights MIT). Runs on the CPU.
Install once with: install_once.bat ai  (downloads the 'small' model, about 460 MB, into models\\hf)."""
import os

SIZE = os.environ.get("DTC_WHISPER_MODEL", "small")
_model = None


def _model_path():
    from faster_whisper.utils import download_model
    return download_model(SIZE, local_files_only=True)   # never downloads while the app runs


def status():
    import importlib.util
    if importlib.util.find_spec("faster_whisper") is None:
        return {"available": False, "info": "Captions from recordings: run install_once.bat ai"}
    try:
        _model_path()
    except Exception:
        return {"available": False, "info": f"Whisper model '{SIZE}' not downloaded: run install_once.bat ai"}
    return {"available": True, "info": f"Whisper {SIZE} (CPU)"}


def transcribe(wav_path, language=None):
    """[(start, end, text)] in seconds for one recording."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(_model_path(), device="cpu", compute_type="int8")
    segments, _info = _model.transcribe(str(wav_path), language=(language or None) and language[:2],
                                        vad_filter=True, beam_size=1)
    return [(round(s.start, 3), round(s.end, 3), s.text.strip()) for s in segments if s.text.strip()]
