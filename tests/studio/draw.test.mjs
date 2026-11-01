import { test } from "node:test";
import assert from "node:assert/strict";
import { onScreenText, frameSize } from "../../studio/js/render/draw.js";
import { getTemplate } from "../../studio/js/templates.js";

test("short lines are the on-screen text in line templates (no duplicate subtitle)", () => {
  const r = onScreenText(getTemplate("trailer"), { title: "", text: "One team refused to guess." });
  assert.deepEqual(r, { text: "One team refused to guess.", isLine: true });
});

test("long lines fall back to title + subtitles", () => {
  const long = Array.from({ length: 30 }, () => "word").join(" ");
  assert.deepEqual(onScreenText(getTemplate("inspiration"), { title: "Belief", text: long }), { text: "Belief", isLine: false });
});

test("title templates show the scene title", () => {
  assert.deepEqual(onScreenText(getTemplate("explainer"), { title: "How it works", text: "Short." }), { text: "How it works", isLine: false });
});

test("frame sizes for every shape and quality", () => {
  assert.deepEqual(frameSize({ aspect: "16:9", height: 1080 }), [1920, 1080]);
  assert.deepEqual(frameSize({ aspect: "9:16", height: 720 }), [720, 1280]);
  assert.deepEqual(frameSize({ aspect: "1:1", height: 1080 }), [1080, 1080]);
  assert.deepEqual(frameSize({}), [1280, 720]);
});
