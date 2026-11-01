// Engine registry, settings (localStorage only) and the voice library (named presets).
import { elevenlabs } from "./elevenlabs.js";
import { local, DEFAULT_URL } from "./local.js";
import { webspeech } from "./webspeech.js";

export { VoiceError } from "./errors.js";
export const ENGINES = { webspeech, local, elevenlabs };

const SETTINGS_KEY = "dtc.studio.settings";
const PRESETS_KEY = "dtc.studio.voicePresets";

export function loadSettings(storage = globalThis.localStorage) {
  const defaults = { elevenKey: "", elevenModel: "eleven_multilingual_v2", localUrl: DEFAULT_URL, localKey: "", localModel: "tts-1", ffmpegBase: "", theme: "auto" };
  try {
    return { ...defaults, ...JSON.parse(storage?.getItem(SETTINGS_KEY) || "{}") };
  } catch {
    return defaults;
  }
}

export function saveSettings(settings, storage = globalThis.localStorage) {
  storage?.setItem(SETTINGS_KEY, JSON.stringify(settings));
}

export function loadPresets(storage = globalThis.localStorage) {
  try {
    const list = JSON.parse(storage?.getItem(PRESETS_KEY) || "[]");
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

export function savePreset(name, voice, storage = globalThis.localStorage) {
  const list = loadPresets(storage).filter((p) => p.name !== name);
  const { engine, voiceId, voiceName, lang, speed, pitch, stability, similarity } = voice;
  list.push({ name, voice: { engine, voiceId, voiceName, lang, speed, pitch, stability, similarity } });
  list.sort((a, b) => a.name.localeCompare(b.name));
  storage?.setItem(PRESETS_KEY, JSON.stringify(list));
  return list;
}

export function deletePreset(name, storage = globalThis.localStorage) {
  const list = loadPresets(storage).filter((p) => p.name !== name);
  storage?.setItem(PRESETS_KEY, JSON.stringify(list));
  return list;
}

/** Key identifying a generated clip: same text + same voice settings = reuse the clip. */
export function audioKey(text, voice) {
  const v = [voice.engine, voice.voiceId, voice.speed, voice.pitch, voice.stability, voice.similarity].join("|");
  let h = 2166136261;
  for (const ch of `${v}::${text}`) {
    h ^= ch.codePointAt(0);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h.toString(36);
}

/** The voice a scene uses: its own override or the project voice. */
export function sceneVoice(project, scene) {
  return scene.voice ? { ...project.voice, ...scene.voice } : project.voice;
}
