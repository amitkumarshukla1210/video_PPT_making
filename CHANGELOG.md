# Changelog — Design to Cost · Presentation & Video Studio

The version number is in the file `VERSION` and is shown in the app header, the studio footer and
the black start-up window. Numbering: **MAJOR.MINOR.PATCH**
- **PATCH** (1.2.**1**): small fixes, nothing new to learn.
- **MINOR** (1.**3**.0): new features; your projects keep working.
- **MAJOR** (**2**.0.0): a big change that may need a fresh setup or changes to old projects.

## 1.4.3 — 2026-11-14
- Fix: `update_windows.bat` said "Update FAILED" after a successful update when the old
  `setup_windows.bat` was already gone. The files were updated; only the final message was wrong.

## 1.4.2 — 2026-11-14
- Local AI: if `llama3.2:3b` is not downloaded, the app now uses a suitable model you already have in
  Ollama (for example `qwen3.5:4b` or `qwen3:8b`). Qwen 3 models answer directly (no "thinking" text).
- Updater: a broken or half-downloaded update ZIP is deleted, so the next run downloads a fresh copy.

## 1.4.1 — 2026-11-14
- Clearer file names: **`setup_windows.bat` is now `install_once.bat`** (run it once, or again to
  add an option such as `ai`, `images`, `clone`). Every day you open the app with
  **`start_windows.bat`**, as before. `update_windows.bat` removes the old `setup_windows.bat`.

## 1.4.0 — 2026-11-13
Local AI, all on your laptop, with no API key:
- **PPT → corporate video:** the AI writes the narration from every slide (title, points, PPT
  speaker notes), in 28 languages. It uses Ollama with Llama 3.2 3B (commercial use allowed).
- **Dubbing:** one click makes a translated copy of a project, voiced in your cloned voice (or a
  stock voice of that language). You check it, then render.
- **Your recordings:** background-noise cleanup, and exact captions from what you actually said (Whisper).
- **Music library:** music beds composed by the app in 5 moods, free of copyright, plus sound
  effects and an optional "whoosh" at each slide change.
- **Studio, write scenes from an idea:** from a short clip up to **long cinematic videos (about 8 minutes,
  55 scenes)**. The AI plans the story first, then writes it in parts.
- **Studio, picture creator:** a picture for every scene from a prompt, using Stable Diffusion LCM on
  OpenVINO with your Intel graphics.
- New install options: `setup_windows.bat ai` and `setup_windows.bat images`.
- Fix: scene thumbnails refresh when a picture changes.

## 1.3.0 — 2026-11-04
- Refresh both workspaces with a branded home prompt, sidebar navigation, and task-specific entry points while preserving the Design to Cost logo and product name.
- Add an original ready-to-try sample picture and narrated-video workflow in the main app and Video & Voice Studio.
- Make the Studio offline-first: remove hosted voice services, API-key fields, and configurable remote TTS endpoints. Only the local app voice server can generate exportable narration; built-in browser voices remain preview-only.
- **My cloned voice in the Studio:** the local voice server now offers your own cloned voice (23 languages incl. Hindi), using the voice sample recorded once in the Presentation app. No API key, no internet.
- Ask before downloading the optional MP4/MP3 converter; WebM, WAV, and subtitles remain available without it.
- Document unavailable offline categories and update the end-to-end coverage for the sample voice-over export.

## 1.2.0 — 2026-11-01
- **New: Video & Voice Studio** web page (`/studio/`, also hostable on GitHub Pages):
  - 5 templates; script → scenes.
  - Voices: browser preview or the local voice server.
  - Exports: WebM, MP4, WAV, MP3 and SRT; 10-minute limit.
- New: OpenAI-compatible speech endpoint `/v1/audio/speech` in the local app.
- New: software version shown in the app, plus `backup_windows.bat` and `update_windows.bat`.
- New: automatic tests on GitHub (CI), and GitHub Pages hosting.

## 1.1.1 — 2026-10-25
- Setup copes with slow or unstable internet (longer timeouts, automatic retries).

## 1.1.0 — 2026-10-24
- Design to Cost theme and DC logo everywhere.
- Video length limit of 15 minutes.
- Voice clone (Chatterbox, 23 languages incl. Hindi) and a gender filter for voices.
- Presenter in the corner: your own webcam or phone recording per slide, or your photo.
- Logo intro/outro; Reels 9:16, square 1:1 and short-clip exports.

## 1.0.0 — 2026-10-18
- First release:
  - Screenshots + notes → branded PowerPoint, with an editable narration script.
  - Offline voice-over (Kokoro / Piper / eSpeak / Windows voices).
  - MP4 with subtitles and music.
  - Local web page, which also works from a phone.
