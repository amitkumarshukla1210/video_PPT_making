// Inspirations: 100 example videos in 9 categories. "Use this example" makes a project and opens Make a video.
const $ = (s) => document.querySelector(s);
let cat = null, data = null, chosen = null;
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast" + (err ? " err" : "");
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.add("hidden"), err ? 9000 : 3000);
}
async function api(path, opts = {}) {
  if (opts.json !== undefined) { opts.body = JSON.stringify(opts.json); opts.headers = { "Content-Type": "application/json" }; delete opts.json; }
  const r = await fetch(path, opts);
  const d = r.headers.get("content-type")?.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error(d.error || d || r.statusText);
  return d;
}
const LOOK = { corporate: "Corporate", cinematic: "Cinematic", bold: "Bold", warm: "Warm" };

function renderChips() {
  const all = { id: null, label: "All examples", icon: "▦", count: data.examples.length };
  $("#chips").innerHTML = [all, ...data.categories].map((c) =>
    `<button class="chip${cat === c.id ? " on" : ""}" role="tab" aria-selected="${cat === c.id}" data-cat="${c.id ?? ""}">
      <span aria-hidden="true">${c.icon}</span> ${esc(c.label)} <small>${c.count}</small></button>`).join("");
}
function renderGrid() {
  const list = data.examples.filter((e) => !cat || e.category === cat);
  $("#grid").innerHTML = list.map((e) => `
    <article class="ex" data-id="${e.id}">
      <div class="ex-thumb" data-preview="${e.id}" title="Play preview"><img src="${e.thumb}" alt="" loading="lazy">
        <span class="ex-play" aria-hidden="true">▶</span><span class="ex-format">${e.format}</span></div>
      <div class="ex-body">
        <div class="ex-cat">${e.icon} ${esc(e.category_label)}</div>
        <h3>${esc(e.name)}</h3>
        <p>${esc(e.blurb)}</p>
        <div class="ex-tags">${e.kind === "preset" ? "<span>⚡ your photo + effect</span>" : `<span>${e.scenes} scenes</span>`}<span>${LOOK[e.look]} look</span><span>♪ ${esc(e.music)}</span>${e.kind === "preset" ? "" : e.voice ? "<span>🎙 voice-over</span>" : "<span>music only</span>"}</div>
        <div class="ex-actions"><button class="btn btn-outline small" data-preview="${e.id}">▶ Preview</button>
        <button class="btn btn-primary small" data-use="${e.id}">${e.kind === "preset" ? "Use with my photo →" : "Use this example →"}</button></div>
      </div>
    </article>`).join("");
}
function stopVideo() {
  const v = $("#useVideo");
  v.pause(); v.removeAttribute("src"); v.load();
}
function play(e) {
  const v = $("#useVideo");
  $("#useStatus").textContent = "Making the preview… the first time takes about 10–20 seconds, then it is instant.";
  v.src = e.preview;
  v.onplaying = () => { $("#useStatus").textContent = "Preview · about 10 s of the opening and first scenes, with the music"; };
  v.onerror = () => { $("#useStatus").textContent = "The preview could not be made. You can still use the example."; };
  v.play().catch(() => {});
}
function open(e, autoplay = false) {
  chosen = e;
  $("#useCat").textContent = `${e.icon} ${e.category_label} · ${e.format}`;
  $("#useTitle").textContent = e.name;
  $("#useBlurb").textContent = e.blurb;
  stopVideo();
  $("#useVideo").poster = e.thumb;
  $("#useStatus").textContent = "Press ▶ to watch a short preview.";
  $("#useVideo").onplay = () => { if (!$("#useVideo").getAttribute("src")) play(e); };
  $("#useName").value = e.name;
  $("#useTopic").value = "";
  $("#useNote").textContent = data.ai
    ? "With a topic, the local AI rewrites the example for it (about 1 minute). Leave it empty to use the example as it is."
    : "The local AI is not running: the example opens as it is and you change the words in step 2.";
  $("#useTopic").disabled = !data.ai;
  const preset = e.kind === "preset";
  for (const id of ["#useName", "#useTopic", "#useLang", "#useNote"]) {
    $(id).classList.toggle("hidden", preset);
    document.querySelector(`label[for=${id.slice(1)}]`)?.classList.toggle("hidden", preset);
  }
  $("#useGo").textContent = preset ? "Use with my photo →" : "Use this example →";
  if (preset) $("#useNote").textContent = "";
  $("#useBox").classList.remove("hidden");
  if (autoplay) play(e); else $("#useName").focus();
}
async function use() {
  if (chosen.kind === "preset") { location.href = `/tools/video?preset=${chosen.id}`; return; }
  $("#useGo").disabled = true;
  try {
    const r = await api(`/api/inspirations/${chosen.id}/use`, { method: "POST",
      json: { name: $("#useName").value, topic: $("#useTopic").value, language: $("#useLang").value } });
    if (r.note) toast(r.note);
    if (r.job) {
      const box = $("#useProg"); box.classList.remove("hidden");
      for (;;) {
        const j = (await api(`/api/projects/${r.project}/job`)).ai;
        box.querySelector(".bar > div").style.width = Math.max(5, (j.fraction || 0) * 100) + "%";
        box.querySelector("p").textContent = j.message || "The local AI is writing…";
        if (j.state === "done") break;
        if (j.state === "error") { toast(`${j.error} — the example was kept as it is.`, true); break; }
        await sleep(1200);
      }
    }
    location.href = `/make?p=${r.project}&step=2`;
  } catch (e) { toast(e.message, true); $("#useGo").disabled = false; }
}
async function init() {
  data = await api("/api/inspirations");
  cat = new URLSearchParams(location.search).get("cat");
  renderChips(); renderGrid();
  $("#chips").onclick = (e) => {
    const b = e.target.closest("[data-cat]"); if (!b) return;
    cat = b.dataset.cat || null; renderChips(); renderGrid();
    history.replaceState(null, "", cat ? `?cat=${cat}` : "/inspirations");
  };
  $("#grid").onclick = (e) => {
    const pv = e.target.closest("[data-preview]");
    if (pv) return open(data.examples.find((x) => x.id === pv.dataset.preview), true);
    const b = e.target.closest("[data-use]");
    if (b) open(data.examples.find((x) => x.id === b.dataset.use));
  };
  const close = () => { stopVideo(); $("#useBox").classList.add("hidden"); };
  $("#useCancel").onclick = close;
  $("#useBox").onclick = (e) => { if (e.target.id === "useBox") close(); };
  $("#useGo").onclick = use;
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  document.body.dataset.ready = "true";
}
init().catch((e) => toast(e.message, true));
