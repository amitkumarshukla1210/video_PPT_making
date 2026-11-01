import { test } from "node:test";
import assert from "node:assert/strict";
import { elevenlabs, API } from "../../studio/js/voices/elevenlabs.js";
import { local } from "../../studio/js/voices/local.js";
import { webspeech } from "../../studio/js/voices/webspeech.js";
import { audioKey, loadPresets, savePreset, deletePreset, sceneVoice, loadSettings } from "../../studio/js/voices/index.js";
import { encodeWav } from "../../studio/js/render/audio.js";

const settings = { elevenKey: "test-key", localUrl: "http://localhost:9999/" };
const voice = { engine: "elevenlabs", voiceId: "v1", speed: 1.5, stability: 0.4, similarity: 0.9 };

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

test("ElevenLabs request shape: key header, voice id, clamped settings", async () => {
  const f = fakeFetch(200, new Uint8Array([1, 2, 3]), "audio/mpeg");
  const blob = await elevenlabs.synthesize("Hello", voice, settings, { fetchImpl: f });
  assert.equal(blob.size, 3);
  const { url, opts } = f.calls[0];
  assert.equal(url, `${API}/text-to-speech/v1?output_format=mp3_44100_128`);
  assert.equal(opts.headers["xi-api-key"], "test-key");
  const body = JSON.parse(opts.body);
  assert.equal(body.voice_settings.speed, 1.2);
  assert.equal(body.voice_settings.similarity_boost, 0.9);
});

test("ElevenLabs errors become friendly VoiceErrors", async () => {
  const cases = [
    [401, { detail: { status: "invalid_api_key", message: "Invalid API key" } }, "auth"],
    [401, { detail: { status: "quota_exceeded", message: "This request exceeds your quota" } }, "quota"],
    [429, { detail: { status: "too_many_concurrent_requests" } }, "quota"],
    [500, "oops", "server"],
  ];
  for (const [status, body, code] of cases) {
    await assert.rejects(elevenlabs.synthesize("x", voice, settings, { fetchImpl: fakeFetch(status, body) }), (e) => e.name === "VoiceError" && e.code === code && e.fallback === true);
  }
  await assert.rejects(elevenlabs.synthesize("x", voice, settings, { fetchImpl: async () => { throw new TypeError("Failed to fetch"); } }), (e) => e.code === "network");
  await assert.rejects(elevenlabs.synthesize("x", voice, { elevenKey: "" }), (e) => e.code === "auth");
});

test("ElevenLabs voice list mapping", async () => {
  const f = fakeFetch(200, { voices: [{ voice_id: "a", name: "Rachel", labels: { gender: "female", accent: "american" } }] });
  const list = await elevenlabs.listVoices(settings, f);
  assert.deepEqual(list, [{ id: "a", name: "Rachel", lang: "american", gender: "female" }]);
});

test("local server: OpenAI-compatible request, voice list and 404 fallback", async () => {
  const f = fakeFetch(200, new Uint8Array(100), "audio/wav");
  await local.synthesize("Hi", { voiceId: "kokoro:af_heart", speed: 1.1 }, settings, { fetchImpl: f });
  assert.equal(f.calls[0].url, "http://localhost:9999/v1/audio/speech");
  assert.deepEqual(JSON.parse(f.calls[0].opts.body), { model: "tts-1", input: "Hi", voice: "kokoro:af_heart", speed: 1.1, response_format: "wav" });
  const list = await local.listVoices(settings, fakeFetch(200, { voices: [{ id: "kokoro:af_heart", name: "Heart" }] }));
  assert.equal(list[0].id, "kokoro:af_heart");
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
  assert.equal(loadSettings({ getItem: () => "{broken" }).localUrl, "http://localhost:8000");
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
