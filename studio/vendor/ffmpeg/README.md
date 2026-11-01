# Vendored: ffmpeg.wasm wrapper (MIT)

| Folder | Package | Version | Licence |
|---|---|---|---|
| `ffmpeg/` | [`@ffmpeg/ffmpeg`](https://github.com/ffmpegwasm/ffmpeg.wasm) `dist/esm` | 0.12.15 | MIT |
| `util/` | [`@ffmpeg/util`](https://github.com/ffmpegwasm/ffmpeg.wasm) `dist/esm` | 0.12.2 | MIT |

Copied unchanged. They are vendored (not loaded from a CDN) because the wrapper starts a module
Web Worker, and browsers only allow same-origin worker scripts.

The FFmpeg core itself (`@ffmpeg/core` 0.12.10, **single-threaded**, GPL-2.0-or-later, ~31 MB) is
**not** stored here. `studio/js/render/ffmpeg.js` downloads it from jsDelivr only when the user
exports MP4 (when the browser can't record MP4 natively) or MP3. The single-threaded core needs no
`SharedArrayBuffer`, so the page works on GitHub Pages without COOP/COEP headers.
