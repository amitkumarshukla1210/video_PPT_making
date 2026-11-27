// Tools: Video, Image, Audio, Character, World. Plain JavaScript, no build step.
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
let st = null, pickedImage = null;
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
const opts = (obj, sel) => Object.entries(obj).map(([k, v]) => `<option value="${esc(k)}"${k === sel ? " selected" : ""}>${esc(v)}</option>`).join("");

async function refresh() { st = await api("/api/tools/state"); }

// Background job of the tools (pictures, clips): progress bar until done.
async function waitJob(box) {
  const bar = box.querySelector(".bar > div"), text = box.querySelector("p");
  box.classList.remove("hidden");
  for (;;) {
    const j = await api("/api/tools/job");
    bar.style.width = (j.state === "done" ? 100 : Math.max(4, (j.fraction || 0) * 100)) + "%";
    text.textContent = j.state === "running" ? `${j.message || j.stage || "Working…"} · ${j.elapsed || 0}s` : "";
    if (j.state === "done") { box.classList.add("hidden"); return j.result; }
    if (j.state === "error" || j.state === "cancelled") { box.classList.add("hidden"); throw new Error(j.error || "Stopped"); }
    await sleep(1000);
  }
}

function mediaRow(kind, f) {
  const player = kind === "videos" ? `<video controls preload="metadata" src="${f.url}"></video>`
    : kind === "audio" ? `<audio controls preload="none" src="${f.url}"></audio>` : "";
  return `<div class="media-row">${player}<span class="muted">${esc(f.name)} · ${esc(f.date)} · ${f.size_kb} KB</span>
    <a class="btn btn-outline small" href="${f.url}?dl=1">⬇ Download</a>
    <button class="btn btn-outline small danger" data-del="${kind}/${esc(f.name)}">🗑</button></div>`;
}
function renderMedia() {
  $("#videoList").innerHTML = st.media.videos.map((f) => mediaRow("videos", f)).join("") || '<p class="muted">No clips yet.</p>';
  $("#audioList").innerHTML = st.media.audio.map((f) => mediaRow("audio", f)).join("") || '<p class="muted">No audio yet.</p>';
  $("#imageList").innerHTML = st.media.images.map((f) => `<figure class="pic">
      <img src="${f.url}" alt="" loading="lazy"><figcaption>
      <button class="btn btn-outline small" data-clip="${esc(f.name)}" title="Make an animated clip">🎬 Clip</button>
      <a class="btn btn-outline small" href="${f.url}?dl=1">⬇</a>
      <button class="btn btn-outline small danger" data-del="images/${esc(f.name)}">🗑</button></figcaption></figure>`).join("")
    || '<p class="muted">No pictures yet.</p>';
  $("#clipPick").innerHTML = st.media.images.slice(0, 24).map((f) => `<button class="pick${f.name === pickedImage ? " on" : ""}" data-pick="${esc(f.name)}">
      <img src="${f.url}" alt="" loading="lazy"></button>`).join("") || '<p class="muted">No pictures yet — upload one or create one in Image.</p>';
}

// ---------- Video ----------
async function makeClip() {
  if (!pickedImage) return toast("Choose a picture first", true);
  $("#clipGo").disabled = true;
  try {
    await api("/api/tools/clip", { method: "POST", json: { image: pickedImage, title: $("#clipTitle").value,
      subtitle: $("#clipSub").value, look: $("#clipLook").value, seconds: +$("#clipSecs").value, music: $("#clipMusic").value,
      fx: $("#clipFx").value } });
    const r = await waitJob($("#clipProg"));
    await refresh(); renderMedia();
    $("#clipResult").innerHTML = `<video controls autoplay src="/media/videos/${r.video}"></video>
      <a class="btn btn-primary small" href="/media/videos/${r.video}?dl=1">⬇ Download the clip</a>`;
  } catch (e) { toast(e.message, true); } finally { $("#clipGo").disabled = false; }
}

// ---------- Image ----------
function renderRefChips() {
  const all = [...st.characters, ...st.worlds];
  $("#imgRefs").innerHTML = all.length ? "Insert: " + all.map((i) => `<button class="chip small" data-ins="${esc(i.tag)}">${esc(i.tag)}</button>`).join("")
    : '<span class="muted">Tip: save people in <a href="/tools/character">Character</a> and places in <a href="/tools/world">World</a>, then type @Name here so they look the same in every picture.</span>';
}
async function makeImages() {
  if (!st.images.available) return toast(st.images.info, true);
  $("#imgGo").disabled = true;
  try {
    await api("/api/tools/image", { method: "POST", json: { prompt: $("#imgPrompt").value, style: $("#imgStyle").value,
      aspect: $("#imgAspect").value, n: +$("#imgN").value } });
    await waitJob($("#imgProg"));
    await refresh(); renderMedia();
    toast("Pictures ready — they are in My pictures below");
    $("#imgReport").classList.add("hidden");
  } catch (e) {
    toast("Picture creation failed — see the message below", true);
    $("#imgReport pre").textContent = e.message + "\n\nClick “🔍 Check picture creator” for a full report.";
    $("#imgReport").classList.remove("hidden", "ok");
  } finally { $("#imgGo").disabled = false; }
}

// ---------- Audio ----------
function fillVoice(engineName, lang, voiceId) {
  const eng = st.engines.find((e) => e.name === engineName) || st.engines.find((e) => e.name === st.default_engine);
  $("#vEngine").innerHTML = st.engines.map((e) => `<option value="${e.name}" ${e.available ? "" : "disabled"}>${esc(e.label)}${e.available ? "" : " — not installed"}</option>`).join("");
  $("#vEngine").value = eng?.name || "";
  const voices = eng ? eng.voices : [];
  const langs = [...new Set(voices.map((v) => v.lang))];
  $("#vLang").innerHTML = langs.map((l) => `<option>${esc(l)}</option>`).join("");
  $("#vLang").value = langs.includes(lang) ? lang : (langs.find((l) => l.startsWith("en")) || langs[0] || "");
  const vs = voices.filter((v) => v.lang === $("#vLang").value);
  $("#vVoice").innerHTML = vs.map((v) => `<option value="${esc(v.id)}">${esc(v.label)}${v.gender ? " · " + v.gender : ""}</option>`).join("");
  if (vs.some((v) => v.id === voiceId)) $("#vVoice").value = voiceId;
}
function currentVoice() {
  return { engine: $("#vEngine").value, lang: $("#vLang").value, voice: $("#vVoice").value, speed: +$("#vSpeed").value };
}
async function makeVoice() {
  $("#vGo").disabled = true; $("#vStatus").textContent = "Speaking…";
  try {
    const r = await api("/api/tools/voice", { method: "POST", json: { text: $("#vText").value, ...currentVoice() } });
    await refresh(); renderMedia();
    $("#vStatus").innerHTML = `<audio controls autoplay src="${r.url}"></audio>`;
  } catch (e) { $("#vStatus").textContent = ""; toast(e.message, true); } finally { $("#vGo").disabled = false; }
}
async function makeMusic() {
  $("#mGo").disabled = true; $("#mStatus").textContent = "Composing…";
  try {
    const r = await api("/api/tools/music", { method: "POST", json: { mood: $("#mMood").value, seconds: +$("#mSecs").value } });
    await refresh(); renderMedia();
    $("#mStatus").innerHTML = `<audio controls autoplay src="${r.url}"></audio>`;
  } catch (e) { $("#mStatus").textContent = ""; toast(e.message, true); } finally { $("#mGo").disabled = false; }
}

// ---------- Character / World ----------
const REF = {
  characters: { title: "Characters", one: "character", ph: "e.g. Maya, 30, short black hair, round glasses, red raincoat, warm smile",
    hint: "Save a person once. Type their @Name in picture prompts and in Make a video ideas — the description is filled in, so they look the same in every scene. A voice can be saved for them too (used in Audio › Speak as).", voice: true, pic: "🖼 Create portrait" },
  worlds: { title: "Worlds", one: "place", ph: "e.g. Old City: narrow stone streets, warm lanterns, wet cobblestones, night",
    hint: "Save a place once and reuse it as @Place, so every scene happens in the same world. (A 3D world you can walk through is not possible offline; scenes use camera moves instead.)", voice: false, pic: "🖼 Create a view" },
};
function renderRefs(kind) {
  const R = REF[kind], sec = $(`section[data-kind=${kind}]`), list = st[kind];
  sec.innerHTML = `<h3>${R.title}</h3><p class="muted">${R.hint}</p>
    <div class="grid-opts"><div><label for="${kind}Name">Name</label><input id="${kind}Name" placeholder="${kind === "worlds" ? "e.g. Old City" : "e.g. Maya"}"></div></div>
    <label for="${kind}Desc">How ${kind === "worlds" ? "it looks" : "they look"}</label><textarea id="${kind}Desc" rows="3" placeholder="${R.ph}"></textarea>
    ${R.voice ? `<label class="check"><input type="checkbox" id="${kind}UseVoice"> Save the voice chosen in Audio for this character</label>` : ""}
    <input type="hidden" id="${kind}Id">
    <div class="row wrap"><button class="btn btn-primary" data-save="${kind}">💾 Save ${R.one}</button><button class="btn btn-outline" data-new="${kind}">New</button><span class="muted" id="${kind}Status"></span></div>
    <div class="progress hidden" id="${kind}Prog"><div class="bar"><div></div></div><p class="muted"></p></div>
    <div class="ref-grid">${list.map((i) => `<article class="ref">
      <div class="ref-pic">${i.image ? `<img src="/media/images/${esc(i.image)}" alt="">` : `<span>${kind === "worlds" ? "🌍" : "🧑"}</span>`}</div>
      <div class="ref-body"><b>${esc(i.name)}</b> <code>${esc(i.tag)}</code><p>${esc(i.description)}</p>
      ${i.voice ? `<p class="muted">🎙 ${esc(i.voice.engine)} · ${esc(i.voice.voice || "default")}</p>` : ""}
      <div class="row wrap"><button class="btn btn-outline small" data-pic="${kind}/${i.id}" ${st.images.available ? "" : "disabled title='Picture creator not installed'"}>${R.pic}</button>
      <button class="btn btn-outline small" data-edit="${kind}/${i.id}">✎ Edit</button>
      <button class="btn btn-outline small" data-copy="${esc(i.tag)}">Copy ${esc(i.tag)}</button>
      <button class="btn btn-outline small danger" data-delref="${kind}/${i.id}">🗑</button></div></div></article>`).join("")
      || `<p class="muted">No ${R.title.toLowerCase()} yet.</p>`}</div>`;
}

// ---------- start ----------
function show(tool) {
  $$(".tool").forEach((s) => s.classList.toggle("hidden", s.id !== "t-" + tool));
  $$(".tool-tabs a").forEach((a) => a.classList.toggle("on", a.dataset.t === tool));
}
async function init() {
  await refresh();
  $("#clipLook").innerHTML = opts(st.looks, "cinematic");
  $("#clipFx").innerHTML = opts(st.fx, "drift");
  $("#clipPreset").insertAdjacentHTML("beforeend", Object.entries(st.presets).map(([k, p]) => `<option value="${k}">⚡ ${esc(p.name)}</option>`).join(""));
  const usePreset = (id) => {
    const p = st.presets[id]; if (!p) return;
    $("#clipPreset").value = id; $("#clipFx").value = p.fx; $("#clipLook").value = p.look; $("#clipMusic").value = p.music;
    $("#clipTitle").value = p.title; $("#clipSub").value = p.subtitle || "";
    const secs = String(Math.round(p.seconds));
    if (![...$("#clipSecs").options].some((o) => o.value === secs)) $("#clipSecs").insertAdjacentHTML("beforeend", `<option>${secs}</option>`);
    $("#clipSecs").value = secs;
  };
  $("#clipPreset").onchange = () => usePreset($("#clipPreset").value);
  const qp = new URLSearchParams(location.search).get("preset");
  if (qp) { usePreset(qp); setTimeout(() => toast("Preset ready — now pick or upload your photo, then Make the clip"), 300); }
  $("#clipMusic").insertAdjacentHTML("beforeend", opts(st.moods, "cinematic"));
  $("#clipMusic").value = "cinematic";
  $("#imgStyle").innerHTML = opts(st.styles, "cinematic");
  $("#mMood").innerHTML = opts(st.moods, "corporate");
  $("#sfxList").innerHTML = Object.entries(st.sfx).map(([k, v]) => `<div class="media-row"><audio controls preload="none" src="/library/sfx/${k}.wav"></audio>
    <span>${esc(v)}</span><button class="btn btn-outline small" data-sfx="${k}">＋ Save to My audio</button></div>`).join("");
  $("#vAs").insertAdjacentHTML("beforeend", st.characters.filter((c) => c.voice).map((c) => `<option value="${c.id}">${esc(c.tag)}</option>`).join(""));
  fillVoice(st.default_engine, "en-us");
  if (!st.images.available) $("#imgStatus").textContent = `Picture creator: ${st.images.info}`;
  renderMedia(); renderRefChips(); renderRefs("characters"); renderRefs("worlds");
  show(document.body.dataset.tool);

  $("#clipUpload").onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f, f.name);
    try { const r = await api("/api/tools/upload", { method: "POST", body: fd }); pickedImage = r.name; await refresh(); renderMedia(); }
    catch (err) { toast(err.message, true); }
  };
  $("#clipGo").onclick = makeClip;
  $("#imgGo").onclick = makeImages;
  $("#imgCheck").onclick = async () => {
    $("#imgCheck").disabled = true;
    try {
      await api("/api/tools/image/check", { method: "POST" });
      const r = await waitJob($("#imgProg"));
      $("#imgReport pre").textContent = r.report;
      $("#imgReport").classList.remove("hidden");
      $("#imgReport").classList.toggle("ok", r.ok);
      toast(r.ok ? "The picture creator works" : "The picture creator has a problem — copy the report and send it", !r.ok);
    } catch (e) { toast(e.message, true); } finally { $("#imgCheck").disabled = false; }
  };
  $("#imgCopy").onclick = async () => {
    try { await navigator.clipboard.writeText($("#imgReport pre").textContent); toast("Report copied"); }
    catch (e) { toast("Select the text and copy it with Ctrl+C", true); }
  };
  $("#vGo").onclick = makeVoice;
  $("#mGo").onclick = makeMusic;
  $("#vEngine").onchange = () => fillVoice($("#vEngine").value);
  $("#vLang").onchange = () => fillVoice($("#vEngine").value, $("#vLang").value);
  $("#vSpeed").oninput = () => ($("#vSpeedOut").textContent = (+$("#vSpeed").value).toFixed(2));
  $("#vAs").onchange = () => {
    const c = st.characters.find((x) => x.id === $("#vAs").value);
    if (c?.voice) { fillVoice(c.voice.engine, c.voice.lang, c.voice.voice); $("#vSpeed").value = c.voice.speed || 1; }
  };

  document.addEventListener("click", async (e) => {
    const t = e.target.closest("button, [data-pick]"); if (!t) return;
    const d = t.dataset;
    try {
      if (d.pick) { pickedImage = d.pick; renderMedia(); }
      else if (d.clip) { pickedImage = d.clip; history.replaceState(null, "", "/tools/video"); show("video"); renderMedia(); window.scrollTo({ top: 0 }); }
      else if (d.ins) { const ta = $("#imgPrompt"); ta.value = (ta.value + " " + d.ins + " ").replace(/^\s+/, ""); ta.focus(); }
      else if (d.del) {
        if (!confirm("Delete this file?")) return;
        await api(`/api/tools/media/${d.del}`, { method: "DELETE" }); await refresh(); renderMedia();
      } else if (d.sfx) { await api(`/api/tools/sfx/${d.sfx}`, { method: "POST" }); await refresh(); renderMedia(); toast("Saved to My audio"); }
      else if (d.save) {
        const k = d.save;
        const body = { id: $(`#${k}Id`).value || undefined, name: $(`#${k}Name`).value, description: $(`#${k}Desc`).value };
        if (k === "characters" && $(`#${k}UseVoice`).checked) body.voice = currentVoice();
        await api(`/api/tools/${k}`, { method: "POST", json: body });
        await refresh(); renderRefs(k); renderRefChips(); toast("Saved");
      } else if (d.new) { const k = d.new; $(`#${k}Id`).value = ""; $(`#${k}Name`).value = ""; $(`#${k}Desc`).value = ""; }
      else if (d.edit) {
        const [k, id] = d.edit.split("/"); const i = st[k].find((x) => x.id === id);
        $(`#${k}Id`).value = i.id; $(`#${k}Name`).value = i.name; $(`#${k}Desc`).value = i.description; $(`#${k}Name`).focus();
      } else if (d.copy) { await navigator.clipboard?.writeText(d.copy).catch(() => {}); toast(`${d.copy} copied — paste it into a prompt`); }
      else if (d.delref) {
        const [k, id] = d.delref.split("/");
        if (!confirm("Delete it? Pictures you already made stay in My media.")) return;
        await api(`/api/tools/${k}/${id}`, { method: "DELETE" }); await refresh(); renderRefs(k); renderRefChips();
      } else if (d.pic) {
        const [k, id] = d.pic.split("/");
        await api(`/api/tools/${k}/${id}/picture`, { method: "POST" });
        await waitJob($(`#${k}Prog`)); await refresh(); renderRefs(k); renderMedia();
      }
    } catch (err) { toast(err.message, true); }
  });
  document.body.dataset.ready = "true";
}
init().catch((e) => toast(e.message, true));
