# Video & Voice Studio — plan

## 1. Repo summary (as found)

| Area | What exists |
|---|---|
| Purpose | "Design to Cost — Presentation & Video Studio": screenshots + notes → branded PPTX + narrated MP4, offline on Windows |
| Stack | Python 3.11–3.13, Flask + waitress (local server on `0.0.0.0:8000`), python-pptx, Pillow, FFmpeg (system or `imageio-ffmpeg`), Kokoro / Piper / eSpeak / Windows SAPI TTS, optional Chatterbox voice clone in `.venv-clone` |
| Front end | One server-rendered page `app/templates/index.html` + plain ES2020 `app/static/app.js` + `style.css` on top of `dtc-theme.css` (Design to Cost theme: navy `#152238`, blue `#1f5fa8`, orange accent `#e07b1f`, Segoe UI). **No build tool, no npm.** |
| Tests | `pytest` (`tests/test_pipeline.py`, `tests/test_features.py`): end-to-end FFmpeg renders with eSpeak |
| CI | none |
| Hosting | none (local app only) |
| Branches | `main` (initial commit only) ← PR #1 `claude/gracious-fermat-vw5d1a` (all app code, open) |

## 2. Decisions

| Decision | Why |
|---|---|
| New page lives in **`studio/`** as a **static, client-side app** (HTML + ES modules, no bundler) | Must be hostable on GitHub Pages (no server) and match the repo's no-build-tool style. |
| Same page is also served by the local Flask app at **`/studio/`** | One app for the user; and the local server becomes the "local TTS server". |
| Flask gets an **OpenAI-compatible `POST /v1/audio/speech`** (+ `GET /v1/audio/voices`) backed by the existing Kokoro/Piper/eSpeak engines, with CORS + Private-Network-Access headers | Makes engine (c) work out of the box, also from the GitHub Pages copy (`https` page → `http://localhost` is allowed for localhost). |
| ffmpeg.wasm: vendor the small MIT wrapper (`@ffmpeg/ffmpeg` 0.12.15, `@ffmpeg/util` 0.12.2) in `studio/vendor/`; load the **single-threaded core** (`@ffmpeg/core` 0.12.10, GPL-2.0+) lazily from jsDelivr as blob URLs | The wrapper's worker must be same-origin; the single-thread core needs no `SharedArrayBuffer`, so no COOP/COEP headers (GitHub Pages can't set them). Core is loaded only when the user exports MP4/MP3. |
| MP4: use **native `MediaRecorder` MP4** when the browser supports it (Chrome ≥ 126, Safari), else WebM → ffmpeg.wasm (`libx264 ultrafast`, AAC) | Native is instant; wasm transcode of 10 min 1080p is slow, so only as fallback. |
| Rendering is **real time** (canvas `captureStream` + Web Audio → `MediaRecorder`) | Only portable way without a server; a 10-min video takes ~10 min; progress + cancel provided. Audio-only export is mixed **offline** (`OfflineAudioContext`, fast). |
| Web Speech voices are **preview-only** | Browsers don't expose speech-synthesis audio to Web Audio / MediaRecorder, so it can't be put into a file. Export with this engine is blocked with a clear message and a one-click switch to the local server / ElevenLabs. |
| Media (images, video clips, music, generated voice) in **IndexedDB**; project JSON in **localStorage** (autosave) | localStorage is ~5 MB; media is large. JSON download can optionally embed media as data URLs for a portable file. |
| Ducking = **gain automation computed from the timeline** (music dips while any voice clip plays) | Deterministic, identical in live render and offline audio export; no sidechain node exists in Web Audio. |
| Hard limit **10 min** in the studio (the existing PPT video tool keeps its 15-min limit) | As specified. Enforced in the timeline module, UI meter and export guard. |
| ElevenLabs key: `localStorage` only, sent only to `api.elevenlabs.io` in the `xi-api-key` header, never logged, never in project JSON | As specified. |

## 3. Architecture

```
studio/studio.html           page shell (header, icon strip, work areas, settings dialog); studio/index.html redirects to it
studio/css/studio.css        DTC theme tokens + dark mode + responsive layout
studio/js/main.js            boot, UI wiring, rendering of lists, keyboard shortcuts
studio/js/templates.js       5 templates (scene structure, durations, text/transition style, music mood, pacing)
studio/js/scenes.js          script → scenes splitter, word counts, duration estimates
studio/js/timeline.js        timeline from scenes + voice durations, 10-min limit, SRT/cues
studio/js/store.js           project state, autosave, undo/redo, JSON import/export, validation
studio/js/media.js           IndexedDB blob store (+ data-URL embed/restore for portable JSON)
studio/js/voices/*.js        engines: elevenlabs, webspeech, local (OpenAI-compatible) + registry, presets
studio/js/render/draw.js     draws one frame at time t (backgrounds, Ken Burns, text, subtitles, transitions, cards)
studio/js/render/audio.js    decode, voice schedule, music ducking, offline mix, WAV encoder
studio/js/render/export.js   real-time capture (MediaRecorder), cancel, progress, format choice
studio/js/render/ffmpeg.js   lazy ffmpeg.wasm loader + transcode helpers
studio/vendor/ffmpeg/        vendored MIT wrapper (+ LICENSE note)
app/main.py                  + /studio/ static route, + /v1/audio/speech, /v1/audio/voices
tests/studio/*.test.mjs      node --test unit tests for pure modules
tests/test_studio_e2e.py     Playwright (Chromium) end-to-end against the Flask server
.github/workflows/ci.yml     pytest + node tests on every push/PR
.github/workflows/pages.yml  deploys studio/ to GitHub Pages
```

## 4. Data flow

1. Template → `store.project.template` (defaults for durations, styles, music mood, pacing).
2. Script textarea → `scenes.split()` → `project.scenes[]` (id, title, text, background, durationHint, transition, voiceOverride).
3. Per scene: engine.synthesize(text, voiceSettings) → audio `Blob` → IndexedDB (`voice:<sceneId>:<hash>`), duration stored on the scene. Hash = text + voice settings, so unchanged scenes are never regenerated.
4. `timeline.build(project)` → scene start/end, title/end cards, captions; `limit` check (10 min).
5. Preview: same `draw.frame(ctx, t)` + Web Audio graph, in a small canvas.
6. Export video: canvas `captureStream(30)` + `MediaStreamAudioDestinationNode` → `MediaRecorder` → WebM/MP4 → (optional) ffmpeg.wasm → download. SRT always available.
7. Export audio: `OfflineAudioContext` render of the same audio graph → WAV (own encoder) → (optional) MP3 via ffmpeg.wasm.

## 5. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Web Speech audio can't be captured | Preview-only, clear message, switch button. |
| ffmpeg.wasm is ~31 MB and slow single-threaded | Lazy-loaded only for MP4 fallback / MP3; native MP4 preferred; progress + cancel. |
| CDN blocked / offline | Error explains; WebM and WAV exports still work; core URL configurable in Settings. |
| Real-time render ties up the tab | Progress, ETA, cancel; warns not to switch tabs (Chrome throttles background tabs → uses `requestAnimationFrame` fallback to timers). |
| localStorage quota | Media in IndexedDB; autosave catches `QuotaExceededError` and tells the user. |
| ElevenLabs errors (401, 429/quota, network) | Mapped to friendly messages; preview falls back to browser voice automatically. |
| Cross-origin images taint canvas | Only user-uploaded files (blob URLs) are used, never remote URLs. |

## 6. Test plan

- **Unit (node --test, no deps):** scene splitting (paragraphs, headings, long text, empty), template defaults, timeline maths, 10-min limit and remaining time, SRT formatting, undo/redo, project JSON validation/migration, WAV encoder header, ElevenLabs error mapping, local-server request shape.
- **E2E (pytest + Playwright Chromium, against Flask):** page loads with no console errors; template → script → scenes (edit, reorder, delete, undo/redo); background colour + uploaded image; voice preset save/load; local engine synth via `/v1/audio/speech` (eSpeak in CI); preview; WebM export of a short project (checks file size + duration with FFmpeg); SRT download; WAV export; 10-min limit blocks export; project JSON download → upload round-trip; dark mode toggle; keyboard-only path; mobile viewport layout. ffmpeg.wasm MP4 conversion tested with the core served locally (CDN blocked in CI sandbox).
- **API (pytest):** `/v1/audio/speech` returns WAV/MP3, validates input, CORS/PNA headers.

## 7. Hosting plan

- **GitHub Pages:** `.github/workflows/pages.yml` uploads `studio/` as the Pages artifact on push to `main` (and manual dispatch). Settings → Pages → Source: *GitHub Actions* (one-time click by the owner). URL: `https://<owner>.github.io/video_PPT_making/studio.html`.
- Everything uses relative paths, so it also works at `/studio/` on the local Flask server and from any static host.
- No secrets in the repo; ElevenLabs key lives only in the user's browser.
