// Project state with undo/redo, autosave and JSON import/export validation.
import { getTemplate, TEMPLATES } from "./templates.js";
import { newId, splitScript } from "./scenes.js";

export const SCHEMA = "dtc-studio/1";
export const STORAGE_KEY = "dtc.studio.project";
const HISTORY_LIMIT = 100;

export function newProject(templateId = "explainer") {
  const tpl = getTemplate(templateId);
  return {
    schema: SCHEMA,
    id: newId("p"),
    title: "Design to Cost",
    template: tpl.id,
    script: "",
    scenes: [],
    voice: { engine: "webspeech", voiceId: "", voiceName: "", lang: "en-US", speed: 1, pitch: 1, stability: 0.5, similarity: 0.75 },
    music: { mediaId: null, name: "", volume: tpl.music.volume, duck: true },
    cards: { title: true, end: true },
    subtitles: { burn: true },
    format: { aspect: "16:9", height: 720 },
    updated: new Date().toISOString(),
  };
}

const ASPECTS = ["16:9", "9:16", "1:1"];

/** Check and repair a project loaded from a file or storage. Throws with a readable message. */
export function validateProject(data) {
  if (!data || typeof data !== "object") throw new Error("This file is not a studio project.");
  if (data.schema !== SCHEMA) throw new Error(`Unsupported project format (${data.schema || "unknown"}).`);
  if (!Array.isArray(data.scenes)) throw new Error("The project has no scene list.");
  const base = newProject(TEMPLATES[data.template] ? data.template : "explainer");
  const p = { ...base, ...data };
  p.template = base.template; // unknown template ids fall back to the default
  p.voice = { ...base.voice, ...(data.voice || {}) };
  p.music = { ...base.music, ...(data.music || {}) };
  p.cards = { ...base.cards, ...(data.cards || {}) };
  p.subtitles = { ...base.subtitles, ...(data.subtitles || {}) };
  p.format = { ...base.format, ...(data.format || {}) };
  if (!ASPECTS.includes(p.format.aspect)) p.format.aspect = "16:9";
  if (![720, 1080].includes(Number(p.format.height))) p.format.height = 720;
  p.scenes = data.scenes.map((s, i) => ({
    id: typeof s.id === "string" && s.id ? s.id : newId("sc"),
    title: String(s.title ?? `Scene ${i + 1}`),
    text: String(s.text ?? ""),
    background: s.background && typeof s.background === "object" ? { kind: "color", color: "#152238", mediaId: null, ...s.background } : { kind: "color", color: "#152238", mediaId: null },
    transition: s.transition || null,
    fixedSeconds: Number(s.fixedSeconds) > 0 ? Number(s.fixedSeconds) : null,
    voice: s.voice || null,
    imagePrompt: typeof s.imagePrompt === "string" ? s.imagePrompt.slice(0, 900) : "",
    audio: s.audio && s.audio.mediaId ? s.audio : null,
  }));
  return p;
}

export class Store {
  constructor(storage = globalThis.localStorage) {
    this.storage = storage;
    this.listeners = new Set();
    this.past = [];
    this.future = [];
    this.saveTimer = null;
    this.lastSaveError = null;
    this.project = this.loadAutosave() || newProject();
  }

  loadAutosave() {
    try {
      const raw = this.storage?.getItem(STORAGE_KEY);
      return raw ? validateProject(JSON.parse(raw)) : null;
    } catch {
      return null;
    }
  }

  subscribe(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  emit(reason) {
    for (const fn of this.listeners) fn(this.project, reason);
  }

  /** Apply a change. `recipe(draft)` mutates a deep copy; history is kept unless `undoable` is false. */
  update(recipe, { undoable = true, reason = "edit", coalesce = null } = {}) {
    const before = JSON.stringify(this.project);
    const draft = JSON.parse(before);
    recipe(draft);
    const after = JSON.stringify(draft);
    if (after === before) return;
    if (undoable) {
      const last = this.past[this.past.length - 1];
      // typing in one field merges into one undo step
      if (!(coalesce && last && last.coalesce === coalesce && Date.now() - last.at < 1500)) {
        this.past.push({ json: before, coalesce, at: Date.now() });
        if (this.past.length > HISTORY_LIMIT) this.past.shift();
      } else {
        last.at = Date.now();
      }
      this.future = [];
    }
    draft.updated = new Date().toISOString();
    this.project = draft;
    this.scheduleSave();
    this.emit(reason);
  }

  canUndo() {
    return this.past.length > 0;
  }

  canRedo() {
    return this.future.length > 0;
  }

  undo() {
    const prev = this.past.pop();
    if (!prev) return false;
    this.future.push(JSON.stringify(this.project));
    this.project = JSON.parse(prev.json);
    this.scheduleSave();
    this.emit("undo");
    return true;
  }

  redo() {
    const next = this.future.pop();
    if (!next) return false;
    this.past.push({ json: JSON.stringify(this.project), coalesce: null, at: 0 });
    this.project = JSON.parse(next);
    this.scheduleSave();
    this.emit("redo");
    return true;
  }

  replace(project, reason = "load") {
    this.past = [];
    this.future = [];
    this.project = validateProject(project);
    this.saveNow();
    this.emit(reason);
  }

  scheduleSave() {
    clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(() => this.saveNow(), 400);
  }

  saveNow() {
    clearTimeout(this.saveTimer);
    try {
      this.storage?.setItem(STORAGE_KEY, JSON.stringify(this.project));
      this.lastSaveError = null;
    } catch (e) {
      this.lastSaveError = e && e.name === "QuotaExceededError"
        ? "Browser storage is full — download the project as a file to keep it."
        : `Autosave failed: ${e?.message || e}`;
    }
    return !this.lastSaveError;
  }

  // ---------- scene helpers ----------
  splitFromScript(script) {
    this.update((p) => {
      p.script = script;
      const old = p.scenes;
      p.scenes = splitScript(script, p.template).map((s, i) => {
        // keep backgrounds the user already chose, by position
        if (old[i]) s.background = old[i].background;
        return s;
      });
    }, { reason: "split" });
  }

  moveScene(id, delta) {
    this.update((p) => {
      const i = p.scenes.findIndex((s) => s.id === id);
      const j = i + delta;
      if (i < 0 || j < 0 || j >= p.scenes.length) return;
      [p.scenes[i], p.scenes[j]] = [p.scenes[j], p.scenes[i]];
    }, { reason: "reorder" });
  }

  deleteScene(id) {
    this.update((p) => {
      p.scenes = p.scenes.filter((s) => s.id !== id);
    }, { reason: "delete" });
  }

  editScene(id, fields, coalesce = null) {
    this.update((p) => {
      const s = p.scenes.find((x) => x.id === id);
      if (!s) return;
      Object.assign(s, fields);
      // changed words make the old voice clip stale
      if ("text" in fields || "voice" in fields) s.audio = null;
      // a new background must redraw the scene list (its thumbnail); typing only updates labels
    }, { reason: "background" in fields ? "media" : "scene", coalesce });
  }
}
