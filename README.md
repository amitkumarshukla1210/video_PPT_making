# Design to Cost — Presentation & Video Studio

A free, open-source app for **Design to Cost** that runs **offline on your Windows laptop**. It turns screenshots and notes (or an existing PowerPoint) into:

- a **branded PowerPoint** in the Design to Cost theme (navy `#152238`, blue `#1f5fa8`, orange `#e07b1f`, Segoe UI, DC logo), with the narration in the speaker notes
- an **editable narration script** for each slide
- a **presentation video (MP4, max 15 minutes)** with:
  - a voice-over in a stock voice **or your own cloned voice**
  - **you in the corner** explaining the slides, from a phone or webcam recording, or your photo
  - a logo intro and outro, subtitles (`.srt`) and optional music
- **social formats**: Instagram Reels / Shorts 9:16, square 1:1, and short clips of selected slides

You can use it from the laptop's browser or from your **phone's browser over home Wi-Fi**. Heavy work always runs on the laptop.

---

## Video & Voice Studio (web page, no install needed)

A second tool in this repo: a **browser page** that turns a script into a narrated video or an audio
piece. It runs fully in the browser, so it can be hosted for free on GitHub Pages.

**Live URL** (after the one-time Pages setup below): `https://<user>.github.io/<repo>/studio.html`
— for this repo: **https://amitkumarshukla1210.github.io/video_PPT_making/studio.html**

### Features
- **5 templates:** Inspiration, Film trailer, Explainer, Product video and Audio documentary. Each sets the scene structure, default lengths, text style, transition, music mood and voice pacing.
- **Workflow:** choose a template → write or paste a script → **Split into scenes**. You can then edit, add, reorder (↑↓) and delete scenes, give each one a colour, image or video background, and set its length.
- **Voice engines** (switchable):
  - **Browser / Windows voices** — free and offline, but **preview only**: browsers don't give the audio to the page, so it can't go into a file.
  - **Local voice server** — this repo's app (Kokoro / Piper / eSpeak) or any OpenAI-compatible `/v1/audio/speech` server.
  - **ElevenLabs** — with your own API key, kept only in this browser.
- **Voice controls:** voice list, speed, pitch (browser voices), stability and similarity (ElevenLabs).
  - You can preview and regenerate one scene at a time, or give a scene its own voice.
  - A **voice library** saves named presets.
  - Errors (wrong key, quota used up, no internet) show a clear message, and the preview falls back to a browser voice.
- **Video:**
  - 720p or 1080p, in 16:9, 9:16 or 1:1.
  - Fade, slide and zoom transitions, slow pan/zoom on images, and title and end cards with the DC logo.
  - Subtitles burned into the picture, plus a `.srt` download.
  - Background music that is lowered automatically under the voice.
  - A progress bar and a Cancel button.
- **Hard limit of 10 minutes:** a meter shows the time left, and export is blocked when the video is too long.
- **Export formats:**
  - **WebM** (native).
  - **MP4** — recorded directly where the browser supports it, otherwise converted with ffmpeg.wasm. ffmpeg.wasm is downloaded only when it's needed.
  - **Audio only:** **WAV** or **MP3**.
- **Projects:** autosave in the browser, undo/redo (Ctrl+Z / Ctrl+Y), and Save/Open as a `.json` file that includes your images and music.
- Dark/light mode, phone and tablet layouts, keyboard and screen-reader friendly.

### How to use the studio
1. Open the page: either the live URL, or **http://localhost:8000/studio/** while `start_windows.bat` is running.
2. Click a template, then **Use template sample** or paste your own script, then **Split into scenes**.
3. Under **Voice**, choose the engine:
   - **Local voice server**: works out of the box when the Design to Cost app is running on this laptop.
   - **ElevenLabs**: click ⚙ **Settings** and paste your API key.
4. Click **▶ Play preview**. Then choose the shape, quality and file type, and click **Export**.

### Voice engine setup
| Engine | Setup |
|---|---|
| Browser / Windows voices | Nothing. Preview only. |
| Local voice server | Run `start_windows.bat`. The page calls `http://localhost:8000/v1/audio/speech`; the server allows calls from `localhost` and `*.github.io` pages. Another server: ⚙ Settings → *Server URL*. |
| ElevenLabs | ⚙ Settings → paste your key. It is stored only in this browser (localStorage), sent only to `api.elevenlabs.io`, and never saved in project files or the repo. |

### Run locally, and test
```
start_windows.bat                       # then open http://localhost:8000/studio/
node --test tests/studio/*.test.mjs     # unit tests (no install)
python -m pytest -q                     # app + speech API + browser end-to-end tests
```
The end-to-end tests need `pip install playwright` and `python -m playwright install chromium`.
The MP4/MP3 tests also need the ffmpeg.wasm core in `tests/.cache`; CI does this:
`cd tests/.cache && npm pack @ffmpeg/core@0.12.10 && mkdir ffmpeg-core && tar xzf ffmpeg-core-0.12.10.tgz -C ffmpeg-core`.

### Hosting on GitHub Pages (one time)
1. Merge the pull request into `main`.
2. **Settings → Pages → Source: GitHub Actions.**
3. The `CI` workflow runs the tests and then publishes `studio/` to Pages. Every later merge to `main` updates the site.

More detail: `docs/studio-plan.md` (design), `docs/studio-report.md` (results), `docs/studio-bugs.md` (bugs fixed).

---

## Quick start (Windows), step by step

You only do steps 1–3 once.

1. **Install Python** (free) from <https://www.python.org/downloads/>. Choose version 3.11, 3.12 or 3.13.
   During installation, **tick "Add python.exe to PATH"**.
2. **Download this app.** On the GitHub page, click the green **Code** button, then **Download ZIP**. Unzip it to a simple folder, for example `C:\DTC-Studio`.
3. **Double-click `setup_windows.bat`.** It needs the internet **once** (about 10 minutes, roughly 500 MB) and downloads the Kokoro voices.
   Optional extras: open a Command Prompt in that folder and type one of these. You can combine them, e.g. `setup_windows.bat clone gpu`.

   | Command | What it adds |
   |---|---|
   | `setup_windows.bat clone` | **Voice clone**, so the app can speak in *your* voice. About 3 GB extra. |
   | `setup_windows.bat gpu` | Uses your graphics card for the voices (NVIDIA, AMD or Intel). |
   | `setup_windows.bat small` | Smaller, faster voice model for older laptops. |
   | `setup_windows.bat piper` | Extra languages through Piper voices. |
4. **Double-click `start_windows.bat`.** A black window opens; keep it open while you use the app. Your browser opens at `http://localhost:8000`.
5. **On your phone:** connect to the same Wi-Fi, click **📱 Phone** in the app and scan the QR code. If Windows Firewall asks about Python, allow it on **Private networks**.

After setup you can switch off the internet. Everything works offline.

## How to use it

| Step | What you do |
|---|---|
| **1. Project details** | Enter the title, subtitle, your name, company and contact. The **Design to Cost logo** is used by default; you can upload another logo per project. |
| **2. Slides** | Click **Add screenshots** (many at once), or **Import existing PPTX**. Name files `01_cost-summary.png`, `02_bom.png` and so on: they are added in that order and the name becomes the title. One line of notes becomes one bullet.<br>**Explain a slide yourself:**<br>• On the **laptop**: **🎥 Record** uses the webcam and shows the narration as a teleprompter.<br>• On the **phone**: **📱 Phone camera / file** opens the front camera.<br>Your video appears in the corner of that slide, and **your real voice** is used. |
| **3. Narration & voice** | **Write narration** drafts the text from your notes; edit it freely. Pick an engine, language, gender, voice and speed, and click ▶ to hear it.<br>**Voice clone:** tick the consent box, then record or upload 10–30 s of yourself reading the suggested text. Choose **"My cloned voice"** as the engine. |
| **4. Presenter** | Optional **photo** for slides you didn't record. Choose the corner (bottom-right / top-right), shape (circle / rounded) and size. |
| **5. Build** | Music (auto-ducks under the voice) and logo intro/outro on/off. The **length meter** shows minutes used out of **15:00**, plus the **estimated render time** for your laptop. Then **Build PowerPoint** and **Render video**.<br>Under **Social formats & short clips**, pick Reels 9:16, square 1:1 or YouTube 16:9, optionally a slide range (e.g. slides 3–4 = a short clip), and subtitles burned into the picture. |

Your work is saved automatically in `projects\<project-name>\`.

---

## Tool choice per requirement

I chose tools whose **licence allows commercial use**, such as a monetised YouTube channel. "Runs on CPU" means it works without a graphics card.

| # | Requirement | Tool / model | Licence | Commercial use (monetised YouTube)? | Runs on CPU? | Status |
|---|---|---|---|---|---|---|
| 0 | Design to Cost theme + logo everywhere | `dtc-theme.css`, DC logo redrawn at high resolution | yours | ✅ | ✅ | ✅ **Done**: app header, favicon, slides, video intro/outro |
| 1a | Screenshots + notes → branded .pptx | **python-pptx** + **Pillow** | MIT / MIT-CMU | ✅ | ✅ | ✅ **Done** |
| 1b | Import an existing PPT | **python-pptx** (titles, text, pictures, notes → re-branded) | MIT | ✅ | ✅ | 🟡 **Partly**: content is re-branded, not copied pixel-for-pixel. Save `.ppt` as `.pptx` first. |
| 1c | Editable narration per slide | Built-in offline script writer (EN, HI) | MIT | ✅ | ✅ | ✅ **Done** |
| 2 | **Video max 15 min** | Length meter + check before and during rendering | — | — | ✅ | ✅ **Done** |
| 3a | Voice-over, voice selection (male/female, language, speed) | **Kokoro-82M** | Apache-2.0 | ✅ | ✅ about real time | ✅ **Done** for EN US/UK, Hindi, ES, FR, IT, PT |
| 3b | More languages | **Piper**; **eSpeak NG** as backup | GPL-3.0 engines; **licence differs per Piper voice** | 🟡 check each voice | ✅ | 🟡 **Partly**: quality varies by language |
| 3c | **Voice clone** (your own voice) | **Chatterbox Multilingual** (Resemble AI), 23 languages incl. Hindi | MIT (code + weights) | ✅ Yes, for your own voice or with written permission. Output carries an inaudible AI watermark. | ⚠️ Works but slow: roughly 3–5 s of compute per second of speech on CPU. 15 min of speech ≈ 45–75 min. An NVIDIA GPU is about 8× faster. | ✅ **Done** (code tested with a stand-in model; see *Testing*) |
| 4 | **Your video in the corner explaining the slides** | Recording in the browser (MediaRecorder) or phone camera, combined with **FFmpeg** | LGPL/GPL (separate program) | ✅ | ✅ ~3× slower than a plain slide | ✅ **Done**: your real face and real voice |
| 4b | Presenter from one photo | Photo in the corner bubble | — | ✅ | ✅ | ✅ **Done** without lip movement. AI lip-sync (SadTalker, Apache-2.0) is **not included**: on CPU it needs hours for 15 min, and some of its helper models have research-only licences. Your own recording (row 4) gives a better result. |
| 5 | Office backgrounds (boardroom, stage) | — | — | — | — | ⏸ **Not built**: your own recording already shows your real background. A virtual background would need person-cutout (rembg MIT / MediaPipe Apache-2.0) and is slow on CPU. |
| 6 | Transitions, logo intro/outro, music, subtitles | **FFmpeg** (fades, zoom, sidechain ducking, mov_text, libass) | LGPL/GPL | ✅ | ✅ | ✅ **Done**: dip-to-navy transitions, animated logo intro + outro, `.srt` + embedded subtitles, burned-in subtitles for Reels |
| 7 | Export: YouTube 16:9, Reels 9:16, square 1:1, short clips | **FFmpeg** reframing (blurred fill) + cut by slide | LGPL/GPL | ✅ | ✅ | ✅ **Done** |
| 8 | One simple UI, localhost + phone | **Flask** + **waitress** + plain HTML/JS | BSD-3 / ZPL-2.1 | ✅ | ✅ | ✅ **Done** |
| 9 | GPU if available, CPU fallback, render-time estimate | FFmpeg NVENC / QSV / AMF auto-detect; onnxruntime CUDA/DirectML; PyTorch CUDA (clone) | MIT | ✅ | ✅ | ✅ **Done** |

**Avoided because they don't allow commercial use:**
- **Coqui XTTS-v2**: CPML, non-commercial.
- **F5-TTS** weights: CC-BY-NC.
- **Wav2Lip**: non-commercial.
- **LivePortrait**: its InsightFace face models are non-commercial.
- **SDXL-Turbo**: non-commercial licence.
- **Meta NLLB** translation: CC-BY-NC.

**Not open-source:** the Windows built-in voices are only a fallback; check Microsoft's terms before monetising.

*Licences can change. Re-check the licence of each model you download before publishing monetised videos. This table is guidance, not legal advice.*

---

## Stages

| Stage | What you get | Status |
|---|---|---|
| **1. Core** | Branded PPTX, editable narration, offline voice-over MP4, subtitles, music, local + phone UI, GPU detect, estimate | ✅ Done |
| **2. Voice** | Voice selection with a gender filter, **voice clone** (Chatterbox, 23 languages), recording or upload of the voice sample with a consent check | ✅ Done |
| **3. Presenter** | **Your recording in the corner** with a webcam teleprompter or phone camera, your real voice; photo presenter; position, shape and size options | ✅ Done |
| **4. Cinematic & formats** | Animated logo intro/outro, 15-minute limit, Reels 9:16, square 1:1, short clips by slide range, burned-in subtitles | ✅ Done |
| **5. Polish** | One-click installer without Python, local-AI script rewrite (Ollama), offline translation, exact rendering of imported PPTX, virtual office backgrounds, AI lip-sync on GPU | Ideas for later; tell me which matter most |

## Voices

| Engine | Quality | Languages | Setup |
|---|---|---|---|
| **Kokoro** (default) | ★★★★★ natural | English US/UK, Hindi, Spanish, French, Italian, Portuguese; male + female | `setup_windows.bat` |
| **My cloned voice** | ★★★★ your own voice | 23: English, Hindi, Arabic, German, French, Spanish, Chinese, Japanese, Russian… | `setup_windows.bat clone`, then record a sample in the app |
| **Piper** | ★★★★ | 40+ | `setup_windows.bat piper` |
| **Windows voices** | ★★★ | whatever Windows has | automatic (fallback) |
| **eSpeak NG** | ★★ robotic | 100+ | optional install |

Tips for a good voice clone:
- Record in a quiet room, 20 cm from the microphone.
- Read 15–30 seconds at your normal presenting pace.
- Use one sample per project, and re-record it if the voice sounds off.

**Only clone your own voice, or a voice you have written permission for.**

## Speed (what to expect on a normal 4-core laptop)

| Work | Time |
|---|---|
| Kokoro voice | About real time (10 min of speech ≈ 3–10 min). |
| Cloned voice on CPU | About 3–5× slower than real time; plan a coffee break for long videos. With an NVIDIA GPU it is about real time. |
| Slides | Encoding takes about 0.1× real time, so a 15-minute video encodes in about 1.5–3 minutes. |
| Slides with your recording | About 3× the time of a plain slide. |
| Re-rendering | Voices and recordings are cached, so after small edits only changed slides are redone. |

The app shows its estimate for **your** laptop before you render.

---

## GitHub in simple words

- **Repository (repo):** the online folder with the app's files.
- **Branch:** a separate copy where new work is made. This work is on `claude/gracious-fermat-vw5d1a`.
- **Commit:** a saved snapshot of changes with a short message.
- **Pull request (PR):** a request to copy a branch's changes into the main version. Tab *Files changed* shows every change.
- **Merge:** on the PR page click **Merge pull request**, then **Confirm merge**. After that, **Code → Download ZIP** on the main page gives the newest version.
- **Testing before merging:** switch the branch drop-down (top left, says `main`) to `claude/gracious-fermat-vw5d1a`, then **Code → Download ZIP**.

## For developers

```
studio/              Video & Voice Studio (static page: studio.html, css/, js/, vendor/ffmpeg)
app/
  main.py            web server + API (Flask, served by waitress on 0.0.0.0:8000); also serves /studio/
  speech_api.py      OpenAI-compatible /v1/audio/speech + /v1/audio/voices for the studio
  config.py          brand, folders, video settings, 15-minute limit
  layout.py          slide layout shared by PPTX and video (+ presenter bubble positions)
  ppt_builder.py     branded .pptx; narration -> speaker notes
  ppt_import.py      existing .pptx -> slides
  slide_render.py    slides -> 1920x1080 PNG frames, presenter bubble
  script_writer.py   offline narration drafts (EN, HI)
  media.py           recordings, voice samples and photos -> standard formats
  tts/               kokoro / clone (+ clone_worker in .venv-clone) / piper / sapi / espeak
  video.py           timeline, voice-over, presenter overlay, intro/outro, mux, exports, estimate
  ffmpeg_utils.py    FFmpeg discovery, GPU encoder detection, speed benchmark
  jobs.py            background render/export with progress and cancel
  templates/, static/  one-page UI (Design to Cost theme, works on phones)
scripts/             one-time model downloads
tests/               end-to-end tests (python -m pytest -q tests)
```

Security note: the app listens on your home network so your phone can reach it. Don't run it on public Wi-Fi. To keep it laptop-only, set `DTC_HOST=127.0.0.1`.
