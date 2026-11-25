// Bibliothèque : sélection de plusieurs séries et actions groupées (catégories, tout lu / non lu, AniList, retrait).
// Chargé après series.js ; partage la portée globale des autres fichiers (état : librarySelecting, librarySelected).

const libraryToolbar = document.getElementById("library-toolbar");
const librarySelectionCount = document.getElementById("library-selection-count");
const librarySelectAllBtn = document.getElementById("library-select-all-btn");
const libraryActionsBtn = document.getElementById("library-actions-btn");
const bulkModal = document.getElementById("bulk-modal");
const bulkCategoryModal = document.getElementById("bulk-category-modal");
const bulkCategoryList = document.getElementById("bulk-category-list");
const bulkAnilistModal = document.getElementById("bulk-anilist-modal");
const bulkAnilistInput = document.getElementById("bulk-anilist-input");
const bulkAnilistSearchBtn = document.getElementById("bulk-anilist-search");
const bulkAnilistResults = document.getElementById("bulk-anilist-results");
let bulkChanged = false; // une action a modifié la bibliothèque pendant que la feuille était ouverte

const countLabel = (n, word) => `${n} ${word}${n > 1 ? "s" : ""}`;

function setLibrarySelecting(on, firstId = null) {
  librarySelecting = on;
  librarySelected = new Set(firstId !== null ? [firstId] : []);
  document.body.classList.toggle("library-selecting", on);
  libraryToolbar.classList.toggle("hidden", !on);
  grid.querySelectorAll(".card").forEach((card) => card.classList.toggle("selected", librarySelected.has(Number(card.dataset.id))));
  updateLibrarySelectionCount();
}

function toggleLibrarySelection(id, card) {
  if (librarySelected.has(id)) librarySelected.delete(id); else librarySelected.add(id);
  card.classList.toggle("selected", librarySelected.has(id));
  updateLibrarySelectionCount();
}

function updateLibrarySelectionCount() {
  const n = librarySelected.size;
  librarySelectionCount.textContent = `${n} sélectionnée${n > 1 ? "s" : ""}`;
  libraryActionsBtn.disabled = n === 0;
  librarySelectAllBtn.textContent = n > 0 && n === libraryShown.length ? "Aucune" : "Tout";
}

document.getElementById("library-select-btn").addEventListener("click", () => {
  homeMenu.classList.add("hidden");
  setLibrarySelecting(true);
});
document.getElementById("library-select-cancel-btn").addEventListener("click", () => setLibrarySelecting(false));
librarySelectAllBtn.addEventListener("click", () => {
  const all = librarySelected.size === libraryShown.length;
  librarySelected = new Set(all ? [] : libraryShown.map((s) => s.id));
  grid.querySelectorAll(".card").forEach((card) => card.classList.toggle("selected", librarySelected.has(Number(card.dataset.id))));
  updateLibrarySelectionCount();
});
// Changer d'onglet quitte la sélection.
navButtons.forEach((btn) => {
  btn.addEventListener("click", () => { if (librarySelecting) setLibrarySelecting(false); });
});

// Appui long sur une carte : passe en mode sélection avec cette série déjà cochée.
let pressTimer = null;
let pressStart = null;
let swallowClick = false;
grid.addEventListener("pointerdown", (e) => {
  swallowClick = false; // un relâchement d'appui long qui n'a pas produit de clic ne doit pas manger le suivant
  const card = e.target.closest(".card");
  if (!card || librarySelecting || (e.pointerType === "mouse" && e.button !== 0)) return;
  pressStart = { x: e.clientX, y: e.clientY };
  pressedCard = card;
  card.classList.add("pressing"); // la couverture s'enfonce doucement pendant l'appui
  pressTimer = setTimeout(() => {
    pressTimer = null;
    swallowClick = true;
    showLongPressDone(card);
    setLibrarySelecting(true, Number(card.dataset.id));
    if (navigator.vibrate) navigator.vibrate(15);
  }, 480);
});
let pressedCard = null;
const cancelPress = () => {
  clearTimeout(pressTimer);
  pressTimer = null;
  if (pressedCard) pressedCard.classList.remove("pressing");
  pressedCard = null;
};
grid.addEventListener("pointermove", (e) => {
  if (pressTimer && pressStart && Math.hypot(e.clientX - pressStart.x, e.clientY - pressStart.y) > 10) cancelPress();
});
["pointerup", "pointercancel", "pointerleave"].forEach((type) => grid.addEventListener(type, cancelPress));
grid.addEventListener("contextmenu", (e) => { if (e.target.closest(".card")) e.preventDefault(); });
// Le relâchement qui suit l'appui long ne doit pas décocher la série qu'il vient de cocher.
grid.addEventListener("click", (e) => {
  if (swallowClick) { swallowClick = false; e.stopPropagation(); e.preventDefault(); }
}, true);

// --- Feuille des actions ---
libraryActionsBtn.addEventListener("click", () => {
  document.getElementById("bulk-modal-title").textContent = countLabel(librarySelected.size, "série") + " sélectionnée" + (librarySelected.size > 1 ? "s" : "");
  openModal(bulkModal);
});
document.getElementById("bulk-modal-close").addEventListener("click", () => closeModal(bulkModal));
closeOnBackdrop(bulkModal);

async function runBulk(action, extra = {}) {
  const res = await fetch("/api/series/bulk", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ series_ids: [...librarySelected], action, ...extra }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Action impossible");
  return data.count;
}

bulkModal.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-bulk]");
  if (!btn) return;
  const action = btn.dataset.bulk;
  const n = librarySelected.size;
  if (action === "state") {
    openBulkStateSheet();
    return;
  }
  if (action === "categories") {
    swapModal(bulkModal, bulkCategoryModal);
    openBulkCategories();
    return;
  }
  if (action === "anilist") {
    startBulkAnilist();
    return;
  }
  if (action === "delete" && !confirm(`Retirer ${countLabel(n, "série")} de la bibliothèque ? Leur progression et leur historique seront perdus.`)) return;
  if (action === "mark_unread" && !confirm(`Marquer tous les chapitres de ${countLabel(n, "série")} comme non lus ? (AniList n'est pas modifié)`)) return;
  try {
    const count = await runBulk(action);
    const done = { mark_read: "marquée(s) comme lue(s)", mark_unread: "marquée(s) comme non lue(s)", delete: "retirée(s)" }[action];
    toast(`${countLabel(count, "série")} ${done}`, "ok");
    closeModal(bulkModal);
    setLibrarySelecting(false);
    loadLibrary();
  } catch (err) {
    toast(err.message, "error");
  }
});

// --- Catégories : case cochée (toutes dedans), partielle (certaines), vide (aucune) ---
async function openBulkCategories() {
  bulkChanged = false;
  bulkCategoryList.innerHTML = "";
  const res = await fetch("/api/series/bulk/categories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ series_ids: [...librarySelected] }),
  });
  const categories = await res.json();
  if (!categories.length) {
    bulkCategoryList.innerHTML = '<p class="section-label">Aucune catégorie pour l\'instant : crée-en dans Réglages › Catégories.</p>';
    return;
  }
  for (const c of categories) {
    const label = document.createElement("label");
    label.innerHTML = `<input type="checkbox"> <span>${escapeHtml(c.name)}</span><em></em>`;
    const input = label.querySelector("input");
    const count = label.querySelector("em");
    const render = (inCat) => {
      input.checked = inCat === c.total;
      input.indeterminate = inCat > 0 && inCat < c.total;
      count.textContent = inCat > 0 && inCat < c.total ? `${inCat} / ${c.total}` : "";
    };
    render(c.count);
    input.addEventListener("change", async () => {
      const add = input.checked; // une case partielle devient cochée au premier toucher
      try {
        await runBulk(add ? "add_category" : "remove_category", { category_id: c.id });
        render(add ? c.total : 0);
        bulkChanged = true;
      } catch (err) {
        render(c.count);
        toast(err.message, "error");
      }
    });
    bulkCategoryList.appendChild(label);
  }
}
document.getElementById("bulk-category-close").addEventListener("click", () => closeModal(bulkCategoryModal));
closeOnBackdrop(bulkCategoryModal);
watchModalClosed(bulkCategoryModal, () => {
  if (!bulkChanged) return;
  toast("Catégories mises à jour", "ok");
  setLibrarySelecting(false);
  loadLibrary();
});

// --- AniList : les séries non liées, une par une ; le meilleur résultat est proposé, on choisit ou on passe ---
let anilistQueue = [];
let anilistIndex = 0;
let anilistLinkedCount = 0;

function startBulkAnilist() {
  const chosen = libraryShown.filter((s) => librarySelected.has(s.id));
  anilistQueue = chosen.filter((s) => !s.anilist_id);
  const already = chosen.length - anilistQueue.length;
  if (!anilistQueue.length) {
    closeModal(bulkModal);
    toast(chosen.length > 1 ? "Ces séries sont déjà toutes liées à AniList." : "Cette série est déjà liée à AniList.");
    return;
  }
  if (already) toast(`${countLabel(already, "série")} déjà liée${already > 1 ? "s" : ""} : ignorée${already > 1 ? "s" : ""}`);
  anilistIndex = 0;
  anilistLinkedCount = 0;
  bulkChanged = false;
  swapModal(bulkModal, bulkAnilistModal);
  showAnilistStep();
}

function showAnilistStep() {
  const s = anilistQueue[anilistIndex];
  document.getElementById("bulk-anilist-step").textContent = `${anilistIndex + 1} / ${anilistQueue.length}`;
  document.getElementById("bulk-anilist-cover").src = s.cover_url || "";
  document.getElementById("bulk-anilist-title").textContent = s.title || "Sans titre";
  document.getElementById("bulk-anilist-skip").textContent = anilistIndex + 1 < anilistQueue.length ? "Passer" : "Passer et terminer";
  bulkAnilistInput.value = s.title || "";
  bulkAnilistSearch();
}

function nextAnilistStep() {
  anilistIndex += 1;
  if (anilistIndex < anilistQueue.length) showAnilistStep();
  else closeModal(bulkAnilistModal);
}

async function bulkAnilistSearch() {
  const q = bulkAnilistInput.value.trim();
  if (!q) return;
  const step = anilistIndex;
  bulkAnilistSearchBtn.disabled = true;
  bulkAnilistResults.innerHTML = '<li class="section-label">Recherche…</li>';
  try {
    const res = await fetch(`/api/anilist/search?q=${encodeURIComponent(q)}`);
    const results = await res.json().catch(() => null);
    if (step !== anilistIndex) return; // on est passé à la série suivante entre-temps
    bulkAnilistResults.innerHTML = "";
    if (!res.ok || !Array.isArray(results)) {
      const msg = results && typeof results.detail === "string" ? results.detail : "Recherche AniList impossible pour l'instant.";
      bulkAnilistResults.innerHTML = `<li class="error">⚠️ ${escapeHtml(msg)}</li>`;
      return;
    }
    if (!results.length) {
      bulkAnilistResults.innerHTML = '<li class="section-label">Aucun résultat : modifie la recherche ou passe.</li>';
      return;
    }
    results.forEach((r, i) => {
      const li = document.createElement("li");
      li.className = "anilist-result-row" + (i === 0 ? " best" : "");
      li.innerHTML = `
        <img src="${escapeHtml(r.cover_url)}" alt="" loading="lazy">
        <span>${escapeHtml(r.title)}${r.year ? " (" + r.year + ")" : ""}</span>
        ${i === 0 ? '<em class="best-tag">Meilleur résultat</em>' : ""}
      `;
      li.addEventListener("click", () => linkAnilist(r, li));
      bulkAnilistResults.appendChild(li);
    });
  } finally {
    bulkAnilistSearchBtn.disabled = false;
  }
}

async function linkAnilist(result, li) {
  const s = anilistQueue[anilistIndex];
  li.classList.add("busy");
  try {
    const res = await fetch(`/api/series/${s.id}/anilist/link`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ anilist_id: result.id, title: result.title }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(typeof data.detail === "string" ? data.detail : "Liaison refusée");
    }
    anilistLinkedCount += 1;
    bulkChanged = true;
    nextAnilistStep();
  } catch (err) {
    li.classList.remove("busy");
    toast(err.message, "error");
  }
}

bulkAnilistSearchBtn.addEventListener("click", bulkAnilistSearch);
bulkAnilistInput.addEventListener("keydown", (e) => { if (e.key === "Enter") bulkAnilistSearch(); });
document.getElementById("bulk-anilist-skip").addEventListener("click", nextAnilistStep);
document.getElementById("bulk-anilist-close").addEventListener("click", () => closeModal(bulkAnilistModal));
closeOnBackdrop(bulkAnilistModal);
watchModalClosed(bulkAnilistModal, () => {
  if (anilistLinkedCount) toast(`${countLabel(anilistLinkedCount, "série")} liée${anilistLinkedCount > 1 ? "s" : ""} à AniList`, "ok");
  if (!bulkChanged) return;
  setLibrarySelecting(false);
  loadLibrary();
});

// Remplace une feuille ouverte par une autre sans toucher à l'historique : fermer puis rouvrir aussitôt ferait
// partir le « retour » du navigateur une entrée trop loin (et quitter l'appli).
function swapModal(from, to) {
  const top = layers[layers.length - 1];
  from.classList.add("hidden");
  prepareSheet(to);
  to.classList.remove("hidden");
  if (top && top.el === from) {
    Object.assign(top, { el: to, view: to.firstElementChild, close: () => hideSheet(to) });
  } else {
    pushLayer({ el: to, view: to.firstElementChild, close: () => hideSheet(to) });
  }
}

// Appelle onClose quand la feuille se ferme, quelle que soit la manière (bouton, fond, geste retour).
function watchModalClosed(el, onClose) {
  new MutationObserver(() => {
    if (el.classList.contains("hidden") && el.dataset.wasOpen === "1") {
      el.dataset.wasOpen = "";
      onClose();
    } else if (!el.classList.contains("hidden")) {
      el.dataset.wasOpen = "1";
    }
  }).observe(el, { attributes: true, attributeFilter: ["class"] });
}
