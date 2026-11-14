// Local AI helpers served by the Design to Cost app on this computer (no API key, no cloud):
// scene writing (Ollama), picture creation (Stable Diffusion LCM on OpenVINO), and the music library.
import { DEFAULT_URL } from "./voices/local.js";
import { VoiceError, errorFromResponse, networkError } from "./voices/errors.js";

const SERVICE = "Local voice server";   // same app; its messages explain how to start it

async function call(path, opts = {}, fetchImpl = fetch) {
  let res;
  try {
    res = await fetchImpl(`${DEFAULT_URL}${path}`, opts);
  } catch (e) {
    throw networkError(SERVICE, e);
  }
  if (!res.ok) {
    let message = "";
    try {
      message = (await res.clone().json()).error?.message || "";
    } catch {
      /* not JSON */
    }
    if (message && res.status >= 500) throw new VoiceError("server", message, { status: res.status, fallback: false });
    throw await errorFromResponse(res, SERVICE);
  }
  return res;
}

export async function aiStatus(fetchImpl = fetch) {
  try {
    return await (await call("/v1/ai/status", {}, fetchImpl)).json();
  } catch {
    return { llm: { available: false, info: "Start the Design to Cost app on this computer to use the local AI." },
      images: { available: false, info: "Start the Design to Cost app on this computer to use the picture creator." } };
  }
}

/** Idea → { script, scenes: [{ title, line, image }] } */
export async function writeScenes({ idea, template, scenes = 5, language = "en", style = "" }, fetchImpl = fetch) {
  const res = await call("/v1/ai/scenes", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idea, template, scenes, language, style }),
  }, fetchImpl);
  return res.json();
}

/** Long videos: start the scene writer in the background and poll it. onProgress(message). */
export async function writeScenesLong(args, onProgress = () => {}, fetchImpl = fetch, pollMs = 2000) {
  await call("/v1/ai/scenes", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...args, background: true }),
  }, fetchImpl);
  for (;;) {
    await new Promise((r) => setTimeout(r, pollMs));
    const job = await (await call("/v1/ai/jobs/scenes", {}, fetchImpl)).json();
    if (job.state === "done") return job.result;
    if (job.state === "error") throw new VoiceError("server", job.error || "The scene writer failed.", { fallback: false });
    onProgress(`${job.message || "Writing scenes"} · ${Math.round(job.elapsed || 0)} s`);
  }
}

/** Prompt → PNG Blob */
export async function createImage(prompt, aspect = "16:9", fetchImpl = fetch) {
  const res = await call("/v1/images/generations", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, n: 1, aspect }),
  }, fetchImpl);
  const data = await res.json();
  const b64 = data.data?.[0]?.b64_json;
  if (!b64) throw new VoiceError("server", "The picture creator returned no picture.", { fallback: false });
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  return new Blob([bytes], { type: "image/png" });
}

export async function libraryList(fetchImpl = fetch) {
  return (await call("/v1/library", {}, fetchImpl)).json();
}

export async function libraryMusic(mood, fetchImpl = fetch) {
  return (await call(`/v1/library/music/${encodeURIComponent(mood)}.wav`, {}, fetchImpl)).blob();
}

/** The picture prompt for a scene: the AI's own prompt, else its title and words. */
export function scenePicturePrompt(scene, projectTitle = "") {
  return (scene.imagePrompt || [scene.title, scene.text].filter(Boolean).join(". ") || projectTitle).slice(0, 900);
}
