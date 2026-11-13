import { test } from "node:test";
import assert from "node:assert/strict";
import { Store, newProject, validateProject, SCHEMA, STORAGE_KEY } from "../../studio/js/store.js";

function memStorage() {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), m };
}

test("undo / redo of scene edits, reorder and delete", () => {
  const s = new Store(memStorage());
  s.splitFromScript("A.\n\nB.\n\nC.");
  const ids = s.project.scenes.map((x) => x.id);
  s.moveScene(ids[2], -1);
  assert.deepEqual(s.project.scenes.map((x) => x.text), ["A.", "C.", "B."]);
  s.deleteScene(ids[0]);
  assert.equal(s.project.scenes.length, 2);
  s.undo();
  assert.equal(s.project.scenes.length, 3);
  s.undo();
  assert.deepEqual(s.project.scenes.map((x) => x.text), ["A.", "B.", "C."]);
  s.redo();
  assert.deepEqual(s.project.scenes.map((x) => x.text), ["A.", "C.", "B."]);
  assert.ok(s.canUndo() && s.canRedo());
});

test("typing in one field is one undo step; new edits clear redo", () => {
  const s = new Store(memStorage());
  s.splitFromScript("A.");
  const id = s.project.scenes[0].id;
  for (const t of ["A", "AB", "ABC"]) s.editScene(id, { text: t }, `${id}:text`);
  s.undo();
  assert.equal(s.project.scenes[0].text, "A.");
  s.redo();
  s.undo();
  s.editScene(id, { title: "x" });
  assert.equal(s.canRedo(), false);
});

test("editing text invalidates the voice clip", () => {
  const s = new Store(memStorage());
  s.splitFromScript("A.");
  const id = s.project.scenes[0].id;
  s.update((p) => (p.scenes[0].audio = { mediaId: "m", seconds: 1, key: "k" }), { undoable: false });
  s.editScene(id, { title: "New title" });
  assert.ok(s.project.scenes[0].audio);
  s.editScene(id, { text: "Changed." });
  assert.equal(s.project.scenes[0].audio, null);
});

test("autosave writes to storage and a new Store reloads it", () => {
  const mem = memStorage();
  const s = new Store(mem);
  s.update((p) => (p.title = "Saved title"));
  s.saveNow();
  const again = new Store(mem);
  assert.equal(again.project.title, "Saved title");
});

test("quota errors are reported, not thrown", () => {
  const s = new Store({ getItem: () => null, setItem: () => { const e = new Error("full"); e.name = "QuotaExceededError"; throw e; } });
  assert.equal(s.saveNow(), false);
  assert.match(s.lastSaveError, /storage is full/);
});

test("project JSON round trip and validation", () => {
  const p = newProject("trailer");
  p.scenes = [{ id: "a", title: "T", text: "x" }];
  const back = validateProject(JSON.parse(JSON.stringify(p)));
  assert.equal(back.template, "trailer");
  assert.equal(back.scenes[0].background.kind, "color");
  assert.throws(() => validateProject({ schema: "other", scenes: [] }), /Unsupported/);
  assert.throws(() => validateProject({ schema: SCHEMA }), /scene list/);
  assert.throws(() => validateProject(null), /not a studio project/);
  const fixed = validateProject({ schema: SCHEMA, scenes: [], format: { aspect: "4:3", height: 999 }, template: "nope" });
  assert.deepEqual(fixed.format, { aspect: "16:9", height: 720 });
  assert.equal(fixed.template, "explainer");
});

test("saved projects contain no credential fields", () => {
  const mem = memStorage();
  const s = new Store(mem);
  s.saveNow();
  assert.doesNotMatch(mem.m.get(STORAGE_KEY), /apiKey|secret|token/i);
});

test("a background change redraws the scene list; typing does not", () => {
  const s = new Store(memStorage());
  s.splitFromScript("A.");
  const id = s.project.scenes[0].id;
  const reasons = [];
  s.subscribe((_, r) => reasons.push(r));
  s.editScene(id, { text: "B." }, `${id}:text`);
  s.editScene(id, { background: { kind: "image", mediaId: "m1", color: "#000000" } });
  assert.deepEqual(reasons, ["scene", "media"]);
});
