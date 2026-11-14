// My projects: every project on this laptop with its videos and files.
const $ = (s) => document.querySelector(s);
let all = [];
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast" + (err ? " err" : "");
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.add("hidden"), err ? 8000 : 2800);
}

function fileRow(p, f) {
  const shape = f.name.startsWith("reel") ? "vertical" : f.name.startsWith("square") ? "square" : "";
  const play = f.kind === "mp4" ? `<button class="btn btn-outline small" data-play="${esc(f.url)}" data-shape="${shape}">▶ Play</button>` : "";
  return `<div class="file"><b>${f.kind === "mp4" ? "🎬" : f.kind === "pptx" ? "▤" : "📝"} ${esc(f.label)}</b>
    <span class="muted">${esc(f.date)} · ${f.size_mb} MB</span>${play}
    <a class="btn btn-outline small" href="${esc(f.url)}?dl=1">⬇ Download</a></div>`;
}

function render() {
  const q = $("#search").value.trim().toLowerCase();
  const only = $("#onlyVideos").checked;
  const list = all.filter((p) => (!q || `${p.name} ${p.title}`.toLowerCase().includes(q)) &&
    (!only || p.files.some((f) => f.kind === "mp4")));
  $("#count").textContent = `${list.length} of ${all.length} projects`;
  $("#list").innerHTML = list.length ? list.map((p) => {
    const vids = p.files.filter((f) => f.kind === "mp4").length;
    return `<article class="card proj" data-id="${esc(p.id)}">
      <div class="proj-thumb">${p.thumb ? `<img src="${esc(p.thumb)}" alt="" loading="lazy">` : "no picture yet"}</div>
      <div>
        <h3>${esc(p.name)}</h3>
        <div class="proj-meta">${p.slides} scenes · ${vids} video${vids === 1 ? "" : "s"} · created ${esc(p.created)} · last change ${esc(p.modified)}${p.dubbed_from ? " · dubbed copy" : ""}</div>
        <div class="proj-actions">
          <a class="btn btn-primary small" href="/make?p=${esc(p.id)}&step=2">✦ Continue: script, voice, video</a>
          <a class="btn btn-outline small" href="/?p=${esc(p.id)}">▤ Open in Presentation</a>
          <button class="btn btn-outline small danger" data-del="${esc(p.id)}">🗑 Delete</button>
        </div>
        <div class="files">${p.files.length ? p.files.map((f) => fileRow(p, f)).join("") : '<span class="muted">No video or files yet — click “Continue” to make the video.</span>'}</div>
      </div></article>`;
  }).join("") : `<div class="card empty-box">${all.length ? "No project matches your search." : 'No projects yet. <a href="/make">Make your first video →</a>'}</div>`;
}

async function load() {
  const r = await fetch("/api/my_projects");
  all = await r.json();
  render();
  document.body.dataset.ready = "true";
}

$("#search").oninput = render;
$("#onlyVideos").onchange = render;
$("#list").addEventListener("click", async (e) => {
  const play = e.target.closest("[data-play]");
  if (play) {
    const row = play.closest(".file");
    const open = row.nextElementSibling?.classList.contains("file-video");
    document.querySelectorAll(".file-video").forEach((v) => v.remove());
    if (!open) row.insertAdjacentHTML("afterend", `<div class="file-video"><video controls autoplay class="${play.dataset.shape}" src="${play.dataset.play}"></video></div>`);
    return;
  }
  const del = e.target.closest("[data-del]");
  if (del) {
    const p = all.find((x) => x.id === del.dataset.del);
    if (!confirm(`Delete “${p.name}” with all its videos and files? This cannot be undone.\n(Tip: backup_windows.bat keeps a copy of all projects.)`)) return;
    const r = await fetch(`/api/projects/${p.id}`, { method: "DELETE" });
    if (!r.ok) return toast("Could not delete", true);
    all = all.filter((x) => x.id !== p.id);
    render();
    toast("Project deleted");
  }
});
load().catch((e) => toast(e.message, true));
