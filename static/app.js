const navButtons = document.querySelectorAll(".nav-btn");
const libraryView = document.getElementById("library-view");
const updatesView = document.getElementById("updates-view");
const historyView = document.getElementById("history-view");
const settingsView = document.getElementById("settings-view");
const chaptersView = document.getElementById("chapters-view");
const topViews = {
  "library-view": libraryView,
  "updates-view": updatesView,
  "history-view": historyView,
  "settings-view": settingsView,
};

const grid = document.getElementById("grid");
const emptyMsg = document.getElementById("empty-msg");
const addBtn = document.getElementById("add-btn");
const addForm = document.getElementById("add-form");
const addUrl = document.getElementById("add-url");
const addCategoryCheckboxes = document.getElementById("add-category-checkboxes");
const addSubmit = document.getElementById("add-submit");
const addCancel = document.getElementById("add-cancel");
const addError = document.getElementById("add-error");
const anilistTokenInput = document.getElementById("anilist-token-input");
const anilistTokenSave = document.getElementById("anilist-token-save");
const anilistStatus = document.getElementById("anilist-status");
const manageCategoriesBtnSettings = document.getElementById("manage-categories-btn-settings");
const refreshAllBtn = document.getElementById("refresh-all-btn");
const refreshStatusText = document.getElementById("refresh-status-text");
const sortSelect = document.getElementById("sort-select");
const statusSelect = document.getElementById("status-select");
const genreSelect = document.getElementById("genre-select");
const hideReadCheckbox = document.getElementById("hide-read-checkbox");
const searchInput = document.getElementById("search-input");
const searchToggleBtn = document.getElementById("search-toggle-btn");
const searchBar = document.getElementById("search-bar");
const filterToggleBtn = document.getElementById("filter-toggle-btn");
const filterModal = document.getElementById("filter-modal");
const filterModalClose = document.getElementById("filter-modal-close");
const categoryTabs = document.getElementById("category-tabs");
const manageCategoriesBtn = document.getElementById("manage-categories-btn");

const categoryModal = document.getElementById("category-modal");
const categoryManageList = document.getElementById("category-manage-list");
const newCategoryInput = document.getElementById("new-category-input");
const newCategoryBtn = document.getElementById("new-category-btn");
const categoryModalClose = document.getElementById("category-modal-close");

const backBtn = document.getElementById("back-btn");
const recheckSeriesBtn = document.getElementById("recheck-series-btn");
const editSeriesBtn = document.getElementById("edit-series-btn");
const chaptersList = document.getElementById("chapters-list");
const selectModeBtn = document.getElementById("select-mode-btn");
const selectAllBtn = document.getElementById("select-all-btn");
const bulkReadBtn = document.getElementById("bulk-read-btn");
const bulkUnreadBtn = document.getElementById("bulk-unread-btn");
const removeSeriesBtn = document.getElementById("remove-series-btn");
const continueReadingBtn = document.getElementById("continue-reading-btn");

const detailCover = document.getElementById("detail-cover");
const detailTitle = document.getElementById("detail-title");
const detailAltNamesWrap = document.getElementById("detail-alt-names-wrap");
const detailAltNames = document.getElementById("detail-alt-names");
const altNamesToggle = document.getElementById("alt-names-toggle");
const detailMeta = document.getElementById("detail-meta");
const detailGenres = document.getElementById("detail-genres");
const detailAuthor = document.getElementById("detail-author");
const detailEditor = document.getElementById("detail-editor");
const detailTeam = document.getElementById("detail-team");
const detailSourceLink = document.getElementById("detail-source-link");
const anilistActionBtn = document.getElementById("anilist-action-btn");
const categoryActionBtn = document.getElementById("category-action-btn");
const seriesCategoryModal = document.getElementById("series-category-modal");
const seriesCategoryModalClose = document.getElementById("series-category-modal-close");
const anilistModal = document.getElementById("anilist-modal");
const anilistModalClose = document.getElementById("anilist-modal-close");
const anilistLinked = document.getElementById("anilist-linked");
const anilistLinkedTitle = document.getElementById("anilist-linked-title");
const anilistSearchInput = document.getElementById("anilist-search-input");
const anilistSearchBtn = document.getElementById("anilist-search-btn");
const anilistSearchResults = document.getElementById("anilist-search-results");
const anilistStatusSelect = document.getElementById("anilist-status-select");
const anilistProgressInput = document.getElementById("anilist-progress-input");
const anilistScoreInput = document.getElementById("anilist-score-input");
const anilistStartInput = document.getElementById("anilist-start-input");
const anilistEndInput = document.getElementById("anilist-end-input");
const anilistSaveBtn = document.getElementById("anilist-save-btn");
const anilistUnlinkBtn = document.getElementById("anilist-unlink-btn");
const anilistStatusText = document.getElementById("anilist-status-text");
const detailSynopsisWrap = document.getElementById("detail-synopsis-wrap");
const detailSynopsis = document.getElementById("detail-synopsis");
const synopsisToggle = document.getElementById("synopsis-toggle");
const categoryCheckboxes = document.getElementById("category-checkboxes");
const editForm = document.getElementById("edit-form");
const editTitleInput = document.getElementById("edit-title-input");
const editCoverInput = document.getElementById("edit-cover-input");
const editSaveBtn = document.getElementById("edit-save-btn");
const editCancelBtn = document.getElementById("edit-cancel-btn");

let currentSeriesId = null;
let activeCategoryId = "";
let searchDebounce = null;
let currentChapters = [];
let selectionMode = false;
let selectedChapterIds = new Set();

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function formatDateBucket(dateStr) {
  if (!dateStr) return "";
  const date = new Date(dateStr.replace(" ", "T") + "Z");
  const now = new Date();
  const diffDays = Math.floor((now - date) / 86400000);
  if (diffDays <= 0) return "Aujourd'hui";
  if (diffDays === 1) return "Hier";
  if (diffDays < 7) return "Cette semaine";
  if (diffDays < 30) return "Ce mois-ci";
  return "Plus ancien";
}

function goToTopView(viewId) {
  navButtons.forEach((b) => b.classList.toggle("active", b.dataset.view === viewId));
  Object.values(topViews).forEach((v) => v.classList.add("hidden"));
  chaptersView.classList.add("hidden");
  topViews[viewId].classList.remove("hidden");
}

navButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    goToTopView(btn.dataset.view);
    if (btn.dataset.view === "updates-view") loadUpdates();
    if (btn.dataset.view === "history-view") loadHistory();
    if (btn.dataset.view === "settings-view") loadSettingsAnilistStatus();
  });
});

async function loadSettingsAnilistStatus() {
  const res = await fetch("/api/settings/anilist");
  const status = await res.json();
  anilistStatus.textContent = status.configured
    ? "Jeton AniList déjà configuré."
    : "Aucun jeton configuré pour l'instant.";
}

function renderGroupedList(container, items, dateField, labelFn) {
  container.innerHTML = "";
  if (items.length === 0) {
    container.innerHTML = '<p class="empty-msg">Rien pour l\'instant.</p>';
    return;
  }
  let lastBucket = null;
  for (const item of items) {
    const bucket = formatDateBucket(item[dateField]);
    if (bucket !== lastBucket) {
      const h2 = document.createElement("h2");
      h2.className = "date-bucket";
      h2.textContent = bucket;
      container.appendChild(h2);
      lastBucket = bucket;
    }
    const row = document.createElement("div");
    row.className = "update-row";
    row.innerHTML = `
      <img src="${item.series_cover || ""}" alt="" loading="lazy">
      <span>${labelFn(item)}</span>
    `;
    row.addEventListener("click", () => {
      goToTopView("library-view");
      libraryView.classList.add("hidden");
      openChaptersView(item.series_id);
    });
    container.appendChild(row);
  }
}

async function loadUpdates() {
  const res = await fetch("/api/updates");
  const items = await res.json();
  renderGroupedList(
    document.getElementById("updates-list"),
    items,
    "discovered_at",
    (item) => `Chapitre ${escapeHtml(item.number)} de ${escapeHtml(item.series_title)}`
  );
}

async function loadHistory() {
  const [statsRes, itemsRes] = await Promise.all([fetch("/api/stats"), fetch("/api/history")]);
  const stats = await statsRes.json();
  const items = await itemsRes.json();

  const statsDiv = document.getElementById("history-stats");
  statsDiv.innerHTML = `
    <div class="stat-box"><strong>${stats.chapters_this_week}</strong><span>cette semaine</span></div>
    <div class="stat-box"><strong>${stats.chapters_this_month}</strong><span>ce mois-ci</span></div>
    <div class="stat-box"><strong>${stats.total_read}</strong><span>au total</span></div>
    ${stats.top_series_title ? `<div class="stat-box"><strong>${escapeHtml(stats.top_series_title)}</strong><span>${stats.top_series_count} chapitres · plus lue</span></div>` : ""}
  `;

  renderGroupedList(
    document.getElementById("history-list"),
    items,
    "read_at",
    (item) => `Chapitre ${escapeHtml(item.number)} de ${escapeHtml(item.series_title)}`
  );
}

document.getElementById("clear-history-btn").addEventListener("click", async () => {
  if (!confirm("Effacer tout l'historique de lecture ? (les chapitres restent marqués comme lus, seul l'historique disparaît)")) return;
  await fetch("/api/history", { method: "DELETE" });
  loadHistory();
});

async function loadCategoryTabs() {
  const res = await fetch("/api/categories");
  const categories = await res.json();
  categoryTabs.innerHTML = "";
  const allBtn = document.createElement("button");
  allBtn.textContent = "Tous";
  allBtn.className = "tab" + (activeCategoryId === "" ? " active" : "");
  allBtn.addEventListener("click", () => { activeCategoryId = ""; loadCategoryTabs(); loadLibrary(); });
  categoryTabs.appendChild(allBtn);
  for (const c of categories) {
    const btn = document.createElement("button");
    btn.textContent = c.name;
    btn.className = "tab" + (activeCategoryId === c.id ? " active" : "");
    btn.addEventListener("click", () => { activeCategoryId = c.id; loadCategoryTabs(); loadLibrary(); });
    categoryTabs.appendChild(btn);
  }
}

async function loadCategoryManageList() {
  const res = await fetch("/api/categories");
  const categories = await res.json();
  categoryManageList.innerHTML = "";
  for (const c of categories) {
    const li = document.createElement("li");
    li.className = "category-manage-row";
    li.innerHTML = `
      <input type="text" value="${escapeHtml(c.name)}" data-id="${c.id}">
      <button class="rename-cat-btn" data-id="${c.id}">✓</button>
      <button class="delete-cat-btn" data-id="${c.id}">🗑</button>
    `;
    categoryManageList.appendChild(li);
  }
  categoryManageList.querySelectorAll(".rename-cat-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const input = categoryManageList.querySelector(`input[data-id="${btn.dataset.id}"]`);
      await fetch(`/api/categories/${btn.dataset.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: input.value.trim() }),
      });
      loadCategoryTabs();
      if (currentSeriesId) loadSeriesCategories();
    });
  });
  categoryManageList.querySelectorAll(".delete-cat-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("Supprimer cette catégorie ?")) return;
      await fetch(`/api/categories/${btn.dataset.id}`, { method: "DELETE" });
      loadCategoryManageList();
      loadCategoryTabs();
      loadLibrary();
    });
  });
}

anilistTokenSave.addEventListener("click", async () => {
  const token = anilistTokenInput.value.trim();
  if (!token) return;
  await fetch("/api/settings/anilist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  anilistTokenInput.value = "";
  anilistStatus.textContent = "Jeton enregistré.";
});

manageCategoriesBtn.addEventListener("click", () => {
  categoryModal.classList.remove("hidden");
  loadCategoryManageList();
});
manageCategoriesBtnSettings.addEventListener("click", () => {
  categoryModal.classList.remove("hidden");
  loadCategoryManageList();
});
categoryModalClose.addEventListener("click", () => categoryModal.classList.add("hidden"));

searchToggleBtn.addEventListener("click", () => {
  searchBar.classList.toggle("hidden");
  if (!searchBar.classList.contains("hidden")) searchInput.focus();
});
filterToggleBtn.addEventListener("click", () => filterModal.classList.remove("hidden"));
filterModalClose.addEventListener("click", () => filterModal.classList.add("hidden"));
newCategoryBtn.addEventListener("click", async () => {
  const name = newCategoryInput.value.trim();
  if (!name) return;
  await fetch("/api/categories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  newCategoryInput.value = "";
  loadCategoryManageList();
  loadCategoryTabs();
});

async function loadAddCategoryCheckboxes() {
  const res = await fetch("/api/categories");
  const categories = await res.json();
  addCategoryCheckboxes.innerHTML = "";
  if (categories.length === 0) {
    addCategoryCheckboxes.innerHTML = '<span class="section-label">Aucune catégorie créée pour l\'instant.</span>';
    return;
  }
  addCategoryCheckboxes.innerHTML = '<span class="section-label">Catégorie(s) :</span>';
  for (const c of categories) {
    const label = document.createElement("label");
    label.className = "category-check-label";
    label.innerHTML = `<input type="checkbox" value="${c.id}"> ${escapeHtml(c.name)}`;
    addCategoryCheckboxes.appendChild(label);
  }
}

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

function saveFilters() {
  const state = {
    sort: sortSelect.value,
    status: statusSelect.value,
    genre: genreSelect.value,
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
  saveFilters();
  const params = new URLSearchParams({
    sort: sortSelect.value,
    hide_fully_read: hideReadCheckbox.checked,
  });
  if (activeCategoryId) params.set("category_id", activeCategoryId);
  if (genreSelect.value) params.set("genre", genreSelect.value);
  if (statusSelect.value) params.set("status", statusSelect.value);
  if (searchInput.value.trim()) params.set("search", searchInput.value.trim());

  const res = await fetch(`/api/series?${params}`);
  const series = await res.json();

  grid.innerHTML = "";
  emptyMsg.classList.toggle("hidden", series.length > 0);

  for (const s of series) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="cover-wrap">
        <img src="${s.cover_url || ""}" alt="" loading="lazy">
        <div class="badge-stack">
          ${s.unread_count > 0 ? `<span class="badge">${s.unread_count}</span>` : ""}
          ${s.last_error ? `<span class="badge badge-error" title="${escapeHtml(s.last_error)}">⚠️</span>` : ""}
        </div>
      </div>
      <div class="info">
        <div class="title">${escapeHtml(s.title || "Sans titre")}</div>
        <div class="chapter">${s.last_chapter_number ? "Ch. " + s.last_chapter_number : "?"}</div>
      </div>
    `;
    card.addEventListener("click", () => openChaptersView(s.id));
    grid.appendChild(card);
  }
}

async function openChaptersView(seriesId) {
  currentSeriesId = seriesId;
  selectionMode = false;
  selectedChapterIds.clear();
  selectModeBtn.textContent = "Sélectionner";
  selectAllBtn.classList.add("hidden");
  bulkReadBtn.classList.add("hidden");
  bulkUnreadBtn.classList.add("hidden");
  libraryView.classList.add("hidden");
  chaptersView.classList.remove("hidden");
  editForm.classList.add("hidden");
  seriesCategoryModal.classList.add("hidden");
  await loadSeriesDetail();
  await loadChapters();
}

async function loadSeriesDetail() {
  const res = await fetch(`/api/series/${currentSeriesId}`);
  const s = await res.json();
  detailCover.src = s.cover_url || "";
  detailTitle.textContent = s.title || "Sans titre";

  detailAltNames.textContent = s.alt_names ? "Aussi connu sous : " + s.alt_names : "";
  detailAltNamesWrap.classList.remove("expanded");
  altNamesToggle.classList.add("hidden");
  altNamesToggle.textContent = "voir plus";
  requestAnimationFrame(() => {
    if (detailAltNames.scrollWidth > detailAltNames.clientWidth) {
      altNamesToggle.classList.remove("hidden");
    }
  });

  detailMeta.textContent = [s.category, s.year, s.status].filter(Boolean).join(" · ");

  detailGenres.innerHTML = "";
  for (const g of s.genres || []) {
    const chip = document.createElement("span");
    chip.className = "genre-chip";
    chip.textContent = g;
    detailGenres.appendChild(chip);
  }

  detailAuthor.textContent = s.author ? "Auteur : " + s.author : "";
  detailEditor.textContent = s.editor ? "Éditeur : " + s.editor : "";
  detailTeam.textContent = s.team ? "Team trad : " + s.team : "";
  detailSourceLink.href = s.url;
  renderAnilistSection(s);

  detailSynopsis.textContent = s.synopsis || "";
  detailSynopsisWrap.classList.remove("expanded");
  synopsisToggle.classList.add("hidden");
  synopsisToggle.textContent = "voir plus";
  requestAnimationFrame(() => {
    if (detailSynopsis.scrollHeight > detailSynopsis.clientHeight + 2) {
      synopsisToggle.classList.remove("hidden");
    }
  });

  editTitleInput.value = s.title || "";
  editCoverInput.value = s.cover_url || "";
}

async function loadSeriesCategories() {
  const [allRes, seriesRes] = await Promise.all([
    fetch("/api/categories"),
    fetch(`/api/series/${currentSeriesId}`),
  ]);
  const allCategories = await allRes.json();
  const series = await seriesRes.json();
  const memberIds = new Set((series.categories || []).map((c) => c.id));

  categoryCheckboxes.innerHTML = "";
  if (allCategories.length === 0) {
    categoryCheckboxes.textContent = "Aucune catégorie créée (bouton ⚙ dans la bibliothèque).";
    return;
  }
  for (const c of allCategories) {
    const label = document.createElement("label");
    label.className = "category-check-label";
    label.innerHTML = `<input type="checkbox" ${memberIds.has(c.id) ? "checked" : ""}> ${escapeHtml(c.name)}`;
    label.querySelector("input").addEventListener("change", async (e) => {
      const method = e.target.checked ? "POST" : "DELETE";
      await fetch(`/api/series/${currentSeriesId}/categories/${c.id}`, { method });
    });
    categoryCheckboxes.appendChild(label);
  }
}

function updateContinueReadingButton() {
  const unread = currentChapters.filter((c) => !c.is_read).sort((a, b) => a.number_float - b.number_float);
  if (unread.length === 0) {
    continueReadingBtn.classList.add("hidden");
    return;
  }
  const next = unread[0];
  continueReadingBtn.textContent = `Continuer la lecture : Chapitre ${next.number}`;
  continueReadingBtn.classList.remove("hidden");
  continueReadingBtn.onclick = () => {
    window.open(next.url, "_blank");
    markReadUpTo(next.number);
  };
}

async function loadChapters() {
  const res = await fetch(`/api/series/${currentSeriesId}/chapters`);
  currentChapters = await res.json();
  updateContinueReadingButton();

  chaptersList.innerHTML = "";
  for (const c of currentChapters) {
    const li = document.createElement("li");
    const isSelected = selectedChapterIds.has(c.id);
    li.className = "chapter-row" + (c.is_read ? " read" : "") + (isSelected ? " selected" : "");

    if (selectionMode) {
      li.innerHTML = `
        <input type="checkbox" class="select-checkbox" ${isSelected ? "checked" : ""}>
        <span class="chapter-number">Chapitre ${escapeHtml(c.number)}</span>
      `;
      const cb = li.querySelector(".select-checkbox");
      cb.addEventListener("change", (e) => {
        if (e.target.checked) selectedChapterIds.add(c.id); else selectedChapterIds.delete(c.id);
        li.classList.toggle("selected", e.target.checked);
      });
      li.addEventListener("click", (e) => {
        if (e.target === cb) return;
        cb.checked = !cb.checked;
        cb.dispatchEvent(new Event("change"));
      });
    } else {
      li.innerHTML = `
        <input type="checkbox" class="chapter-checkbox" ${c.is_read ? "checked" : ""}>
        <span class="chapter-number">Chapitre ${escapeHtml(c.number)}</span>
      `;
      li.querySelector(".chapter-checkbox").addEventListener("click", async (e) => {
        e.stopPropagation();
        const isRead = e.target.checked;
        if (isRead) {
          const earlierUnread = currentChapters.some(
            (ch) => ch.number_float < c.number_float && !ch.is_read
          );
          if (earlierUnread) {
            const cascade = confirm(
              "Des chapitres précédents ne sont pas encore marqués comme lus. Les marquer aussi ?"
            );
            if (cascade) {
              await markReadUpTo(c.number);
              return;
            }
          }
        }
        await toggleChapterRead(c.id, isRead);
        li.classList.toggle("read", isRead);
        c.is_read = isRead;
        updateContinueReadingButton();
      });
      li.addEventListener("click", () => {
        window.open(c.url, "_blank");
        markReadUpTo(c.number);
      });
    }
    chaptersList.appendChild(li);
  }
}

async function toggleChapterRead(chapterId, isRead) {
  await fetch(`/api/chapters/${chapterId}/toggle-read`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_read: isRead }),
  });
}

async function markReadUpTo(number) {
  await fetch(`/api/series/${currentSeriesId}/mark-read-up-to`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ number: String(number) }),
  });
  loadChapters();
}

selectModeBtn.addEventListener("click", () => {
  selectionMode = !selectionMode;
  selectedChapterIds.clear();
  selectModeBtn.textContent = selectionMode ? "Annuler la sélection" : "Sélectionner";
  selectAllBtn.classList.toggle("hidden", !selectionMode);
  bulkReadBtn.classList.toggle("hidden", !selectionMode);
  bulkUnreadBtn.classList.toggle("hidden", !selectionMode);
  loadChapters();
});

selectAllBtn.addEventListener("click", () => {
  if (selectedChapterIds.size === currentChapters.length) {
    selectedChapterIds.clear();
  } else {
    selectedChapterIds = new Set(currentChapters.map((c) => c.id));
  }
  loadChapters();
});

async function bulkSetRead(isRead) {
  if (selectedChapterIds.size === 0) return;
  await fetch("/api/chapters/bulk-read", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chapter_ids: [...selectedChapterIds], is_read: isRead }),
  });
  selectedChapterIds.clear();
  selectionMode = false;
  selectModeBtn.textContent = "Sélectionner";
  selectAllBtn.classList.add("hidden");
  bulkReadBtn.classList.add("hidden");
  bulkUnreadBtn.classList.add("hidden");
  loadChapters();
}

bulkReadBtn.addEventListener("click", () => bulkSetRead(true));
bulkUnreadBtn.addEventListener("click", () => bulkSetRead(false));

recheckSeriesBtn.addEventListener("click", async () => {
  recheckSeriesBtn.disabled = true;
  recheckSeriesBtn.textContent = "...";
  await fetch(`/api/series/${currentSeriesId}/recheck`, { method: "POST" });
  await loadSeriesDetail();
  await loadChapters();
  recheckSeriesBtn.disabled = false;
  recheckSeriesBtn.textContent = "↻ Actualiser";
});

removeSeriesBtn.addEventListener("click", async () => {
  if (!confirm("Retirer cette série de la bibliothèque ?")) return;
  await fetch(`/api/series/${currentSeriesId}`, { method: "DELETE" });
  backToLibrary();
});

function backToLibrary() {
  chaptersView.classList.add("hidden");
  goToTopView("library-view");
  currentSeriesId = null;
  loadLibrary();
}

backBtn.addEventListener("click", backToLibrary);

altNamesToggle.addEventListener("click", () => {
  const expanded = detailAltNamesWrap.classList.toggle("expanded");
  altNamesToggle.textContent = expanded ? "voir moins" : "voir plus";
});

synopsisToggle.addEventListener("click", () => {
  const expanded = detailSynopsisWrap.classList.toggle("expanded");
  synopsisToggle.textContent = expanded ? "voir moins" : "voir plus";
});

editSeriesBtn.addEventListener("click", () => editForm.classList.toggle("hidden"));
editCancelBtn.addEventListener("click", () => editForm.classList.add("hidden"));

function renderAnilistSection(s) {
  if (s.anilist_id) {
    anilistActionBtn.textContent = "✓ " + (s.anilist_title || "AniList");
    anilistActionBtn.classList.add("linked");
    anilistActionBtn.dataset.linked = "1";
    anilistLinkedTitle.textContent = s.anilist_title || s.anilist_id;
    anilistStatusSelect.value = s.anilist_status || "CURRENT";
    anilistProgressInput.value = s.anilist_progress ?? "";
    anilistScoreInput.value = s.anilist_score ?? "";
    anilistStartInput.value = s.anilist_start_date || "";
    anilistEndInput.value = s.anilist_end_date || "";
    anilistStatusText.textContent = s.anilist_last_error ? "⚠️ " + s.anilist_last_error : "";
  } else {
    anilistActionBtn.textContent = "🔗 AniList";
    anilistActionBtn.classList.remove("linked");
    anilistActionBtn.dataset.linked = "";
    anilistSearchResults.innerHTML = "";
    anilistSearchInput.value = s.title || "";
  }
  // Repliée par défaut à chaque (re)chargement de la fiche.
  anilistLinked.classList.add("hidden");
}

anilistActionBtn.addEventListener("click", () => {
  if (anilistActionBtn.dataset.linked === "1") {
    anilistLinked.classList.toggle("hidden");
  } else {
    anilistModal.classList.remove("hidden");
  }
});
anilistModalClose.addEventListener("click", () => anilistModal.classList.add("hidden"));

categoryActionBtn.addEventListener("click", () => {
  seriesCategoryModal.classList.remove("hidden");
  loadSeriesCategories();
});
seriesCategoryModalClose.addEventListener("click", () => seriesCategoryModal.classList.add("hidden"));

anilistSearchBtn.addEventListener("click", async () => {
  const q = anilistSearchInput.value.trim();
  if (!q) return;
  anilistSearchBtn.disabled = true;
  anilistSearchBtn.textContent = "...";
  try {
    const res = await fetch(`/api/anilist/search?q=${encodeURIComponent(q)}`);
    const results = await res.json();
    anilistSearchResults.innerHTML = "";
    for (const r of results) {
      const li = document.createElement("li");
      li.className = "anilist-result-row";
      li.innerHTML = `
        <img src="${r.cover_url || ""}" alt="" loading="lazy">
        <span>${escapeHtml(r.title)}${r.year ? " (" + r.year + ")" : ""}</span>
      `;
      li.addEventListener("click", async () => {
        const linkRes = await fetch(`/api/series/${currentSeriesId}/anilist/link`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ anilist_id: r.id, title: r.title }),
        });
        const data = await linkRes.json();
        renderAnilistSection(data);
        anilistModal.classList.add("hidden");
      });
      anilistSearchResults.appendChild(li);
    }
  } finally {
    anilistSearchBtn.disabled = false;
    anilistSearchBtn.textContent = "Rechercher";
  }
});

anilistSaveBtn.addEventListener("click", async () => {
  anilistSaveBtn.disabled = true;
  try {
    const res = await fetch(`/api/series/${currentSeriesId}/anilist/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: anilistStatusSelect.value,
        progress: anilistProgressInput.value !== "" ? parseInt(anilistProgressInput.value, 10) : null,
        score: anilistScoreInput.value !== "" ? parseFloat(anilistScoreInput.value) : null,
        start_date: anilistStartInput.value || null,
        end_date: anilistEndInput.value || null,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur inconnue");
    renderAnilistSection(data);
    if (!data.anilist_last_error) anilistStatusText.textContent = "Enregistré ✓";
  } catch (e) {
    anilistStatusText.textContent = "⚠️ " + e.message;
  } finally {
    anilistSaveBtn.disabled = false;
  }
});

anilistUnlinkBtn.addEventListener("click", async () => {
  if (!confirm("Délier cette série d'AniList ?")) return;
  const res = await fetch(`/api/series/${currentSeriesId}/anilist`, { method: "DELETE" });
  const data = await res.json();
  renderAnilistSection(data);
});

editSaveBtn.addEventListener("click", async () => {
  await fetch(`/api/series/${currentSeriesId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: editTitleInput.value, cover_url: editCoverInput.value }),
  });
  editForm.classList.add("hidden");
  loadSeriesDetail();
});

refreshAllBtn.addEventListener("click", async () => {
  await fetch("/api/series/refresh-all", { method: "POST" });
  pollRefreshStatus();
});

async function pollRefreshStatus() {
  refreshAllBtn.disabled = true;
  const res = await fetch("/api/refresh-status");
  const status = await res.json();

  if (status.is_running) {
    const pct = status.total > 0 ? Math.round((status.completed / status.total) * 100) : 0;
    refreshAllBtn.textContent = `${pct}%`;
    refreshStatusText.textContent = status.total > 0 ? `${status.completed}/${status.total}` : "";
    setTimeout(pollRefreshStatus, 1000);
  } else {
    refreshAllBtn.disabled = false;
    refreshAllBtn.textContent = "↻";
    refreshStatusText.textContent = "";
    loadLibrary();
  }
}

fetch("/api/refresh-status").then((r) => r.json()).then((status) => {
  if (status.is_running) pollRefreshStatus();
});

sortSelect.addEventListener("change", loadLibrary);
statusSelect.addEventListener("change", loadLibrary);
genreSelect.addEventListener("change", loadLibrary);
hideReadCheckbox.addEventListener("change", loadLibrary);
searchInput.addEventListener("input", () => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(loadLibrary, 300);
});

addBtn.addEventListener("click", () => {
  addForm.classList.toggle("hidden");
  addError.classList.add("hidden");
  if (!addForm.classList.contains("hidden")) loadAddCategoryCheckboxes();
});

addCancel.addEventListener("click", () => {
  addForm.classList.add("hidden");
  addUrl.value = "";
});

const addSummary = document.getElementById("add-summary");

addSubmit.addEventListener("click", async () => {
  const urls = addUrl.value.split("\n").map((u) => u.trim()).filter(Boolean);
  if (urls.length === 0) return;
  const categoryIds = [...addCategoryCheckboxes.querySelectorAll("input:checked")].map((i) => parseInt(i.value, 10));

  addSubmit.disabled = true;
  addError.classList.add("hidden");
  addSummary.classList.add("hidden");

  let success = 0;
  const failures = [];

  for (let i = 0; i < urls.length; i++) {
    addSubmit.textContent = urls.length > 1 ? `Ajout ${i + 1}/${urls.length}...` : "Ajout...";
    try {
      const res = await fetch("/api/series", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: urls[i], category_ids: categoryIds }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Erreur inconnue");
      success++;
    } catch (e) {
      failures.push(`${urls[i]} : ${e.message}`);
    }
  }

  addSubmit.disabled = false;
  addSubmit.textContent = "Ajouter";

  if (failures.length === 0) {
    addUrl.value = "";
    addForm.classList.add("hidden");
  } else {
    addSummary.textContent = `${success} ajoutée(s), ${failures.length} échec(s) :\n` + failures.join("\n");
    addSummary.classList.remove("hidden");
  }

  loadGenreSelect();
  loadStatuses();
  loadCategoryTabs();
  loadLibrary();
});

async function init() {
  const saved = getSavedFilters();
  if (saved.sort) sortSelect.value = saved.sort;
  if (saved.search) searchInput.value = saved.search;
  if (saved.hideRead) hideReadCheckbox.checked = saved.hideRead;
  if (saved.categoryId) activeCategoryId = saved.categoryId;

  await loadGenreSelect();
  await loadStatuses();
  if (saved.genre) genreSelect.value = saved.genre;
  if (saved.status) statusSelect.value = saved.status;

  await loadCategoryTabs();
  await loadLibrary();

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
}

init();