import { test } from "node:test";
import assert from "node:assert/strict";
import { buildTimeline, toSrt, srtTime, captionChunks, musicGainAt, duckingPoints, MAX_SECONDS, formatClock } from "../../studio/js/timeline.js";
import { newProject } from "../../studio/js/store.js";
import { splitScript } from "../../studio/js/scenes.js";
import { getTemplate } from "../../studio/js/templates.js";

function project(script, tpl = "explainer") {
  const p = newProject(tpl);
  p.scenes = splitScript(script, tpl);
  return p;
}

test("timeline adds title card, scenes and end card back to back", () => {
  const p = project("One.\n\nTwo.");
  const tl = buildTimeline(p);
  assert.deepEqual(tl.items.map((i) => i.type), ["title", "scene", "scene", "end"]);
  for (let i = 1; i < tl.items.length; i++) assert.equal(tl.items[i].start, tl.items[i - 1].end);
  assert.equal(tl.total, tl.items.at(-1).end);
});

test("cards can be switched off", () => {
  const p = project("One.");
  p.cards = { title: false, end: false };
  assert.deepEqual(buildTimeline(p).items.map((i) => i.type), ["scene"]);
});

test("real voice length drives the scene length", () => {
  const p = project("Hello there.");
  p.cards = { title: false, end: false };
  p.scenes[0].audio = { mediaId: "x", seconds: 12, key: "k" };
  const it = buildTimeline(p).items[0];
  const tpl = getTemplate("explainer");
  assert.equal(it.voiceStart, 0.35);
  assert.equal(it.voiceEnd, 12.35);
  assert.ok(Math.abs(it.end - (0.35 + 12 + tpl.voice.pauseAfterScene)) < 1e-9);
  assert.equal(it.estimated, false);
});

test("10-minute limit and remaining time", () => {
  const p = project("Short.");
  let tl = buildTimeline(p);
  assert.equal(tl.overLimit, false);
  assert.ok(Math.abs(tl.remaining - (MAX_SECONDS - tl.total)) < 1e-6);
  p.scenes[0].audio = { mediaId: "x", seconds: 601, key: "k" };
  tl = buildTimeline(p);
  assert.equal(tl.overLimit, true);
  assert.ok(tl.remaining < 0);
});

test("SRT timestamps and blocks", () => {
  assert.equal(srtTime(0), "00:00:00,000");
  assert.equal(srtTime(3661.5), "01:01:01,500");
  assert.equal(srtTime(-2), "00:00:00,000");
  const srt = toSrt([{ start: 1, end: 2.5, text: "Hello." }, { start: 3, end: 4, text: "Bye." }]);
  assert.equal(srt, "1\n00:00:01,000 --> 00:00:02,500\nHello.\n\n2\n00:00:03,000 --> 00:00:04,000\nBye.\n");
});

test("captions follow the voice clip and never overlap", () => {
  const p = project("This is the first sentence. And here is a second, slightly longer sentence for the test.");
  p.cards = { title: true, end: false };
  p.scenes[0].audio = { mediaId: "x", seconds: 6, key: "k" };
  const tl = buildTimeline(p);
  const it = tl.items[1];
  assert.ok(tl.captions.length >= 2);
  assert.ok(Math.abs(tl.captions[0].start - it.voiceStart) < 1e-6);
  assert.ok(tl.captions.at(-1).end <= it.voiceEnd);
  for (let i = 1; i < tl.captions.length; i++) assert.ok(tl.captions[i].start >= tl.captions[i - 1].end);
  assert.equal(tl.captions.map((c) => c.text).join(" "), p.scenes[0].text);
});

test("caption chunks stay short", () => {
  const chunks = captionChunks("one two three four five six seven eight nine ten eleven twelve thirteen.");
  assert.ok(chunks.every((c) => c.split(" ").length <= 9));
  assert.deepEqual(captionChunks("   "), []);
});

test("music ducks under the voice and recovers", () => {
  const p = project("Hi.");
  p.cards = { title: true, end: true };
  p.scenes[0].audio = { mediaId: "x", seconds: 4, key: "k" };
  const tl = buildTimeline(p);
  const v = tl.items[1];
  assert.equal(musicGainAt(tl, 0.5, 0.5), 0.5);
  assert.ok(Math.abs(musicGainAt(tl, v.voiceStart + 1, 0.5) - 0.15) < 1e-9);
  assert.equal(musicGainAt(tl, tl.total - 0.1, 0.5), 0.5);
  const pts = duckingPoints(tl, 0.5);
  assert.ok(pts.some(([t, g]) => t === v.voiceStart && g === 0.15));
});

test("clock format", () => {
  assert.equal(formatClock(0), "0:00");
  assert.equal(formatClock(600), "10:00");
  assert.equal(formatClock(61.4), "1:01");
});

test("a length set by the user wins over the template minimum but never cuts the voice", () => {
  const p = project("Hi.", "documentary");
  p.cards = { title: false, end: false };
  p.scenes[0].fixedSeconds = 5;
  assert.equal(buildTimeline(p).total, 5);
  p.scenes[0].audio = { mediaId: "x", seconds: 2, key: "k" };
  assert.equal(buildTimeline(p).total, 5);
  p.scenes[0].audio.seconds = 6;
  assert.ok(Math.abs(buildTimeline(p).total - (0.35 + 6 + 0.4)) < 1e-9);
});
