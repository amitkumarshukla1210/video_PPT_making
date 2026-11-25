// Inspirations: 32 example videos in 8 categories. "Use this example" makes a project and opens Make a video.
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
      <div class="ex-thumb"><img src="${e.thumb}" alt="" loading="lazy"><span class="ex-format">${e.format}</span></div>
      <div class="ex-body">
        <div class="ex-cat">${e.icon} ${esc(e.category_label)}</div>
        <h3>${esc(e.name)}</h3>
        <p>${esc(e.blurb)}</p>
        <div class="ex-tags"><span>${e.scenes} scenes</span><span>${LOOK[e.look]} look</span><span>♪ ${esc(e.music)}</span>${e.voice ? "<span>🎙 voice-over</span>" : "<span>music only</span>"}</div>
        <button class="btn btn-primary small" data-use="${e.id}">Use this example →</button>
      </div>
    </article>`).join("");
}
function open(e) {
  chosen = e;
  $("#useCat").textContent = `${e.icon} ${e.category_label} · ${e.format}`;
  $("#useTitle").textContent = e.name;
  $("#useBlurb").textContent = e.blurb;
  $("#useThumb").src = e.thumb;
  $("#useName").value = e.name;
  $("#useTopic").value = "";
  $("#useNote").textContent = data.ai
    ? "With a topic, the local AI rewrites the example for it (about 1 minute). Leave it empty to use the example as it is."
    : "The local AI is not running: the example opens as it is and you change the words in step 2.";
  $("#useTopic").disabled = !data.ai;
  $("#useBox").classList.remove("hidden");
  $("#useName").focus();
}
async function use() {
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
    const b = e.target.closest("[data-use]") || e.target.closest(".ex-thumb")?.parentElement.querySelector("[data-use]");
    if (b) open(data.examples.find((x) => x.id === b.dataset.use));
  };
  $("#useCancel").onclick = () => $("#useBox").classList.add("hidden");
  $("#useGo").onclick = use;
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("#useBox").classList.add("hidden"); });
  document.body.dataset.ready = "true";
}
init().catch((e) => toast(e.message, true));
