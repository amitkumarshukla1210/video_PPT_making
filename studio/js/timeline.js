// Timeline: where every card, scene, voice clip and caption sits in time. Pure functions.
import { getTemplate } from "./templates.js";
import { estimateSceneSeconds } from "./scenes.js";

export const MAX_SECONDS = 10 * 60; // hard limit for any export
export const VOICE_LEAD = 0.35; // silence before the voice starts in a scene
export const MIN_VOICE_TAIL = 0.4; // minimum silence after a voice clip

/** Build the timeline. Scenes with generated audio use its real length; others are estimated. */
export function buildTimeline(project) {
  const tpl = getTemplate(project.template);
  const speed = Number(project.voice?.speed) || 1;
  const items = [];
  let t = 0;
  const title = project.cards?.title ?? true;
  const end = project.cards?.end ?? true;
  const projectTitle = (project.title || "").trim() || "Untitled";

  if (title) {
    const d = tpl.titleCard.seconds;
    items.push({ type: "title", start: t, end: t + d, text: tpl.titleCard.text.replace("{title}", projectTitle) });
    t += d;
  }
  for (const scene of project.scenes) {
    let d;
    let voiceStart = null;
    let voiceEnd = null;
    if (scene.audio && scene.audio.seconds > 0) {
      const pause = Math.max(tpl.voice.pauseAfterScene, MIN_VOICE_TAIL);
      d = Math.max(scene.fixedSeconds || 0, VOICE_LEAD + scene.audio.seconds + pause, tpl.sceneSeconds.min);
      voiceStart = t + VOICE_LEAD;
      voiceEnd = voiceStart + scene.audio.seconds;
    } else {
      d = estimateSceneSeconds(scene, tpl, speed);
    }
    items.push({
      type: "scene",
      sceneId: scene.id,
      start: t,
      end: t + d,
      text: scene.text,
      title: scene.title,
      transition: scene.transition || tpl.transition,
      voiceStart,
      voiceEnd,
      estimated: voiceStart === null,
    });
    t += d;
  }
  if (end) {
    const d = tpl.endCard.seconds;
    items.push({ type: "end", start: t, end: t + d, text: tpl.endCard.text.replace("{title}", projectTitle) });
    t += d;
  }
  const total = round3(t);
  return {
    items,
    total,
    max: MAX_SECONDS,
    remaining: round3(MAX_SECONDS - total),
    overLimit: total > MAX_SECONDS,
    captions: buildCaptions(items),
  };
}

function round3(x) {
  return Math.round(x * 1000) / 1000;
}

/** Break text into readable caption chunks (≤ maxWords, split at sentences first). */
export function captionChunks(text, maxWords = 9) {
  const clean = (text || "").replace(/\s+/g, " ").trim();
  if (!clean) return [];
  const sentences = clean.match(/[^.!?।]+[.!?।]+["')\]]*|[^.!?।]+$/gu) || [clean];
  const out = [];
  for (const s of sentences.map((x) => x.trim()).filter(Boolean)) {
    const words = s.split(" ");
    const parts = Math.ceil(words.length / maxWords);
    const size = Math.ceil(words.length / parts);
    for (let i = 0; i < words.length; i += size) out.push(words.slice(i, i + size).join(" "));
  }
  return out;
}

/** Captions for scenes: during the voice clip if there is one, else across the scene minus margins. */
export function buildCaptions(items) {
  const cues = [];
  for (const it of items) {
    if (it.type !== "scene") continue;
    const chunks = captionChunks(it.text);
    if (!chunks.length) continue;
    const a = it.voiceStart ?? it.start + VOICE_LEAD;
    const b = it.voiceEnd ?? Math.max(a + 0.5, it.end - 0.4);
    const span = Math.max(b - a, 0.5);
    const totalChars = chunks.reduce((n, c) => n + c.length, 0);
    let t = a;
    for (const c of chunks) {
      const d = (span * c.length) / totalChars;
      cues.push({ start: round3(t), end: round3(t + d - 0.04), text: c });
      t += d;
    }
  }
  return cues;
}

export function srtTime(sec) {
  const ms = Math.max(0, Math.round(sec * 1000));
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  const r = ms % 1000;
  const p = (n, w = 2) => String(n).padStart(w, "0");
  return `${p(h)}:${p(m)}:${p(s)},${p(r, 3)}`;
}

export function toSrt(cues) {
  return cues.map((c, i) => `${i + 1}\n${srtTime(c.start)} --> ${srtTime(c.end)}\n${c.text}\n`).join("\n");
}

export function formatClock(sec) {
  const s = Math.max(0, Math.round(sec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Which item is on screen at time t (binary search would be overkill for ≤ a few hundred items). */
export function itemAt(timeline, t) {
  const { items } = timeline;
  for (let i = 0; i < items.length; i++) if (t < items[i].end) return i;
  return items.length - 1;
}

export function captionAt(timeline, t) {
  return timeline.captions.find((c) => t >= c.start && t < c.end) || null;
}

/** Music volume at time t: ducks to `duck` × base while a voice clip plays (with short ramps). */
export function musicGainAt(timeline, t, base, duck = 0.3, ramp = 0.25) {
  let g = 1;
  for (const it of timeline.items) {
    if (it.voiceStart == null) continue;
    if (t >= it.voiceStart - ramp && t <= it.voiceEnd + ramp) {
      let k = 1;
      if (t < it.voiceStart) k = (it.voiceStart - t) / ramp;
      else if (t > it.voiceEnd) k = (t - it.voiceEnd) / ramp;
      g = Math.min(g, duck + (1 - duck) * Math.min(1, Math.max(0, k)));
    }
  }
  return base * g;
}

/** Points for AudioParam automation implementing the same ducking curve. */
export function duckingPoints(timeline, base, duck = 0.3, ramp = 0.25) {
  const pts = [[0, base]];
  for (const it of timeline.items) {
    if (it.voiceStart == null) continue;
    const a = Math.max(0, it.voiceStart - ramp);
    pts.push([a, base], [it.voiceStart, base * duck], [it.voiceEnd, base * duck], [it.voiceEnd + ramp, base]);
  }
  return pts.sort((x, y) => x[0] - y[0]);
}
