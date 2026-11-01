// ElevenLabs text-to-speech over its public REST API. The key comes from Settings (localStorage)
// and is sent only to api.elevenlabs.io in the xi-api-key header.
import { VoiceError, errorFromResponse, networkError } from "./errors.js";

export const API = "https://api.elevenlabs.io/v1";
const SERVICE = "ElevenLabs";

export const elevenlabs = {
  id: "elevenlabs",
  label: "ElevenLabs (your API key)",
  canExport: true,
  controls: { speed: true, pitch: false, stability: true, similarity: true },

  ready(settings) {
    return settings.elevenKey ? { ok: true } : { ok: false, reason: "Add your ElevenLabs API key in Settings." };
  },

  async listVoices(settings, fetchImpl = fetch) {
    if (!settings.elevenKey) throw new VoiceError("auth", "Add your ElevenLabs API key in Settings.");
    let res;
    try {
      res = await fetchImpl(`${API}/voices`, { headers: { "xi-api-key": settings.elevenKey } });
    } catch (e) {
      throw networkError(SERVICE, e);
    }
    if (!res.ok) throw await errorFromResponse(res, SERVICE);
    const data = await res.json();
    return (data.voices || []).map((v) => ({
      id: v.voice_id,
      name: v.name,
      lang: v.labels?.language || v.labels?.accent || "",
      gender: v.labels?.gender || "",
    }));
  },

  /** Returns an audio Blob (MP3). */
  async synthesize(text, voice, settings, { signal, fetchImpl = fetch } = {}) {
    if (!settings.elevenKey) throw new VoiceError("auth", "Add your ElevenLabs API key in Settings.");
    if (!voice.voiceId) throw new VoiceError("bad_request", "Choose an ElevenLabs voice first.");
    const body = {
      text,
      model_id: settings.elevenModel || "eleven_multilingual_v2",
      voice_settings: {
        stability: clamp(voice.stability ?? 0.5, 0, 1),
        similarity_boost: clamp(voice.similarity ?? 0.75, 0, 1),
        speed: clamp(voice.speed ?? 1, 0.7, 1.2),
      },
    };
    let res;
    try {
      res = await fetchImpl(`${API}/text-to-speech/${encodeURIComponent(voice.voiceId)}?output_format=mp3_44100_128`, {
        method: "POST",
        headers: { "xi-api-key": settings.elevenKey, "Content-Type": "application/json", Accept: "audio/mpeg" },
        body: JSON.stringify(body),
        signal,
      });
    } catch (e) {
      throw networkError(SERVICE, e);
    }
    if (!res.ok) throw await errorFromResponse(res, SERVICE);
    return res.blob();
  },
};

function clamp(v, lo, hi) {
  return Math.min(hi, Math.max(lo, Number(v)));
}
