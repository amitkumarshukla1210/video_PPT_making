// Video & Voice Studio — page wiring. Data lives in store.js; drawing/export in render/*.
import { TEMPLATES, TEMPLATE_IDS, getTemplate } from "./templates.js";
import { makeScene, wordCount, speechSeconds } from "./scenes.js";
import { buildTimeline, toSrt, formatClock, MAX_SECONDS } from "./timeline.js";
import { Store, newProject, validateProject } from "./store.js";
import { putMedia, getMedia, mediaUrl, embedMedia, restoreMedia, releaseUrls } from "./media.js";
import { ENGINES, VoiceError, loadSettings, saveSettings, loadPresets, savePreset, deletePreset, sceneVoice, audioKey } from "./voices/index.js";
import { webspeech } from "./voices/webspeech.js";
import { drawFrame, frameSize, syncVideos } from "./render/draw.js";
import { decodeBlob, scheduleAudio } from "./render/audio.js";
import { aiStatus, writeScenes, writeScenesLong, createImage, libraryList, libraryMusic, scenePicturePrompt } from "./ai.js";
import { prepareVoices, recordVideo, exportAudio, loadAssets, loadAudio, disposeAssets } from "./render/export.js";

const $ = (s, root = document) => root.querySelector(s);
const store = new Store();
let settings = loadSettings();
let voiceList = [];
let busy = null; // AbortController of the running job
let resultUrls = [];
const LOGO_URL = new URL("../assets/logo.png", import.meta.url).href;

// ---------- helpers ----------
function toast(msg, isErr = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = `toast${isErr ? " err" : ""}`;
  t.hidden = false;
  clearTimeout(t._h);
  t._h = setTimeout(() => (t.hidden = true), isErr ? 8000 : 3000);
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

function download(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

function slug() {
  return (store.project.title || "video").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "video";
}

function isTyping(el) {
  return el && (el.tagName === "TEXTAREA" || (el.tagName === "INPUT" && !["checkbox", "range", "color", "file", "button"].includes(el.type)) || el.isContentEditable);
}

// ---------- theme ----------
function applyTheme() {
  document.documentElement.dataset.theme = settings.theme || "auto";
  const dark = settings.theme === "dark" || (settings.theme !== "light" && matchMedia("(prefers-color-scheme: dark)").matches);
  $("#themeBtn").setAttribute("aria-pressed", String(dark));
  $("#themeBtn").title = dark ? "Switch to light mode" : "Switch to dark mode";
}

// ---------- templates strip ----------
function renderTemplates() {
  const cur = store.project.template;
  $("#templates").innerHTML = TEMPLATE_IDS.map((id) => {
    const t = TEMPLATES[id];
    const on = id === cur;
    return `<button type="button" class="tpl" role="radio" aria-checked="${on}" tabindex="${on ? 0 : -1}" data-tpl="${id}">
      <span class="ico" aria-hidden="true">${t.icon}</span><span><span class="t-name">${esc(t.name)}</span><span class="t-blurb">${esc(t.blurb)}</span></span></button>`;
  }).join("");
}

function chooseTemplate(id) {
  const tpl = getTemplate(id);
  store.update((p) => {
    p.template = id;
    p.music.volume = tpl.music.volume;
  }, { reason: "template" });
  $("#exportFormat").value = tpl.audioOnly ? "mp3" : ($("#exportFormat").value === "mp3" ? "webm" : $("#exportFormat").value);
}

// ---------- scenes ----------
async function setThumb(el, scene) {
  const bg = scene.background || {};
  el.style.background = bg.color || "#152238";
  el.innerHTML = "";
  if (bg.mediaId && bg.kind !== "color") {
    const url = await mediaUrl(bg.mediaId);
    if (!url) return;
    const media = document.createElement(bg.kind === "video" ? "video" : "img");
    media.src = url;
    media.alt = "";
    if (bg.kind === "video") media.muted = true;
    el.append(media);
  } else {
    el.textContent = "Colour";
  }
}

function sceneTimes() {
  const tl = buildTimeline(store.project);
  const map = new Map();
  for (const it of tl.items) if (it.type === "scene") map.set(it.sceneId, it);
  return { tl, map };
}

function voiceBadge(scene) {
  if (!scene.text.trim()) return `<span class="badge">no text</span>`;
  if (!scene.audio) return `<span class="badge">voice not made</span>`;
  const v = sceneVoice(store.project, scene);
  const fresh = scene.audio.key === audioKey(scene.text, v);
  return fresh ? `<span class="badge ok">voice ready</span>` : `<span class="badge stale">voice out of date</span>`;
}


function renderScenes() {
  const { scenes } = store.project;
  const { map } = sceneTimes();
  const presets = loadPresets();
  $("#sceneCount").textContent = scenes.length ? `(${scenes.length})` : "";
  $("#scenesEmpty").classList.toggle("hidden", scenes.length > 0);
  const list = $("#scenes");
  list.innerHTML = scenes.map((s, i) => {
    const it = map.get(s.id);
    const tr = s.transition?.type || "";
    return `<li class="scene" data-id="${s.id}">
      <div>
        <div class="thumb" data-thumb aria-hidden="true"></div>
        <div class="scene-tools">
          <button type="button" class="icon-btn small" data-act="say" aria-label="Preview voice of scene ${i + 1}" title="Preview voice">▶</button>
          <button type="button" class="icon-btn small" data-act="regen" aria-label="Regenerate voice of scene ${i + 1}" title="Regenerate voice">↻</button>
          <button type="button" class="icon-btn small" data-act="picture" aria-label="Create a picture for scene ${i + 1}" title="Create picture (local AI)">🖼</button>
          <button type="button" class="icon-btn small" data-act="up" aria-label="Move scene ${i + 1} up" title="Move up" ${i === 0 ? "disabled" : ""}>↑</button>
          <button type="button" class="icon-btn small" data-act="down" aria-label="Move scene ${i + 1} down" title="Move down" ${i === scenes.length - 1 ? "disabled" : ""}>↓</button>
          <button type="button" class="icon-btn small danger" data-act="del" aria-label="Delete scene ${i + 1}" title="Delete">✕</button>
        </div>
      </div>
      <div class="scene-body">
        <div class="scene-head"><span class="num">${i + 1}</span>
          <input data-k="title" value="${esc(s.title)}" aria-label="Title of scene ${i + 1}" placeholder="On-screen title"></div>
        <textarea data-k="text" rows="3" aria-label="Voiceover text of scene ${i + 1}" placeholder="What the voice says">${esc(s.text)}</textarea>
        <div class="scene-meta">
          <label>Background <input type="color" data-k="color" value="${esc(s.background?.color || "#152238")}" aria-label="Background colour of scene ${i + 1}"></label>
          <label class="btn btn-outline small-btn" style="padding:4px 8px">Image / video<input type="file" data-k="media" accept="image/*,video/*" class="visually-hidden" aria-label="Background image or video for scene ${i + 1}"></label>
          ${s.background?.mediaId ? `<button type="button" class="btn btn-outline" style="padding:4px 8px" data-act="clearmedia">Use colour</button>` : ""}
          <label>Transition <select data-k="transition" aria-label="Transition into scene ${i + 1}">
            <option value="" ${!tr ? "selected" : ""}>Template</option>
            ${["fade", "slide", "zoom"].map((x) => `<option value="${x}" ${tr === x ? "selected" : ""}>${x[0].toUpperCase() + x.slice(1)}</option>`).join("")}
          </select></label>
          <label>Voice <select data-k="voice" aria-label="Voice for scene ${i + 1}">
            <option value="">Project voice</option>
            ${presets.map((p) => `<option value="${esc(p.name)}" ${s.voice && s.voice.preset === p.name ? "selected" : ""}>${esc(p.name)}</option>`).join("")}
          </select></label>
          <label class="prompt-field">Picture prompt <input data-k="imagePrompt" value="${esc(s.imagePrompt || "")}" placeholder="blank = title + words" aria-label="Picture prompt for scene ${i + 1}"></label>
          <label>Length <input type="number" data-k="seconds" min="1" max="300" step="0.5" value="${s.fixedSeconds ?? ""}" placeholder="auto" style="width:72px" aria-label="Length of scene ${i + 1} in seconds (blank = automatic)"></label>
          <span data-dur>${it ? `${(it.end - it.start).toFixed(1)} s${it.estimated ? " (est.)" : ""}` : ""}</span>
          <span data-badge>${voiceBadge(s)}</span>
        </div>
      </div>
    </li>`;
  }).join("");
  for (const li of list.querySelectorAll(".scene")) {
    const scene = scenes.find((x) => x.id === li.dataset.id);
    setThumb(li.querySelector("[data-thumb]"), scene);
  }
}

/** Update durations/badges without rebuilding the list (keeps focus while typing). */
function updateSceneMeta() {
  const { map } = sceneTimes();
  for (const li of document.querySelectorAll("#scenes .scene")) {
    const scene = store.project.scenes.find((x) => x.id === li.dataset.id);
    const it = map.get(li.dataset.id);
    if (!scene || !it) continue;
    li.querySelector("[data-dur]").textContent = `${(it.end - it.start).toFixed(1)} s${it.estimated ? " (est.)" : ""}`;
    li.querySelector("[data-badge]").innerHTML = voiceBadge(scene);
  }
}

// ---------- voice panel ----------
function renderEngines() {
  $("#engine").innerHTML = Object.values(ENGINES).map((e) => `<option value="${e.id}">${esc(e.label)}</option>`).join("");
}

function renderVoicePanel() {
  const v = store.project.voice;
  const engine = ENGINES[v.engine] || ENGINES.webspeech;
  $("#engine").value = engine.id;
  for (const [k, id] of [["pitch", "#pitchField"], ["stability", "#stabilityField"], ["similarity", "#similarityField"]]) {
    $(id).classList.toggle("hidden", !engine.controls[k]);
  }
  for (const k of ["speed", "pitch", "stability", "similarity"]) {
    if (document.activeElement !== $(`#${k}`)) $(`#${k}`).value = v[k];
    $(`#${k}Out`).textContent = Number(v[k]).toFixed(2);
  }
  const sel = $("#voiceSelect");
  const opts = voiceList.map((x) => `<option value="${esc(x.id)}">${esc(x.name)}${x.lang ? ` · ${esc(x.lang)}` : ""}${x.gender ? ` · ${esc(x.gender)}` : ""}</option>`);
  sel.innerHTML = opts.length ? opts.join("") : `<option value="">(default voice)</option>`;
  if (voiceList.some((x) => x.id === v.voiceId)) sel.value = v.voiceId;
  const ready = engine.ready(settings);
  $("#engineNote").textContent = !ready.ok ? ready.reason
    : engine.canExport ? `${engine.label}: voices are saved into your video and audio files.`
      : "Browser voices can only be previewed. Start the local Design to Cost app and choose its voice server for narrated exports, or untick “Include voiceover”.";
  if ((v.voiceId || "").startsWith("clone:")) {
    $("#engineNote").textContent += " Your cloned voice: allow about 3–5 s per second of speech without an NVIDIA graphics card.";
  }
  renderPresets();
}

async function loadVoiceList({ quiet = false } = {}) {
  const engine = ENGINES[store.project.voice.engine] || ENGINES.webspeech;
  try {
    voiceList = await engine.listVoices(settings);
    const v = store.project.voice;
    if (voiceList.length && !voiceList.some((x) => x.id === v.voiceId)) {
      const first = voiceList.find((x) => (x.lang || "").toLowerCase().startsWith("en")) || voiceList[0];
      store.update((p) => {
        p.voice.voiceId = first.id;
        p.voice.voiceName = first.name;
      }, { undoable: false, reason: "voices" });
    }
  } catch (e) {
    voiceList = [];
    if (!quiet) toast(e.message || String(e), true);
    $("#engineNote").textContent = e.message || String(e);
  }
  renderVoicePanel();
}

function renderPresets() {
  const list = loadPresets();
  $("#presets").innerHTML = list.length ? list.map((p) => `<li data-name="${esc(p.name)}"><span><span class="p-name">${esc(p.name)}</span>
    <span class="muted"> · ${esc(ENGINES[p.voice.engine]?.label.split(" (")[0] || p.voice.engine)}${p.voice.voiceName ? ` · ${esc(p.voice.voiceName)}` : ""}</span></span>
    <span class="row" style="margin:0"><button type="button" class="btn btn-outline" data-act="apply">Use</button>
    <button type="button" class="icon-btn small danger" data-act="del" aria-label="Delete preset ${esc(p.name)}">✕</button></span></li>`).join("")
    : `<li class="muted">No presets yet.</li>`;
}

/** Speak `text` with `voice`. Paid/local engines fall back to the browser voice on errors. */
async function speak(text, voice, blob = null) {
  webspeech.stop();
  const engine = ENGINES[voice.engine] || webspeech;
  if (!engine.canExport) return webspeech.speak(text, voice);
  try {
    const b = blob || await engine.synthesize(text, voice, settings);
    const url = URL.createObjectURL(b);
    const a = new Audio(url);
    a.onended = a.onerror = () => URL.revokeObjectURL(url);
    await a.play().catch(() => {});
  } catch (e) {
    if (e instanceof VoiceError && e.fallback) {
      toast(`${e.message} Playing the browser voice instead.`, true);
      return webspeech.speak(text, { ...voice, voiceId: "" });
    }
    toast(e.message || String(e), true);
  }
}

async function sceneVoicePreview(id, regenerate = false) {
  const scene = store.project.scenes.find((s) => s.id === id);
  if (!scene || !scene.text.trim()) return toast("This scene has no voiceover text.", true);
  const voice = sceneVoice(store.project, scene);
  if (!ENGINES[voice.engine]?.canExport) return speak(scene.text, voice);
  try {
    if (regenerate) store.editScene(id, { audio: null });
    await prepareVoices(store, settings, { only: [id] });
    const s = store.project.scenes.find((x) => x.id === id);
    const blob = s?.audio ? await getMedia(s.audio.mediaId) : null;
    if (blob) await speak(scene.text, voice, blob);
    if (regenerate) toast("Voice regenerated.");
  } catch (e) {
    if (e instanceof VoiceError && e.fallback) {
      toast(`${e.message} Playing the browser voice instead.`, true);
      webspeech.speak(scene.text, { ...voice, voiceId: "" });
    } else toast(e.message || String(e), true);
  }
}

// ---------- music ----------
function renderMusic() {
  const m = store.project.music;
  $("#musicName").textContent = m.mediaId ? m.name || "music added" : "No music";
  $("#musicMood").textContent = `Suggested mood: ${getTemplate(store.project.template).music.mood}`;
  if (document.activeElement !== $("#musicVol")) $("#musicVol").value = m.volume;
  $("#musicVolOut").textContent = `${Math.round(m.volume * 100)}%`;
  $("#musicDuck").checked = m.duck !== false;
}

// ---------- export panel & limit ----------
function renderExport() {
  const p = store.project;
  $("#aspect").value = p.format.aspect;
  $("#height").value = String(p.format.height);
  $("#burnSubs").checked = !!p.subtitles.burn;
  $("#titleCard").checked = !!p.cards.title;
  $("#endCard").checked = !!p.cards.end;
  const tl = buildTimeline(p);
  const pct = Math.min(100, (tl.total / MAX_SECONDS) * 100);
  $("#meterFill").style.width = `${pct}%`;
  $("#meterFill").classList.toggle("over", tl.overLimit);
  $("#meter").setAttribute("aria-valuenow", String(Math.round(tl.total)));
  const lt = $("#limitText");
  lt.classList.toggle("over", tl.overLimit);
  lt.textContent = tl.overLimit
    ? `Too long: ${formatClock(tl.total)} of max ${formatClock(MAX_SECONDS)} — ${formatClock(-tl.remaining)} over. Export is blocked until you shorten it.`
    : `Length ${formatClock(tl.total)} of max ${formatClock(MAX_SECONDS)} · ${formatClock(tl.remaining)} left${tl.items.some((x) => x.estimated) ? " (estimated until voices are made)" : ""}`;
  $("#exportBtn").disabled = tl.overLimit || !!busy;
  $("#exportBtn").title = tl.overLimit ? "Over the 10-minute limit" : "";
  $("#previewTime").textContent = `${formatClock(Number($("#scrub").value) / 100 * tl.total)} / ${formatClock(tl.total)}`;
  sizePreview();
}

function sizePreview() {
  const [W, H] = frameSize(store.project.format);
  const c = $("#previewCanvas");
  const scale = Math.min(640 / W, 400 / H);
  const w = Math.round(W * scale);
  const h = Math.round(H * scale);
  if (c.width !== w || c.height !== h) {
    c.width = w;
    c.height = h;
  }
}

function renderMeta() {
  const p = store.project;
  if (document.activeElement !== $("#projectTitle")) $("#projectTitle").value = p.title;
  if (document.activeElement !== $("#script")) $("#script").value = p.script;
  const words = wordCount(p.script);
  $("#scriptStats").textContent = words ? `${words} words · about ${formatClock(speechSeconds(p.script, getTemplate(p.template).voice.pace, p.voice.speed))} of speech` : "";
  $("#undoBtn").disabled = !store.canUndo();
  $("#redoBtn").disabled = !store.canRedo();
}

// ---------- preview player ----------
const player = { playing: false, ctx: null, sched: null, raf: 0, assets: null, from: 0, t0: 0, spoken: null };
let idle = { assets: null, sig: "" };

function mediaSignature(p) {
  return p.scenes.map((s) => s.background?.mediaId || "").join(",");
}

async function drawIdle() {
  if (player.playing) return;
  const p = store.project;
  const sig = mediaSignature(p);
  if (!idle.assets || idle.sig !== sig) {
    if (idle.assets) disposeAssets(idle.assets);
    idle = { assets: await loadAssets(p, LOGO_URL), sig };
  }
  const tl = buildTimeline(p);
  const t = (Number($("#scrub").value) / 100) * tl.total;
  drawFrame($("#previewCanvas").getContext("2d"), p, tl, Math.min(t, Math.max(0, tl.total - 0.001)), idle.assets);
}

async function play() {
  if (player.playing) return stop();
  const p = store.project;
  const tl = buildTimeline(p);
  if (!tl.items.length) return;
  player.playing = true;
  $("#playBtn").textContent = "■ Stop";
  $("#playBtn").setAttribute("aria-pressed", "true");
  player.assets = await loadAssets(p, LOGO_URL);
  const { voices, music } = await loadAudio(p);
  player.ctx = new AudioContext();
  await player.ctx.resume();
  player.from = (Number($("#scrub").value) / 100) * tl.total;
  if (player.from >= tl.total - 0.05) player.from = 0;
  player.t0 = player.ctx.currentTime + 0.1 - player.from;
  player.sched = scheduleAudio(player.ctx, player.ctx.destination, tl, voices, music, p, player.t0, player.from);
  player.spoken = new Set();
  const ctx2d = $("#previewCanvas").getContext("2d");
  const loop = () => {
    if (!player.playing) return;
    const t = player.ctx.currentTime - player.t0;
    if (t >= tl.total) return stop(true);
    syncVideos(p, tl, Math.max(0, t), player.assets, true);
    drawFrame(ctx2d, p, tl, Math.max(0, t), player.assets);
    // scenes without a saved clip are read by the browser voice during preview
    for (const it of tl.items) {
      if (it.type === "scene" && it.voiceStart == null && t >= it.start + 0.3 && t < it.end && !player.spoken.has(it.sceneId)) {
        player.spoken.add(it.sceneId);
        const scene = p.scenes.find((s) => s.id === it.sceneId);
        if (scene?.text) webspeech.speak(scene.text, ENGINES[sceneVoice(p, scene).engine]?.canExport ? { ...sceneVoice(p, scene), voiceId: "" } : sceneVoice(p, scene));
      }
    }
    $("#scrub").value = String((t / tl.total) * 100);
    $("#previewTime").textContent = `${formatClock(t)} / ${formatClock(tl.total)}`;
    player.raf = requestAnimationFrame(loop);
  };
  loop();
}

function stop(ended = false) {
  player.playing = false;
  cancelAnimationFrame(player.raf);
  player.sched?.stop();
  player.ctx?.close().catch(() => {});
  webspeech.stop();
  if (player.assets) disposeAssets(player.assets);
  idle = { assets: null, sig: "" }; // object URLs were released; reload on next idle draw
  player.assets = null;
  player.ctx = null;
  $("#playBtn").textContent = "▶ Play preview";
  $("#playBtn").setAttribute("aria-pressed", "false");
  if (ended) $("#scrub").value = "0";
  drawIdle();
}

// ---------- jobs: voices & export ----------
function setBusy(ctrl, label = "") {
  busy = ctrl;
  $("#cancelBtn").classList.toggle("hidden", !ctrl);
  $("#progress").classList.toggle("hidden", !ctrl && !label);
  for (const id of ["#exportBtn", "#genVoicesBtn"]) $(id).disabled = !!ctrl;
  if (!ctrl) renderExport();
}

function progress(f, msg) {
  $("#barFill").style.width = `${Math.round(Math.max(0, Math.min(1, f)) * 100)}%`;
  $("#progressText").textContent = msg;
}

function clearResults() {
  for (const u of resultUrls) URL.revokeObjectURL(u);
  resultUrls = [];
  $("#results").innerHTML = "";
}

function showResult(blob, name, kind, note = "") {
  clearResults();
  const url = URL.createObjectURL(blob);
  resultUrls.push(url);
  const mb = (blob.size / 1e6).toFixed(1);
  const media = kind === "video" ? `<video controls src="${url}"></video>` : kind === "audio" ? `<audio controls src="${url}"></audio>` : "";
  $("#results").innerHTML = `${media}<div class="row"><a class="btn btn-primary" href="${url}" download="${esc(name)}" id="downloadLink">⬇ Download ${esc(name)} (${mb} MB)</a></div>${note ? `<p class="muted">${esc(note)}</p>` : ""}`;
}

async function generateVoices() {
  const ctrl = new AbortController();
  setBusy(ctrl, "voices");
  try {
    await prepareVoices(store, settings, { signal: ctrl.signal, onProgress: progress });
    toast("All voiceovers are ready.");
    progress(1, "All voiceovers are ready.");
  } catch (e) {
    voiceFailure(e);
  } finally {
    setBusy(null);
  }
}

function voiceFailure(e) {
  if (e?.name === "AbortError") return progress(0, "Cancelled.");
  const msg = e?.message || String(e);
  progress(0, msg);
  toast(msg, true);
}

async function runExport() {
  const fmt = $("#exportFormat").value;
  const p = store.project;
  if (fmt === "srt") return download(new Blob([toSrt(buildTimeline(p).captions)], { type: "application/x-subrip" }), `${slug()}.srt`);
  const tl = buildTimeline(p);
  if (tl.overLimit) return toast(`Over the ${MAX_SECONDS / 60}-minute limit — shorten the video first.`, true);
  const needsConverter = fmt === "mp3" || (fmt === "mp4" && !MediaRecorder.isTypeSupported("video/mp4"));
  if (needsConverter && !confirm("This export needs the optional ffmpeg.wasm converter (about 31 MB), which will be downloaded from jsDelivr only if you approve. Continue?")) {
    return toast("Export cancelled. WebM video and WAV audio export without the converter.");
  }
  if (player.playing) stop();
  clearResults();
  const ctrl = new AbortController();
  setBusy(ctrl, "export");
  const withVoice = $("#withVoice").checked;
  try {
    if (withVoice && p.scenes.some((s) => s.text.trim())) {
      await prepareVoices(store, settings, { signal: ctrl.signal, onProgress: (f, m) => progress(f * 0.2, m) });
    }
    let project = store.project;
    if (!withVoice) project = { ...project, scenes: project.scenes.map((s) => ({ ...s, audio: null })) };
    if (fmt === "wav" || fmt === "mp3") {
      const { blob } = await exportAudio(project, settings, { format: fmt, signal: ctrl.signal, onProgress: progress });
      showResult(blob, `${slug()}.${fmt}`, "audio");
    } else {
      const res = await recordVideo(project, settings, { container: fmt, signal: ctrl.signal, onProgress: progress, logoUrl: LOGO_URL, canvas: $("#previewCanvas") });
      const ext = res.mime.includes("mp4") ? "mp4" : "webm";
      showResult(res.blob, `${slug()}.${ext}`, "video", fmt === "mp4" ? (res.nativeMp4 ? "Recorded as MP4 directly by the browser." : "Recorded as WebM and converted to MP4 with ffmpeg.wasm.") : "");
    }
    progress(1, "Export finished.");
    toast("Export finished.");
  } catch (e) {
    voiceFailure(e);
  } finally {
    setBusy(null);
    drawIdle();
  }
}

async function runNarratedSample() {
  if (store.project.scenes.length && !confirm("Replace the current Studio project with the ready-to-try sample?")) return;
  const button = $("#demoBtn");
  button.disabled = true;
  try {
    stop();
    clearResults();
    releaseUrls();
    store.replace(newProject("explainer"), "new");
    const script = "# A clearer starting point\nGood product decisions begin with a shared view of cost.\n\n# See the whole picture\nBring material, process and supplier details together before the design is fixed.\n\n# Decide with confidence\nCompare options early, make trade-offs visible, and keep the team aligned.";
    store.update((p) => {
      p.title = "Cost clarity — sample";
      p.voice.engine = "local";
      p.cards.title = false;
      p.cards.end = true;
      p.format.aspect = "16:9";
      p.format.height = 720;
    }, { reason: "meta" });
    store.splitFromScript(script);
    const response = await fetch(new URL("../assets/sample-cost-story.svg", import.meta.url));
    if (!response.ok) throw new Error("The included sample picture could not be loaded.");
    const mediaId = await putMedia(await response.blob(), "image");
    const first = store.project.scenes[0];
    store.editScene(first.id, { background: { kind: "image", color: "#152238", mediaId } });
    await loadVoiceList();
    if (!voiceList.length) throw new Error("The local voice server is not available. Start the Design to Cost app, then try the narrated sample again.");
    $("#exportFormat").value = "webm";
    $("#withVoice").checked = true;
    await prepareVoices(store, settings, { onProgress: progress });
    render("voice");
    await runExport();
  } catch (e) {
    voiceFailure(e);
  } finally {
    button.disabled = false;
  }
}

// ---------- local AI: scenes from an idea, pictures from prompts, music library ----------
let picturesBusy = false;

async function runAiScenes() {
  const idea = $("#aiIdea").value.trim();
  if (!idea) return toast("Describe your idea first.", true);
  if (store.project.scenes.length && !confirm("Replace the current script and scenes with the AI's scenes?")) return;
  const btn = $("#aiScenesBtn");
  btn.disabled = true;
  $("#aiStudioStatus").textContent = "⏳ The local AI is writing your scenes (about 30–90 s)…";
  try {
    const sel = $("#aiLength").value;
    const count = Math.max(2, Math.min(60, sel === "custom" ? Number($("#aiScenes").value) || 5 : Number(sel)));
    const args = { idea, template: store.project.template, scenes: count, language: $("#aiLanguage").value, style: $("#aiStyle").value.trim() };
    const out = count > 8
      ? await writeScenesLong(args, (m) => ($("#aiStudioStatus").textContent = `⏳ ${m} — a long video takes the local AI several minutes`))
      : await writeScenes(args);
    store.splitFromScript(out.script);
    store.update((p) => {
      p.scenes.forEach((s, k) => { if (out.scenes[k]) s.imagePrompt = out.scenes[k].image; });
      if (!p.title || p.title === "Design to Cost") p.title = out.scenes[0]?.title || p.title;
    }, { reason: "split" });
    $("#aiStudioStatus").textContent = `✔ ${store.project.scenes.length} scenes written. Edit them freely.`
      + (store.project.scenes.length > 12 && $("#aiPictures").checked ? " Creating the pictures takes a while on a laptop (about 20–60 s each)." : "");
    if ($("#aiPictures").checked) await createPictures(store.project.scenes.map((s) => s.id));
  } catch (e) {
    $("#aiStudioStatus").textContent = `❌ ${e.message || e}`;
    toast(e.message || String(e), true);
  } finally {
    btn.disabled = false;
  }
}

async function createPictures(ids) {
  if (picturesBusy) return toast("Pictures are already being created — please wait.");
  picturesBusy = true;
  $("#picturesAllBtn").disabled = true;
  let done = 0;
  try {
    for (const id of ids) {
      const scene = store.project.scenes.find((s) => s.id === id);
      if (!scene) continue;
      $("#aiStudioStatus").textContent = `⏳ Creating picture ${done + 1} of ${ids.length} (about 20–60 s each on a laptop)…`;
      toast(`Creating picture ${done + 1} of ${ids.length}…`);
      const blob = await createImage(scenePicturePrompt(scene, store.project.title), store.project.format.aspect);
      const mediaId = await putMedia(blob, "image");
      const now = store.project.scenes.find((s) => s.id === id);
      if (now) store.editScene(id, { background: { ...now.background, kind: "image", mediaId } });
      done += 1;
    }
    $("#aiStudioStatus").textContent = `✔ ${done} picture(s) created. Preview the video to see them with slow pan and zoom.`;
  } catch (e) {
    $("#aiStudioStatus").textContent = `❌ ${e.message || e}`;
    toast(e.message || String(e), true);
  } finally {
    picturesBusy = false;
    $("#picturesAllBtn").disabled = false;
  }
}

async function loadMusicLibrary() {
  try {
    const lib = await libraryList();
    $("#libMood").innerHTML = `<option value="">Music library (made by the app, free to use)…</option>`
      + lib.music.map((m) => `<option value="${esc(m.id)}">${esc(m.label)}</option>`).join("");
  } catch {
    $("#libMood").innerHTML = `<option value="">Music library: start the Design to Cost app</option>`;
  }
}

async function useLibraryMusic() {
  const mood = $("#libMood").value;
  if (!mood) return toast("Choose a mood from the music library first.", true);
  try {
    const blob = await libraryMusic(mood);
    const mediaId = await putMedia(blob, "music");
    const label = $("#libMood").selectedOptions[0]?.textContent || mood;
    store.update((p) => { p.music.mediaId = mediaId; p.music.name = label; }, { reason: "music" });
    toast(`Using “${label}”. It is lowered automatically under the voice.`);
  } catch (e) {
    toast(e.message || String(e), true);
  }
}

// ---------- project files ----------
async function saveFile() {
  try {
    const data = await embedMedia(store.project);
    download(new Blob([JSON.stringify(data)], { type: "application/json" }), `${slug()}.studio.json`);
  } catch (e) {
    toast(`Could not save: ${e.message || e}`, true);
  }
}

async function openFile(file) {
  try {
    const data = JSON.parse(await file.text());
    validateProject(data); // check before touching storage
    const project = await restoreMedia(data);
    stop();
    clearResults();
    releaseUrls();
    store.replace(project, "load");
    await loadVoiceList({ quiet: true });
    toast(`Opened “${store.project.title}”.`);
  } catch (e) {
    toast(e instanceof SyntaxError ? "That file is not valid JSON." : e.message || String(e), true);
  }
}

// ---------- full render on state change ----------
function render(reason) {
  if (reason !== "scene") renderScenes();
  else updateSceneMeta();
  if (["template", "load", "undo", "redo", "init", "new"].includes(reason)) renderTemplates();
  renderMeta();
  renderVoicePanel();
  renderMusic();
  renderExport();
  if (!player.playing) drawIdle();
  if (store.lastSaveError) toast(store.lastSaveError, true);
}

// ---------- events ----------
function bind() {
  store.subscribe((_, reason) => render(reason));

  $("#templates").addEventListener("click", (e) => {
    const b = e.target.closest("[data-tpl]");
    if (b) chooseTemplate(b.dataset.tpl);
  });
  $("#templates").addEventListener("keydown", (e) => {
    if (!["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].includes(e.key)) return;
    e.preventDefault();
    const i = TEMPLATE_IDS.indexOf(store.project.template);
    const j = (i + (e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1) + TEMPLATE_IDS.length) % TEMPLATE_IDS.length;
    chooseTemplate(TEMPLATE_IDS[j]);
    $(`[data-tpl="${TEMPLATE_IDS[j]}"]`)?.focus();
  });

  $("#projectTitle").addEventListener("input", (e) => store.update((p) => (p.title = e.target.value), { coalesce: "title", reason: "meta" }));
  $("#script").addEventListener("input", (e) => store.update((p) => (p.script = e.target.value), { coalesce: "script", reason: "meta" }));
  $("#splitBtn").addEventListener("click", () => {
    const text = $("#script").value;
    if (!text.trim()) return toast("Write or paste a script first.", true);
    if (store.project.scenes.length && !confirm("Replace the current scenes with scenes from the script?")) return;
    store.splitFromScript(text);
    toast(`${store.project.scenes.length} scenes created. Edit, reorder or delete them below.`);
  });
  $("#sampleBtn").addEventListener("click", () => {
    const tpl = getTemplate(store.project.template);
    store.update((p) => (p.script = tpl.sample), { reason: "meta" });
  });
  $("#demoBtn").addEventListener("click", runNarratedSample);
  $("#aiScenesBtn").addEventListener("click", runAiScenes);
  $("#aiLength").addEventListener("change", (e) => $("#aiScenesField").classList.toggle("hidden", e.target.value !== "custom"));
  $("#picturesAllBtn").addEventListener("click", () => {
    if (!store.project.scenes.length) return toast("Add or write scenes first.", true);
    createPictures(store.project.scenes.map((s) => s.id));
  });
  $("#libUse").addEventListener("click", useLibraryMusic);
  $("#addSceneBtn").addEventListener("click", () => {
    store.update((p) => p.scenes.push(makeScene({ text: "" }, getTemplate(p.template), p.scenes.length)), { reason: "add" });
    document.querySelector("#scenes .scene:last-child textarea")?.focus();
  });

  const list = $("#scenes");
  list.addEventListener("input", (e) => {
    const li = e.target.closest(".scene");
    const k = e.target.dataset.k;
    if (!li || !["title", "text", "imagePrompt"].includes(k)) return;
    store.editScene(li.dataset.id, { [k]: e.target.value }, `${li.dataset.id}:${k}`);
  });
  list.addEventListener("change", async (e) => {
    const li = e.target.closest(".scene");
    if (!li) return;
    const id = li.dataset.id;
    const scene = store.project.scenes.find((s) => s.id === id);
    const k = e.target.dataset.k;
    if (k === "seconds") {
      const v = Number(e.target.value);
      store.editScene(id, { fixedSeconds: v > 0 ? Math.min(300, v) : null });
    } else if (k === "color") store.editScene(id, { background: { ...scene.background, color: e.target.value } });
    else if (k === "transition") {
      const tpl = getTemplate(store.project.template);
      store.editScene(id, { transition: e.target.value ? { type: e.target.value, seconds: tpl.transition.seconds } : null });
    } else if (k === "voice") {
      const preset = loadPresets().find((p) => p.name === e.target.value);
      store.editScene(id, { voice: preset ? { ...preset.voice, preset: preset.name } : null });
    } else if (k === "media" && e.target.files[0]) {
      const f = e.target.files[0];
      if (!/^(image|video)\//.test(f.type)) return toast("Please choose an image or a video file.", true);
      const mediaId = await putMedia(f, f.type.startsWith("video/") ? "video" : "image");
      store.editScene(id, { background: { ...scene.background, kind: f.type.startsWith("video/") ? "video" : "image", mediaId } });
    }
  });
  list.addEventListener("click", (e) => {
    const b = e.target.closest("[data-act]");
    const li = e.target.closest(".scene");
    if (!b || !li) return;
    const id = li.dataset.id;
    const act = b.dataset.act;
    if (act === "up") store.moveScene(id, -1);
    else if (act === "down") store.moveScene(id, 1);
    else if (act === "del") store.deleteScene(id);
    else if (act === "say") sceneVoicePreview(id);
    else if (act === "regen") sceneVoicePreview(id, true);
    else if (act === "picture") createPictures([id]);
    else if (act === "clearmedia") {
      const scene = store.project.scenes.find((s) => s.id === id);
      store.editScene(id, { background: { ...scene.background, kind: "color", mediaId: null } });
    }
    if (["up", "down"].includes(act)) document.querySelector(`#scenes [data-id="${id}"] [data-act="${act}"]:not(:disabled)`)?.focus();
  });

  // voice
  $("#engine").addEventListener("change", (e) => {
    store.update((p) => {
      p.voice.engine = e.target.value;
      p.voice.voiceId = "";
      p.voice.voiceName = "";
    }, { reason: "voice" });
    loadVoiceList();
  });
  $("#voiceSelect").addEventListener("change", (e) => {
    const v = voiceList.find((x) => x.id === e.target.value);
    store.update((p) => {
      p.voice.voiceId = e.target.value;
      p.voice.voiceName = v?.name || "";
      p.voice.lang = v?.lang || p.voice.lang;
    }, { reason: "voice" });
  });
  $("#refreshVoices").addEventListener("click", () => loadVoiceList());
  for (const k of ["speed", "pitch", "stability", "similarity"]) {
    $(`#${k}`).addEventListener("input", (e) => store.update((p) => (p.voice[k] = Number(e.target.value)), { coalesce: `voice:${k}`, reason: "voice" }));
  }
  $("#voicePreviewBtn").addEventListener("click", () => {
    const first = store.project.scenes.find((s) => s.text.trim());
    speak(first?.text.slice(0, 220) || "This is how your video will sound.", store.project.voice);
  });
  $("#genVoicesBtn").addEventListener("click", generateVoices);
  $("#savePresetBtn").addEventListener("click", () => {
    const name = $("#presetName").value.trim();
    if (!name) return toast("Give the preset a name.", true);
    savePreset(name, store.project.voice);
    $("#presetName").value = "";
    renderPresets();
    renderScenes();
    toast(`Saved voice preset “${name}”.`);
  });
  $("#presets").addEventListener("click", (e) => {
    const b = e.target.closest("[data-act]");
    const li = e.target.closest("li[data-name]");
    if (!b || !li) return;
    const preset = loadPresets().find((p) => p.name === li.dataset.name);
    if (b.dataset.act === "apply" && preset) {
      store.update((p) => Object.assign(p.voice, preset.voice), { reason: "voice" });
      loadVoiceList({ quiet: true });
      toast(`Using “${preset.name}”.`);
    } else if (b.dataset.act === "del") {
      deletePreset(li.dataset.name);
      renderPresets();
      renderScenes();
    }
  });

  // music
  $("#musicFile").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      await decodeBlob(f); // reject files the browser can't play
    } catch {
      e.target.value = "";
      return toast("This audio file can't be played by the browser. Try MP3 or WAV.", true);
    }
    const mediaId = await putMedia(f, "music");
    store.update((p) => {
      p.music.mediaId = mediaId;
      p.music.name = f.name;
    }, { reason: "music" });
    e.target.value = "";
  });
  $("#musicClear").addEventListener("click", () => store.update((p) => {
    p.music.mediaId = null;
    p.music.name = "";
  }, { reason: "music" }));
  $("#musicVol").addEventListener("input", (e) => store.update((p) => (p.music.volume = Number(e.target.value)), { coalesce: "musicvol", reason: "music" }));
  $("#musicDuck").addEventListener("change", (e) => store.update((p) => (p.music.duck = e.target.checked), { reason: "music" }));

  // export settings
  $("#aspect").addEventListener("change", (e) => store.update((p) => (p.format.aspect = e.target.value), { reason: "format" }));
  $("#height").addEventListener("change", (e) => store.update((p) => (p.format.height = Number(e.target.value)), { reason: "format" }));
  $("#burnSubs").addEventListener("change", (e) => store.update((p) => (p.subtitles.burn = e.target.checked), { reason: "format" }));
  $("#titleCard").addEventListener("change", (e) => store.update((p) => (p.cards.title = e.target.checked), { reason: "format" }));
  $("#endCard").addEventListener("change", (e) => store.update((p) => (p.cards.end = e.target.checked), { reason: "format" }));
  $("#exportBtn").addEventListener("click", runExport);
  $("#srtBtn").addEventListener("click", () => download(new Blob([toSrt(buildTimeline(store.project).captions)], { type: "application/x-subrip" }), `${slug()}.srt`));
  $("#cancelBtn").addEventListener("click", () => busy?.abort());

  // preview
  $("#playBtn").addEventListener("click", () => play());
  $("#scrub").addEventListener("input", () => {
    if (player.playing) stop();
    renderExport();
    drawIdle();
  });

  // header
  $("#undoBtn").addEventListener("click", () => store.undo());
  $("#redoBtn").addEventListener("click", () => store.redo());
  $("#newBtn").addEventListener("click", () => {
    if (store.project.scenes.length && !confirm("Start a new project? Save the current one as a file first if you want to keep it.")) return;
    stop();
    clearResults();
    releaseUrls();
    store.replace(newProject(store.project.template), "new");
    loadVoiceList({ quiet: true });
  });
  $("#openBtn").addEventListener("click", () => $("#openFile").click());
  $("#openFile").addEventListener("change", (e) => {
    if (e.target.files[0]) openFile(e.target.files[0]);
    e.target.value = "";
  });
  $("#saveBtn").addEventListener("click", saveFile);
  $("#themeBtn").addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme === "dark" || (settings.theme !== "light" && matchMedia("(prefers-color-scheme: dark)").matches);
    settings.theme = dark ? "light" : "dark";
    saveSettings(settings);
    applyTheme();
  });

  // keyboard shortcuts
  document.addEventListener("keydown", (e) => {
    const mod = e.ctrlKey || e.metaKey;
    if (!mod) return;
    const k = e.key.toLowerCase();
    if (k === "s") {
      e.preventDefault();
      saveFile();
    } else if (!isTyping(document.activeElement) && (k === "z" || k === "y")) {
      e.preventDefault();
      if (k === "y" || e.shiftKey) store.redo();
      else store.undo();
    }
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", applyTheme);
  window.addEventListener("pagehide", () => store.saveNow());
}

/** VERSION is copied next to the page when published, and served by the local app at /studio/VERSION. */
async function showVersion() {
  try {
    const res = await fetch("VERSION", { cache: "no-store" });
    const v = res.ok ? (await res.text()).trim() : "";
    if (/^\d+\.\d+\.\d+/.test(v)) $("#appVersion").textContent = ` · version ${v}`;
  } catch {
    /* offline copy without a VERSION file: just don't show it */
  }
}

async function init() {
  applyTheme();
  renderEngines();
  renderTemplates();
  bind();
  render("init");
  showVersion();
  loadMusicLibrary();
  aiStatus().then((st) => {
    if (!st.llm.available) $("#aiStudioStatus").textContent = st.llm.info;
    $("#picturesAllBtn").title = st.images.available ? "Create a picture from each scene's picture prompt" : st.images.info;
  });
  await loadVoiceList({ quiet: true });
  document.body.dataset.ready = "true"; // for tests
}

init().catch((e) => toast(`The studio could not start: ${e.message || e}`, true));

// test hook: lets end-to-end tests read state without reaching into closures
globalThis.__studio = { store, buildTimeline: () => buildTimeline(store.project) };
