// NotebookLM-style client. Talks to the FastAPI backend only over /api.

const api = {
  async get(url) {
    const r = await fetch(url);
    if (!r.ok) throw await err(r);
    return r.json();
  },
  async send(method, url, body) {
    const r = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!r.ok) throw await err(r);
    return r.status === 204 ? null : r.json();
  },
};
async function err(r) {
  let detail = r.statusText;
  try {
    detail = (await r.json()).detail || detail;
  } catch {}
  const e = new Error(detail);
  e.status = r.status;
  return e;
}

// One conversation thread per page load. "New chat" starts a fresh one so the agent's
// short-term memory resets.
const state = { sources: [], threadId: crypto.randomUUID() };
const $ = (id) => document.getElementById(id);
const SUGGESTIONS = [
  "What drove Acme's gross margin improvement in Q2 2024?",
  "Compare Fleet OS growth between Q1 and Q2.",
  "What are the key risks to the subscription strategy?",
];

function escapeHtml(s) {
  return String(s).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

/* ---- sources --------------------------------------------------------------- */

async function loadSources() {
  state.sources = await api.get("/api/sources");
  renderSources();
}

function renderSources() {
  const ul = $("sources");
  ul.innerHTML = "";
  const activeCount = state.sources.filter((s) => s.active).length;
  $("active-count").textContent = `${activeCount} active`;
  $("select-all").checked = activeCount === state.sources.length && state.sources.length > 0;

  for (const s of state.sources) {
    const li = document.createElement("li");
    if (!s.active) li.className = "inactive";
    li.innerHTML = `
      <input type="checkbox" ${s.active ? "checked" : ""} />
      <span class="s-name" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</span>
      <span class="s-meta">${s.chars.toLocaleString()}</span>
      <button class="icon-btn" title="View">👁</button>
      <button class="icon-btn danger" title="Remove">✕</button>`;
    const [chk, , , viewBtn, delBtn] = li.children;
    chk.onchange = () => toggleSource(s.id, chk.checked);
    viewBtn.onclick = () => viewSource(s.id);
    delBtn.onclick = () => deleteSource(s.id);
    ul.appendChild(li);
  }
}

async function toggleSource(id, active) {
  await api.send("PATCH", `/api/sources/${id}`, { active });
  await loadSources();
}
async function deleteSource(id) {
  await api.send("DELETE", `/api/sources/${id}`);
  await loadSources();
}
async function viewSource(id) {
  const s = await api.get(`/api/sources/${id}`);
  openViewer(s.name, s.content);
}

async function addText(e) {
  e.preventDefault();
  const content = $("add-content").value.trim();
  if (!content) return;
  await api.send("POST", "/api/sources", { name: $("add-name").value, content });
  $("add-name").value = "";
  $("add-content").value = "";
  $("add-form").classList.add("hidden");
  await loadSources();
}

async function uploadFile(file) {
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch("/api/sources/upload", { method: "POST", body: fd });
  if (!r.ok) {
    addMessage("system", `⚠ ${(await err(r)).message}`);
    return;
  }
  $("add-form").classList.add("hidden");
  await loadSources();
}

async function webSearch() {
  const query = $("web-query").value.trim();
  if (!query) return;
  const btn = $("web-search-btn");
  const status = $("web-search-status");
  btn.disabled = true;
  status.classList.remove("hidden");
  status.textContent = "Searching the web and reading sources… this can take a minute.";
  try {
    const added = await api.send("POST", "/api/sources/web-search", { query });
    status.textContent = added.length
      ? `Added ${added.length} source(s): ${added.map((s) => s.name).join(", ")}`
      : "No good sources found for that query.";
    $("web-query").value = "";
    await loadSources();
  } catch (e) {
    status.textContent = `⚠ ${e.message}`;
  } finally {
    btn.disabled = false;
  }
}

async function selectAll(checked) {
  await Promise.all(
    state.sources
      .filter((s) => s.active !== checked)
      .map((s) => api.send("PATCH", `/api/sources/${s.id}`, { active: checked }))
  );
  await loadSources();
}

/* ---- chat ------------------------------------------------------------------ */

function renderEmptyState() {
  const m = $("messages");
  if (m.children.length) return;
  const div = document.createElement("div");
  div.className = "empty";
  div.innerHTML = `
    <div>Ask anything about your active sources — answers are grounded and cited.</div>
    <div class="suggestions">${SUGGESTIONS.map(
      (q) => `<button class="suggestion">${escapeHtml(q)}</button>`
    ).join("")}</div>`;
  div.querySelectorAll(".suggestion").forEach((b, i) => {
    b.onclick = () => {
      $("chat-input").value = SUGGESTIONS[i];
      $("chat-form").requestSubmit();
    };
  });
  m.appendChild(div);
}

function clearEmptyState() {
  const e = $("messages").querySelector(".empty");
  if (e) e.remove();
}

function addMessage(role, text, { pending = false } = {}) {
  clearEmptyState();
  const div = document.createElement("div");
  div.className = `msg ${role}${pending ? " pending" : ""}`;
  div.textContent = text;
  $("messages").appendChild(div);
  $("messages").scrollTop = $("messages").scrollHeight;
  return div;
}

function decorateAnswer(div, data) {
  div.className = "msg ai";
  div.textContent = data.answer;
  if (data.citations?.length) {
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.innerHTML = `<div><span class="label">sources:</span> ${data.citations
      .map((c) => `<span class="chip">${escapeHtml(c.source)}</span>`)
      .join("")}</div>`;
    div.appendChild(meta);
  }
  const actions = document.createElement("div");
  actions.className = "msg-actions";
  const save = document.createElement("button");
  save.className = "link-btn";
  save.textContent = "＋ Save to note";
  save.onclick = () => saveNote(data.answer);
  actions.appendChild(save);
  div.appendChild(actions);
}

async function sendMessage(message) {
  addMessage("user", message);
  const pending = addMessage("ai", "thinking…", { pending: true });
  $("send").disabled = true;
  try {
    const data = await api.send("POST", "/api/chat", {
      message,
      thread_id: state.threadId,
    });
    decorateAnswer(pending, data);
  } catch (e) {
    pending.remove();
    addMessage("system", `⚠ ${e.message}`);
  } finally {
    $("send").disabled = false;
    $("messages").scrollTop = $("messages").scrollHeight;
  }
}

/* ---- studio + notes -------------------------------------------------------- */

async function loadArtifacts() {
  const grid = $("artifacts");
  grid.innerHTML = "";
  const arts = [
    { key: "ted", title: "TED talk", icon: "🎤" },
    { key: "podcast", title: "Podcast", icon: "🎙" },
  ];
  for (const a of arts) {
    const btn = document.createElement("button");
    btn.className = "artifact";
    btn.innerHTML = `<span class="a-icon">${a.icon}</span>
      <span class="a-title">${escapeHtml(a.title)}</span>
      <span class="a-badge">Create</span>`;
    btn.onclick = () => startStudioJob(a.key);
    grid.appendChild(btn);
  }
}

async function startStudioJob(kind) {
  try {
    const base = kind === "ted" ? "/api/ted/jobs" : "/api/podcast/jobs";
    const result = await api.send("POST", base, {});
    await handleApproval(kind, result);
  } catch (e) {
    addMessage("system", `⚠ ${e.message}`);
  }
}

async function handleApproval(kind, result) {
  const approval = result.approval || {};
  const text = approval.script_he || approval.episode_text || "No draft returned.";
  openViewer(kind === "ted" ? "TED draft" : "Podcast draft", text);
  const approved = window.confirm("Approve this draft for audio synthesis?");
  const feedback = approved ? null : window.prompt("What should be revised?", "Please improve the draft.");
  if (!approved && !feedback) return;
  const base = kind === "ted" ? "/api/ted/jobs" : "/api/podcast/jobs";
  const next = await api.send("POST", `${base}/${result.job_id}/resume`, {
    action: approved ? "approve" : "revise",
    feedback,
  });
  if (next.approval) await handleApproval(kind, next);
  else addMessage("system", `${kind} is ready for audio synthesis.`);
}

async function loadNotes() {
  renderNotes(await api.get("/api/notes"));
}
function renderNotes(notes) {
  const ul = $("notes");
  ul.innerHTML = "";
  if (!notes.length) {
    ul.innerHTML = `<div class="note-empty">No notes yet — save a grounded answer.</div>`;
    return;
  }
  for (const n of notes) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="n-title" title="${escapeHtml(n.title)}">${escapeHtml(
      n.title
    )}</span><button class="icon-btn danger">✕</button>`;
    li.querySelector("button").onclick = async () => {
      await api.send("DELETE", `/api/notes/${n.id}`);
      loadNotes();
    };
    li.querySelector(".n-title").onclick = () => openViewer(n.title, n.content);
    ul.appendChild(li);
  }
}
async function saveNote(content) {
  const title = content.split("\n")[0].slice(0, 50);
  await api.send("POST", "/api/notes", { title, content });
  loadNotes();
}

/* ---- viewer modal ---------------------------------------------------------- */

function openViewer(title, content) {
  $("viewer-title").textContent = title;
  $("viewer-content").textContent = content;
  $("viewer").classList.remove("hidden");
  $("overlay").classList.remove("hidden");
}
function closeViewer() {
  $("viewer").classList.add("hidden");
  $("overlay").classList.add("hidden");
}

/* ---- wiring ---------------------------------------------------------------- */

$("add-toggle").onclick = () => $("add-form").classList.toggle("hidden");
$("add-cancel").onclick = () => $("add-form").classList.add("hidden");
$("add-form").addEventListener("submit", addText);
$("add-file").onchange = (e) => e.target.files[0] && uploadFile(e.target.files[0]);
$("web-search-btn").onclick = webSearch;
$("select-all").onchange = (e) => selectAll(e.target.checked);

$("chat-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const msg = $("chat-input").value.trim();
  if (!msg) return;
  $("chat-input").value = "";
  sendMessage(msg);
});

$("new-chat").onclick = () => {
  state.threadId = crypto.randomUUID(); // fresh memory
  $("messages").innerHTML = "";
  renderEmptyState();
};

$("close-viewer").onclick = closeViewer;
$("overlay").onclick = closeViewer;

/* ---- init ------------------------------------------------------------------ */

(async function init() {
  await Promise.all([loadSources(), loadArtifacts(), loadNotes()]);
  renderEmptyState();
})();
