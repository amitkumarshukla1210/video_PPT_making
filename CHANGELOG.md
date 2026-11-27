# Changelog — Design to Cost · Presentation & Video Studio

The version number is in the file `VERSION` and is shown in the app header, the studio footer and
the black start-up window. Numbering: **MAJOR.MINOR.PATCH**
- **PATCH** (1.2.**1**): small fixes, nothing new to learn.
- **MINOR** (1.**3**.0): new features; your projects keep working.
- **MAJOR** (**2**.0.0): a big change that may need a fresh setup or changes to old projects.

## 1.9.2 — 2026-11-27
- **Fix: the picture creator failed with "Shape inference … Concat … [2,1280,28,48] [2,640,27,48]".** Pictures were
  drawn at 768×432, but this model only works with sizes in multiples of 64. They are now drawn at 768×448 (and
  448×768 for 9:16), then trimmed to the exact 16:9 / 9:16 shape. This affects Tools › Image, character portraits,
  world views, pictures in Make a video and the Studio's picture creator.
- If the graphics card cannot run the model, or fails while drawing, the picture creator now switches to the
  processor (CPU) instead of failing.
- New **🔍 Check picture creator** button in Tools › Image. It tests the versions, the graphics card, model loading
  and one small picture, and shows a report you can copy. Errors are now short and readable; the full log is kept in
  `models\logs\picture_creator.log`.

## 1.9.1 — 2026-11-27
- Fix: the picture creator failed with "module transformers has no attribute CLIPFeatureExtractor". Version 5
  of the `transformers` package removed that name, but the picture model still uses it.
  - The app now maps it to its replacement, `CLIPImageProcessor`.
  - The picture creator's install now keeps `transformers` below 5. `update_windows.bat` does this for you.
- Tools are now in the order a film is made: **1 Character → 2 Image → 3 World → 4 Audio → 5 Video**, in the
  tabs and in the left menu. Tools opens on Character.
- Pictures are no longer pushed towards "corporate photography". Your prompt and the chosen style decide the look
  (film characters, mythology, anime…).

## 1.9.0 — 2026-11-26
- **Inspirations now has 100 examples in 9 categories:** 11 each in Trending Templates, Short Film, Music Video,
  UGC Ads, Product Ads, Film Trailer, Social Content and Explainer, plus **12 Viral presets**.
- **New: Viral presets** — your photo + a camera effect + words + music, made for Reels and Shorts.
  The 12 effects are: zoom punch on the beat, pull-back reveal, spin-in, glitch, camera shake, polaroid
  drop, split reveal, VHS retro, flash cuts, duotone poster, 3·2·1 countdown and dreamy drift.
  **Use with my photo** opens Tools › Video with the preset filled in; pick your photo and make the clip.
  Every preset can be previewed on a sample photo.
- Tools › Video: new **Effect** list and **Start from a viral preset**.
- A corporate scene with only a title (no points, no narration) now shows as a big statement.

## 1.8.0 — 2026-11-26
- **New: Tools** in the left menu, under ❖ Inspirations. They work like the tool sections of online AI suites,
  but all offline:
  - **🎬 Video** — a picture becomes an animated clip: camera push-in, your words rising over it, music
    (4–15 s, any look). Shortcuts to Make a video, Inspirations and the Studio.
  - **🖼 Image** — pictures from a prompt, with 9 styles, 3 shapes (16:9, 9:16, 1:1) and 1–4 at once, kept in
    My pictures. Each picture has a "Clip" button.
  - **🎙 Audio** — voice-over from text in any installed voice (also your cloned voice, and "speak as" a
    character), music by mood and length, and sound effects. Play, download or save each one.
  - **🧑 Character** — save a person once (name, look, optional portrait and voice). Type **@Name** in picture
    prompts and in Make a video ideas, and the description is filled in, so the person looks the same in
    every scene.
  - **🌍 World** — save a place once and reuse it as **@Place**. A walkable 3D world is not possible offline;
    scenes use camera moves instead.
- Everything you make is kept in the app folder under `my_media\`. Updates keep it, and backups include it.

## 1.7.1 — 2026-11-26
- **Inspirations: ▶ Preview.** Every example can now be played. Click the picture or **▶ Preview** to watch about
  10 seconds of its opening and first scenes, with its music. It is made on your laptop the first time
  (about 10–20 seconds), then it starts instantly.
- Fix: videos played in a dialog were shown mirrored. Only the webcam preview is mirrored now.
- Fix: in charts, "hrs" (hours) was read as "Rs" (rupees), so the wrong bar was highlighted.

## 1.7.0 — 2026-11-25
- **New: Inspirations** (`/inspirations`, first item in the left menu): **32 example videos in 8 categories**, each
  with its category label. The categories are Trending Templates, Short Film, Music Video, UGC Ads, Product Ads,
  Film Trailer, Social Content and Explainer. They are made for film studios, YouTube, Instagram and Facebook,
  not only for business.
  Each example is complete: scenes, on-screen text, narration, picture prompts, format, look and music.
  **Use this example** opens it in Make a video. Type your topic and the local AI rewrites it for you, keeping its shape.
- **Looks** for motion graphics:
  - **Corporate** — Design to Cost colours
  - **Cinematic** — dark, gold, cinema bars
  - **Bold social** — black, yellow, pink
  - **Warm** — cream, terracotta

  Choose one in Make a video step 4.
- New scenes:
  - **statement** — one big centred line, word by word, for trailers, music videos and social clips
  - **film shot** — your picture fills the screen with a slow camera push and the words over it
- Music videos run without a voice: the words land on the beat and the music is louder.
- The Design to Cost logo and page numbers appear only in the Corporate look, or when you upload your own logo.
- Formats now name every platform: YouTube / Facebook video 16:9, Reel (Instagram · Facebook · YouTube Shorts) 9:16,
  and Square post 1:1 (Instagram · Facebook · LinkedIn).
- Rupee amounts use Indian grouping (₹9,00,000).

## 1.6.0 — 2026-11-25
- **New: Motion graphics.** In Make a video step 4 (and in Presentation › Video), choose
  **Animation: Motion graphics**. Each scene's animation is chosen from its own content:
  - title and closing: the words rise in one by one, the orange bar draws, the logo pops
  - one number (e.g. "Steel up 8%"): a big counter that counts up
  - several numbers (e.g. supplier quotes): a bar chart that grows. For costs and prices, the **lowest**
    value (the best quote) is in orange.
  - a picture or screenshot: shown whole on a card, revealed, then a slow camera push-in
  - points: each one appears **when the voice says it**
  - every scene ends with a short push-out, and a thin line runs across the top so the picture never freezes
  - with library music, every cut lands **on the beat**
- Ideas follow huashu-motion (MIT, github.com/alchaincyf/huashu-motion): pick the motion from the content,
  anchor reveals to the narration, cut on the beat. The code is our own and runs offline, with no AI agent.
- Classic slides are still available; existing projects keep their look until you switch.

## 1.5.2 — 2026-11-14
- Back to **port 8000** (http://localhost:8000), so Design to Cost and other software on port 8080 can run
  at the same time. Version 1.5.1 used port 8080; update your bookmarks back to :8000.

## 1.5.1 — 2026-11-14
- The app used port 8080 (changed back in 1.5.2).

## 1.5.0 — 2026-11-14
- **New: Make a video** (`/make`), a guided page in four steps:
  1. **Source:** a PowerPoint, pictures, a document (PDF, Word, text, HTML), a web link, pasted text or just an idea.
  2. **Script, scene by scene:** the local AI writes it (or an offline first draft); edit, remove scenes,
     rewrite with AI, add AI pictures.
  3. **Voice-over:** any installed voice, including your cloned voice; hear it first.
  4. **Video type:** YouTube 16:9, Instagram Reel / YouTube Shorts 9:16, corporate video (logo intro and outro,
     corporate music, captions) or LinkedIn square 1:1.
- **New: My projects** (`/projects`): every project with its videos, PowerPoint and subtitles. Play, download,
  continue, or delete. Each finished video is kept with its type and date, so older versions are not lost.
- The Video & Voice Studio now opens in light (white) mode, even when Windows is in dark mode.
  The ◐ button still switches to dark if you want it.
- Fix: pages no longer run off the right edge of the screen.
- New package: `pypdfium2` (reads PDF pages). `update_windows.bat` installs it automatically.

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
