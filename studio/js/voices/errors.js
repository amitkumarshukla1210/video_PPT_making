// One error type for every voice engine, so the UI can show one clear message and fall back.
export class VoiceError extends Error {
  /** @param {"auth"|"quota"|"network"|"bad_request"|"server"|"unsupported"|"aborted"} code */
  constructor(code, message, { status = 0, fallback = true } = {}) {
    super(message);
    this.name = "VoiceError";
    this.code = code;
    this.status = status;
    this.fallback = fallback; // true = preview may fall back to the browser voice
  }
}

/** Turn an HTTP response (already known to be !ok) into a VoiceError with a friendly message. */
export async function errorFromResponse(res, service) {
  let detail = {};
  try {
    const body = await res.clone().json();
    detail = typeof body.detail === "object" && body.detail ? body.detail : { message: body.detail || body.error?.message || body.error || body.message };
  } catch {
    try {
      detail = { message: (await res.text()).slice(0, 200) };
    } catch {
      /* ignore */
    }
  }
  const status = res.status;
  const code = String(detail.status || detail.code || "").toLowerCase();
  if (code.includes("quota") || code.includes("credit") || (status === 401 && /quota|credits/i.test(detail.message || ""))) {
    return new VoiceError("quota", `${service}: your character quota is used up. Add credits or switch engine.`, { status });
  }
  if (status === 401 || status === 403 || code.includes("invalid_api_key") || code.includes("unauthorized")) {
    return new VoiceError("auth", `${service}: the API key was rejected. Check it in Settings.`, { status });
  }
  if (status === 429) {
    return new VoiceError("quota", `${service}: too many requests or quota exceeded. Wait a minute or switch engine.`, { status });
  }
  if (status >= 400 && status < 500) {
    return new VoiceError("bad_request", `${service}: request refused (${status}) — ${detail.message || "check the voice and text"}.`, { status, fallback: true });
  }
  return new VoiceError("server", `${service} had a problem (${status}). Try again later.`, { status });
}

export function networkError(service, err) {
  if (err?.name === "AbortError") return new VoiceError("aborted", "Cancelled.", { fallback: false });
  return new VoiceError("network", `${service} could not be reached (no internet, server off, or blocked).`);
}
