// Export pipeline: generate missing voice clips, load media, record the canvas in real time,
// convert if needed, and clean up afterwards.
import { ENGINES, audioKey, sceneVoice, VoiceError } from "../voices/index.js";
import { getMedia, putMedia, deleteMedia } from "../media.js";
import { buildTimeline, MAX_SECONDS } from "../timeline.js";
import { drawFrame, frameSize, syncVideos } from "./draw.js";
import { decodeBlob, scheduleAudio, mixOffline, audioBufferToWav } from "./audio.js";
import * as ffmpeg from "./ffmpeg.js";

export const FPS = 30;

/** Which scenes still need a (new) voice clip. */
export function scenesNeedingVoice(project) {
  return project.scenes.filter((s) => s.text.trim() && (!s.audio || s.audio.key !== audioKey(s.text, sceneVoice(project, s))));
}

/**
 * Make sure every scene with text has an up-to-date voice clip.
 * store: Store (clips are saved without creating undo steps). Throws VoiceError on engine failure.
 */
export async function prepareVoices(store, settings, { onProgress, signal, only = null } = {}) {
  const todo = scenesNeedingVoice(store.project).filter((s) => !only || only.includes(s.id));
  let done = 0;
  for (const scene of todo) {
    if (signal?.aborted) throw new DOMException("Cancelled", "AbortError");
    const voice = sceneVoice(store.project, scene);
    const engine = ENGINES[voice.engine];
    if (!engine?.canExport) {
      throw new VoiceError("unsupported", `“${engine?.label || voice.engine}” can only preview. Start the local Design to Cost app and choose its voice server to include narration in an export.`, { fallback: false });
    }
    onProgress?.(done / todo.length, `Voice ${done + 1}/${todo.length}: ${scene.title || "scene"}`);
    const blob = await engine.synthesize(scene.text, voice, settings, { signal });
    const seconds = (await decodeBlob(blob)).duration;
    const old = scene.audio?.mediaId;
    const mediaId = await putMedia(blob, "voice");
    const key = audioKey(scene.text, voice);
    store.update((p) => {
      const s = p.scenes.find((x) => x.id === scene.id);
      if (s && s.text === scene.text) s.audio = { mediaId, seconds, key };
    }, { undoable: false, reason: "voice" });
    if (old && old !== mediaId) deleteMedia(old).catch(() => {});
    done += 1;
  }
  onProgress?.(1, "Voices ready");
}

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("An image could not be loaded."));
    img.src = url;
  });
}

function loadVideo(url) {
  return new Promise((resolve, reject) => {
    const v = document.createElement("video");
    v.muted = true;
    v.playsInline = true;
    v.preload = "auto";
    v.loop = true;
    v.onloadeddata = () => resolve(v);
    v.onerror = () => reject(new Error("A video clip could not be loaded."));
    v.src = url;
  });
}

/** Images/videos/logo used by the draw functions. */
export async function loadAssets(project, logoUrl) {
  const media = new Map();
  const mediaUrls = new Set();
  try {
    for (const s of project.scenes) {
      const id = s.background?.mediaId;
      if (!id || media.has(id) || s.background.kind === "color") continue;
      const blob = await getMedia(id);
      if (!blob) continue;
      const url = URL.createObjectURL(blob);
      mediaUrls.add(url);
      media.set(id, blob.type.startsWith("video/") ? await loadVideo(url) : await loadImage(url));
    }
    let logo = null;
    try {
      logo = await loadImage(logoUrl);
    } catch {
      logo = null;
    }
    return { media, mediaUrls, logo };
  } catch (error) {
    for (const url of mediaUrls) URL.revokeObjectURL(url);
    throw error;
  }
}

export function disposeAssets(assets) {
  for (const el of assets?.media?.values() || []) {
    if (el instanceof HTMLVideoElement) {
      el.pause();
      el.removeAttribute("src");
      el.load();
    }
  }
  assets?.media?.clear();
  for (const url of assets?.mediaUrls || []) URL.revokeObjectURL(url);
  assets?.mediaUrls?.clear();
}

export async function loadAudio(project) {
  const voices = new Map();
  for (const s of project.scenes) {
    if (!s.audio?.mediaId) continue;
    const blob = await getMedia(s.audio.mediaId);
    if (blob) voices.set(s.id, await decodeBlob(blob));
  }
  let music = null;
  if (project.music?.mediaId) {
    const blob = await getMedia(project.music.mediaId);
    if (blob) music = await decodeBlob(blob);
  }
  return { voices, music };
}

/** Best MediaRecorder type for the wanted container; null if the browser can't record it. */
export function pickMime(container) {
  const MR = globalThis.MediaRecorder;
  if (!MR) return null;
  const list = container === "mp4"
    ? ["video/mp4;codecs=avc1.42E01F,mp4a.40.2", "video/mp4;codecs=avc1,mp4a.40.2", "video/mp4"]
    : ["video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm"];
  return list.find((m) => MR.isTypeSupported(m)) || null;
}

export function checkLimit(project) {
  const tl = buildTimeline(project);
  if (tl.overLimit) {
    throw new Error(`The video is ${Math.ceil(tl.total)} s long; the limit is ${MAX_SECONDS / 60} minutes. Remove or shorten scenes (${Math.ceil(-tl.remaining)} s too long).`);
  }
  return tl;
}

/**
 * Record the project in real time. Returns { blob, mime, seconds }.
 * container: "webm" | "mp4". onProgress(fraction, message).
 */
export async function recordVideo(project, settings, { container = "webm", onProgress, signal, logoUrl, canvas: preview } = {}) {
  const timeline = checkLimit(project);
  const [W, H] = frameSize(project.format);
  const nativeMp4 = container === "mp4" ? pickMime("mp4") : null;
  const mime = nativeMp4 || pickMime("webm");
  if (!mime) throw new Error("This browser cannot record video (MediaRecorder missing). Use Chrome, Edge or Firefox.");

  onProgress?.(0, "Loading media…");
  const assets = await loadAssets(project, logoUrl);
  const { voices, music } = await loadAudio(project);
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  const pctx = preview?.getContext("2d");
  const audio = new AudioContext({ sampleRate: 48000 });
  await audio.resume();
  const dest = audio.createMediaStreamDestination();
  const stream = new MediaStream([...canvas.captureStream(FPS).getVideoTracks(), ...dest.stream.getAudioTracks()]);
  const chunks = [];
  const rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: H >= 1080 ? 8_000_000 : 4_000_000, audioBitsPerSecond: 160_000 });
  rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  const stopped = new Promise((resolve) => (rec.onstop = resolve));

  drawFrame(ctx, project, timeline, 0, assets);
  const t0 = audio.currentTime + 0.25;
  // MediaRecorder timestamps video against wall time, so use the same clock for the frame timeline.
  const wallStart = performance.now() + 250;
  const sched = scheduleAudio(audio, dest, timeline, voices, music, project, t0);
  rec.start(1000);
  let cancelled = false;
  try {
    await new Promise((resolve, reject) => {
      let timer = null;
      const tick = () => {
        if (signal?.aborted) {
          cancelled = true;
          clearInterval(timer);
          reject(new DOMException("Cancelled", "AbortError"));
          return;
        }
        const t = Math.max(0, (performance.now() - wallStart) / 1000);
        syncVideos(project, timeline, t, assets, true);
        drawFrame(ctx, project, timeline, Math.min(t, timeline.total - 0.001), assets);
        if (pctx) pctx.drawImage(canvas, 0, 0, pctx.canvas.width, pctx.canvas.height);
        onProgress?.(Math.min(1, t / timeline.total), `Recording ${Math.floor(t)} / ${Math.ceil(timeline.total)} s`);
        if (t >= timeline.total) {
          clearInterval(timer);
          resolve();
        }
      };
      // A timer (not requestAnimationFrame) so a hidden tab keeps recording, if more coarsely.
      timer = setInterval(tick, 1000 / FPS);
    });
  } finally {
    sched.stop();
    if (rec.state !== "inactive") rec.stop();
    await stopped;
    stream.getTracks().forEach((tr) => tr.stop());
    await audio.close();
    disposeAssets(assets);
  }
  if (cancelled) throw new DOMException("Cancelled", "AbortError");
  let blob = new Blob(chunks, { type: mime.split(";")[0] });
  chunks.length = 0;
  if (container === "mp4" && !nativeMp4) {
    onProgress?.(0, "Converting to MP4 (ffmpeg.wasm)…");
    try {
      blob = await ffmpeg.webmToMp4(settings, blob, { signal, onProgress: (f) => onProgress?.(f, `Converting to MP4 ${Math.round(f * 100)}%`) });
    } finally {
      ffmpeg.unload();
    }
  }
  return { blob, mime: blob.type, seconds: timeline.total, nativeMp4: !!nativeMp4 };
}

/** Audio-only export (fast, offline). format: "wav" | "mp3". */
export async function exportAudio(project, settings, { format = "wav", onProgress, signal } = {}) {
  const timeline = checkLimit(project);
  onProgress?.(0.1, "Mixing audio…");
  const { voices, music } = await loadAudio(project);
  const buffer = await mixOffline(timeline, voices, music, project);
  let blob = audioBufferToWav(buffer);
  if (format === "mp3") {
    onProgress?.(0.5, "Encoding MP3 (ffmpeg.wasm)…");
    try {
      blob = await ffmpeg.wavToMp3(settings, blob, { signal, onProgress: (f) => onProgress?.(0.5 + f / 2, `Encoding MP3 ${Math.round(f * 100)}%`) });
    } finally {
      ffmpeg.unload();
    }
  }
  onProgress?.(1, "Done");
  return { blob, seconds: timeline.total, buffer };
}
