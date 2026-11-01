import { test } from "node:test";
import assert from "node:assert/strict";
import { splitScript, wordCount, speechSeconds, estimateSceneSeconds } from "../../studio/js/scenes.js";
import { TEMPLATES, TEMPLATE_IDS, getTemplate } from "../../studio/js/templates.js";

test("blank lines separate scenes", () => {
  const s = splitScript("First scene text.\n\nSecond scene text.\n\n\nThird.", "explainer");
  assert.equal(s.length, 3);
  assert.deepEqual(s.map((x) => x.text), ["First scene text.", "Second scene text.", "Third."]);
});

test("headings become scene titles", () => {
  const s = splitScript("# The problem\nPrices drift.\n# The fix\nLink indices.\n[Outro]\nThanks.\nScene 4: Bonus\nMore.", "explainer");
  assert.deepEqual(s.map((x) => x.title), ["The problem", "The fix", "Outro", "Bonus"]);
  assert.deepEqual(s.map((x) => x.text), ["Prices drift.", "Link indices.", "Thanks.", "More."]);
});

test("lines inside one paragraph are joined; --- forces a break", () => {
  const s = splitScript("Line one\nline two\n---\nNext", "explainer");
  assert.equal(s.length, 2);
  assert.equal(s[0].text, "Line one line two");
});

test("long paragraphs are split at sentence boundaries", () => {
  const sentence = "This sentence has exactly ten words in it for testing. ";
  const s = splitScript(sentence.repeat(14), "explainer");
  assert.ok(s.length >= 2);
  for (const sc of s) assert.ok(wordCount(sc.text) <= 60, `scene too long: ${wordCount(sc.text)}`);
  assert.equal(s.map((x) => x.text).join(" ").split(/\s+/).length, 140);
});

test("a single endless sentence is split by words", () => {
  const s = splitScript(Array.from({ length: 200 }, (_, i) => `w${i}`).join(" "), "explainer");
  assert.ok(s.length >= 3);
});

test("empty / whitespace script gives no scenes", () => {
  assert.equal(splitScript("", "explainer").length, 0);
  assert.equal(splitScript("  \n\n \r\n", "explainer").length, 0);
});

test("Windows line endings work", () => {
  assert.equal(splitScript("A.\r\n\r\nB.", "explainer").length, 2);
});

test("scene ids are unique and backgrounds use the template colour", () => {
  const s = splitScript(TEMPLATES.trailer.sample, "trailer");
  assert.equal(new Set(s.map((x) => x.id)).size, s.length);
  assert.ok(s.every((x) => x.background.color === TEMPLATES.trailer.background.color));
});

test("duration estimate follows words, pace and template limits", () => {
  assert.equal(speechSeconds(""), 0);
  const ten = "one two three four five six seven eight nine ten.";
  assert.ok(Math.abs(speechSeconds(ten, 1, 1) - (10 / 2.5 + 0.25)) < 1e-9);
  assert.ok(speechSeconds(ten, 1, 2) < speechSeconds(ten, 1, 1));
  const tpl = getTemplate("trailer");
  assert.equal(estimateSceneSeconds({ text: "" }, tpl), tpl.sceneSeconds.default);
  assert.equal(estimateSceneSeconds({ text: "Hi." }, tpl), tpl.sceneSeconds.min);
  assert.equal(estimateSceneSeconds({ text: "x", fixedSeconds: 7 }, tpl), 7);
});

test("every template defines the required settings", () => {
  assert.equal(TEMPLATE_IDS.length, 5);
  for (const id of TEMPLATE_IDS) {
    const t = TEMPLATES[id];
    for (const k of ["structure", "sceneSeconds", "text", "transition", "music", "voice", "sample", "kenBurns"]) assert.ok(t[k], `${id}.${k}`);
    assert.ok(["fade", "slide", "zoom"].includes(t.transition.type));
    assert.ok(splitScript(t.sample, id).length >= 4, `${id} sample splits into scenes`);
  }
});
