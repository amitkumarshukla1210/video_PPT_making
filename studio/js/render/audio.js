// Audio: decoding, the voice + music graph (with ducking), offline mix and a WAV encoder.
import { duckingPoints } from "../timeline.js";

export const SAMPLE_RATE = 44100;
const DUCK = 0.3; // music level while someone speaks, relative to its normal level

let decoder = null;
function decodeContext() {
  // Any context can decode; an OfflineAudioContext needs no user gesture.
  if (!decoder) decoder = new OfflineAudioContext(1, 1, SAMPLE_RATE);
  return decoder;
}

export async function decodeBlob(blob) {
  const buf = await blob.arrayBuffer();
  return decodeContext().decodeAudioData(buf);
}

export async function blobSeconds(blob) {
  return (await decodeBlob(blob)).duration;
}

/**
 * Wire voices and music into `ctx`, starting at ctx time `t0`.
 * voiceBuffers: Map(sceneId -> AudioBuffer). Returns { stop } to cancel.
 */
export function scheduleAudio(ctx, dest, timeline, voiceBuffers, musicBuffer, project, t0) {
  const sources = [];
  for (const it of timeline.items) {
    if (it.voiceStart == null) continue;
    const buf = voiceBuffers.get(it.sceneId);
    if (!buf) continue;
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(dest);
    src.start(t0 + it.voiceStart);
    sources.push(src);
  }
  if (musicBuffer) {
    const base = Number(project.music?.volume ?? 0.2);
    const gain = ctx.createGain();
    const pts = project.music?.duck === false ? [[0, base]] : duckingPoints(timeline, base, DUCK);
    gain.gain.setValueAtTime(pts[0][1], t0);
    for (const [time, value] of pts.slice(1)) gain.gain.linearRampToValueAtTime(value, t0 + time);
    // fade out over the last 2 s
    const end = timeline.total;
    gain.gain.setValueAtTime(lastValue(pts, end - 2), t0 + Math.max(0, end - 2));
    gain.gain.linearRampToValueAtTime(0, t0 + end);
    const src = ctx.createBufferSource();
    src.buffer = musicBuffer;
    src.loop = true;
    src.connect(gain).connect(dest);
    src.start(t0);
    src.stop(t0 + end);
    sources.push(src);
  }
  return {
    stop() {
      for (const s of sources) {
        try {
          s.stop();
        } catch {
          /* already stopped */
        }
        s.disconnect();
      }
    },
  };
}

function lastValue(pts, t) {
  let v = pts[0][1];
  for (const [time, value] of pts) if (time <= t) v = value;
  return v;
}

/** Render the whole soundtrack offline (much faster than real time). */
export async function mixOffline(timeline, voiceBuffers, musicBuffer, project) {
  const length = Math.max(1, Math.ceil(timeline.total * SAMPLE_RATE));
  const ctx = new OfflineAudioContext(2, length, SAMPLE_RATE);
  scheduleAudio(ctx, ctx.destination, timeline, voiceBuffers, musicBuffer, project, 0);
  return ctx.startRendering();
}

/** 16-bit PCM WAV from channel data. Pure function (unit-tested). */
export function encodeWav(channels, sampleRate) {
  const n = channels.length;
  const frames = channels[0]?.length || 0;
  const bytes = 44 + frames * n * 2;
  const out = new DataView(new ArrayBuffer(bytes));
  const str = (o, s) => [...s].forEach((c, i) => out.setUint8(o + i, c.charCodeAt(0)));
  str(0, "RIFF");
  out.setUint32(4, bytes - 8, true);
  str(8, "WAVE");
  str(12, "fmt ");
  out.setUint32(16, 16, true);
  out.setUint16(20, 1, true);
  out.setUint16(22, n, true);
  out.setUint32(24, sampleRate, true);
  out.setUint32(28, sampleRate * n * 2, true);
  out.setUint16(32, n * 2, true);
  out.setUint16(34, 16, true);
  str(36, "data");
  out.setUint32(40, frames * n * 2, true);
  let o = 44;
  for (let i = 0; i < frames; i++) {
    for (let c = 0; c < n; c++) {
      const v = Math.max(-1, Math.min(1, channels[c][i]));
      out.setInt16(o, v < 0 ? v * 0x8000 : v * 0x7fff, true);
      o += 2;
    }
  }
  return new Uint8Array(out.buffer);
}

export function audioBufferToWav(buffer) {
  const ch = [];
  for (let i = 0; i < buffer.numberOfChannels; i++) ch.push(buffer.getChannelData(i));
  return new Blob([encodeWav(ch, buffer.sampleRate)], { type: "audio/wav" });
}

/** RMS level of a window of an AudioBuffer (used by tests to check ducking). */
export function rms(buffer, from, to) {
  const d = buffer.getChannelData(0);
  const a = Math.floor(from * buffer.sampleRate);
  const b = Math.min(d.length, Math.floor(to * buffer.sampleRate));
  let s = 0;
  for (let i = a; i < b; i++) s += d[i] * d[i];
  return Math.sqrt(s / Math.max(1, b - a));
}
