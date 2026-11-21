// Popup d'ajout de séries (un ou plusieurs liens).
// Fichier 4/15 : chargé dans l'ordre par index.html ; tous partagent la même portée globale.

const addBtn = document.getElementById("add-btn");
const addModal = document.getElementById("add-modal");
const addStepInput = document.getElementById("add-step-input");
const addStepProgress = document.getElementById("add-step-progress");
const addUrl = document.getElementById("add-url");
const addPasteBtn = document.getElementById("add-paste-btn");
const addCount = document.getElementById("add-count");
const addCategorySection = document.getElementById("add-category-section");
const addCategoryChips = document.getElementById("add-category-chips");
const addSubmit = document.getElementById("add-submit");
const addCancel = document.getElementById("add-cancel");
const addError = document.getElementById("add-error");
const addProgressList = document.getElementById("add-progress-list");
const addSummary = document.getElementById("add-summary");
const addRetryBtn = document.getElementById("add-retry-btn");
const addDoneBtn = document.getElementById("add-done-btn");

// ----- Popup d'ajout -----
const SCAN_MANGA_PREFIX = "https://www.scan-manga.com/";
let addRunning = false;
let addFailedUrls = [];
const addSelectedCategories = new Set();

function extractUrls(text) {
  const seen = new Set();
  const valid = [];
  for (let u of text.match(/https?:\/\/[^\s"'<>]+/g) || []) {
    u = u.replace(/[),.;]+$/, "").replace(/^https?:\/\/(www\.|m\.)?scan-manga\.com/i, "https://www.scan-manga.com");
    if (u.startsWith(SCAN_MANGA_PREFIX) && !seen.has(u)) {
      seen.add(u);
      valid.push(u);
    }
  }
  const ignored = text.split("\n").map((l) => l.trim()).filter((l) => l && !/scan-manga\.com/i.test(l)).length;
  return { valid, ignored };
}

function urlLabel(url) {
  try {
    const last = decodeURIComponent(new URL(url).pathname.split("/").filter(Boolean).pop() || url);
    return last.replace(/\.html$/i, "").replace(/-/g, " ");
  } catch (e) {
    return url;
  }
}

function updateAddCount() {
  const { valid, ignored } = extractUrls(addUrl.value);
  addSubmit.disabled = valid.length === 0;
  addSubmit.textContent = valid.length > 1 ? `Ajouter ${valid.length} séries` : "Ajouter";
  if (!addUrl.value.trim()) {
    addCount.textContent = "";
    addCount.classList.remove("warn");
    return;
  }
  let text = valid.length === 0
    ? "Aucun lien scan-manga.com valide"
    : `${valid.length} lien${valid.length > 1 ? "s" : ""} valide${valid.length > 1 ? "s" : ""}`;
  if (valid.length > 0 && ignored > 0) text += ` · ${ignored} ligne${ignored > 1 ? "s" : ""} ignorée${ignored > 1 ? "s" : ""}`;
  addCount.textContent = text;
  addCount.classList.toggle("warn", valid.length === 0 || ignored > 0);
}

async function loadAddCategoryChips() {
  const res = await fetch("/api/categories");
  const categories = await res.json();
  addCategoryChips.innerHTML = "";
  addCategorySection.classList.toggle("hidden", categories.length === 0);
  const existing = new Set(categories.map((c) => c.id));
  for (const id of [...addSelectedCategories]) if (!existing.has(id)) addSelectedCategories.delete(id);
  for (const c of categories) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip" + (addSelectedCategories.has(c.id) ? " active" : "");
    chip.textContent = c.name;
    chip.addEventListener("click", () => {
      if (addSelectedCategories.has(c.id)) addSelectedCategories.delete(c.id); else addSelectedCategories.add(c.id);
      chip.classList.toggle("active");
    });
    addCategoryChips.appendChild(chip);
  }
}

async function openAddModal(prefill) {
  if (addRunning) {
    addStepInput.classList.add("hidden");
    addStepProgress.classList.remove("hidden");
    openModal(addModal);
    return;
  }
  addStepInput.classList.remove("hidden");
  addStepProgress.classList.add("hidden");
  addCancel.classList.remove("hidden");
  addError.classList.add("hidden");
  if (prefill !== undefined) addUrl.value = prefill;
  updateAddCount();
  openModal(addModal);
  if (window.matchMedia("(pointer: fine)").matches) addUrl.focus();
  await loadAddCategoryChips();
}

function setAddRow(li, state, title, sub, cover) {
  const icons = { wait: "⏳", running: "🔄", ok: "✓", dup: "•", fail: "✗" };
  li.className = "add-row " + state;
  li.innerHTML = "";
  if (cover) {
    const img = document.createElement("img");
    img.alt = "";
    img.src = cover;
    li.appendChild(img);
  } else {
    const icon = document.createElement("span");
    icon.className = "add-row-icon";
    icon.textContent = icons[state];
    li.appendChild(icon);
  }
  const text = document.createElement("div");
  text.className = "add-row-text";
  const strong = document.createElement("strong");
  strong.textContent = title;
  const small = document.createElement("small");
  small.textContent = sub;
  text.append(strong, small);
  li.appendChild(text);
}

async function runAdd(urls) {
  addRunning = true;
  addStepInput.classList.add("hidden");
  addStepProgress.classList.remove("hidden");
  addCancel.classList.add("hidden");
  addDoneBtn.disabled = true;
  addRetryBtn.classList.add("hidden");
  addProgressList.innerHTML = "";

  const rows = urls.map((url) => {
    const li = document.createElement("li");
    setAddRow(li, "wait", urlLabel(url), "En attente");
    addProgressList.appendChild(li);
    return li;
  });

  const categoryIds = [...addSelectedCategories];
  let added = 0;
  let already = 0;
  const failed = [];

  for (let i = 0; i < urls.length; i++) {
    addSummary.textContent = `Ajout en cours… ${i + 1}/${urls.length}`;
    setAddRow(rows[i], "running", urlLabel(urls[i]), "Récupération en cours…");
    rows[i].scrollIntoView({ block: "nearest" });
    try {
      const res = await fetch("/api/series", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: urls[i], category_ids: categoryIds }),
      });
      let data = {};
      try { data = await res.json(); } catch (e) { /* réponse non JSON */ }
      if (res.status === 409) {
        already++;
        setAddRow(rows[i], "dup", urlLabel(urls[i]), "Déjà dans ta bibliothèque");
        continue;
      }
      if (!res.ok) throw new Error(data.detail || `Erreur ${res.status}`);
      added++;
      const chapter = data.last_chapter_number ? `Chapitre ${data.last_chapter_number}` : "Ajoutée";
      setAddRow(rows[i], "ok", data.title || urlLabel(urls[i]), chapter, data.cover_url);
    } catch (e) {
      failed.push(urls[i]);
      setAddRow(rows[i], "fail", urlLabel(urls[i]), e.message);
    }
  }

  addRunning = false;
  addFailedUrls = failed;
  const parts = [];
  if (added) parts.push(`${added} ajoutée${added > 1 ? "s" : ""}`);
  if (already) parts.push(`${already} déjà présente${already > 1 ? "s" : ""}`);
  if (failed.length) parts.push(`${failed.length} échec${failed.length > 1 ? "s" : ""}`);
  addSummary.textContent = parts.join(" · ");
  addDoneBtn.disabled = false;
  addRetryBtn.classList.toggle("hidden", failed.length === 0);

  loadGenreSelect();
  loadStatuses();
  loadCategorySelect();
  loadLibrary();
}

addBtn.addEventListener("click", () => openAddModal());
addCancel.addEventListener("click", () => closeModal(addModal));
addModal.addEventListener("click", (e) => { if (e.target === addModal && !addRunning) closeModal(addModal); });
addUrl.addEventListener("input", () => { addError.classList.add("hidden"); updateAddCount(); });

addPasteBtn.addEventListener("click", async () => {
  try {
    const text = (await navigator.clipboard.readText()).trim();
    if (!text) throw new Error("vide");
    addUrl.value = addUrl.value.trim() ? addUrl.value.trim() + "\n" + text : text;
    addError.classList.add("hidden");
    updateAddCount();
  } catch (e) {
    addError.textContent = "Impossible de lire le presse-papiers : fais un appui long dans la zone de texte, puis « Coller ».";
    addError.classList.remove("hidden");
  }
});

addSubmit.addEventListener("click", () => {
  const { valid } = extractUrls(addUrl.value);
  if (valid.length === 0) return;
  addUrl.value = "";
  runAdd(valid);
});

addRetryBtn.addEventListener("click", () => runAdd(addFailedUrls));

addDoneBtn.addEventListener("click", () => {
  addUrl.value = addFailedUrls.join("\n");
  closeModal(addModal);
});
