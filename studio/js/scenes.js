// Script → scenes. Pure functions, no DOM, so they run in node --test too.
import { getTemplate } from "./templates.js";

export const WORDS_PER_SECOND = 2.5; // calm narration at speed 1.0
const MAX_SCENE_WORDS = 60;

let counter = 0;
export function newId(prefix = "s") {
  counter += 1;
  const rnd = Math.random().toString(36).slice(2, 7);
  return `${prefix}${Date.now().toString(36)}${counter.toString(36)}${rnd}`;
}

export function wordCount(text) {
  const t = (text || "").trim();
  return t ? t.split(/\s+/u).length : 0;
}

/** Seconds needed to speak `text` at template pace × speed. */
export function speechSeconds(text, pace = 1, speed = 1) {
  const words = wordCount(text);
  if (!words) return 0;
  const sentences = (text.match(/[.!?।]+(\s|$)/gu) || []).length;
  return words / (WORDS_PER_SECOND * pace * speed) + sentences * 0.25;
}

/** Scene length before any audio exists: speech estimate + pause, clamped to the template range. */
export function estimateSceneSeconds(scene, template, speed = 1) {
  const tpl = template || getTemplate("explainer");
  const { min, max } = tpl.sceneSeconds;
  if (scene.fixedSeconds) return clamp(scene.fixedSeconds, 0.5, 600);
  const spoken = speechSeconds(scene.text, tpl.voice.pace, speed);
  if (!spoken) return tpl.sceneSeconds.default;
  return clamp(spoken + tpl.voice.pauseAfterScene, min, Math.max(max, spoken + tpl.voice.pauseAfterScene));
}

function clamp(v, lo, hi) {
  return Math.min(hi, Math.max(lo, v));
}

function splitLong(text) {
  // Break very long paragraphs at sentence boundaries into chunks of ≤ MAX_SCENE_WORDS.
  if (wordCount(text) <= MAX_SCENE_WORDS) return [text];
  const sentences = text.match(/[^.!?।]+[.!?।]+["')\]]*\s*|[^.!?।]+$/gu) || [text];
  const out = [];
  let cur = "";
  for (const s of sentences) {
    const next = (cur + " " + s).trim();
    if (cur && wordCount(next) > MAX_SCENE_WORDS) {
      out.push(cur.trim());
      cur = s.trim();
    } else {
      cur = next;
    }
  }
  if (cur.trim()) out.push(cur.trim());
  // A single sentence that is still too long: split by words.
  return out.flatMap((chunk) => {
    const words = chunk.split(/\s+/u);
    if (words.length <= MAX_SCENE_WORDS * 1.5) return [chunk];
    const parts = [];
    for (let i = 0; i < words.length; i += MAX_SCENE_WORDS) parts.push(words.slice(i, i + MAX_SCENE_WORDS).join(" "));
    return parts;
  });
}

/**
 * Split a script into scenes.
 * Rules: blank lines separate scenes; a line starting with "#" (or "Scene:" / "[...]") starts a new
 * scene and becomes its title; "---" is an explicit break; long paragraphs are split by sentences.
 */
export function splitScript(script, templateId = "explainer") {
  const tpl = getTemplate(templateId);
  const lines = (script || "").replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  let cur = { title: "", lines: [] };
  const flush = () => {
    const text = cur.lines.join(" ").replace(/\s+/g, " ").trim();
    if (text || cur.title) blocks.push({ title: cur.title, text });
    cur = { title: "", lines: [] };
  };
  for (const raw of lines) {
    const line = raw.trim();
    const heading = line.match(/^(?:#{1,6}\s+|scene\s*\d*\s*[:.-]\s*|\[(.+)\]\s*$)(.*)$/iu);
    if (!line || /^-{3,}$/.test(line)) {
      flush();
    } else if (heading) {
      flush();
      cur.title = (heading[1] || heading[2] || "").trim();
    } else {
      cur.lines.push(line);
    }
  }
  flush();

  const scenes = [];
  for (const b of blocks) {
    const chunks = b.text ? splitLong(b.text) : [""];
    chunks.forEach((text, i) => {
      scenes.push(makeScene({ title: i === 0 ? b.title : `${b.title || "Scene"} (cont.)`, text }, tpl, scenes.length));
    });
  }
  return scenes;
}

export function makeScene(partial = {}, template, index = 0) {
  const tpl = template || getTemplate("explainer");
  return {
    id: newId("sc"),
    title: partial.title ?? (tpl.structure[index] || `Scene ${index + 1}`),
    text: partial.text ?? "",
    background: partial.background ?? { kind: "color", color: tpl.background.color, mediaId: null },
    transition: partial.transition ?? null, // null = template default
    fixedSeconds: partial.fixedSeconds ?? null,
    voice: partial.voice ?? null, // null = project voice; else a per-scene override
    imagePrompt: partial.imagePrompt ?? "", // picture creator prompt (blank = title + words)
    audio: null, // { mediaId, seconds, key }
  };
}
