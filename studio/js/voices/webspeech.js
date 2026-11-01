// Browser / Windows voices via the Web Speech API: free and offline, but the browser does not
// expose the audio, so it is used for previews only (exports need another engine).
import { VoiceError } from "./errors.js";

function synth() {
  return globalThis.speechSynthesis || null;
}

export function getBrowserVoices(timeout = 1500) {
  const s = synth();
  if (!s) return Promise.resolve([]);
  const now = s.getVoices();
  if (now.length) return Promise.resolve(now);
  return new Promise((resolve) => {
    const done = () => resolve(s.getVoices());
    s.addEventListener?.("voiceschanged", done, { once: true });
    setTimeout(done, timeout);
  });
}

export const webspeech = {
  id: "webspeech",
  label: "Browser / Windows voices (free, preview only)",
  canExport: false,
  controls: { speed: true, pitch: true, stability: false, similarity: false },

  ready() {
    return synth() ? { ok: true } : { ok: false, reason: "This browser has no built-in voices." };
  },

  async listVoices() {
    const voices = await getBrowserVoices();
    return voices.map((v) => ({ id: v.voiceURI || v.name, name: `${v.name}${v.localService ? "" : " (online)"}`, lang: v.lang, gender: "" }));
  },

  async synthesize() {
    throw new VoiceError("unsupported", "Browser voices can be previewed but not saved into a video. Choose the local voice server or ElevenLabs for export.", { fallback: false });
  },

  /** Speak now. Resolves when finished (or cancelled). */
  async speak(text, voice) {
    const s = synth();
    if (!s) throw new VoiceError("unsupported", "This browser has no built-in voices.", { fallback: false });
    s.cancel();
    const voices = await getBrowserVoices();
    return new Promise((resolve) => {
      const u = new SpeechSynthesisUtterance(text);
      const v = voices.find((x) => (x.voiceURI || x.name) === voice.voiceId);
      if (v) u.voice = v;
      u.lang = v?.lang || voice.lang || "en-US";
      u.rate = Math.min(2, Math.max(0.5, Number(voice.speed) || 1));
      u.pitch = Math.min(2, Math.max(0, Number(voice.pitch) || 1));
      u.onend = resolve;
      u.onerror = resolve;
      s.speak(u);
    });
  },

  stop() {
    synth()?.cancel();
  },
};
