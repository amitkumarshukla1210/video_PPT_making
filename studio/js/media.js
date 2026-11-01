// Media blobs (images, clips, music, generated voice) live in IndexedDB; the project only keeps ids.
const DB_NAME = "dtc-studio";
const STORE = "media";
let dbPromise = null;
const urls = new Map(); // id -> object URL (revoked by releaseUrls)

function db() {
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  return dbPromise;
}

function tx(mode, fn) {
  return db().then((d) => new Promise((resolve, reject) => {
    const t = d.transaction(STORE, mode);
    const result = fn(t.objectStore(STORE));
    t.oncomplete = () => resolve(result?.result ?? result);
    t.onerror = () => reject(t.error);
    t.onabort = () => reject(t.error || new Error("Storage aborted (disk full?)"));
  }));
}

export function newMediaId(kind) {
  return `${kind}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export async function putMedia(blob, kind = "file", id = null) {
  const key = id || newMediaId(kind);
  await tx("readwrite", (s) => s.put(blob, key));
  revoke(key);
  return key;
}

export async function getMedia(id) {
  if (!id) return null;
  return tx("readonly", (s) => s.get(id));
}

export async function deleteMedia(id) {
  revoke(id);
  await tx("readwrite", (s) => s.delete(id));
}

export async function mediaUrl(id) {
  if (urls.has(id)) return urls.get(id);
  const blob = await getMedia(id);
  if (!blob) return null;
  const url = URL.createObjectURL(blob);
  urls.set(id, url);
  return url;
}

export function revoke(id) {
  const u = urls.get(id);
  if (u) URL.revokeObjectURL(u);
  urls.delete(id);
}

/** Free every object URL we created (after export, on project switch). */
export function releaseUrls() {
  for (const u of urls.values()) URL.revokeObjectURL(u);
  urls.clear();
}

export function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = () => reject(r.error);
    r.readAsDataURL(blob);
  });
}

export async function dataUrlToBlob(dataUrl) {
  const res = await fetch(dataUrl);
  return res.blob();
}

/** All media ids referenced by a project. */
export function referencedIds(project) {
  const ids = new Set();
  if (project.music?.mediaId) ids.add(project.music.mediaId);
  for (const s of project.scenes) {
    if (s.background?.mediaId) ids.add(s.background.mediaId);
    if (s.audio?.mediaId) ids.add(s.audio.mediaId);
  }
  return [...ids];
}

/** Portable copy of the project: media embedded as data URLs. */
export async function embedMedia(project) {
  const media = {};
  for (const id of referencedIds(project)) {
    const blob = await getMedia(id);
    if (blob) media[id] = await blobToDataUrl(blob);
  }
  return { ...project, media };
}

/** Store embedded media from a downloaded project back into IndexedDB. Returns the project without `media`. */
export async function restoreMedia(data) {
  const { media, ...project } = data;
  if (media && typeof media === "object") {
    for (const [id, url] of Object.entries(media)) {
      if (typeof url === "string" && url.startsWith("data:")) await putMedia(await dataUrlToBlob(url), "file", id);
    }
  }
  return project;
}
