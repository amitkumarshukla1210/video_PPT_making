// ffmpeg.wasm, loaded lazily (only for MP4 fallback / MP3) and torn down after use to free memory.
const CORE_VERSION = "0.12.10";
export const DEFAULT_CORE_BASE = `https://cdn.jsdelivr.net/npm/@ffmpeg/core@${CORE_VERSION}/dist/esm`;

let instance = null;
let blobUrls = [];

async function load(settings, onLog) {
  if (instance) return instance;
  const [{ FFmpeg }, { toBlobURL }] = await Promise.all([
    import("../../vendor/ffmpeg/ffmpeg/index.js"),
    import("../../vendor/ffmpeg/util/index.js"),
  ]);
  const base = (settings?.ffmpegBase || DEFAULT_CORE_BASE).replace(/\/+$/, "");
  let coreURL;
  let wasmURL;
  try {
    coreURL = await toBlobURL(`${base}/ffmpeg-core.js`, "text/javascript");
    wasmURL = await toBlobURL(`${base}/ffmpeg-core.wasm`, "application/wasm");
  } catch (e) {
    throw new Error(`Could not download the MP4 converter (ffmpeg.wasm, about 31 MB) from ${new URL(base).host}. Check your internet, or export WebM instead. (${e.message || e})`);
  }
  blobUrls = [coreURL, wasmURL];
  const ff = new FFmpeg();
  if (onLog) ff.on("log", ({ message }) => onLog(message));
  await ff.load({ coreURL, wasmURL });
  instance = ff;
  return ff;
}

/** Free the worker, its ~100 MB+ of wasm memory and the blob URLs. */
export function unload() {
  if (instance) {
    try {
      instance.terminate();
    } catch {
      /* already gone */
    }
  }
  instance = null;
  for (const u of blobUrls) URL.revokeObjectURL(u);
  blobUrls = [];
}

async function run(settings, input, inName, args, outName, mime, { onProgress, signal } = {}) {
  const ff = await load(settings);
  const progress = ({ progress }) => onProgress?.(Math.min(1, Math.max(0, progress)));
  ff.on("progress", progress);
  const abort = () => unload();
  signal?.addEventListener("abort", abort, { once: true });
  try {
    await ff.writeFile(inName, new Uint8Array(await input.arrayBuffer()));
    const code = await ff.exec(["-i", inName, ...args, outName]);
    if (signal?.aborted) throw new DOMException("Cancelled", "AbortError");
    if (code !== 0) throw new Error(`ffmpeg.wasm failed (exit code ${code}).`);
    const data = await ff.readFile(outName);
    await ff.deleteFile(inName);
    await ff.deleteFile(outName);
    return new Blob([data.buffer], { type: mime });
  } finally {
    signal?.removeEventListener("abort", abort);
    if (instance) instance.off("progress", progress);
  }
}

export function webmToMp4(settings, blob, opts) {
  return run(settings, blob, "in.webm",
    ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"],
    "out.mp4", "video/mp4", opts);
}

export function wavToMp3(settings, blob, opts) {
  return run(settings, blob, "in.wav", ["-c:a", "libmp3lame", "-b:a", "160k"], "out.mp3", "audio/mpeg", opts);
}

export function isLoaded() {
  return !!instance;
}
