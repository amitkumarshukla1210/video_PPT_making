// One error type for every local or browser voice engine, so the UI can report failures clearly.
export class VoiceError extends Error {
  /** @param {"network"|"bad_request"|"server"|"unsupported"|"aborted"} code */
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
  if (status >= 400 && status < 500) {
    return new VoiceError("bad_request", `${service}: request refused (${status}) — ${detail.message || "check the voice and text"}.`, { status, fallback: true });
  }
  return new VoiceError("server", `${service} returned an error (${status}). Check that the local app and voice engine are ready.`, { status });
}

export function networkError(service, err) {
  if (err?.name === "AbortError") return new VoiceError("aborted", "Cancelled.", { fallback: false });
  return new VoiceError("network", `${service} could not be reached. Start the Design to Cost app on this computer and try again.`);
}
