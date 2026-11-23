// Bibliothèque : grille, recherche, filtres et tri, série aléatoire, actualisation de toutes les séries.
// Fichier 2/15 : chargé dans l'ordre par index.html ; tous partagent la même portée globale.

const grid = document.getElementById("grid");
const emptyMsg = document.getElementById("empty-msg");
const refreshAllBtn = document.getElementById("refresh-all-btn");
const refreshStatusText = document.getElementById("refresh-status-text");
const sortSelect = document.getElementById("sort-select");
const statusSelect = document.getElementById("status-select");
const genreSelect = document.getElementById("genre-select");
const anilistFilterSelect = document.getElementById("anilist-filter-select");
const hideReadCheckbox = document.getElementById("hide-read-checkbox");
const searchInput = document.getElementById("search-input");
const searchToggleBtn = document.getElementById("search-toggle-btn");
const searchBar = document.getElementById("search-bar");
const filterToggleBtn = document.getElementById("filter-toggle-btn");
const filterModal = document.getElementById("filter-modal");
const filterModalClose = document.getElementById("filter-modal-close");
const categorySelect = document.getElementById("category-select");
const manageCategoriesBtn = document.getElementById("manage-categories-btn");
const homeMenuBtn = document.getElementById("home-menu-btn");
const homeMenu = document.getElementById("home-menu");
const filterBadge = document.getElementById("filter-badge");
const refreshAllLabel = document.getElementById("refresh-all-label");
const randomSeriesBtn = document.getElementById("random-series-btn");
let libraryShown = []; // séries actuellement affichées dans la bibliothèque (donc déjà filtrées)
let libraryRequest = 0;
let lastLibraryText = null;
let librarySelecting = false; // mode sélection de séries (voir library-select.js)
let librarySelected = new Set();
const updatesRefreshBtn = document.getElementById("updates-refresh-btn");
const updatesRefreshStatus = document.getElementById("updates-refresh-status");
let searchDebounce = null;

// Liste des catégories dans la fenêtre des filtres. Si la catégorie active n'existe plus (supprimée), on la retire.
async function loadCategorySelect() {
  const res = await fetch("/api/categories");
  const categories = await res.json();
  if (activeCategoryId !== "" && !categories.some((c) => String(c.id) === String(activeCategoryId))) {
    activeCategoryId = "";
  }
  categorySelect.innerHTML = '<option value="">Toutes les catégories</option>';
  for (const c of categories) {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.name;
    categorySelect.appendChild(opt);
  }
  categorySelect.value = String(activeCategoryId);
  updateToolbarIndicators();
}

setupPopover(homeMenuBtn, homeMenu);

const emptyText = document.getElementById("empty-text");
const emptyAddBtn = document.getElementById("empty-add-btn");
emptyAddBtn.addEventListener("click", () => openAddModal());

randomSeriesBtn.addEventListener("click", () => {
  if (libraryShown.length === 0) {
    toast("Aucune série à ouvrir avec les filtres actuels.");
    return;
  }
  openChaptersView(libraryShown[Math.floor(Math.random() * libraryShown.length)].id);
});

manageCategoriesBtn.addEventListener("click", () => openSettingsPage("categories"));

searchToggleBtn.addEventListener("click", () => {
  searchBar.classList.toggle("hidden");
  if (!searchBar.classList.contains("hidden")) searchInput.focus();
});
filterToggleBtn.addEventListener("click", () => openModal(filterModal));
filterModalClose.addEventListener("click", () => closeModal(filterModal));

async function loadGenreSelect() {
  const res = await fetch("/api/genres");
  const genres = await res.json();
  const current = genreSelect.value;
  genreSelect.innerHTML = '<option value="">Tous les genres</option>';
  for (const g of genres) {
    const opt = document.createElement("option");
    opt.value = g;
    opt.textContent = g;
    genreSelect.appendChild(opt);
  }
  genreSelect.value = current;
}

async function loadStatuses() {
  const res = await fetch("/api/statuses");
  const statuses = await res.json();
  const current = statusSelect.value;
  statusSelect.innerHTML = '<option value="">Tous les statuts</option>';
  for (const s of statuses) {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s;
    statusSelect.appendChild(opt);
  }
  statusSelect.value = current;
}

// Loupe allumée si une recherche est en cours ; bouton de filtres allumé, avec le nombre de réglages actifs
// (catégorie, genre, statut, séries lues masquées, tri différent du tri par défaut).
function updateToolbarIndicators() {
  const active = [
    activeCategoryId !== "",
    sortSelect.value && sortSelect.value !== "last_checked_at",
    genreSelect.value,
    statusSelect.value,
    anilistFilterSelect.value,
    hideReadCheckbox.checked,
  ].filter(Boolean).length;
  filterToggleBtn.classList.toggle("active", active > 0);
  filterBadge.textContent = String(active);
  filterBadge.classList.toggle("hidden", active === 0);
  searchToggleBtn.classList.toggle("active", searchInput.value.trim() !== "");
}

function saveFilters() {
  const state = {
    sort: sortSelect.value,
    status: statusSelect.value,
    genre: genreSelect.value,
    anilist: anilistFilterSelect.value,
    hideRead: hideReadCheckbox.checked,
    search: searchInput.value,
    categoryId: activeCategoryId,
  };
  localStorage.setItem("stickscans_filters", JSON.stringify(state));
}

function getSavedFilters() {
  try {
    return JSON.parse(localStorage.getItem("stickscans_filters")) || {};
  } catch (e) {
    return {};
  }
}

async function loadLibrary() {
  updateToolbarIndicators();
  saveFilters();
  const params = new URLSearchParams({
    sort: sortSelect.value,
    hide_fully_read: hideReadCheckbox.checked,
  });
  if (activeCategoryId) params.set("category_id", activeCategoryId);
  if (genreSelect.value) params.set("genre", genreSelect.value);
  if (statusSelect.value) params.set("status", statusSelect.value);
  if (anilistFilterSelect.value) params.set("anilist", anilistFilterSelect.value);
  if (searchInput.value.trim()) params.set("search", searchInput.value.trim());

  // Premier affichage : des cartes vides qui pulsent pendant le chargement, plutôt qu'un écran noir.
  if (!grid.querySelector(".card")) {
    grid.innerHTML = '<div class="card skeleton"><div class="cover-wrap"></div><div class="info"><span></span><span></span></div></div>'.repeat(9);
  }
  const request = ++libraryRequest;
  const res = await fetch(`/api/series?${params}`);
  const text = await res.text();
  if (request !== libraryRequest) return; // une demande plus récente (frappe dans la recherche…) a pris le relais
  // Rien n'a changé depuis le dernier affichage (retour d'une fiche, onglet rouvert) : on ne redessine rien.
  if (text === lastLibraryText && grid.querySelector(".card:not(.skeleton)")) return;
  lastLibraryText = text;
  const series = JSON.parse(text);
  libraryShown = series;

  grid.innerHTML = "";
  emptyMsg.classList.toggle("hidden", series.length > 0);
  if (series.length === 0) {
    // Bibliothèque vide : on propose d'ajouter une série ; filtres trop stricts : on le dit.
    const filtered = Boolean(activeCategoryId || genreSelect.value || statusSelect.value || anilistFilterSelect.value || hideReadCheckbox.checked || searchInput.value.trim());
    emptyText.textContent = filtered ? "Aucune série ne correspond à ta recherche ou à tes filtres." : "Aucune série suivie pour l'instant.";
    emptyAddBtn.classList.toggle("hidden", filtered);
  }

  // En mode sélection, les séries qui ne sont plus affichées (filtre, recherche) sortent de la sélection.
  const shownIds = new Set(series.map((s) => s.id));
  librarySelected = new Set([...librarySelected].filter((id) => shownIds.has(id)));

  for (const s of series) {
    const card = document.createElement("div");
    card.className = "card" + (librarySelected.has(s.id) ? " selected" : "");
    card.dataset.id = s.id;
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `${s.title || "Sans titre"}${s.unread_count > 0 ? `, ${s.unread_count} chapitre${s.unread_count > 1 ? "s" : ""} non lu${s.unread_count > 1 ? "s" : ""}` : ""}`);
    card.innerHTML = `
      <div class="cover-wrap">
        <img src="${escapeHtml(s.cover_url)}" alt="" loading="lazy">
        <span class="select-mark" aria-hidden="true">${icon("check")}</span>
        <div class="badge-stack">
          ${s.unread_count > 0 ? `<span class="badge">${s.unread_count}</span>` : ""}
          ${s.last_error ? `<span class="badge badge-error" title="${escapeHtml(s.last_error)}">${icon("alert")}</span>` : ""}
        </div>
      </div>
      <div class="info">
        <div class="title">${escapeHtml(s.title || "Sans titre")}</div>
        <div class="chapter">${s.last_chapter_number ? "Ch. " + escapeHtml(s.last_chapter_number) : "?"}</div>
      </div>
    `;
    markCached(card);
    card.addEventListener("click", () => {
      if (librarySelecting) toggleLibrarySelection(s.id, card);
      else openChaptersView(s.id);
    });
    grid.appendChild(card);
  }
  if (librarySelecting) updateLibrarySelectionCount();
}

async function startRefreshAll() {
  const res = await fetch("/api/series/refresh-all", { method: "POST" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    toast(typeof data.detail === "string" ? data.detail : "Actualisation impossible pour l'instant.", "error", 6000);
    return;
  }
  pollRefreshStatus();
}
refreshAllBtn.addEventListener("click", startRefreshAll);
updatesRefreshBtn.addEventListener("click", startRefreshAll);

async function pollRefreshStatus() {
  refreshAllBtn.disabled = true;
  updatesRefreshBtn.disabled = true;
  updatesRefreshBtn.classList.add("busy");
  let status;
  try {
    status = await (await fetch("/api/refresh-status")).json();
  } catch (e) {
    status = { is_running: false }; // serveur injoignable : on arrête de suivre, les boutons redeviennent utilisables
  }

  if (status.is_running) {
    const pct = status.total > 0 ? Math.round((status.completed / status.total) * 100) : 0;
    const counter = status.total > 0 ? `${status.completed}/${status.total}` : "";
    refreshAllLabel.textContent = `Actualisation… ${pct} %`;
    refreshStatusText.textContent = counter;
    updatesRefreshStatus.textContent = counter;
    setTimeout(pollRefreshStatus, 1000);
  } else {
    refreshAllBtn.disabled = false;
    updatesRefreshBtn.disabled = false;
    updatesRefreshBtn.classList.remove("busy");
    refreshAllLabel.textContent = "Actualiser toutes les séries";
    refreshStatusText.textContent = "";
    updatesRefreshStatus.textContent = "";
    loadLibrary();
    // La page Mises à jour affichée pendant l'actualisation se met à jour toute seule à la fin.
    if (!document.getElementById("updates-view").classList.contains("hidden")) loadUpdates();
  }
}

fetch("/api/refresh-status").then((r) => r.json()).then((status) => {
  if (status.is_running) pollRefreshStatus();
});

categorySelect.addEventListener("change", () => {
  activeCategoryId = categorySelect.value;
  loadLibrary();
});
sortSelect.addEventListener("change", loadLibrary);
statusSelect.addEventListener("change", loadLibrary);
anilistFilterSelect.addEventListener("change", loadLibrary);
genreSelect.addEventListener("change", loadLibrary);
hideReadCheckbox.addEventListener("change", loadLibrary);
searchInput.addEventListener("input", () => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(loadLibrary, 300);
});

closeOnBackdrop(filterModal);
