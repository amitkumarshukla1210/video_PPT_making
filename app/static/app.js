// Design to Cost — Presentation & Video Studio. Plain JavaScript, no build step.
const $ = (s) => document.querySelector(s);
let sys = null, proj = null, saveTimer = null, pollTimer = null;

const LANG_NAMES = { "en-us": "English (US)", "en-gb": "English (UK)", en: "English", hi: "Hindi", es: "Spanish",
  "fr-fr": "French", fr: "French", it: "Italian", "pt-br": "Portuguese (BR)", pt: "Portuguese", de: "German",
  ar: "Arabic", ru: "Russian", zh: "Chinese", ja: "Japanese", ta: "Tamil", te: "Telugu", mr: "Marathi",
  bn: "Bengali", gu: "Gujarati", da: "Danish", el: "Greek", fi: "Finnish", he: "Hebrew", ko: "Korean",
  ms: "Malay", nl: "Dutch", no: "Norwegian", pl: "Polish", sv: "Swedish", sw: "Swahili", tr: "Turkish" };

function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast" + (err ? " err" : "");
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.add("hidden"), err ? 8000 : 2800);
}

async function api(path, opts = {}) {
  if (opts.json !== undefined) {
    opts.body = JSON.stringify(opts.json); opts.headers = { "Content-Type": "application/json" }; delete opts.json;
  }
  const r = await fetch(path, opts);
  const data = r.headers.get("content-type")?.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error(data.error || data || r.statusText);
  return data;
}

async function upload(path, files, field = "files", extra = {}) {
  const fd = new FormData();
  for (const f of files) fd.append(field, f, f.name || "recording.webm");
  for (const [k, v] of Object.entries(extra)) fd.append(k, v);
  return api(path, { method: "POST", body: fd });
}

function busy(btn, on) { if (btn) btn.disabled = on; }
function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function mmss(s) { s = Math.round(s || 0); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; }
const fileUrl = (p) => `/files/${proj.id}/${p}`;

// ---------- projects ----------
async function loadProjects(selectId) {
  const list = await api("/api/projects");
  const sel = $("#projectSelect");
  sel.innerHTML = list.map((p) => `<option value="${p.id}">${esc(p.name)} (${p.slides})</option>`).join("");
  if (!list.length) { await newProject("Design to Cost"); return; }
  let id = selectId;
  try { id = id || localStorage.getItem("dtc.project"); } catch (e) { /* private mode */ }
  sel.value = list.some((p) => p.id === id) ? id : list[0].id;
  await openProject(sel.value);
}

async function newProject(name) {
  name = name || prompt("Project name", "Design to Cost");
  if (!name) return;
  const p = await api("/api/projects", { method: "POST", json: { name } });
  await loadProjects(p.id);
}

async function openProject(id) {
  proj = await api(`/api/projects/${id}`);
  try { localStorage.setItem("dtc.project", id); } catch (e) { /* ignore */ }
  $("#app").classList.remove("hidden");
  render();
  checkJob();
}

// ---------- rendering ----------
function render() {
  document.querySelectorAll("[data-field]").forEach((el) => { el.value = proj[el.dataset.field] || ""; });
  $("#logoImg").src = proj.logo ? fileUrl(proj.logo) : "/static/logo_hd.png";
  $("#scriptTxt").href = `/api/projects/${proj.id}/script.txt`;
  $("#musicName").textContent = proj.music.file ? "✔ music added" : "No music";
  $("#musicVol").value = proj.music.volume; $("#musicVolVal").textContent = Math.round(proj.music.volume * 100) + "%";
  $("#intro").value = proj.intro === false ? "0" : "1";
  const pip = proj.pip || {};
  $("#pipEnabled").value = pip.enabled ? "1" : "0";
  $("#pipPosition").value = pip.position || "br";
  $("#pipShape").value = pip.shape || "circle";
  $("#pipSize").value = pip.size || "m";
  $("#pipPhoto").classList.toggle("hidden", !pip.photo);
  if (pip.photo) $("#pipPhoto").src = fileUrl(pip.photo);
  renderSample(); renderSlides(); renderVoice(); refreshEstimate();
}

function renderSample() {
  const has = !!proj.voice_sample;
  $("#sampleAudio").classList.toggle("hidden", !has);
  if (has) $("#sampleAudio").src = fileUrl(proj.voice_sample);
  $("#sampleInfo").textContent = has ? `✔ Voice sample saved (${proj.voice_sample_seconds || "?"} s). Choose “My cloned voice” as the engine.` : "No voice sample yet.";
  const clone = sys.engines.find((e) => e.name === "clone");
  $("#cloneStatus").textContent = clone.available ? `Voice clone engine: ${clone.info}. Licence: ${clone.licence}.`
    : "Voice clone engine is not installed yet. Run “setup_windows.bat clone” once (downloads about 3 GB). You can record the sample now.";
}

function renderSlides() {
  const box = $("#slides");
  $("#slideCount").textContent = `· ${proj.slides.length} slides`;
  box.innerHTML = proj.slides.map((s, i) => {
    const cover = s.kind !== "content";
    const thumb = s.image ? `<img src="${fileUrl(s.image)}" loading="lazy">`
      : cover ? `${s.kind === "title" ? "Title slide" : "Closing slide"}<br>(navy, logo)` : "Text slide<br>(no screenshot)";
    const rec = s.clip
      ? `<div class="rec-box"><video src="${fileUrl(s.clip)}" controls playsinline preload="metadata"></video>
           <div><span class="badge mine">Your recording · ${mmss(s.clip_seconds)}</span><br>
           <span class="muted">Your own voice and video are used on this slide.</span><br>
           <button class="icon" data-act="unclip">✕ Remove recording</button></div></div>`
      : `<div class="rec-box"><span class="muted">Explain this slide yourself:</span>
           <button class="icon" data-act="rec">🎥 Record</button>
           <label class="icon">📱 Phone camera / file<input type="file" accept="video/*" capture="user" data-act="clipfile" hidden></label></div>`;
    return `<div class="slide ${cover ? "cover" : ""}" data-i="${i}">
      <div><div class="thumb">${thumb}</div>
        <div class="slide-tools">
          ${cover ? "" : `<button class="icon" data-act="up" title="Move up">↑</button>
          <button class="icon" data-act="down" title="Move down">↓</button>
          <label class="icon" title="Replace screenshot">🖼<input type="file" accept="image/*" data-act="img" hidden></label>
          <button class="icon" data-act="del" title="Delete slide">✕</button>`}
          <button class="icon" data-act="say" title="Hear this slide">▶</button>
        </div>
        <div class="secs" data-secs="${i}"></div></div>
      <div class="slide-fields">
        <div class="slide-head"><span class="num">${i + 1}</span>
          <input data-k="title" value="${esc(s.title)}" placeholder="Slide title"></div>
        <div><label>${cover ? "Subtitle" : "Notes for this screen (one line = one bullet)"}</label>
          <textarea data-k="notes" rows="${cover ? 1 : 3}">${esc(s.notes)}</textarea></div>
        <div><label>Narration (what is said — edit freely${s.clip ? "; used for subtitles" : ""})</label>
          <textarea class="script" data-k="script" rows="4">${esc(s.script)}</textarea></div>
        ${rec}
      </div></div>`;
  }).join("");
}

function renderVoice() {
  const engines = sys.engines;
  const eSel = $("#engine");
  eSel.innerHTML = engines.map((e) => `<option value="${e.name}" ${e.available ? "" : "disabled"}>${esc(e.label)}${e.available ? "" : " — not installed"}</option>`).join("");
  let engine = proj.voice.engine;
  if (!engines.find((e) => e.name === engine && e.available)) engine = sys.default_engine || "";
  eSel.value = engine;
  const eng = engines.find((e) => e.name === engine);
  $("#engineInfo").textContent = eng ? `${eng.label}: ${eng.info} · licence ${eng.licence}` :
    "No voice engine installed yet — run setup_windows.bat (it downloads the Kokoro voices once).";
  const voices = eng ? eng.voices : [];
  const langs = [...new Set(voices.map((v) => v.lang))];
  const lSel = $("#lang");
  lSel.innerHTML = langs.map((l) => `<option value="${l}">${LANG_NAMES[l] || l}</option>`).join("");
  const lang = langs.includes(proj.voice.lang) ? proj.voice.lang : langs[0];
  lSel.value = lang || "";
  const g = $("#gender").value;
  $("#gender").disabled = !voices.some((v) => v.gender);
  const vs = voices.filter((v) => v.lang === lang && (!g || !v.gender || v.gender === g));
  $("#voice").innerHTML = vs.map((v) => `<option value="${esc(v.id)}">${esc(v.label)}${v.gender ? " · " + v.gender : ""}</option>`).join("");
  $("#voice").value = vs.some((v) => v.id === proj.voice.voice) ? proj.voice.voice : (vs[0]?.id || "");
  $("#speed").value = proj.voice.speed || 1; $("#speedVal").textContent = (+$("#speed").value).toFixed(2) + "×";
  const changed = proj.voice.engine !== eSel.value || proj.voice.lang !== lSel.value || proj.voice.voice !== $("#voice").value;
  proj.voice = { engine: eSel.value, lang: lSel.value, voice: $("#voice").value, speed: +$("#speed").value };
  if (changed) scheduleSave();
}

async function refreshEstimate() {
  try {
    const e = await api(`/api/projects/${proj.id}/estimate`);
    const pct = Math.min(100, (e.video_seconds / e.max_seconds) * 100);
    $("#meterFill").style.width = pct + "%";
    $("#meterFill").classList.toggle("over", e.over_limit);
    $("#estimate").classList.toggle("over", e.over_limit);
    $("#estimate").innerHTML = `Video length <b>${mmss(e.video_seconds)}</b> of max <b>${mmss(e.max_seconds)}</b>
      ${e.over_limit ? " — <b>probably too long: shorten the narration or remove slides (the exact length is checked when rendering)</b>" : ""}
      · estimated render time on this laptop <b>${mmss(e.render_seconds)}</b>
      <span class="muted">(voice ${mmss(e.tts_seconds)} + video ${mmss(e.encode_seconds)}, ${e.slides} slides, encoder: ${esc(e.encoder)})</span>`;
    e.per_slide.forEach((t, i) => { const el = document.querySelector(`[data-secs="${i}"]`); if (el) el.textContent = `≈ ${mmss(t)} on screen`; });
  } catch (err) { $("#estimate").textContent = err.message; }
}

// ---------- saving ----------
function scheduleSave() { clearTimeout(saveTimer); saveTimer = setTimeout(save, 700); }

async function save() {
  clearTimeout(saveTimer);
  const body = {};
  document.querySelectorAll("[data-field]").forEach((el) => { body[el.dataset.field] = el.value; });
  body.voice = proj.voice; body.music = { volume: +$("#musicVol").value };
  body.intro = $("#intro").value === "1";
  body.pip = { enabled: $("#pipEnabled").value === "1", position: $("#pipPosition").value,
    shape: $("#pipShape").value, size: $("#pipSize").value };
  body.slides = proj.slides.map((s) => ({ id: s.id, title: s.title, notes: s.notes, script: s.script }));
  proj = await api(`/api/projects/${proj.id}`, { method: "PUT", json: body });
  refreshEstimate();
}

// ---------- recorder (webcam on the laptop; on phones the camera opens via the file button) ----------
const rec = { stream: null, recorder: null, chunks: [], timer: null, onDone: null };
const canRecord = () => !!(navigator.mediaDevices && window.MediaRecorder);

async function openRecorder({ title, text, video, onDone }) {
  if (!canRecord()) {
    toast("Live recording needs the laptop browser (localhost). On a phone, use “Phone camera / file”.", true);
    return;
  }
  $("#recTitle").textContent = title;
  $("#prompter").textContent = text || "(No narration text yet — speak freely.)";
  $("#recPreview").classList.toggle("hidden", !video);
  try {
    rec.stream = await navigator.mediaDevices.getUserMedia(video
      ? { video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" }, audio: { echoCancellation: true, noiseSuppression: true } }
      : { audio: { echoCancellation: true, noiseSuppression: true } });
  } catch (e) { toast("Camera/microphone not available: " + e.message, true); return; }
  $("#recPreview").srcObject = video ? rec.stream : null;
  rec.onDone = onDone; rec.video = video;
  $("#recModal").classList.remove("hidden");
  $("#recStart").classList.remove("hidden"); $("#recStop").classList.add("hidden"); $("#recTimer").textContent = "";
}

function startRecording() {
  const types = rec.video ? ["video/webm;codecs=vp8,opus", "video/webm", "video/mp4"] : ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  const mimeType = types.find((t) => MediaRecorder.isTypeSupported(t)) || "";
  rec.chunks = [];
  rec.recorder = new MediaRecorder(rec.stream, mimeType ? { mimeType } : undefined);
  rec.recorder.ondataavailable = (e) => e.data.size && rec.chunks.push(e.data);
  rec.recorder.onstop = async () => {
    const type = rec.recorder.mimeType || (rec.video ? "video/webm" : "audio/webm");
    const ext = type.includes("mp4") ? "mp4" : "webm";
    const file = new File(rec.chunks, `recording.${ext}`, { type });
    closeRecorder();
    await rec.onDone(file);
  };
  rec.recorder.start(1000);
  const t0 = Date.now();
  rec.timer = setInterval(() => { $("#recTimer").textContent = "● " + mmss((Date.now() - t0) / 1000); }, 500);
  $("#recStart").classList.add("hidden"); $("#recStop").classList.remove("hidden");
}

function closeRecorder() {
  clearInterval(rec.timer);
  rec.stream?.getTracks().forEach((t) => t.stop());
  rec.stream = null;
  $("#recModal").classList.add("hidden");
}

async function sendClip(slide, file) {
  await save();
  toast("Processing your recording… (this can take a moment)");
  try { proj = await upload(`/api/projects/${proj.id}/slides/${slide.id}/clip`, [file], "file"); renderSlides(); refreshEstimate(); toast("Recording added to the slide"); }
  catch (err) { toast(err.message, true); }
}

async function sendSample(file) {
  if (!$("#consent").checked) { toast("Please tick the consent box first.", true); return; }
  toast("Saving your voice sample…");
  try { proj = await upload(`/api/projects/${proj.id}/voice_sample`, [file], "file", { consent: "yes" }); render(); toast("Voice sample saved"); }
  catch (err) { toast(err.message, true); }
}

// ---------- events ----------
function bind() {
  $("#projectSelect").onchange = (e) => openProject(e.target.value);
  $("#newProject").onclick = () => newProject();
  $("#phoneBtn").onclick = () => $("#phonePanel").classList.toggle("hidden");
  document.querySelectorAll("[data-field]").forEach((el) => (el.oninput = scheduleSave));

  $("#slides").addEventListener("input", (e) => {
    const k = e.target.dataset.k; if (!k) return;
    proj.slides[+e.target.closest(".slide").dataset.i][k] = e.target.value; scheduleSave();
  });
  $("#slides").addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-act]");
    const act = btn?.dataset.act; if (!act || act === "img" || act === "clipfile") return;
    const i = +btn.closest(".slide").dataset.i;
    const s = proj.slides;
    const lo = s[0]?.kind === "title" ? 1 : 0, hi = s.length - 1 - (s[s.length - 1]?.kind === "closing" ? 1 : 0);
    if (act === "up" && i > lo) [s[i - 1], s[i]] = [s[i], s[i - 1]];
    else if (act === "down" && i < hi) [s[i + 1], s[i]] = [s[i], s[i + 1]];
    else if (act === "del") { if (!confirm("Delete this slide?")) return; s.splice(i, 1); }
    else if (act === "say") return preview(s[i].script || s[i].title, btn);
    else if (act === "rec") {
      return openRecorder({ title: `Record slide ${i + 1}: ${s[i].title}`, text: s[i].script, video: true,
        onDone: (f) => sendClip(s[i], f) });
    } else if (act === "unclip") {
      if (!confirm("Remove your recording from this slide?")) return;
      proj = await api(`/api/projects/${proj.id}/slides/${s[i].id}/clip`, { method: "DELETE" });
      renderSlides(); refreshEstimate(); return;
    } else return;
    renderSlides(); await save();
  });
  $("#slides").addEventListener("change", async (e) => {
    const act = e.target.dataset.act;
    if (!["img", "clipfile"].includes(act) || !e.target.files.length) return;
    const s = proj.slides[+e.target.closest(".slide").dataset.i];
    if (act === "clipfile") return sendClip(s, e.target.files[0]);
    await save();
    proj = await upload(`/api/projects/${proj.id}/slides/${s.id}/image`, e.target.files, "file");
    renderSlides();
  });

  $("#shotFiles").onchange = async (e) => {
    if (!e.target.files.length) return;
    await save(); toast("Uploading screenshots…");
    try { proj = await upload(`/api/projects/${proj.id}/screens`, e.target.files); render(); toast("Screenshots added"); }
    catch (err) { toast(err.message, true); }
    e.target.value = "";
  };
  $("#pptxFile").onchange = async (e) => {
    if (!e.target.files.length) return;
    await save(); toast("Importing PowerPoint…");
    try { proj = await upload(`/api/projects/${proj.id}/import_pptx`, e.target.files, "file"); render(); toast(`Imported ${proj.imported} slides`); }
    catch (err) { toast(err.message, true); }
    e.target.value = "";
  };
  $("#addText").onclick = async () => {
    await save();
    const fd = new FormData(); fd.append("title", "New slide"); fd.append("notes", "");
    proj = await api(`/api/projects/${proj.id}/screens`, { method: "POST", body: fd }); render();
  };
  $("#logoFile").onchange = async (e) => {
    if (!e.target.files.length) return;
    await save(); proj = await upload(`/api/projects/${proj.id}/logo`, e.target.files, "file"); render(); toast("Logo updated");
  };
  $("#logoReset").onclick = async () => { proj = await api(`/api/projects/${proj.id}/logo`, { method: "DELETE" }); render(); };

  $("#draftScript").onclick = () => draft(false);
  $("#redraftScript").onclick = () => { if (confirm("Replace ALL narration with a new draft from your notes?")) draft(true); };

  $("#engine").onchange = (e) => { proj.voice.engine = e.target.value; proj.voice.lang = ""; renderVoice(); refreshEstimate(); };
  $("#lang").onchange = (e) => { proj.voice.lang = e.target.value; proj.voice.voice = ""; renderVoice(); };
  $("#gender").onchange = () => { proj.voice.voice = ""; renderVoice(); };
  $("#voice").onchange = (e) => { proj.voice.voice = e.target.value; scheduleSave(); };
  $("#speed").oninput = (e) => { proj.voice.speed = +e.target.value; $("#speedVal").textContent = (+e.target.value).toFixed(2) + "×"; scheduleSave(); };
  $("#previewVoice").onclick = (e) => preview(null, e.target);

  $("#recSample").onclick = () => {
    if (!$("#consent").checked) { toast("Please tick the consent box first.", true); return; }
    openRecorder({ title: "Record your voice sample (10–30 s)", video: false,
      text: $(".read-this i").textContent, onDone: sendSample });
  };
  $("#sampleFile").onchange = (e) => { if (e.target.files.length) sendSample(e.target.files[0]); e.target.value = ""; };
  $("#sampleClear").onclick = async () => { proj = await api(`/api/projects/${proj.id}/voice_sample`, { method: "POST" }); render(); };
  $("#recStart").onclick = startRecording;
  $("#recStop").onclick = () => rec.recorder?.stop();
  $("#recClose").onclick = () => { if (rec.recorder?.state === "recording") { rec.onDone = async () => {}; rec.recorder.stop(); } closeRecorder(); };

  ["#pipEnabled", "#pipPosition", "#pipShape", "#pipSize", "#intro"].forEach((id) => ($(id).onchange = save));
  $("#pipPhotoFile").onchange = async (e) => {
    if (!e.target.files.length) return;
    await save(); proj = await upload(`/api/projects/${proj.id}/pip_photo`, e.target.files, "file"); render(); toast("Photo added");
  };
  $("#pipPhotoClear").onclick = async () => { proj = await api(`/api/projects/${proj.id}/pip_photo`, { method: "POST" }); render(); };

  $("#musicFile").onchange = async (e) => {
    if (!e.target.files.length) return;
    await save(); proj = await upload(`/api/projects/${proj.id}/music`, e.target.files, "file"); render();
  };
  $("#musicClear").onclick = async () => { proj = await api(`/api/projects/${proj.id}/music`, { method: "POST" }); render(); };
  $("#musicVol").oninput = (e) => { $("#musicVolVal").textContent = Math.round(e.target.value * 100) + "%"; scheduleSave(); };

  $("#buildPptx").onclick = async (e) => {
    busy(e.target, true);
    try { await save(); const r = await api(`/api/projects/${proj.id}/pptx`, { method: "POST" }); showResult({ pptx: r.url }); toast("PowerPoint ready"); }
    catch (err) { toast(err.message, true); }
    busy(e.target, false);
  };
  $("#renderVideo").onclick = async () => {
    try { await save(); await api(`/api/projects/${proj.id}/render`, { method: "POST" }); checkJob(); }
    catch (err) { toast(err.message, true); }
  };
  $("#cancelRender").onclick = () => api(`/api/projects/${proj.id}/cancel`, { method: "POST" });
  $("#exPreset").innerHTML = Object.entries(sys.presets).map(([k, v]) => `<option value="${k}" ${k === "reels" ? "selected" : ""}>${esc(v)}</option>`).join("");
  $("#exportBtn").onclick = async () => {
    const from = $("#exFrom").value, to = $("#exTo").value || from;
    try {
      await api(`/api/projects/${proj.id}/export`, { method: "POST", json: { preset: $("#exPreset").value,
        slide_from: from ? +from : null, slide_to: to ? +to : null, burn_subs: $("#exSubs").value === "1" } });
      checkJob();
    } catch (err) { toast(err.message, true); }
  };
}

async function draft(overwrite) {
  await save();
  proj = await api(`/api/projects/${proj.id}/script`, { method: "POST", json: { overwrite } });
  render(); toast("Narration drafted — read it and edit anything you like");
}

async function preview(text, btn) {
  busy(btn, true);
  if (proj.voice.engine === "clone") toast("Loading your cloned voice… the first preview can take a minute.");
  try {
    await save();
    const r = await api(`/api/projects/${proj.id}/preview_voice`, { method: "POST", json: { text, ...proj.voice } });
    const a = $("#previewAudio"); a.src = r.url; a.classList.remove("hidden"); a.play();
  } catch (err) { toast(err.message, true); }
  busy(btn, false);
}

function showResult(r) {
  const v = Date.now();
  let html = "";
  if (r.video) html += `<video controls src="${r.video}?v=${v}"></video>`;
  html += `<div class="row wrap">`;
  if (r.pptx) html += `<a class="btn btn-primary" href="${r.pptx}?dl=1">⬇ PowerPoint (.pptx)</a>`;
  if (r.video) html += `<a class="btn btn-primary accent" href="${r.video}?dl=1">⬇ Video (.mp4)</a>`;
  if (r.srt) html += `<a class="btn btn-outline" href="${r.srt}?dl=1">⬇ Subtitles (.srt)</a>`;
  html += `<a class="btn btn-outline" href="/api/projects/${proj.id}/script.txt">⬇ Script (.txt)</a></div>`;
  if (r.seconds) html += `<p class="muted">Video length ${mmss(r.seconds)} · rendered in ${mmss(r.render_seconds)}</p>`;
  $("#results").innerHTML = html;
}

const STAGES = ["Drawing slides", "Voice-over", "Timeline", "Encoding video", "Final mix", "Done"];

async function checkJob() {
  clearTimeout(pollTimer);
  const pid = proj.id;
  const j = await api(`/api/projects/${pid}/job`);
  if (pid !== proj.id) return;
  const running = j.state === "running";
  $("#progress").classList.toggle("hidden", j.state === "idle");
  $("#renderVideo").disabled = running;
  $("#cancelRender").classList.toggle("hidden", !running);
  if (j.state !== "idle") {
    const si = Math.max(STAGES.indexOf(j.stage), 0);
    const pct = j.state === "done" ? 100 : Math.min(99, ((si + (j.fraction || 0)) / (STAGES.length - 1)) * 100);
    $("#barFill").style.width = pct + "%";
    $("#progressText").textContent = j.state === "error" ? "❌ " + j.error
      : j.state === "cancelled" ? "Cancelled" : `${j.stage}: ${j.message}  ·  ${mmss(j.elapsed)} elapsed`;
  }
  if (j.state === "done" && j.result) showResult(j.result);
  const x = j.export || { state: "idle" };
  $("#exportBtn").disabled = x.state === "running";
  $("#exProgress").textContent = x.state === "running" ? `Exporting… ${x.message} · ${mmss(x.elapsed)}`
    : x.state === "error" ? "❌ " + x.error : (x.result?.note || "");
  if (x.state === "done" && x.result) {
    const vertical = x.result.file.includes("reels");
    $("#exResults").innerHTML = `<video controls class="${vertical ? "vertical" : ""}" src="${x.result.file}?v=${Date.now()}"></video>
      <div><a class="btn btn-primary" href="${x.result.file}?dl=1">⬇ ${esc(x.result.label)} (${mmss(x.result.seconds)})</a></div>`;
  }
  if (running || x.state === "running") pollTimer = setTimeout(checkJob, 1500);
}

(async function init() {
  try {
    sys = await api("/api/system");
    bind();
    $("#phoneUrl").textContent = sys.phone_url; $("#phoneUrl").href = sys.phone_url;
    $("#qr").innerHTML = sys.qr_svg;
    await loadProjects();
  } catch (err) { toast("Cannot reach the app: " + err.message, true); }
})();
