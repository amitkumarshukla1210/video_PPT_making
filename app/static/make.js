// Make a video: source -> script scene by scene -> voice -> video type. Plain JavaScript, no build step.
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
let sys = null, proj = null, saveTimer = null;

function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast" + (err ? " err" : "");
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.add("hidden"), err ? 9000 : 3000);
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
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const mmss = (s) => { s = Math.round(s || 0); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------- steps ----------
function show(step) {
  for (let i = 1; i <= 4; i++) $(`#step${i}`).classList.toggle("hidden", i !== step);
  $$("#stepper li").forEach((li) => {
    const n = +li.dataset.step;
    li.classList.toggle("current", n === step);
    li.classList.toggle("done", n < step);
  });
  if (proj) history.replaceState(null, "", `/make?p=${proj.id}&step=${step}`);
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (step === 2) renderScenes();
  if (step === 3) renderVoice();
  if (step === 4) refreshEstimate();
}

// Polls a background job; key "" = render/make video, "ai" = source / script / pictures.
async function waitJob(key, box) {
  const bar = box.querySelector(".bar > div"), text = box.querySelector("p");
  box.classList.remove("hidden");
  for (;;) {
    const all = await api(`/api/projects/${proj.id}/job`);
    const j = key ? all[key] : all;
    if (!j || j.state === "idle") { await sleep(800); continue; }
    bar.style.width = (j.state === "done" ? 100 : Math.max(3, Math.min(99, (j.fraction || 0) * 100))) + "%";
    text.textContent = j.state === "running" ? `${j.stage}: ${j.message || "working…"} · ${mmss(j.elapsed)}` : "";
    if (j.state === "done") { box.classList.add("hidden"); return j.result; }
    if (j.state === "error" || j.state === "cancelled") { box.classList.add("hidden"); throw new Error(j.error || "Stopped"); }
    await sleep(1200);
  }
}

// ---------- 1 · source ----------
const HINTS = {
  pptx: [".pptx", "Your PowerPoint (.pptx). Each slide becomes a scene; speaker notes are used for the script."],
  pictures: ["image/*", "Pictures in the order you want them (sorted by file name: 01_..., 02_...)."],
  document: [".pdf,.docx,.txt,.md,.html,.htm,.pptx", "PDF (each page becomes a scene with its picture), Word .docx, text, Markdown or a saved web page."],
};
function kind() { return $("input[name=kind]:checked").value; }
function onKind() {
  const k = kind();
  $("#srcFiles").classList.toggle("hidden", !HINTS[k]);
  $("#srcUrl").classList.toggle("hidden", k !== "url");
  $("#srcText").classList.toggle("hidden", !["text", "idea"].includes(k));
  if (HINTS[k]) { $("#files").accept = HINTS[k][0]; $("#filesHint").textContent = HINTS[k][1]; $("#files").value = ""; }
  $("#textLabel").textContent = k === "idea" ? "Your idea (a few sentences)" : "Paste the text";
  $("#text").placeholder = k === "idea"
    ? "e.g. How our design-to-cost programme cut the BOM cost of our pump by 12% without changing performance"
    : "Paste a report, an email, meeting notes…";
  $("#scenesBox").classList.toggle("hidden", ["pptx", "pictures"].includes(k));
  $("#pics").checked = ["url", "text", "idea"].includes(k) && sys?.ai?.images?.available;
}

async function start() {
  const k = kind();
  const files = $("#files").files;
  if (HINTS[k] && !files.length) return toast("Choose your file(s) first", true);
  if (k === "url" && !$("#url").value.trim()) return toast("Paste the web link first", true);
  if (["text", "idea"].includes(k) && !$("#text").value.trim()) return toast("Write or paste the text first", true);
  const name = $("#name").value.trim() || (files[0]?.name.replace(/\.[^.]+$/, "")) ||
    ($("#url").value.trim() ? new URL($("#url").value.trim()).hostname : "") || "New video";
  $("#go1").disabled = true;
  try {
    $("#status1").textContent = "Creating the project…";
    proj = await api("/api/projects", { method: "POST", json: { name } });
    const fd = new FormData();
    fd.append("kind", k);
    for (const f of files) if (HINTS[k]) fd.append("files", f, f.name);
    fd.append("url", $("#url").value.trim());
    fd.append("text", $("#text").value);
    fd.append("scenes", $("#scenes").value);
    fd.append("language", $("#language").value);
    fd.append("video_type", $("#vtype1").value);
    fd.append("ai", $("#useAi").checked ? "1" : "0");
    fd.append("pictures", $("#pics").checked ? "1" : "0");
    $("#status1").textContent = files.length ? "Uploading…" : "";
    await api(`/api/projects/${proj.id}/source`, { method: "POST", body: fd });
    $("#status1").textContent = "";
    const r = await waitJob("ai", $("#prog1"));
    proj = await api(`/api/projects/${proj.id}`);
    $(`input[name=vtype][value=${$("#vtype1").value}]`).checked = true;
    toast(`${r.slides} scenes ready${r.ai ? " — script written by the local AI" : " — first-draft script written"}. Check it below.`);
    show(2);
  } catch (e) {
    $("#status1").textContent = "";
    toast(e.message, true);
    if (proj) { await api(`/api/projects/${proj.id}`, { method: "DELETE" }).catch(() => {}); proj = null; }
  } finally { $("#go1").disabled = false; }
}

// ---------- 2 · script ----------
const KIND_LABEL = { title: "Opening", closing: "Closing", content: "Scene" };
function seconds(text) { return (text.trim().split(/\s+/).filter(Boolean).length / 2.5) || 0; }
function renderScenes() {
  let n = 0, total = 0;
  $("#sceneList").innerHTML = proj.slides.map((s, i) => {
    if (s.kind === "content") n++;
    total += seconds(s.script || "") + 1.5;
    const pic = s.image ? `<img src="/files/${proj.id}/${esc(s.image)}" alt="">` : `<span class="no-pic">${s.kind === "content" ? "no picture" : KIND_LABEL[s.kind]}</span>`;
    return `<li class="scene" data-i="${i}">
      <div class="scene-pic">${pic}</div>
      <div class="scene-body">
        <div class="scene-top"><span class="badge">${s.kind === "content" ? "Scene " + n : KIND_LABEL[s.kind]}</span>
          <span class="muted secs">${Math.round(seconds(s.script || ""))} s</span>
          ${s.kind === "content" ? `<button class="btn btn-outline small" data-del="${i}" title="Remove this scene">✕</button>` : ""}</div>
        <input data-k="title" value="${esc(s.title)}" aria-label="On-screen title">
        <textarea data-k="script" rows="3" aria-label="Narration">${esc(s.script)}</textarea>
      </div></li>`;
  }).join("");
  $("#scriptStats").textContent = `${n} scenes · about ${mmss(total)}`;
  $("#openPres").href = `/?p=${proj.id}`;
}
function scheduleSave() { clearTimeout(saveTimer); saveTimer = setTimeout(saveScript, 700); }
async function saveScript() {
  clearTimeout(saveTimer);
  const slides = proj.slides.map((s) => ({ id: s.id, title: s.title, script: s.script }));
  proj = await api(`/api/projects/${proj.id}`, { method: "PUT", json: { slides } });
}
async function aiJob(path, body, label) {
  $("#status2").textContent = label;
  try {
    await saveScript();
    await api(`/api/projects/${proj.id}/${path}`, { method: "POST", json: body });
    await waitJob("ai", $("#prog2"));
    proj = await api(`/api/projects/${proj.id}`);
    renderScenes();
    toast("Done");
  } catch (e) { toast(e.message, true); } finally { $("#status2").textContent = ""; }
}

// ---------- 3 · voice ----------
function renderVoice() {
  const engines = sys.engines;
  const eSel = $("#engine");
  eSel.innerHTML = engines.map((e) => `<option value="${e.name}" ${e.available ? "" : "disabled"}>${esc(e.label)}${e.available ? "" : " — not installed"}</option>`).join("");
  let engine = proj.voice.engine;
  if (!engines.find((e) => e.name === engine && e.available)) engine = sys.default_engine || "";
  eSel.value = engine;
  fillVoices();
}
function fillVoices(keep = true) {
  const eng = sys.engines.find((e) => e.name === $("#engine").value);
  const voices = eng ? eng.voices : [];
  const langs = [...new Set(voices.map((v) => v.lang))];
  const want = keep ? proj.voice.lang : $("#vlang").value;
  $("#vlang").innerHTML = langs.map((l) => `<option value="${esc(l)}">${esc(sys.languages?.[l] || l)}</option>`).join("");
  const pl = (proj.language || "en").slice(0, 2);
  $("#vlang").value = langs.includes(want) ? want : (langs.find((l) => l.startsWith(pl)) || langs[0] || "");
  const vs = voices.filter((v) => v.lang === $("#vlang").value);
  $("#voice").innerHTML = vs.map((v) => `<option value="${esc(v.id)}">${esc(v.label)}${v.gender ? " · " + v.gender : ""}</option>`).join("");
  $("#voice").value = vs.some((v) => v.id === proj.voice.voice) ? proj.voice.voice : (vs[0]?.id || "");
  $("#speed").value = proj.voice.speed || 1;
  $("#speedOut").textContent = (+$("#speed").value).toFixed(2);
  $("#engineNote").textContent = !eng ? "No voice engine installed yet — run install_once.bat."
    : eng.needs_sample && !proj.voice_sample ? "Your cloned voice needs a 10–30 s recording first: open “Fine-tune in Presentation” › Voice clone, record once, then come back."
    : (eng.info || "");
}
async function saveVoice() {
  proj = await api(`/api/projects/${proj.id}`, { method: "PUT", json: { voice: {
    engine: $("#engine").value, lang: $("#vlang").value, voice: $("#voice").value, speed: +$("#speed").value } } });
}

// ---------- 4 · video ----------
async function refreshEstimate() {
  try {
    const e = await api(`/api/projects/${proj.id}/estimate`);
    $("#estimate").textContent = `Video length about ${mmss(e.video_seconds)} · making it takes about ${mmss(e.render_seconds)} on this laptop.`;
  } catch (e) { $("#estimate").textContent = ""; }
}
async function makeVideo() {
  $("#go4").disabled = true;
  $("#cancel4").classList.remove("hidden");
  $("#result").classList.add("hidden");
  try {
    const type = $("input[name=vtype]:checked").value;
    await api(`/api/projects/${proj.id}/make_video`, { method: "POST",
      json: { type, captions: $("#captions").checked, music: $("#music").value } });
    const r = await waitJob("", $("#prog4"));
    const vertical = type === "reel";
    $("#result").innerHTML = `<h3>✅ Your video is ready — ${esc(r.label)} · ${mmss(r.seconds)}</h3>
      <video controls class="${vertical ? "vertical" : type === "square" ? "square" : ""}" src="${r.video}?v=${Date.now()}"></video>
      <div class="row wrap">
        <a class="btn btn-primary" href="${r.video}?dl=1">⬇ Download the video</a>
        <a class="btn btn-outline" href="${r.pptx}?dl=1">⬇ PowerPoint</a>
        <a class="btn btn-outline" href="${r.srt}?dl=1">⬇ Subtitles (.srt)</a>
        <a class="btn btn-outline" href="/projects">▦ My projects</a>
      </div>
      <p class="muted">Made in ${mmss(r.render_seconds)}. Want another format? Choose another video type above and click “Make the video” again — every version is kept in My projects.</p>`;
    $("#result").classList.remove("hidden");
  } catch (e) { toast(e.message, true); } finally {
    $("#go4").disabled = false; $("#cancel4").classList.add("hidden");
  }
}

// ---------- start ----------
async function init() {
  sys = await api("/api/system");
  const langs = sys.languages || { en: "English" };
  $("#language").innerHTML = Object.entries(langs).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  $("#language").value = "en";
  const ai = sys.ai || {};
  if (!ai.llm?.available) { $("#useAi").checked = false; $("#useAi").disabled = true; $("#aiNote").textContent = `(${ai.llm?.info || "not installed"} — a simple first draft is written instead)`; }
  else $("#aiNote").textContent = `(${ai.llm.model})`;
  if (!ai.images?.available) { $("#pics").disabled = true; $("#picNote").textContent = "(not installed: install_once.bat images)"; }
  for (const m of ["corporate", "calm", "cinematic", "documentary", "tech"]) $("#music").insertAdjacentHTML("beforeend", `<option value="${m}">Music library · ${m}</option>`);

  $$("input[name=kind]").forEach((r) => (r.onchange = onKind));
  onKind();
  $("#go1").onclick = start;
  $("#sceneList").addEventListener("input", (e) => {
    const li = e.target.closest(".scene"); if (!li || !e.target.dataset.k) return;
    proj.slides[+li.dataset.i][e.target.dataset.k] = e.target.value;
    if (e.target.dataset.k === "script") li.querySelector(".secs").textContent = `${Math.round(seconds(e.target.value))} s`;
    scheduleSave();
  });
  $("#sceneList").addEventListener("click", async (e) => {
    const i = e.target.dataset.del; if (i === undefined) return;
    if (!confirm("Remove this scene?")) return;
    proj.slides.splice(+i, 1);
    await saveScript(); renderScenes();
  });
  $("#rewrite").onclick = () => aiJob("ai_script", { overwrite: true, language: proj.language }, "The local AI is rewriting the narration…");
  $("#morePics").onclick = () => aiJob("pictures", {}, "Creating pictures…");
  if (!ai.llm?.available) $("#rewrite").disabled = true;
  if (!ai.images?.available) $("#morePics").disabled = true;
  $("#go2").onclick = async () => { await saveScript(); show(3); };
  $("#engine").onchange = () => { fillVoices(false); saveVoice(); };
  $("#vlang").onchange = () => { fillVoices(false); saveVoice(); };
  $("#voice").onchange = saveVoice;
  $("#speed").oninput = () => { $("#speedOut").textContent = (+$("#speed").value).toFixed(2); };
  $("#speed").onchange = saveVoice;
  $("#hear").onclick = async () => {
    $("#hear").disabled = true;
    try {
      await saveVoice();
      const first = proj.slides.find((s) => s.kind === "content" && s.script) || proj.slides[0];
      const r = await api(`/api/projects/${proj.id}/preview_voice`, { method: "POST", json: { text: first?.script } });
      $("#player").src = r.url; $("#player").classList.remove("hidden"); $("#player").play();
    } catch (e) { toast(e.message, true); } finally { $("#hear").disabled = false; }
  };
  $("#go3").onclick = async () => { await saveVoice(); show(4); };
  $("#go4").onclick = makeVideo;
  $("#cancel4").onclick = () => api(`/api/projects/${proj.id}/cancel`, { method: "POST" });
  $$("[data-back]").forEach((b) => (b.onclick = () => show(+b.dataset.back)));
  $$("#stepper li").forEach((li) => (li.onclick = () => { if (proj && +li.dataset.step > 1) show(+li.dataset.step); }));

  // continue an existing project: /make?p=<id>&step=2
  const q = new URLSearchParams(location.search);
  if (q.get("p")) {
    try {
      proj = await api(`/api/projects/${q.get("p")}`);
      if (proj.video_type) $(`input[name=vtype][value=${proj.video_type}]`).checked = true;
      show(Math.min(4, Math.max(2, +q.get("step") || 2)));
    } catch (e) { toast("That project was not found", true); }
  }
  document.body.dataset.ready = "true";
}
init().catch((e) => toast(e.message, true));
