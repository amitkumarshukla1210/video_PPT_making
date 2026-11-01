# Video & Voice Studio — delivery report

## Result
- New static page **`studio/studio.html`**. It is served by the app at `http://localhost:8000/studio/` and is deployable to GitHub Pages at `https://<user>.github.io/<repo>/studio.html`.
- **Tests: 70 / 70 passing.**
  - 39 unit tests: `node --test tests/studio/*.test.mjs`.
  - 31 Python tests: `python -m pytest -q`. That is the 5 existing app tests, 5 speech-API tests and 21 browser end-to-end tests.
- **Bugs found and fixed: 7**, see `docs/studio-bugs.md`.
- Lint: the repo has no linter configured. `pyflakes` is clean on the touched Python files, and `node --check` is clean on all JS.
- Secret scan: no keys or tokens in the repo. `.gitignore` now blocks `.env`, `*.har`, `*.key`, `*.pem`, `*secret*`, `*apikey*` and test output.

## What the end-to-end tests cover (Chromium, fresh context and empty storage per test)
| Case | Test |
|---|---|
| Every template (5) makes a 10-second video with a non-empty file (WebM, decoded length 9–11.5 s, VP8/9 + Opus) | `test_every_template_exports_a_10_second_video[*]` |
| 10-minute limit blocks export and shows the time left / over | `test_ten_minute_limit_blocks_export` |
| Engine switch (browser ↔ local ↔ ElevenLabs), voice list, controls per engine | `test_engine_switch_and_voice_list` |
| Invalid ElevenLabs key: clear error, preview falls back to the browser voice, key never in the project | `test_invalid_elevenlabs_key_shows_error_and_falls_back` |
| Scene add / edit / reorder / delete, undo / redo (buttons + Ctrl+Z / Ctrl+Y), transition per scene | `test_scene_add_edit_reorder_delete_undo_redo` |
| `.srt` matches the voice timing exactly | `test_srt_matches_the_voice_timing` |
| Music ducking applied (music level under the voice measured at 0.2–0.4× the normal level) | `test_music_is_ducked_under_the_voice` |
| Project save → new → open round trip, including an embedded image; a broken file gives a message | `test_project_save_and_open_round_trip` |
| Autosave survives a reload | `test_autosave_survives_reload` |
| MP4 via ffmpeg.wasm: H.264 + AAC; core downloaded **only** when MP4 is exported | `test_mp4_export_via_ffmpeg_wasm_is_lazy` |
| MP4 recorded natively when the browser supports it (no ffmpeg download) | `test_mp4_export_native_when_supported` |
| Audio-only WAV + MP3 (Audio documentary defaults to MP3) | `test_audio_only_export_wav_and_mp3` |
| Mobile 390 px: one column, no sideways scrolling | `test_mobile_layout` |
| Dark/light mode, keyboard template choice (arrow keys) | `test_dark_mode_and_keyboard_template_choice` |
| Voice library presets, per-scene voice, regenerate one scene | `test_voice_presets_and_per_scene_voice` |
| Cancel stops a running export | `test_cancel_stops_a_running_export` |
| No console errors on the page (checked after **every** test) | `studio` fixture |
| Page structure, headings, accessible button names | `test_page_loads_and_is_accessible` |

ElevenLabs and the local voice server are mocked with Playwright route interception, so no real or paid API is called. The ffmpeg.wasm core is served from `tests/.cache`.

## Decisions made without asking
1. **Branch base.** The PR targets `main`. It therefore also contains the app from PR #1, which is not merged yet, so one merge puts everything live.
2. **Static page, no build tool.** Plain ES modules, matching the repo's no-bundler style. Also served by the Flask app.
3. **Browser voices are preview-only.** Browsers don't expose speech-synthesis audio to the page, so it can't be recorded. Export with that engine asks you to pick another engine, or to untick *Include voiceover*.
4. **The local Flask app gained an OpenAI-compatible `/v1/audio/speech` endpoint.** It is backed by Kokoro / Piper / eSpeak, and sends CORS and Private-Network-Access headers for `localhost`, the LAN and `*.github.io`. That makes the "local TTS server" engine work out of the box, even from the GitHub Pages copy.
5. **ffmpeg.wasm setup:**
   - The small MIT wrapper is vendored in `studio/vendor/ffmpeg`, because the worker must be same-origin.
   - The single-threaded GPL core (~31 MB) is fetched from jsDelivr only when exporting MP4 (and the browser can't record MP4 itself) or MP3.
   - It is unloaded afterwards, and object URLs are revoked after export and on project change.
6. **Rendering is real time** (canvas + MediaRecorder), so a 10-minute video takes about 10 minutes. Audio-only exports are mixed offline, which is fast.
7. **Storage:** media lives in IndexedDB and the project in localStorage. Downloaded project files embed media as data URLs, so they are portable.
8. **Templates:** "line" templates (Inspiration, Trailer) show the short spoken line as big on-screen text without a duplicate subtitle. "Title" templates (Explainer, Product, Documentary) show the scene title, with the narration as subtitles.
9. **Per-scene "Length (s)" field.** Added so you can set an exact scene length. A typed length overrides the template minimum but never cuts a voice short.
10. **The 10-minute limit applies to the studio only.** The existing PPT video tool keeps its 15-minute limit.

## Known limitations
- **Real-time rendering:** keep the tab visible while exporting. Hidden tabs are throttled by the browser, and the video becomes choppy.
- **MP4 conversion with ffmpeg.wasm is slow** (single-threaded); expect roughly 0.3–1× real time for 720p. Chrome and Edge 126+ and Safari record MP4 directly, which is instant.
- **ElevenLabs was not tested against the real API** (only mocked, by design). Its request format follows ElevenLabs' public REST docs.
- **Video backgrounds play muted.** The soundtrack is voice + music.
- **Firefox cannot record MP4,** so it always uses the ffmpeg.wasm path.
- **The GitHub Pages copy can't use the local voice server from a phone** (`localhost` means the phone itself). Use ElevenLabs, or open the studio from the laptop's app over Wi-Fi.
