const $ = (id) => document.getElementById(id);
const results = $("results");
const summary = $("summary");
const status = $("upload-status");

const escape = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function setStatus(message, tone) {
  const tones = { busy: "text-slate-500", ok: "text-emerald-600", error: "text-red-600" };
  status.className = `mt-3 text-sm ${tones[tone]}`;
  status.textContent = message;
  status.classList.remove("hidden");
}

function card(asset) {
  const preview = asset.kind === "image"
    ? `<img src="${escape(asset.url)}" alt="${escape(asset.original_name)}"
            class="w-full h-40 object-cover bg-slate-100" loading="lazy">`
    : `<pre class="h-40 overflow-hidden bg-slate-50 p-3 text-xs text-slate-600 whitespace-pre-wrap font-mono">${escape((asset.text_content || "").slice(0, 240))}</pre>`;

  const score = asset.score === undefined ? ""
    : `<span class="shrink-0 px-2 py-0.5 rounded-full bg-slate-800 text-white text-xs font-mono">${asset.score.toFixed(2)}</span>`;

  const warning = asset.metadata_ok ? ""
    : `<p class="text-xs text-amber-600 mb-2">No AI metadata &mdash; this asset will not appear in search.</p>`;

  const tags = (asset.tags || [])
    .map((t) => `<span class="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-xs">${escape(t)}</span>`)
    .join("");

  return `
    <article class="bg-white rounded-xl shadow-sm overflow-hidden flex flex-col">
      <a href="${escape(asset.url)}" target="_blank" rel="noopener">${preview}</a>
      <div class="p-4 flex flex-col gap-2 grow">
        <div class="flex items-start justify-between gap-2">
          <h3 class="font-medium text-sm break-all">${escape(asset.original_name)}</h3>
          ${score}
        </div>
        ${warning}
        <p class="text-sm text-slate-600 grow">${escape(asset.description) || "<span class='text-slate-400'>No description.</span>"}</p>
        <div class="flex flex-wrap gap-1">${tags}</div>
      </div>
    </article>`;
}

function render(assets, context) {
  summary.textContent = context;
  results.innerHTML = assets.length
    ? assets.map(card).join("")
    : `<p class="text-slate-400 col-span-full">Nothing to show.</p>`;
}

async function loadAll() {
  summary.textContent = "Loading…";
  const assets = await (await fetch("/api/assets")).json();
  render(assets, `${assets.length} asset${assets.length === 1 ? "" : "s"} in the knowledge base.`);
}

async function runSearch() {
  const q = $("query").value.trim();
  if (!q) return loadAll();
  summary.textContent = "Searching…";
  results.innerHTML = "";
  const response = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
  if (!response.ok) {
    const { detail } = await response.json().catch(() => ({}));
    return render([], detail || "Search failed.");
  }
  const hits = await response.json();
  render(hits, `${hits.length} result${hits.length === 1 ? "" : "s"} for “${q}”, best match first.`);
}

async function upload() {
  const input = $("file");
  const file = input.files[0];
  if (!file) return setStatus("Choose a file first.", "error");

  $("upload-btn").disabled = true;
  setStatus(`Uploading ${file.name} and generating metadata… this takes a few seconds.`, "busy");
  try {
    const body = new FormData();
    body.append("file", file);
    const response = await fetch("/api/upload", { method: "POST", body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Upload failed.");
    setStatus(
      data.metadata_ok
        ? `Added ${data.original_name}.`
        : `Added ${data.original_name}, but metadata generation failed, so it is not searchable.`,
      data.metadata_ok ? "ok" : "error",
    );
    input.value = "";
    $("query").value = "";
    await loadAll();
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    $("upload-btn").disabled = false;
  }
}

$("upload-btn").addEventListener("click", upload);
$("search-btn").addEventListener("click", runSearch);
$("clear-btn").addEventListener("click", () => { $("query").value = ""; loadAll(); });
$("query").addEventListener("keydown", (e) => { if (e.key === "Enter") runSearch(); });
document.querySelectorAll(".example").forEach((b) =>
  b.addEventListener("click", () => { $("query").value = b.textContent; runSearch(); }));

loadAll();
