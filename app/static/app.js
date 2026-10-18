// Design to Cost Studio — plain JavaScript, no build step.
const $ = (s) => document.querySelector(s);
let sys = null, proj = null, saveTimer = null, pollTimer = null;

const LANG_NAMES = { "en-us": "English (US)", "en-gb": "English (UK)", hi: "Hindi", es: "Spanish", "fr-fr": "French",
  fr: "French", it: "Italian", "pt-br": "Portuguese (BR)", de: "German", ar: "Arabic", ru: "Russian", zh: "Chinese",
  ja: "Japanese", ta: "Tamil", te: "Telugu", mr: "Marathi", bn: "Bengali", gu: "Gujarati" };

function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast" + (err ? " err" : "");
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.add("hidden"), err ? 7000 : 2500);
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

async function upload(path, files, field = "files") {
  const fd = new FormData();
  for (const f of files) fd.append(field, f);
  return api(path, { method: "POST", body: fd });
}

function busy(btn, on) { if (btn) btn.disabled = on; }

// ---------- projects ----------
async function loadProjects(selectId) {
  const list = await api("/api/projects");
  const sel = $("#projectSelect");
  sel.innerHTML = list.map((p) => `<option value="${p.id}">${esc(p.name)} (${p.slides})</option>`).join("");
  if (!list.length) { await newProject("Design to Cost"); return; }
  const id = selectId || localStorage.getItem("dtc.project") || list[0].id;
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
  localStorage.setItem("dtc.project", id);
  $("#app").classList.remove("hidden");
  render();
  checkJob();
}

function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

// ---------- rendering ----------
function render() {
  document.querySelectorAll("[data-field]").forEach((el) => { el.value = proj[el.dataset.field] || ""; });
  $("#logoImg").src = proj.logo ? `/files/${proj.id}/${proj.logo}` : "/static/logo_placeholder.png";
  $("#scriptTxt").href = `/api/projects/${proj.id}/script.txt`;
  $("#musicName").textContent = proj.music.file ? "✔ " + proj.music.file.split("_").slice(2).join("_") : "No music";
  $("#musicVol").value = proj.music.volume; $("#musicVolVal").textContent = Math.round(proj.music.volume * 100) + "%";
  renderSlides(); renderVoice(); refreshEstimate();
}

function renderSlides() {
  const box = $("#slides");
  $("#slideCount").textContent = `${proj.slides.length} slides`;
  box.innerHTML = proj.slides.map((s, i) => {
    const cover = s.kind !== "content";
    const thumb = s.image ? `<img src="/files/${proj.id}/${s.image}" loading="lazy">`
      : cover ? `${s.kind === "title" ? "Title slide" : "Closing slide"}<br>(navy, logo)` : "Text slide<br>(no screenshot)";
    return `<div class="slide ${cover ? "cover" : ""}" data-i="${i}">
      <div><div class="thumb">${thumb}</div>
        <div class="slide-tools" style="margin-top:6px">
          ${cover ? "" : `<button class="icon" data-act="up" title="Move up">↑</button>
          <button class="icon" data-act="down" title="Move down">↓</button>
          <label class="icon" title="Replace screenshot">🖼<input type="file" accept="image/*" data-act="img" hidden></label>
          <button class="icon" data-act="del" title="Delete slide">✕</button>`}
          <button class="icon" data-act="say" title="Hear this slide">▶</button>
        </div></div>
      <div class="slide-fields">
        <div class="slide-head"><span class="num">${i + 1}</span>
          <input data-k="title" value="${esc(s.title)}" placeholder="Slide title"></div>
        <label>${cover ? "Subtitle" : "Notes for this screen (one line = one bullet)"}
          <textarea data-k="notes" rows="${cover ? 1 : 3}">${esc(s.notes)}</textarea></label>
        <label>Narration (what the voice will say — edit freely)
          <textarea class="script" data-k="script" rows="4">${esc(s.script)}</textarea></label>
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
  let lang = langs.includes(proj.voice.lang) ? proj.voice.lang : langs[0];
  lSel.value = lang || "";
  const vs = voices.filter((v) => v.lang === lang);
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
    $("#estimate").innerHTML = `Estimated video length <b>${mmss(e.video_seconds)}</b> · estimated render time on this laptop
      <b>${mmss(e.render_seconds)}</b> <span class="muted">(voice ${mmss(e.tts_seconds)} + video ${mmss(e.encode_seconds)}, ${e.slides} slides, encoder: ${esc(e.encoder)})</span>`;
  } catch (err) { $("#estimate").textContent = err.message; }
}

function mmss(s) { s = Math.round(s || 0); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; }

// ---------- saving ----------
function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(save, 700);
}

async function save() {
  clearTimeout(saveTimer);
  const body = {};
  document.querySelectorAll("[data-field]").forEach((el) => { body[el.dataset.field] = el.value; });
  body.voice = proj.voice; body.music = { volume: +$("#musicVol").value };
  body.slides = proj.slides.map((s) => ({ id: s.id, title: s.title, notes: s.notes, script: s.script }));
  proj = await api(`/api/projects/${proj.id}`, { method: "PUT", json: body });
  refreshEstimate();
}

// ---------- events ----------
function bind() {
  $("#projectSelect").onchange = (e) => openProject(e.target.value);
  $("#newProject").onclick = () => newProject();
  $("#phoneBtn").onclick = () => $("#phonePanel").classList.toggle("hidden");
  document.querySelectorAll("[data-field]").forEach((el) => (el.oninput = scheduleSave));

  $("#slides").addEventListener("input", (e) => {
    const k = e.target.dataset.k; if (!k) return;
    const i = +e.target.closest(".slide").dataset.i;
    proj.slides[i][k] = e.target.value; scheduleSave();
  });
  $("#slides").addEventListener("click", async (e) => {
    const act = e.target.dataset.act; if (!act || act === "img") return;
    const i = +e.target.closest(".slide").dataset.i;
    const s = proj.slides;
    const lo = s[0]?.kind === "title" ? 1 : 0, hi = s.length - 1 - (s[s.length - 1]?.kind === "closing" ? 1 : 0);
    if (act === "up" && i > lo) [s[i - 1], s[i]] = [s[i], s[i - 1]];
    else if (act === "down" && i < hi) [s[i + 1], s[i]] = [s[i], s[i + 1]];
    else if (act === "del") { if (!confirm("Delete this slide?")) return; s.splice(i, 1); }
    else if (act === "say") { return preview(s[i].script || s[i].title, e.target); }
    else return;
    renderSlides(); await save();
  });
  $("#slides").addEventListener("change", async (e) => {
    if (e.target.dataset.act !== "img" || !e.target.files.length) return;
    const s = proj.slides[+e.target.closest(".slide").dataset.i];
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
    await save();
    proj = await upload(`/api/projects/${proj.id}/logo`, e.target.files, "file"); render(); toast("Logo updated");
  };
  $("#logoReset").onclick = async () => { proj = await api(`/api/projects/${proj.id}/logo`, { method: "DELETE" }); render(); };

  $("#draftScript").onclick = () => draft(false);
  $("#redraftScript").onclick = () => { if (confirm("Replace ALL narration with a new draft from your notes?")) draft(true); };

  $("#engine").onchange = (e) => { proj.voice.engine = e.target.value; proj.voice.lang = ""; renderVoice(); };
  $("#lang").onchange = (e) => { proj.voice.lang = e.target.value; proj.voice.voice = ""; renderVoice(); };
  $("#voice").onchange = (e) => { proj.voice.voice = e.target.value; scheduleSave(); };
  $("#speed").oninput = (e) => { proj.voice.speed = +e.target.value; $("#speedVal").textContent = (+e.target.value).toFixed(2) + "×"; scheduleSave(); };
  $("#previewVoice").onclick = (e) => preview(null, e.target);

  $("#musicFile").onchange = async (e) => {
    if (!e.target.files.length) return;
    await save(); proj = await upload(`/api/projects/${proj.id}/music`, e.target.files, "file"); render();
  };
  $("#musicClear").onclick = async () => { proj = await api(`/api/projects/${proj.id}/music`, { method: "POST" }); render(); };
  $("#musicVol").oninput = (e) => { $("#musicVolVal").textContent = Math.round(e.target.value * 100) + "%"; scheduleSave(); };

  $("#buildPptx").onclick = async (e) => {
    busy(e.target, true);
    try {
      await save();
      const r = await api(`/api/projects/${proj.id}/pptx`, { method: "POST" });
      showResult({ pptx: r.url }); toast("PowerPoint ready");
    } catch (err) { toast(err.message, true); }
    busy(e.target, false);
  };
  $("#renderVideo").onclick = async () => {
    try { await save(); await api(`/api/projects/${proj.id}/render`, { method: "POST" }); checkJob(); }
    catch (err) { toast(err.message, true); }
  };
  $("#cancelRender").onclick = () => api(`/api/projects/${proj.id}/cancel`, { method: "POST" });
}

async function draft(overwrite) {
  await save();
  proj = await api(`/api/projects/${proj.id}/script`, { method: "POST", json: { overwrite } });
  render(); toast("Narration drafted — read it and edit anything you like");
}

async function preview(text, btn) {
  busy(btn, true);
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
  if (r.pptx) html += `<a class="btn" href="${r.pptx}?dl=1">⬇ PowerPoint (.pptx)</a>`;
  if (r.video) html += `<a class="btn orange" href="${r.video}?dl=1">⬇ Video (.mp4)</a>`;
  if (r.srt) html += `<a class="btn ghost" href="${r.srt}?dl=1">⬇ Subtitles (.srt)</a>`;
  html += `<a class="btn ghost" href="/api/projects/${proj.id}/script.txt">⬇ Script (.txt)</a></div>`;
  if (r.seconds) html += `<p class="muted">Video length ${mmss(r.seconds)} · rendered in ${mmss(r.render_seconds)}</p>`;
  $("#results").innerHTML = html;
}

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
    const stages = ["Drawing slides", "Voice-over", "Timeline", "Encoding video", "Final mix", "Done"];
    const si = Math.max(stages.indexOf(j.stage), 0);
    const pct = j.state === "done" ? 100 : Math.min(99, ((si + (j.fraction || 0)) / (stages.length - 1)) * 100);
    $("#barFill").style.width = pct + "%";
    $("#progressText").textContent = j.state === "error" ? "❌ " + j.error
      : j.state === "cancelled" ? "Cancelled" : `${j.stage}: ${j.message}  ·  ${mmss(j.elapsed)} elapsed`;
  }
  if (j.state === "done" && j.result) showResult(j.result);
  if (running) pollTimer = setTimeout(checkJob, 1500);
}

(async function init() {
  bind();
  try {
    sys = await api("/api/system");
    $("#phoneUrl").textContent = sys.phone_url; $("#phoneUrl").href = sys.phone_url;
    $("#qr").innerHTML = sys.qr_svg;
    await loadProjects();
  } catch (err) { toast("Cannot reach the app: " + err.message, true); }
})();
