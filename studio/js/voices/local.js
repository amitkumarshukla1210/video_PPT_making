// Any OpenAI-compatible speech server: POST {base}/v1/audio/speech → audio.
// The Design to Cost app (start_windows.bat) provides one at http://localhost:8000 with Kokoro/Piper/eSpeak.
import { VoiceError, errorFromResponse, networkError } from "./errors.js";

const SERVICE = "Local voice server";
export const DEFAULT_URL = "http://localhost:8000";

export const local = {
  id: "local",
  label: "Local voice server (Kokoro / Piper / eSpeak)",
  canExport: true,
  controls: { speed: true, pitch: false, stability: false, similarity: false },

  ready() {
    return { ok: true };
  },

  async listVoices(settings, fetchImpl = fetch) {
    let res;
    try {
      res = await fetchImpl(`${DEFAULT_URL}/v1/audio/voices`);
    } catch (e) {
      throw networkError(SERVICE, e);
    }
    if (res.status === 404) {
      // Plain OpenAI-compatible servers have no voice list: offer the common names.
      return ["alloy", "echo", "fable", "onyx", "nova", "shimmer"].map((n) => ({ id: n, name: n, lang: "", gender: "" }));
    }
    if (!res.ok) throw await errorFromResponse(res, SERVICE);
    const data = await res.json();
    return (data.voices || []).map((v) => ({ id: v.id, name: v.name || v.id, lang: v.lang || "", gender: v.gender || "", engine: v.engine || "" }));
  },

  /** Returns an audio Blob (WAV by default). */
  async synthesize(text, voice, settings, { signal, fetchImpl = fetch } = {}) {
    let res;
    try {
      res = await fetchImpl(`${DEFAULT_URL}/v1/audio/speech`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: settings.localModel || "tts-1",
          input: text,
          voice: voice.voiceId || "alloy",
          speed: Math.min(4, Math.max(0.25, Number(voice.speed) || 1)),
          response_format: "wav",
        }),
        signal,
      });
    } catch (e) {
      throw networkError(SERVICE, e);
    }
    if (!res.ok) throw await errorFromResponse(res, SERVICE);
    const blob = await res.blob();
    if (!blob.size) throw new VoiceError("server", `${SERVICE} returned empty audio.`);
    return blob;
  },
};
