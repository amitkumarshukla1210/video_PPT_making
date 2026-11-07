import { test } from "node:test";
import assert from "node:assert/strict";
import { DEFAULT_URL, local } from "../../studio/js/voices/local.js";
import { webspeech } from "../../studio/js/voices/webspeech.js";
import { audioKey, ENGINES, loadPresets, savePreset, deletePreset, sceneVoice, loadSettings } from "../../studio/js/voices/index.js";
import { encodeWav } from "../../studio/js/render/audio.js";

const settings = {};
const voice = { engine: "local", voiceId: "kokoro:af_heart", speed: 1.5 };

function fakeFetch(status, body, type = "application/json") {
  const calls = [];
  const fn = async (url, opts = {}) => {
    calls.push({ url, opts });
    const payload = typeof body === "string" || body instanceof Uint8Array ? body : JSON.stringify(body);
    return new Response(payload, { status, headers: { "Content-Type": type } });
  };
  fn.calls = calls;
  return fn;
}

test("the Studio exposes only built-in preview and local synthesis engines", () => {
  assert.deepEqual(Object.keys(ENGINES).sort(), ["local", "webspeech"]);
  const saved = loadSettings({ getItem: () => JSON.stringify({ theme: "dark", remoteAccessToken: "old-secret", localAccessToken: "old-secret" }) });
  assert.deepEqual(saved, { theme: "dark" });
});

test("local server: requests stay on localhost and return voice list and audio", async () => {
  const f = fakeFetch(200, new Uint8Array(100), "audio/wav");
  await local.synthesize("Hi", { voiceId: "kokoro:af_heart", speed: 1.1 }, settings, { fetchImpl: f });
  assert.equal(f.calls[0].url, `${DEFAULT_URL}/v1/audio/speech`);
  assert.deepEqual(Object.keys(f.calls[0].opts.headers), ["Content-Type"]);
  assert.deepEqual(JSON.parse(f.calls[0].opts.body), { model: "tts-1", input: "Hi", voice: "kokoro:af_heart", speed: 1.1, response_format: "wav" });
  const listFetch = fakeFetch(200, { voices: [{ id: "kokoro:af_heart", name: "Heart" }] });
  const list = await local.listVoices({ voiceServiceUrl: "https://example.invalid", accessToken: "secret" }, listFetch);
  assert.equal(list[0].id, "kokoro:af_heart");
  assert.equal(listFetch.calls[0].url, `${DEFAULT_URL}/v1/audio/voices`);
  assert.equal(f.calls[0].url.startsWith("http://localhost:"), true);
  const fallback = await local.listVoices(settings, fakeFetch(404, { error: "nope" }));
  assert.ok(fallback.some((v) => v.id === "alloy"));
  await assert.rejects(local.synthesize("Hi", {}, settings, { fetchImpl: fakeFetch(200, new Uint8Array(0), "audio/wav") }), /empty audio/);
});

test("browser voices refuse to export (no audio access)", async () => {
  assert.equal(webspeech.canExport, false);
  await assert.rejects(webspeech.synthesize(), (e) => e.code === "unsupported" && e.fallback === false);
});

test("audio key changes with text or voice settings only", () => {
  const a = audioKey("Hello", voice);
  assert.equal(a, audioKey("Hello", { ...voice }));
  assert.notEqual(a, audioKey("Hello!", voice));
  assert.notEqual(a, audioKey("Hello", { ...voice, speed: 1 }));
});

test("voice presets: save, replace, delete; per-scene override", () => {
  const m = new Map();
  const st = { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) };
  savePreset("Calm", { ...voice, extra: "ignored" }, st);
  savePreset("Calm", { ...voice, speed: 0.9 }, st);
  savePreset("Bold", voice, st);
  assert.deepEqual(loadPresets(st).map((p) => p.name), ["Bold", "Calm"]);
  assert.equal(loadPresets(st)[1].voice.speed, 0.9);
  assert.equal("extra" in loadPresets(st)[0].voice, false);
  deletePreset("Bold", st);
  assert.equal(loadPresets(st).length, 1);
  const project = { voice: { engine: "local", voiceId: "a", speed: 1 } };
  assert.equal(sceneVoice(project, { voice: null }).voiceId, "a");
  assert.equal(sceneVoice(project, { voice: { voiceId: "b" } }).voiceId, "b");
  assert.equal(loadSettings({ getItem: () => "{broken" }).theme, "auto");
});

test("WAV encoder writes a valid header and clamps samples", () => {
  const bytes = encodeWav([new Float32Array([0, 1, -1, 2]), new Float32Array([0, 0.5, -0.5, -2])], 44100);
  const dv = new DataView(bytes.buffer);
  assert.equal(String.fromCharCode(...bytes.slice(0, 4)), "RIFF");
  assert.equal(String.fromCharCode(...bytes.slice(8, 12)), "WAVE");
  assert.equal(dv.getUint16(22, true), 2);
  assert.equal(dv.getUint32(24, true), 44100);
  assert.equal(dv.getUint32(40, true), 16);
  assert.equal(bytes.length, 44 + 16);
  assert.equal(dv.getInt16(48, true), 32767);
  assert.equal(dv.getInt16(58, true), -32768);
});
