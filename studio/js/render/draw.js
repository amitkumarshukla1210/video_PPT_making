// Draws one video frame at time t. Used by the live preview and by the exporter, so they match.
import { getTemplate } from "../templates.js";
import { itemAt, captionAt } from "../timeline.js";

export const SIZES = {
  "16:9": { 720: [1280, 720], 1080: [1920, 1080] },
  "9:16": { 720: [720, 1280], 1080: [1080, 1920] },
  "1:1": { 720: [720, 720], 1080: [1080, 1080] },
};

export function frameSize(format) {
  const a = SIZES[format?.aspect] || SIZES["16:9"];
  return a[format?.height] || a[720];
}

const NAVY = "#152238";
const ORANGE = "#e07b1f";

function scaledFont(font, k) {
  return font.replace(/(\d+(?:\.\d+)?)px/, (_, n) => `${Math.round(Number(n) * k)}px`);
}

/** Wrap text to lines that fit maxWidth. */
export function wrapLines(ctx, text, maxWidth) {
  const words = String(text || "").split(/\s+/).filter(Boolean);
  const lines = [];
  let cur = "";
  for (const w of words) {
    const trial = cur ? `${cur} ${w}` : w;
    if (ctx.measureText(trial).width <= maxWidth || !cur) cur = trial;
    else {
      lines.push(cur);
      cur = w;
    }
  }
  if (cur) lines.push(cur);
  return lines;
}

function cover(ctx, src, sw, sh, W, H, zoom, panX, panY) {
  if (!sw || !sh) return;
  const s = Math.max(W / sw, H / sh) * zoom;
  const dw = sw * s;
  const dh = sh * s;
  const x = (W - dw) / 2 + panX * W;
  const y = (H - dh) / 2 + panY * H;
  ctx.drawImage(src, x, y, dw, dh);
}

function drawBackground(ctx, W, H, scene, p, index, tpl, assets) {
  const bg = scene.background || {};
  ctx.fillStyle = bg.color || tpl.background.color || NAVY;
  ctx.fillRect(0, 0, W, H);
  const src = bg.mediaId ? assets.media.get(bg.mediaId) : null;
  if (!src) return false;
  const kb = tpl.kenBurns;
  const dir = index % 2 ? -1 : 1; // alternate pan direction scene by scene
  const zoom = 1 + kb.zoom * (index % 2 ? 1 - p : p);
  const panX = dir * kb.pan * (p - 0.5);
  const panY = -kb.pan * 0.5 * (p - 0.5);
  if (src instanceof HTMLVideoElement) cover(ctx, src, src.videoWidth, src.videoHeight, W, H, 1 + kb.zoom * 0.3 * p, 0, 0);
  else cover(ctx, src, src.naturalWidth || src.width, src.naturalHeight || src.height, W, H, zoom, panX, panY);
  return true;
}

function shade(ctx, W, H, where) {
  const g = ctx.createLinearGradient(0, where === "top" ? 0 : H, 0, where === "top" ? H * 0.6 : H * 0.35);
  g.addColorStop(0, "rgba(14,26,44,0.75)");
  g.addColorStop(1, "rgba(14,26,44,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, H);
}

function drawHeadline(ctx, W, H, text, tpl, k) {
  if (!text) return;
  const st = tpl.text;
  ctx.font = scaledFont(st.font, k);
  const size = parseFloat(ctx.font.match(/(\d+(?:\.\d+)?)px/)?.[1] || 48);
  const margin = W * 0.07;
  const lines = wrapLines(ctx, st.caps ? text.toUpperCase() : text, W - margin * 2).slice(0, 4);
  const lh = size * 1.18;
  const block = lh * lines.length;
  let y = st.position === "top" ? H * 0.12 : st.position === "bottom" ? H * 0.72 - block : (H - block) / 2;
  ctx.textAlign = st.align;
  ctx.textBaseline = "top";
  const x = st.align === "center" ? W / 2 : margin;
  if (st.align === "left") {
    ctx.fillStyle = ORANGE;
    ctx.fillRect(margin - size * 0.35, y + size * 0.1, size * 0.12, block - size * 0.2);
  }
  ctx.fillStyle = st.color;
  if (st.shadow) {
    ctx.shadowColor = "rgba(0,0,0,0.55)";
    ctx.shadowBlur = size * 0.25;
    ctx.shadowOffsetY = size * 0.05;
  }
  for (const line of lines) {
    ctx.fillText(line, x + (st.align === "left" ? size * 0.15 : 0), y);
    y += lh;
  }
  ctx.shadowColor = "transparent";
  ctx.shadowBlur = 0;
  ctx.shadowOffsetY = 0;
}

function drawCard(ctx, W, H, item, p, assets, k) {
  const g = ctx.createLinearGradient(0, 0, W, H);
  g.addColorStop(0, NAVY);
  g.addColorStop(1, "#1f5fa8");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, H);
  const appear = Math.min(1, p * 3);
  ctx.globalAlpha *= 1;
  const logo = assets.logo;
  const unit = Math.min(W, H);
  if (logo && logo.naturalWidth) {
    const s = unit * 0.16 * (0.92 + 0.08 * appear);
    ctx.save();
    ctx.globalAlpha *= appear;
    ctx.drawImage(logo, (W - s) / 2, H * 0.5 - s * 1.25, s, s);
    ctx.restore();
  }
  ctx.save();
  ctx.globalAlpha *= appear;
  ctx.fillStyle = "#ffffff";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.font = `700 ${Math.round(60 * k)}px 'Segoe UI', Arial, sans-serif`;
  const lines = wrapLines(ctx, item.text, W * 0.84).slice(0, 3);
  let y = H * 0.5;
  for (const line of lines) {
    ctx.fillText(line, W / 2, y);
    y += 72 * k;
  }
  ctx.fillStyle = ORANGE;
  const bar = W * 0.12 * appear;
  ctx.fillRect((W - bar) / 2, y + 18 * k, bar, 6 * k);
  ctx.restore();
}

function drawCaption(ctx, W, H, text, tpl) {
  const size = Math.round(Math.min(W, H) * tpl.subtitles.size * (W < H ? 1.25 : 1));
  ctx.font = `600 ${size}px 'Segoe UI', Arial, sans-serif`;
  const lines = wrapLines(ctx, text, W * 0.82).slice(0, 3);
  const lh = size * 1.25;
  const padX = size * 0.6;
  const padY = size * 0.35;
  let y = H * (W < H ? 0.8 : 0.9) - lines.length * lh;
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  for (const line of lines) {
    const w = ctx.measureText(line).width + padX * 2;
    ctx.fillStyle = "rgba(14,26,44,0.78)";
    roundRect(ctx, (W - w) / 2, y - padY / 2, w, lh + padY / 2, size * 0.25);
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.fillText(line, W / 2, y + padY * 0.2);
    y += lh + padY / 2;
  }
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

const LINE_MAX_WORDS = 16;

/** Text drawn big on screen for a scene: its spoken line (short lines, "line" templates) or its title. */
export function onScreenText(tpl, scene) {
  const words = (scene.text || "").trim().split(/\s+/).filter(Boolean).length;
  if (tpl.onScreen === "line" && words && words <= LINE_MAX_WORDS) return { text: scene.text.trim(), isLine: true };
  return { text: scene.title || "", isLine: false };
}

function drawItem(ctx, W, H, project, timeline, index, t, assets) {
  const tpl = getTemplate(project.template);
  const item = timeline.items[index];
  const p = Math.min(1, Math.max(0, (t - item.start) / Math.max(item.end - item.start, 0.001)));
  const k = Math.min(W, H) / 1080; // template sizes are designed for 1080 px on the short side
  if (item.type !== "scene") {
    drawCard(ctx, W, H, item, p, assets, k);
    return;
  }
  const scene = project.scenes.find((s) => s.id === item.sceneId) || { background: {} };
  const sceneIndex = project.scenes.indexOf(scene);
  const hasMedia = drawBackground(ctx, W, H, scene, p, sceneIndex, tpl, assets);
  if (hasMedia) shade(ctx, W, H, tpl.text.position === "top" ? "top" : "bottom");
  drawHeadline(ctx, W, H, onScreenText(tpl, scene).text, tpl, k);
}

/** Draw the frame at time t, including transitions and burned-in subtitles. */
export function drawFrame(ctx, project, timeline, t, assets) {
  const { width: W, height: H } = ctx.canvas;
  ctx.save();
  ctx.globalAlpha = 1;
  ctx.fillStyle = NAVY;
  ctx.fillRect(0, 0, W, H);
  if (!timeline.items.length) {
    ctx.restore();
    return;
  }
  const i = itemAt(timeline, t);
  const item = timeline.items[i];
  const next = timeline.items[i + 1];
  const prev = timeline.items[i - 1];
  // Transition window: half before and half after each boundary.
  let pair = null;
  if (next) {
    const T = (next.transition || getTemplate(project.template).transition).seconds;
    if (t > item.end - T / 2) pair = { a: i, b: i + 1, k: (t - (item.end - T / 2)) / T, type: (next.transition || getTemplate(project.template).transition).type };
  }
  if (!pair && prev) {
    const T = (item.transition || getTemplate(project.template).transition).seconds;
    if (t < item.start + T / 2) pair = { a: i - 1, b: i, k: (t - (item.start - T / 2)) / T, type: (item.transition || getTemplate(project.template).transition).type };
  }
  if (!pair) {
    drawItem(ctx, W, H, project, timeline, i, t, assets);
  } else {
    const k = Math.min(1, Math.max(0, pair.k));
    const e = k * k * (3 - 2 * k); // smoothstep
    if (pair.type === "slide") {
      ctx.save();
      ctx.translate(-e * W, 0);
      drawItem(ctx, W, H, project, timeline, pair.a, t, assets);
      ctx.restore();
      ctx.save();
      ctx.translate((1 - e) * W, 0);
      drawItem(ctx, W, H, project, timeline, pair.b, t, assets);
      ctx.restore();
    } else if (pair.type === "zoom") {
      ctx.save();
      ctx.translate(W / 2, H / 2);
      ctx.scale(1 + e * 0.35, 1 + e * 0.35);
      ctx.translate(-W / 2, -H / 2);
      drawItem(ctx, W, H, project, timeline, pair.a, t, assets);
      ctx.restore();
      ctx.save();
      ctx.globalAlpha = e;
      ctx.translate(W / 2, H / 2);
      ctx.scale(0.85 + 0.15 * e, 0.85 + 0.15 * e);
      ctx.translate(-W / 2, -H / 2);
      drawItem(ctx, W, H, project, timeline, pair.b, t, assets);
      ctx.restore();
    } else {
      drawItem(ctx, W, H, project, timeline, pair.a, t, assets);
      ctx.save();
      ctx.globalAlpha = e;
      drawItem(ctx, W, H, project, timeline, pair.b, t, assets);
      ctx.restore();
    }
  }
  if (project.subtitles?.burn) {
    const cue = captionAt(timeline, t);
    const tpl = getTemplate(project.template);
    const scene = item.type === "scene" ? project.scenes.find((s) => s.id === item.sceneId) : null;
    // a scene whose spoken line is already the big on-screen text gets no second copy at the bottom
    if (cue && !(scene && onScreenText(tpl, scene).isLine)) drawCaption(ctx, W, H, cue.text, tpl);
  }
  ctx.restore();
}

/** Keep background video clips playing in step with the timeline (muted; voice/music carry the sound). */
export function syncVideos(project, timeline, t, assets, playing = true) {
  const active = new Set();
  const i = itemAt(timeline, t);
  for (const j of [i - 1, i, i + 1]) {
    const it = timeline.items[j];
    if (!it || it.type !== "scene") continue;
    const scene = project.scenes.find((s) => s.id === it.sceneId);
    const v = scene?.background?.mediaId ? assets.media.get(scene.background.mediaId) : null;
    if (!(v instanceof HTMLVideoElement)) continue;
    active.add(v);
    const local = Math.max(0, t - it.start);
    const want = v.duration ? local % v.duration : local;
    if (Math.abs(v.currentTime - want) > 0.5) v.currentTime = want;
    if (playing && v.paused) v.play().catch(() => {});
    if (!playing && !v.paused) v.pause();
  }
  for (const v of assets.media.values()) if (v instanceof HTMLVideoElement && !active.has(v) && !v.paused) v.pause();
}
