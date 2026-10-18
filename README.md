# Design to Cost — Presentation & Video Studio

A free, open-source app that runs **offline on your Windows laptop**. It turns screenshots and notes (or an existing PowerPoint) into:

- a **branded PowerPoint** (navy `#152238`, blue `#1f5fa8`, orange `#e07b1f`, Segoe UI, logo slot), with the narration in the speaker notes
- an **editable narration script** for each slide
- a **voice-over video (MP4)** with subtitles (`.srt`) and optional background music

Everything runs on the laptop. You can use it from the laptop's browser or from your **phone's browser over home Wi-Fi**.

> **Status: Stage 1 of 5 is done.** The presenter avatar, office backgrounds, cinematic effects and social-media formats are planned for later stages. See the [Plan](#the-plan-5-stages).

---

## Quick start (Windows), step by step

You only do steps 1–3 once.

1. **Install Python** (free) from <https://www.python.org/downloads/>. Choose version 3.11, 3.12 or 3.13.
   During installation, **tick "Add python.exe to PATH"**.
2. **Download this app.**
   - On the GitHub page of this repository, click the green **Code** button, then **Download ZIP**.
   - Unzip it to a simple folder, for example `C:\DTC-Studio`.
3. **Double-click `setup_windows.bat`.** It needs the internet **once** (about 10 minutes, roughly 500 MB). It installs the open-source packages into a private folder (`.venv`) and downloads the Kokoro voice model.
   Optional extras (run from a Command Prompt in that folder):
   - `setup_windows.bat gpu`: lets the voice model use your graphics card (NVIDIA, AMD or Intel).
   - `setup_windows.bat small`: smaller, faster voice model for older laptops.
   - `setup_windows.bat piper`: extra languages through Piper voices.
4. **Double-click `start_windows.bat`.** A black window opens; keep it open while you use the app. Your browser opens at `http://localhost:8000`.
5. **On your phone:** connect to the same Wi-Fi, click **📱 Phone** in the app and scan the QR code. You can also type the address shown in the black window, for example `http://192.168.1.20:8000`.
   If Windows Firewall asks about Python, allow it on **Private networks**.

After setup you can switch off the internet. The app works fully offline.

## How to use it (5 steps on one page)

| Step | What you do |
|---|---|
| 1. Project details | Enter the title, subtitle, your name, company and contact. **Upload your logo**; until then a "YOUR LOGO" placeholder is used. In PowerPoint you can also right-click the logo and choose *Change Picture*. |
| 2. Slides | Click **Add screenshots** (you can select many at once), or **Import existing PPTX**. Name files `01_cost-summary.png`, `02_bom.png` and so on: they are added in that order and the file name becomes the slide title. Type notes for each screen; **one line becomes one bullet**. Use ↑ ↓ to reorder. |
| 3. Narration & voice | Click **Write narration**. The app drafts what the voice will say from your notes. **Edit the text freely.** Then pick the engine, language, voice (male/female) and speed, and click ▶ to hear it. |
| 4. Music (optional) | Choose a music file. It is lowered automatically while the voice speaks. |
| 5. Build | You see the **estimated video length and render time**. Click **Build PowerPoint** and/or **Render video**, then download the `.pptx`, `.mp4`, `.srt` and script. |

Your work is saved automatically in `projects\<project-name>\`.

---

## Tool choice per requirement

I chose tools whose **licence allows commercial use**, such as a monetised YouTube channel. Where an option is popular but **not** allowed commercially, it is listed under *Avoided* so you don't pick it by mistake.

"Runs on CPU" means it works without a graphics card. "Status" says how well the requirement can be met with free offline tools.

| # | Requirement | Tool / model chosen | Licence | Commercial use (monetised YouTube)? | Runs on CPU? | Status |
|---|---|---|---|---|---|---|
| 1a | Screenshots + notes → branded .pptx, logo slot | **python-pptx** + **Pillow** | MIT / MIT-CMU (HPND) | ✅ Yes | ✅ Yes | ✅ **Fully met** (Stage 1) |
| 1b | Import an existing PPT | **python-pptx** (titles, text, pictures, notes) → rebuilt in your brand | MIT | ✅ Yes | ✅ Yes | 🟡 **Partly met**: content and pictures are imported and re-branded, not copied pixel-for-pixel. Stage 2 adds exact slide images via **LibreOffice** (MPL-2.0). Save `.ppt` as `.pptx` first. |
| 1c | Editable narration per slide | Built-in offline script writer (Stage 1). Stage 2: optional local AI rewrite with **Ollama** + **Qwen2.5-7B-Instruct** or **Phi-4-mini** | Ollama MIT; Qwen2.5-7B Apache-2.0; Phi-4-mini MIT | ✅ Yes | ✅ Yes (the AI rewrite takes about 10–40 s per slide on CPU) | ✅ **Fully met**: drafted from notes, fully editable, saved in the PPT notes and as `.txt` |
| 2a | Offline voice-over, male + female, corporate tone | **Kokoro-82M** via kokoro-onnx | Weights Apache-2.0; kokoro-onnx MIT | ✅ Yes | ✅ Yes (around real time on a 4-core laptop) | ✅ **Fully met** for English (US/UK), Hindi, Spanish, French, Italian and Portuguese |
| 2b | Many world languages | **Piper** voices (German, Arabic, Russian, Chinese and 40+ more); **eSpeak NG** as a basic fallback | Piper engine GPL-3.0 (piper1-gpl), **licence differs per voice**; eSpeak NG GPL-3.0 | 🟡 Engine yes. **Check each Piper voice's licence** (most are CC0/CC-BY/MIT, a few are non-commercial). Audio you create with a GPL program is yours. | ✅ Yes | 🟡 **Partly met**: quality varies by language. Stage 2 adds offline translation with **Argos Translate** (MIT; check each language model's licence). |
| 3 | Talking-head avatar from one photo, lip-synced, in a corner | Stage 3: **SadTalker**; **MuseTalk** as the GPU option; **rembg**/**MediaPipe** to cut out the person | SadTalker Apache-2.0; MuseTalk MIT; rembg MIT; MediaPipe Apache-2.0 | 🟡 Code yes. **Verify each downloaded weight file** (some face-helper models in this field are research-only). | ⚠️ Technically yes, but **very slow**: a 30-minute video could take many hours on CPU. An NVIDIA GPU (6 GB+) is recommended. | 🟡 **Partly met**: realistic "talking photo" with head motion, not a full studio presenter. CPU-only users get an option to animate the avatar only on the intro and outro. |
| 4 | Office backgrounds (boardroom, modern office, stage), presenter in front, slides on a screen or side panel | Stage 3: built-in backgrounds drawn by the app (no licence issues) + your own photos; optional one-time generation with **Stable Diffusion XL 1.0**; layout composited with **FFmpeg** | App: MIT; SDXL 1.0: CreativeML Open RAIL++-M | ✅ Yes (RAIL++ allows commercial use with use-based restrictions) | ✅ Compositing yes; generating a background takes about 5–15 min on CPU, done once | ✅ **Fully met** as still backgrounds. Moving 3-D sets are not possible offline at this quality. |
| 5a | Transitions, intro/outro with logo, music, subtitles (.srt), up to ~30 min | **FFmpeg** (fade/xfade, sidechain ducking, mov_text); later **faster-whisper** for word-accurate subtitle timing | FFmpeg LGPL/GPL (used as a separate program); faster-whisper MIT; Whisper weights MIT | ✅ Yes | ✅ Yes | ✅ **Stage 1:** dip-to-navy transitions, `.srt` + embedded subtitles, music with auto-ducking, 30-minute videos. **Stage 4:** cinematic crossfades, zoom on screenshots, animated logo intro/outro, burned-in subtitles. |
| 5b | Export presets: YouTube 16:9 1080p, Reels 9:16, square 1:1, short clips | **FFmpeg** scaling/cropping + app-made vertical and square layouts | as above | ✅ Yes | ✅ Yes | ✅ **Stage 1:** YouTube 16:9 1080p. **Stage 4:** 9:16, 1:1 and per-slide short clips. |
| 6 | One simple UI, localhost + phone over Wi-Fi, rendering on the laptop | **Flask** + **waitress** + plain HTML/JS | BSD-3 / ZPL-2.1 | ✅ Yes | ✅ Yes | ✅ **Fully met** (Stage 1) |
| 7 | Normal laptop: GPU if available, CPU fallback, render-time estimate | **FFmpeg** encoder auto-detect (NVIDIA NVENC → Intel QSV → AMD AMF → CPU x264); **onnxruntime** CUDA/DirectML for voice | FFmpeg as above; onnxruntime MIT; onnxruntime-directml MIT | ✅ Yes | ✅ Yes | ✅ **Fully met** (Stage 1). The estimate is measured on *your* laptop with a quick benchmark. |

**Avoided because they don't allow commercial use:**
- **Coqui XTTS-v2**: CPML, non-commercial.
- **F5-TTS** weights: CC-BY-NC.
- **Wav2Lip**: non-commercial.
- **LivePortrait**: its InsightFace face models are non-commercial.
- **SDXL-Turbo**: non-commercial licence.
- **Meta NLLB** translation: CC-BY-NC.

**Not open-source:** the Windows built-in voices (Microsoft David/Zira, Hindi Kalpana/Hemant) are offered only as a fallback. Check Microsoft's terms before monetising videos made with them.

*Licences can change. Before publishing monetised videos, re-check the licence of each model file you download. This table is guidance, not legal advice.*

---

## The plan (5 stages)

| Stage | What you get | Status |
|---|---|---|
| **1. Core** | Project structure; screenshots/notes or PPTX import → branded `.pptx` with logo slot; editable narration (EN/HI drafts); offline voice-over (Kokoro, Piper, eSpeak, Windows voices); MP4 1080p with dip-to-navy transitions; `.srt` + embedded subtitles; background music with ducking; render-time estimate; GPU/CPU auto-detect; localhost + phone UI with QR code | ✅ **Done** |
| **2. Script & language** | Local AI rewrite in a corporate tone (Ollama, optional); offline translation to Hindi and other languages (Argos); exact slide images from imported PPTX (LibreOffice); pronunciation dictionary (e.g. "BOM" → "B-O-M", "EBITDA"); per-slide pause and voice settings | Planned |
| **3. Presenter & backgrounds** | Upload one photo → lip-synced talking head (SadTalker); background removal; presenter in a corner or in front of a boardroom, modern office or conference-stage background, with slides on a screen or side panel; GPU check and avatar render-time estimate | Planned |
| **4. Cinematic & formats** | Crossfade/slide/zoom transitions, Ken Burns zoom on screenshots, animated logo intro/outro, burned-in subtitles, word-accurate timing (faster-whisper); presets: YouTube 16:9 1080p, Reels 9:16, square 1:1, short clips per slide, thumbnail | Planned |
| **5. Polish** | One-click Windows installer (no Python needed), render queue, resume after a crash, project backup (.zip) | Planned |

---

## Voices

| Engine | Quality | Languages | Setup |
|---|---|---|---|
| **Kokoro** (default) | ★★★★★ natural | English US/UK, Hindi, Spanish, French, Italian, Portuguese; male + female | `setup_windows.bat` downloads it |
| **Piper** | ★★★★ | 40+ languages | `setup_windows.bat piper`, or put any `*.onnx` + `*.onnx.json` voice from [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices) in `models\piper\` |
| **Windows voices** | ★★★ | whatever Windows has installed | automatic on Windows (fallback) |
| **eSpeak NG** | ★★ robotic | 100+ | optional: install from [espeak-ng releases](https://github.com/espeak-ng/espeak-ng/releases) |

Tips for a corporate sound:
- Use speed 0.95–1.0×.
- Write short sentences.
- Spell out abbreviations the way you want them spoken. Example: "B O M" or "bill of materials".

## Speed (what to expect)

- **Voice, Kokoro on CPU:** around real time. 10 minutes of narration takes about 3–10 minutes, faster with `setup_windows.bat gpu`.
- **Video encoding:** about 0.1× real time on a 4-core CPU, so a 30-minute video encodes in about 3–5 minutes. It is faster with an NVIDIA, Intel or AMD GPU, which the app detects automatically.
- **Re-rendering:** voice-over is cached, so after small edits only the changed slides are spoken again.

The app shows its estimate for **your** laptop before you render.

---

## GitHub in simple words

- **Repository (repo):** the online folder that holds the app's files.
- **Branch:** a separate copy where new work is made without touching the main version. Stage 1 was built on the branch `claude/gracious-fermat-vw5d1a`.
- **Commit:** a saved snapshot of changes, with a short message.
- **Pull request (PR):** a request to copy a branch's changes into the main version. You can read every change on the PR page (tab *Files changed*).
- **Merge:** accepting the pull request. Click the green **Merge pull request** button on the PR page, then **Confirm merge**. After that, **Code → Download ZIP** on the main page gives you the newest version.
- **Before merging:** you can test the branch. On the repo page, switch the branch drop-down (top left, says `main`) to `claude/gracious-fermat-vw5d1a`, then **Code → Download ZIP**.

## For developers

```
app/
  main.py            web server + API (Flask, served by waitress on 0.0.0.0:8000)
  config.py          brand colours, folders, video settings
  layout.py          one slide layout shared by the PPTX builder and the video renderer
  ppt_builder.py     branded .pptx (python-pptx); narration -> speaker notes
  ppt_import.py      existing .pptx -> slides
  slide_render.py    slides -> 1920x1080 PNG frames (Pillow)
  script_writer.py   offline narration drafts (EN, HI)
  tts/               kokoro / piper / sapi / espeak engines
  video.py           voice-over, timeline, subtitles, FFmpeg encode + mux, estimate
  ffmpeg_utils.py    FFmpeg discovery, GPU encoder detection, speed benchmark
  jobs.py            background render with progress / cancel
  templates/, static/  the one-page UI (plain HTML/CSS/JS, works on phones)
scripts/download_models.py   one-time model download
tests/test_pipeline.py       end-to-end test: screenshots -> PPTX -> MP4 + SRT
```

Run the tests with `python -m pytest -q tests`. They use whichever voice engine is installed.

Security note: the app listens on your home network so your phone can reach it. Anyone on the same Wi-Fi could open it, so don't run it on public Wi-Fi. To keep it laptop-only, set `DTC_HOST=127.0.0.1`.
