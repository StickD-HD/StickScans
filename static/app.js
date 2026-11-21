// --- Authentification : si la session expire, on renvoie vers la page de connexion ---
const _originalFetch = window.fetch.bind(window);
window.fetch = async (...args) => {
  const res = await _originalFetch(...args);
  if (res.status === 401 && !String(args[0]).startsWith("/api/auth/")) {
    location.href = "/login?next=" + encodeURIComponent(location.pathname + location.search);
  }
  return res;
};

const authSection = document.getElementById("auth-section");
const logoutBtn = document.getElementById("logout-btn");
_originalFetch("/api/auth/status")
  .then((r) => r.json())
  .then((status) => { if (status.enabled && authSection) authSection.classList.remove("hidden"); })
  .catch(() => {});
if (logoutBtn) {
  logoutBtn.addEventListener("click", async () => {
    await _originalFetch("/api/auth/logout", { method: "POST" });
    location.href = "/login";
  });
}

const navButtons = document.querySelectorAll(".nav-btn");
const libraryView = document.getElementById("library-view");
const updatesView = document.getElementById("updates-view");
const historyView = document.getElementById("history-view");
const settingsView = document.getElementById("settings-view");
const chaptersView = document.getElementById("chapters-view");
const checksView = document.getElementById("checks-view");
const topViews = {
  "library-view": libraryView,
  "updates-view": updatesView,
  "history-view": historyView,
  "settings-view": settingsView,
  "checks-view": checksView, // ouvert depuis Réglages, pas dans la barre du bas
};

const grid = document.getElementById("grid");
const emptyMsg = document.getElementById("empty-msg");
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

const anilistConnected = document.getElementById("anilist-connected");
const anilistConnectForm = document.getElementById("anilist-connect-form");
const anilistAvatar = document.getElementById("anilist-avatar");
const anilistUsername = document.getElementById("anilist-username");
const anilistExpiry = document.getElementById("anilist-expiry");
const anilistTokenAlert = document.getElementById("anilist-token-alert");
const anilistCheckBtn = document.getElementById("anilist-check-btn");
const anilistChangeBtn = document.getElementById("anilist-change-btn");
const anilistDisconnectBtn = document.getElementById("anilist-disconnect-btn");
const anilistHelp = document.getElementById("anilist-help");
const anilistRedirectUrl = document.getElementById("anilist-redirect-url");
const anilistCopyRedirect = document.getElementById("anilist-copy-redirect");
const anilistClientIdInput = document.getElementById("anilist-client-id-input");
const anilistAuthorizeLink = document.getElementById("anilist-authorize-link");
const anilistTokenInput = document.getElementById("anilist-token-input");
const anilistTokenError = document.getElementById("anilist-token-error");
const anilistTokenSave = document.getElementById("anilist-token-save");
const anilistTokenCancel = document.getElementById("anilist-token-cancel");
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
const categorySelect = document.getElementById("category-select");
const manageCategoriesBtn = document.getElementById("manage-categories-btn");
const homeMenuBtn = document.getElementById("home-menu-btn");
const homeMenu = document.getElementById("home-menu");
const filterBadge = document.getElementById("filter-badge");
const refreshAllLabel = document.getElementById("refresh-all-label");
const randomSeriesBtn = document.getElementById("random-series-btn");
let libraryShown = []; // séries actuellement affichées dans la bibliothèque (donc déjà filtrées)

const categoryManageList = document.getElementById("category-manage-list");
const newCategoryInput = document.getElementById("new-category-input");
const newCategoryBtn = document.getElementById("new-category-btn");

const backBtn = document.getElementById("back-btn");
const recheckSeriesBtn = document.getElementById("recheck-series-btn");
const chaptersList = document.getElementById("chapters-list");
const selectModeBtn = document.getElementById("select-mode-btn");
const selectAllBtn = document.getElementById("select-all-btn");
const bulkReadBtn = document.getElementById("bulk-read-btn");
const bulkUnreadBtn = document.getElementById("bulk-unread-btn");
const removeSeriesBtn = document.getElementById("remove-series-btn");
const continueReadingBtn = document.getElementById("continue-reading-btn");

const detailCover = document.getElementById("detail-cover");
const detailTitle = document.getElementById("detail-title");
const detailSourceBtn = document.getElementById("detail-source-btn");
const updatesRefreshBtn = document.getElementById("updates-refresh-btn");
const updatesRefreshStatus = document.getElementById("updates-refresh-status");
const detailMeta = document.getElementById("detail-meta");
const detailGenres = document.getElementById("detail-genres");
const detailAuthor = document.getElementById("detail-author");
const detailEditor = document.getElementById("detail-editor");
const detailTeam = document.getElementById("detail-team");
const detailNextCheck = document.getElementById("detail-next-check");
const CHECK_REASON_LABELS = {
  between: "entre deux sorties",
  window: "sortie attendue",
  late: "sortie en retard",
  dormant: "série probablement en pause",
  error: "après une erreur",
};
const detailSourceLink = document.getElementById("detail-source-link");
const anilistActionBtn = document.getElementById("anilist-action-btn");
const libraryBtn = document.getElementById("library-btn");
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
const detailMenuBtn = document.getElementById("detail-menu-btn");
const detailMenu = document.getElementById("detail-menu");
const categoryMenuBtn = document.getElementById("category-menu-btn");
const resetProgressBtn = document.getElementById("reset-progress-btn");
const chaptersToolbar = document.getElementById("chapters-toolbar");
const selectCancelBtn = document.getElementById("select-cancel-btn");

let currentSeriesId = null;
let activeCategoryId = "";
let searchDebounce = null;
let currentChapters = [];
let currentAnilistProgress = null; // progression AniList de la série ouverte (null = non liée)
let selectionMode = false;
let selectedChapterIds = new Set();
let lastTopView = "library-view";
let viewBeforeDetail = "library-view";
let scrollBeforeDetail = 0;

// --- Navigation « retour » ---
// Chaque écran secondaire (fiche série, popups) est une « couche » liée à une entrée d'historique :
// le geste retour d'Android, le balayage depuis le bord sur iOS et le bouton « Retour » ferment
// tous la couche du dessus. close() ne touche qu'à l'affichage.
const layers = [];
let lastPopAt = 0;

function pushLayer(layer) {
  layers.push(layer);
  history.pushState({ layer: layers.length }, "");
}

window.addEventListener("popstate", (e) => {
  lastPopAt = Date.now();
  const depth = (e.state && e.state.layer) || 0;
  while (layers.length > depth) layers.pop().close();
});

function openModal(el) {
  if (!el.classList.contains("hidden")) return;
  el.classList.remove("hidden");
  pushLayer({ el, close: () => el.classList.add("hidden") });
}

function closeModal(el) {
  const top = layers[layers.length - 1];
  if (top && top.el === el) history.back();
  else el.classList.add("hidden");
}

[filterModal, anilistModal, seriesCategoryModal].forEach((m) => {
  m.addEventListener("click", (e) => { if (e.target === m) closeModal(m); });
});

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatDateBucket(dateStr) {
  if (!dateStr) return "";
  const date = new Date(dateStr.replace(" ", "T") + "Z");
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diffDays = Math.round((startOfDay(new Date()) - startOfDay(date)) / 86400000);
  if (diffDays <= 0) return "Aujourd'hui";
  if (diffDays === 1) return "Hier";
  if (diffDays < 7) return "Cette semaine";
  if (diffDays < 30) return "Ce mois-ci";
  return "Plus ancien";
}

function formatTimeLabel(dateStr) {
  if (!dateStr) return "";
  const date = new Date(dateStr.replace(" ", "T") + "Z");
  const time = `${date.getHours()}h${String(date.getMinutes()).padStart(2, "0")}`;
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diffDays = Math.round((startOfDay(new Date()) - startOfDay(date)) / 86400000);
  if (diffDays <= 1) return `à ${time}`; // le titre de section dit déjà "Aujourd'hui" ou "Hier"
  if (diffDays < 7) return `${date.toLocaleDateString("fr-FR", { weekday: "long" })} à ${time}`;
  return `${date.toLocaleDateString("fr-FR", { day: "numeric", month: "short" })} à ${time}`;
}

// Date à venir (UTC, format SQLite) : « aujourd'hui à 15h20 », « demain à 3h05 », « mardi à 9h00 », « 12 déc. à 9h00 ».
function formatFuture(dateStr) {
  const date = new Date(dateStr.replace(" ", "T") + "Z");
  const time = `${date.getHours()}h${String(date.getMinutes()).padStart(2, "0")}`;
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diffDays = Math.round((startOfDay(date) - startOfDay(new Date())) / 86400000);
  if (date <= new Date()) return "dès que possible";
  if (diffDays === 0) return `aujourd'hui à ${time}`;
  if (diffDays === 1) return `demain à ${time}`;
  if (diffDays < 7) return `${date.toLocaleDateString("fr-FR", { weekday: "long" })} à ${time}`;
  return `${date.toLocaleDateString("fr-FR", { day: "numeric", month: "short" })} à ${time}`;
}

function formatWait(seconds) {
  const m = Math.ceil(Math.max(0, seconds) / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  return m % 60 ? `${h} h ${String(m % 60).padStart(2, "0")}` : `${h} h`;
}

// Phrase d'état du site, ou "" si les requêtes peuvent partir normalement.
function sitePauseText(st) {
  if (st.blocked) return `Le site a refusé les requêtes : pause encore ${formatWait(st.remaining_seconds)} (refus n° ${st.strikes}). Aucune requête n'est envoyée pendant ce temps.`;
  if (st.quota_reached) return `Limite de ${st.daily_limit} requêtes par jour atteinte : les vérifications reprennent demain.`;
  if (!st.auto_enabled) return "Vérifications automatiques désactivées (Réglages › Mises à jour).";
  return "";
}

function goToTopView(viewId) {
  lastTopView = viewId;
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
    if (btn.dataset.view === "settings-view") showSettingsPage(null);
  });
});

let anilistEditing = false;
let anilistStatusCache = null;

function updateAuthorizeLink() {
  const id = anilistClientIdInput.value.trim();
  const valid = /^\d+$/.test(id);
  anilistAuthorizeLink.classList.toggle("disabled", !valid);
  if (valid) {
    anilistAuthorizeLink.href = `https://anilist.co/api/v2/oauth/authorize?client_id=${id}&response_type=token`;
  } else {
    anilistAuthorizeLink.removeAttribute("href");
  }
}

function showAnilistTokenError(message) {
  anilistTokenError.textContent = message || "";
  anilistTokenError.classList.toggle("hidden", !message);
}

function renderAnilistSettings(status) {
  anilistStatusCache = status;
  const connected = status.configured && !anilistEditing;
  anilistConnected.classList.toggle("hidden", !connected);
  anilistConnectForm.classList.toggle("hidden", connected);
  anilistTokenCancel.classList.toggle("hidden", !(status.configured && anilistEditing));
  showAnilistTokenError("");
  if (status.client_id && !anilistClientIdInput.value) anilistClientIdInput.value = status.client_id;
  updateAuthorizeLink();
  anilistHelp.open = !status.configured;
  if (!status.configured) return;

  anilistUsername.textContent = status.name || "Compte connecté";
  if (status.avatar) {
    anilistAvatar.src = status.avatar;
    anilistAvatar.classList.remove("hidden");
  } else {
    anilistAvatar.classList.add("hidden");
  }

  let expiryText = "Date d'expiration inconnue";
  let warn = false;
  if (status.expired) {
    expiryText = "Jeton expiré";
    warn = true;
  } else if (status.expires_at) {
    const date = new Date(status.expires_at + "T00:00:00Z").toLocaleDateString("fr-FR", {
      day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
    });
    expiryText = `Valable jusqu'au ${date} (${status.days_left} j)`;
    warn = status.days_left <= 30;
  }
  anilistExpiry.textContent = expiryText;
  anilistExpiry.classList.toggle("warn", warn);

  const alertText = status.error || (status.expired ? "Ton jeton a expiré : génère-en un nouveau." : "");
  anilistTokenAlert.textContent = alertText ? "⚠️ " + alertText : "";
  anilistTokenAlert.classList.toggle("hidden", !alertText);
}

async function loadSettingsAnilistStatus() {
  anilistEditing = false;
  try {
    const res = await fetch("/api/settings/anilist");
    renderAnilistSettings(await res.json());
  } catch (e) {
    anilistConnected.classList.add("hidden");
  }
}

function renderGroupedList(container, items, dateField, labelFn, showTime = false) {
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
      <img src="${escapeHtml(item.series_cover)}" alt="" loading="lazy">
      <span>${labelFn(item)}${showTime ? `<small class="update-time">${formatTimeLabel(item[dateField])}</small>` : ""}</span>
    `;
    row.addEventListener("click", () => openChaptersView(item.series_id));
    container.appendChild(row);
  }
}

async function loadUpdates() {
  fetch("/api/site-status").then((r) => r.json()).then((st) => {
    const banner = document.getElementById("updates-pause-banner");
    const text = sitePauseText(st);
    banner.textContent = text ? "⏸ " + text : "";
    banner.classList.toggle("hidden", !text);
  }).catch(() => {});
  const res = await fetch("/api/updates");
  const items = await res.json();
  renderGroupedList(
    document.getElementById("updates-list"),
    items,
    "discovered_at",
    (item) => `Chapitre ${escapeHtml(item.number)} de ${escapeHtml(item.series_title)}`,
    true
  );
}

// Regroupe les lectures d'une même série faites à moins de 30 min d'écart (une "session").
function groupHistory(items) {
  const parse = (s) => new Date(s.replace(" ", "T") + "Z").getTime();
  const groups = [];
  for (const item of items) {
    const last = groups[groups.length - 1];
    const lastTime = last ? parse(last.chapters[last.chapters.length - 1].read_at) : 0;
    if (last && last.series_id === item.series_id && lastTime - parse(item.read_at) <= 30 * 60 * 1000) {
      last.chapters.push(item);
    } else {
      groups.push({ series_id: item.series_id, series_title: item.series_title, series_cover: item.series_cover, read_at: item.read_at, chapters: [item] });
    }
  }
  return groups;
}

function renderHistoryList(container, items) {
  container.innerHTML = "";
  if (items.length === 0) {
    container.innerHTML = '<p class="empty-msg">Rien pour l\'instant.</p>';
    return;
  }
  let lastBucket = null;
  for (const group of groupHistory(items)) {
    const bucket = formatDateBucket(group.read_at);
    if (bucket !== lastBucket) {
      const h2 = document.createElement("h2");
      h2.className = "date-bucket";
      h2.textContent = bucket;
      container.appendChild(h2);
      lastBucket = bucket;
    }
    const numbers = group.chapters.map((c) => c.number_float);
    const first = group.chapters.find((c) => c.number_float === Math.min(...numbers));
    const lastCh = group.chapters.find((c) => c.number_float === Math.max(...numbers));
    const count = group.chapters.length;
    const label = count === 1
      ? `Chapitre ${escapeHtml(first.number)} de ${escapeHtml(group.series_title)}`
      : `Chapitres ${escapeHtml(first.number)} à ${escapeHtml(lastCh.number)} de ${escapeHtml(group.series_title)}`;
    const row = document.createElement("div");
    row.className = "update-row";
    row.innerHTML = `
      <img src="${escapeHtml(group.series_cover)}" alt="" loading="lazy">
      <span>${label}${count > 1 ? `<small class="update-time">${count} chapitres</small>` : ""}</span>
      <button class="history-remove-btn" title="Retirer de l'historique" aria-label="Retirer de l'historique">✕</button>
    `;
    row.addEventListener("click", () => openChaptersView(group.series_id));
    row.querySelector(".history-remove-btn").addEventListener("click", async (e) => {
      e.stopPropagation();
      const msg = count === 1
        ? "Retirer ce chapitre de l'historique ? (il reste marqué comme lu)"
        : `Retirer ces ${count} chapitres de l'historique ? (ils restent marqués comme lus)`;
      if (!confirm(msg)) return;
      await fetch("/api/history/remove", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chapter_ids: group.chapters.map((c) => c.chapter_id) }),
      });
      loadHistory();
    });
    container.appendChild(row);
  }
}

// --- Journal des vérifications (Réglages > Voir le journal) ---

function fmtDuration(sec) {
  if (sec == null) return "—";
  if (sec < 60) return `${sec.toFixed(1).replace(".", ",")} s`;
  const m = Math.floor(sec / 60), s = Math.round(sec % 60);
  if (m < 60) return `${m} min ${String(s).padStart(2, "0")} s`;
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`;
}

function formatWhen(dateStr) {
  const label = formatTimeLabel(dateStr); // "à 15h07" | "jeudi à 8h05" | "12 sept. à 11h00"
  if (!label.startsWith("à ")) return label;
  const date = new Date(dateStr.replace(" ", "T") + "Z");
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diffDays = Math.round((startOfDay(new Date()) - startOfDay(date)) / 86400000);
  return (diffDays === 0 ? "Aujourd'hui " : "Hier ") + label;
}

const TRIGGER_LABELS = { auto: "Auto", manuel: "Manuel", "série": "1 série" };

function renderChecksSummary(s) {
  const last = s.last_run;
  const errClass = s.errors_24h > 0 ? " warn" : "";
  document.getElementById("checks-summary").innerHTML = `
    <div class="stat-box"><strong>${last ? fmtDuration(last.duration_seconds) : "—"}</strong><span>dernière vérification${last && last.status !== "terminée" ? " (" + last.status + ")" : ""}</span></div>
    <div class="stat-box"><strong>${fmtDuration(s.avg_run_seconds)}</strong><span>durée moyenne (auto)</span></div>
    <div class="stat-box"><strong>${fmtDuration(s.avg_series_seconds)}</strong><span>par série, en moyenne</span></div>
    <div class="stat-box${errClass}"><strong>${s.errors_24h} / ${s.checks_24h}</strong><span>erreurs sur 24 h</span></div>
    ${s.from_cache_24h > 0 ? `<div class="stat-box"><strong>${s.from_cache_24h}</strong><span>reprises d'une copie (24 h), site non sollicité</span></div>` : ""}
  `;
  const runs = s.recent_runs;
  let extra = "";
  if (runs.length) {
    const max = Math.max(...runs.map((r) => r.duration_seconds), 1);
    const bars = runs.map((r) => {
      const h = Math.max(4, Math.round((r.duration_seconds / max) * 44));
      const tip = `${formatWhen(r.started_at)} · ${fmtDuration(r.duration_seconds)}${r.error_count ? " · " + r.error_count + " erreur(s)" : ""}`;
      return `<div class="run-col" title="${escapeHtml(tip)}"><i class="${r.error_count ? "err" : "on"}" style="height:${h}px"></i></div>`;
    }).join("");
    extra += `<div class="week-chart"><div class="week-title">Durée des ${runs.length} dernières vérifications automatiques · max ${fmtDuration(max)}</div><div class="run-bars">${bars}</div></div>`;
  }
  if (s.slowest_series.length) {
    extra += `<div class="week-chart"><div class="week-title">Séries les plus lentes · 7 derniers jours</div>` +
      s.slowest_series.map((x) => `<div class="slow-row"><span>${escapeHtml(x.series_title)}</span><b>${fmtDuration(x.avg_seconds)}</b></div>`).join("") + `</div>`;
  }
  document.getElementById("checks-extra").innerHTML = extra;
}

function renderChecksList(runs) {
  const list = document.getElementById("checks-list");
  list.innerHTML = "";
  if (!runs.length) {
    list.innerHTML = '<p class="empty-msg">Aucune vérification enregistrée pour l\'instant. Elles apparaîtront ici dès la prochaine.</p>';
    return;
  }
  for (const run of runs) {
    const row = document.createElement("div");
    row.className = "run-row";
    // « interrompue » avec une durée = coupée par un refus du site (compteurs connus) ;
    // sans durée = coupée par un redémarrage de l'appli.
    const finished = run.status === "terminée" || (run.status === "interrompue" && run.duration_seconds != null);
    const state = finished
      ? `${run.status === "interrompue" ? '<em class="warn-text">interrompue (site)</em> · ' : ""}${fmtDuration(run.duration_seconds)} · ${run.ok_count} OK${run.error_count ? ` · <em class="warn-text">${run.error_count} erreur${run.error_count > 1 ? "s" : ""}</em>` : ""}${run.new_chapters ? ` · ${run.new_chapters} nouveau${run.new_chapters > 1 ? "x" : ""}` : ""}`
      : `<em class="warn-text">${escapeHtml(run.status)}</em>`;
    row.innerHTML = `
      <div class="run-head">
        <div><strong>${formatWhen(run.started_at)}</strong><small class="update-time">${state}</small></div>
        <span class="run-badge">${TRIGGER_LABELS[run.trigger] || run.trigger}</span>
      </div>
      <div class="run-detail hidden"></div>
    `;
    const detail = row.querySelector(".run-detail");
    row.querySelector(".run-head").addEventListener("click", async () => {
      const nowHidden = detail.classList.toggle("hidden");
      if (!nowHidden && !detail.dataset.loaded) {
        detail.textContent = "Chargement…";
        const res = await fetch(`/api/checks/${run.id}`);
        detail.innerHTML = renderRunDetail(await res.json());
        detail.dataset.loaded = "1";
      }
    });
    list.appendChild(row);
  }
}

function renderRunDetail(run) {
  const cached = run.items.filter((i) => i.source === "cache").length;
  const busy = run.items.reduce((sum, i) => sum + (i.duration_seconds || 0), 0);
  const pauses = run.status === "terminée" && run.total > 1 && run.duration_seconds ? Math.max(0, run.duration_seconds - busy) : null;
  const head = `<p class="run-note">${run.total} série${run.total > 1 ? "s" : ""} · temps passé à récupérer les pages : ${fmtDuration(busy)}${pauses != null ? ` · pauses anti-blocage entre séries : ${fmtDuration(pauses)}` : ""}${cached ? ` · ${cached} reprise${cached > 1 ? "s" : ""} d'une copie (site non sollicité)` : ""}</p>`;
  const lines = run.items.map((i) => {
    const icon = i.ok ? (i.new_chapters ? "🆕" : (i.source === "cache" ? "♻" : "✓")) : "⚠";
    const copyTag = i.source === "cache" ? " · copie" : "";
    const extra = i.ok ? (i.new_chapters ? ` · chap. ${escapeHtml(i.new_chapters)}` : "") + copyTag : `<small class="run-error">${escapeHtml(i.error || "")}</small>`;
    return `<div class="item-row ${i.ok ? "" : "bad"}"><span class="item-icon">${icon}</span><span class="item-title">${escapeHtml(i.series_title || "?")}${extra}</span><b>${fmtDuration(i.duration_seconds)}</b></div>`;
  }).join("");
  return head + lines;
}

async function loadChecks() {
  const [summaryRes, listRes] = await Promise.all([fetch("/api/checks/summary"), fetch("/api/checks?limit=60")]);
  renderChecksSummary(await summaryRes.json());
  renderChecksList(await listRes.json());
}

document.getElementById("download-db-btn").addEventListener("click", () => {
  const tzOffset = -new Date().getTimezoneOffset();
  window.location.href = `/api/database/download?tz_offset=${tzOffset}`;
});

const importDbBtn = document.getElementById("import-db-btn");
const importDbInput = document.getElementById("import-db-input");

if (importDbBtn && importDbInput) {
  importDbBtn.addEventListener("click", () => {
    importDbInput.click();
  });

  importDbInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!confirm("⚠️ ATTENTION : L'importation va écraser TOUTE ta bibliothèque et ton historique actuels. Es-tu sûr de vouloir continuer ?")) {
      e.target.value = ""; // Réinitialiser
      return;
    }

    importDbBtn.disabled = true;
    importDbBtn.textContent = "Importation en cours...";

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/database/import", {
        method: "POST",
        body: formData,
      });
      
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Erreur lors de l'importation");
      
      alert("Base de données importée avec succès ! L'application va se recharger.");
      location.reload(); // Recharge la page pour afficher les nouvelles données
    } catch (err) {
      alert("Erreur : " + err.message);
    } finally {
      importDbBtn.disabled = false;
      importDbBtn.textContent = "Importer une base";
      e.target.value = "";
    }
  });
}

document.getElementById("open-checks-btn").addEventListener("click", () => {
  goToTopView("checks-view");
  navButtons.forEach((b) => b.classList.toggle("active", b.dataset.view === "settings-view"));
  lastTopView = "settings-view";
  loadChecks();
});
document.getElementById("checks-back-btn").addEventListener("click", () => goToTopView("settings-view"));
document.getElementById("checks-refresh-btn").addEventListener("click", loadChecks);

async function loadHistory() {
  const tzOffset = -new Date().getTimezoneOffset(); // minutes d'avance sur UTC (Paris été : 120)
  const [statsRes, itemsRes] = await Promise.all([fetch(`/api/stats?tz_offset=${tzOffset}`), fetch("/api/history")]);
  const stats = await statsRes.json();
  const items = await itemsRes.json();

  // Par défaut : seul le graphique des 7 jours est visible. Les autres stats s'ouvrent d'un appui.
  let statsOpen = false;
  try { statsOpen = localStorage.getItem("historyStatsOpen") === "1"; } catch (e) {}
  const statsDiv = document.getElementById("history-stats");
  const toggleHtml = `<button type="button" class="stats-toggle-link" aria-expanded="${statsOpen}">${statsOpen ? "Masquer ▴" : "Plus de stats ▾"}</button>`;
  statsDiv.innerHTML = `
    ${renderWeekChart(stats.last_7_days, toggleHtml)}
    <div class="stats-details${statsOpen ? "" : " hidden"}">
      <div class="stat-box"><strong>${stats.chapters_this_week}</strong><span>cette semaine</span></div>
      <div class="stat-box"><strong>${stats.chapters_this_month}</strong><span>ce mois-ci</span></div>
      <div class="stat-box"><strong>${stats.total_read}</strong><span>au total</span></div>
      <div class="stat-box"><strong>${stats.streak_days}</strong><span>${stats.streak_days > 1 ? "jours d'affilée" : "jour d'affilée"}</span></div>
      ${stats.top_series_title ? `<div class="stat-box"><strong>${escapeHtml(stats.top_series_title)}</strong><span>${stats.top_series_count} chapitres · plus lue</span></div>` : ""}
    </div>
  `;
  const toggleBtn = statsDiv.querySelector(".stats-toggle-link");
  const detailsDiv = statsDiv.querySelector(".stats-details");
  toggleBtn.addEventListener("click", () => {
    const nowHidden = detailsDiv.classList.toggle("hidden");
    toggleBtn.setAttribute("aria-expanded", String(!nowHidden));
    toggleBtn.textContent = nowHidden ? "Plus de stats ▾" : "Masquer ▴";
    try { localStorage.setItem("historyStatsOpen", nowHidden ? "0" : "1"); } catch (e) {}
  });

  renderHistoryList(document.getElementById("history-list"), items);
}

function renderWeekChart(days, toggleHtml = "") {
  const max = Math.max(1, ...days.map((d) => d.count));
  const letters = ["D", "L", "M", "M", "J", "V", "S"];
  const bars = days.map((d) => {
    const height = d.count === 0 ? 3 : Math.max(8, Math.round((d.count / max) * 44));
    const letter = letters[new Date(d.date + "T12:00:00").getDay()];
    return `<div class="week-col"><em>${d.count || ""}</em><i class="${d.count ? "on" : ""}" style="height:${height}px"></i><b>${letter}</b></div>`;
  }).join("");
  return `<div class="week-chart"><div class="week-head"><div class="week-title">Chapitres lus par jour · 7 derniers jours</div>${toggleHtml}</div><div class="week-bars">${bars}</div></div>`;
}

document.getElementById("clear-history-btn").addEventListener("click", async () => {
  if (!confirm("Effacer tout l'historique de lecture ? (les chapitres restent marqués comme lus, seul l'historique disparaît)")) return;
  await fetch("/api/history", { method: "DELETE" });
  loadHistory();
});

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
      loadCategorySelect();
      if (currentSeriesId) loadSeriesCategories();
    });
  });
  categoryManageList.querySelectorAll(".delete-cat-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("Supprimer cette catégorie ?")) return;
      await fetch(`/api/categories/${btn.dataset.id}`, { method: "DELETE" });
      loadCategoryManageList();
      await loadCategorySelect();
      loadLibrary();
    });
  });
}

async function saveAnilistToken() {
  const token = anilistTokenInput.value.trim();
  if (!token) {
    showAnilistTokenError("Colle ton jeton d'abord.");
    return;
  }
  anilistTokenSave.disabled = true;
  anilistTokenSave.textContent = "Vérification...";
  showAnilistTokenError("");
  try {
    const res = await fetch("/api/settings/anilist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur inconnue");
    anilistTokenInput.value = "";
    anilistEditing = false;
    renderAnilistSettings(data);
  } catch (e) {
    showAnilistTokenError(e.message);
  } finally {
    anilistTokenSave.disabled = false;
    anilistTokenSave.textContent = "Connecter";
  }
}

anilistTokenSave.addEventListener("click", saveAnilistToken);
anilistTokenInput.addEventListener("keydown", (e) => { if (e.key === "Enter") saveAnilistToken(); });

anilistTokenCancel.addEventListener("click", () => {
  anilistEditing = false;
  anilistTokenInput.value = "";
  if (anilistStatusCache) renderAnilistSettings(anilistStatusCache);
});

anilistChangeBtn.addEventListener("click", () => {
  anilistEditing = true;
  if (anilistStatusCache) renderAnilistSettings(anilistStatusCache);
  anilistTokenInput.focus();
});

anilistCheckBtn.addEventListener("click", async () => {
  anilistCheckBtn.disabled = true;
  anilistCheckBtn.textContent = "Vérification...";
  try {
    const res = await fetch("/api/settings/anilist/check", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur inconnue");
    renderAnilistSettings(data);
    if (!data.error && !data.expired) anilistTokenAlert.classList.add("hidden");
  } catch (e) {
    anilistTokenAlert.textContent = "⚠️ " + e.message;
    anilistTokenAlert.classList.remove("hidden");
  } finally {
    anilistCheckBtn.disabled = false;
    anilistCheckBtn.textContent = "Vérifier";
  }
});

anilistDisconnectBtn.addEventListener("click", async () => {
  if (!confirm("Déconnecter AniList ? Tes séries restent liées, mais plus rien ne sera envoyé tant qu'un nouveau jeton n'est pas configuré.")) return;
  const res = await fetch("/api/settings/anilist", { method: "DELETE" });
  anilistEditing = false;
  renderAnilistSettings(await res.json());
});

anilistClientIdInput.addEventListener("input", updateAuthorizeLink);
anilistClientIdInput.addEventListener("change", () => {
  fetch("/api/settings/anilist/client-id", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: anilistClientIdInput.value.trim() }),
  }).catch(() => {});
});

anilistCopyRedirect.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(anilistRedirectUrl.textContent.trim());
    anilistCopyRedirect.textContent = "Copié ✓";
  } catch (e) {
    const range = document.createRange();
    range.selectNodeContents(anilistRedirectUrl);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    anilistCopyRedirect.textContent = "Sélectionné";
  }
  setTimeout(() => { anilistCopyRedirect.textContent = "Copier"; }, 1600);
});

// Menus contextuels (accueil et fiche) : se ferment dès qu'on choisit une entrée, qu'on touche ailleurs ou sur Échap.
function setupPopover(button, menu) {
  const close = () => {
    menu.classList.add("hidden");
    button.setAttribute("aria-expanded", "false");
  };
  button.addEventListener("click", (e) => {
    e.stopPropagation();
    const opening = menu.classList.contains("hidden");
    menu.classList.toggle("hidden", !opening);
    button.setAttribute("aria-expanded", String(opening));
  });
  menu.addEventListener("click", close);
  // Phase de capture : le menu se ferme même si l'élément touché (ligne de chapitre, carte...) arrête la propagation.
  document.addEventListener("click", (e) => {
    if (!menu.contains(e.target) && !button.contains(e.target)) close();
  }, true);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
  });
  return close;
}
setupPopover(homeMenuBtn, homeMenu);
setupPopover(detailMenuBtn, detailMenu);

randomSeriesBtn.addEventListener("click", () => {
  if (libraryShown.length === 0) {
    alert("Aucune série à ouvrir avec les filtres actuels.");
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
  loadCategorySelect();
});

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
  if (searchInput.value.trim()) params.set("search", searchInput.value.trim());

  const res = await fetch(`/api/series?${params}`);
  const series = await res.json();
  libraryShown = series;

  grid.innerHTML = "";
  emptyMsg.classList.toggle("hidden", series.length > 0);

  for (const s of series) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="cover-wrap">
        <img src="${escapeHtml(s.cover_url)}" alt="" loading="lazy">
        <div class="badge-stack">
          ${s.unread_count > 0 ? `<span class="badge">${s.unread_count}</span>` : ""}
          ${s.last_error ? `<span class="badge badge-error" title="${escapeHtml(s.last_error)}">⚠️</span>` : ""}
        </div>
      </div>
      <div class="info">
        <div class="title">${escapeHtml(s.title || "Sans titre")}</div>
        <div class="chapter">${s.last_chapter_number ? "Ch. " + escapeHtml(s.last_chapter_number) : "?"}</div>
      </div>
    `;
    card.addEventListener("click", () => openChaptersView(s.id));
    grid.appendChild(card);
  }
}

async function openChaptersView(seriesId) {
  currentSeriesId = seriesId;
  currentChapters = [];
  currentAnilistProgress = null;
  anilistAlignBanner.classList.add("hidden");
  setSelectionMode(false);
  if (chaptersView.classList.contains("hidden")) {
    viewBeforeDetail = lastTopView;
    scrollBeforeDetail = window.scrollY;
    Object.values(topViews).forEach((v) => v.classList.add("hidden"));
    chaptersView.classList.remove("hidden");
    window.scrollTo(0, 0);
    pushLayer({ detail: true, close: closeDetailUI });
  }
  await loadSeriesDetail();
  await loadChapters();
  syncAnilist(); // en arrière-plan : récupère ce qui a changé sur AniList depuis la dernière fois
}

async function loadSeriesDetail() {
  const res = await fetch(`/api/series/${currentSeriesId}`);
  const s = await res.json();
  detailCover.src = s.cover_url || "";
  detailTitle.textContent = s.title || "Sans titre";

  const statusPill = s.status ? `<span class="status-pill ${statusClass(s.status)}">${escapeHtml(s.status)}</span>` : "";
  detailMeta.innerHTML = statusPill + escapeHtml([s.category, s.year].filter(Boolean).join(" · "));

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
  detailNextCheck.textContent = s.next_check_at
    ? `Prochaine vérification : ${formatFuture(s.next_check_at)}${CHECK_REASON_LABELS[s.check_reason] ? " (" + CHECK_REASON_LABELS[s.check_reason] + ")" : ""}`
    : "Prochaine vérification : dès que possible";
  detailSourceLink.href = s.url;
  detailSourceBtn.href = s.url;
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
    categoryCheckboxes.textContent = "Aucune catégorie créée (menu ⚙ de la bibliothèque).";
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
  const unread = currentChapters.filter((c) => !c.is_read && c.url).sort((a, b) => a.number_float - b.number_float);
  if (unread.length === 0) {
    continueReadingBtn.classList.add("hidden");
    return;
  }
  const next = unread[0];
  continueReadingBtn.textContent = `Continuer la lecture : Chapitre ${next.number}`;
  continueReadingBtn.classList.remove("hidden");
  continueReadingBtn.onclick = () => {
    window.open(next.url, "_blank", "noopener");
    markReadUpTo(next.number);
  };
}

async function loadChapters() {
  const res = await fetch(`/api/series/${currentSeriesId}/chapters`);
  currentChapters = await res.json();
  updateContinueReadingButton();
  updateAlignBanner();
  const total = currentChapters.length;
  document.getElementById("chapters-count").innerHTML = total
    ? `<strong>${total}</strong> chapitre${total > 1 ? "s" : ""}`
    : "";

  chaptersList.innerHTML = "";
  for (const c of currentChapters) {
    const li = document.createElement("li");
    const isSelected = selectedChapterIds.has(c.id);
    const noLink = c.link_type === "aucun" || !c.url;
    const linkTag = noLink ? '<span class="chapter-tag">pas de lien</span>' : "";
    li.className = "chapter-row" + (c.is_read ? " read" : "") + (isSelected ? " selected" : "") + (noLink ? " no-link" : "");

    if (selectionMode) {
      li.innerHTML = `
        <input type="checkbox" class="select-checkbox" ${isSelected ? "checked" : ""}>
        <span class="chapter-number">Chapitre ${escapeHtml(c.number)}</span>
        ${linkTag}
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
        ${linkTag}
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
        if (noLink) return; // rien à ouvrir : on peut quand même cocher le chapitre comme lu
        window.open(c.url, "_blank", "noopener");
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

function setSelectionMode(on) {
  selectionMode = on;
  selectedChapterIds.clear();
  selectModeBtn.textContent = on ? "✕ Annuler la sélection" : "☑ Sélectionner";
  chaptersToolbar.classList.toggle("hidden", !on);
}

selectModeBtn.addEventListener("click", () => {
  setSelectionMode(!selectionMode);
  loadChapters();
});
selectCancelBtn.addEventListener("click", () => {
  setSelectionMode(false);
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
  setSelectionMode(false);
  loadChapters();
}

bulkReadBtn.addEventListener("click", () => bulkSetRead(true));
bulkUnreadBtn.addEventListener("click", () => bulkSetRead(false));

recheckSeriesBtn.addEventListener("click", async () => {
  recheckSeriesBtn.disabled = true;
  detailMenuBtn.classList.add("busy");
  try {
    const res = await fetch(`/api/series/${currentSeriesId}/recheck`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    await loadSeriesDetail();
    await loadChapters();
    if (data.check_error) alert("Vérification impossible : " + data.check_error);
  } finally {
    recheckSeriesBtn.disabled = false;
    detailMenuBtn.classList.remove("busy");
  }
});

resetProgressBtn.addEventListener("click", async () => {
  if (!confirm("Remettre tous les chapitres de cette série en « non lu » ? Ils disparaîtront aussi de l'historique de lecture.")) return;
  await fetch(`/api/series/${currentSeriesId}/reset-progress`, { method: "POST" });
  await loadSeriesDetail();
  await loadChapters();
});

categoryMenuBtn.addEventListener("click", () => {
  openModal(seriesCategoryModal);
  loadSeriesCategories();
});
// « Dans la bibliothèque » : la bibliothèque est l'ensemble des séries, toutes catégories confondues ; un toucher la retire.
libraryBtn.addEventListener("click", () => removeSeriesBtn.click());

removeSeriesBtn.addEventListener("click", async () => {
  if (!confirm("Retirer cette série de la bibliothèque ?")) return;
  await fetch(`/api/series/${currentSeriesId}`, { method: "DELETE" });
  backToLibrary();
});

// Ferme la fiche (affichage seulement) et revient à l'onglet d'où l'on venait.
function closeDetailUI() {
  chaptersView.classList.add("hidden");
  goToTopView(viewBeforeDetail);
  currentSeriesId = null;
  const reload = { "library-view": loadLibrary, "updates-view": loadUpdates, "history-view": loadHistory }[viewBeforeDetail];
  Promise.resolve(reload && reload()).then(() => window.scrollTo(0, scrollBeforeDetail));
}

function backToLibrary() {
  const top = layers[layers.length - 1];
  if (top && top.detail) history.back();
  else closeDetailUI();
}

backBtn.addEventListener("click", backToLibrary);

synopsisToggle.addEventListener("click", () => {
  const expanded = detailSynopsisWrap.classList.toggle("expanded");
  synopsisToggle.textContent = expanded ? "voir moins" : "voir plus";
});

// --- Alignement StickScans <- AniList, et synchro automatique de l'état AniList ---
const anilistAlignBanner = document.getElementById("anilist-align-banner");
const anilistAlignText = document.getElementById("anilist-align-text");
const anilistAlignBtn = document.getElementById("anilist-align-btn");

// Propose de marquer comme lus ici les chapitres qu'AniList indique comme lus mais qui ne le sont pas dans l'appli.
function updateAlignBanner() {
  const progress = currentAnilistProgress;
  const missing = progress > 0
    ? currentChapters.filter((c) => !c.is_read && c.number_float <= progress).length
    : 0;
  anilistAlignBanner.classList.toggle("hidden", missing === 0);
  if (missing === 0) return;
  const s = (n) => (n > 1 ? "s" : "");
  anilistAlignText.textContent =
    `AniList indique ${progress} chapitre${s(progress)} lu${s(progress)}, mais ${missing} ${missing > 1 ? "ne sont" : "n'est"} pas marqué${s(missing)} comme lu${s(missing)} ici.`;
  anilistAlignBtn.textContent = `Marquer ${missing} chapitre${s(missing)} comme lu${s(missing)}`;
}

anilistAlignBtn.addEventListener("click", async () => {
  if (!confirm("Marquer ces chapitres comme lus dans StickScans ? Ils n'apparaîtront pas dans l'historique.")) return;
  anilistAlignBtn.disabled = true;
  try {
    const res = await fetch(`/api/series/${currentSeriesId}/anilist/align-local`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alert(data.detail || "Alignement impossible");
      return;
    }
    await loadSeriesDetail();
    await loadChapters();
  } catch (e) {
    alert("Impossible de joindre le serveur");
  } finally {
    anilistAlignBtn.disabled = false;
  }
});

// Demande au serveur de recopier l'état AniList (au plus une fois par minute côté serveur).
// À l'ouverture de l'appli, à l'ouverture d'une fiche et au retour sur l'appli : on y voit ainsi ce qui a été
// modifié ailleurs. Une fiche ouverte est rafraîchie, sauf si son formulaire AniList est déplié (saisie en cours).
let anilistSyncing = false;
async function syncAnilist() {
  if (anilistSyncing) return;
  anilistSyncing = true;
  try {
    const res = await fetch("/api/anilist/sync", { method: "POST" });
    if (!res.ok) return;
    const data = await res.json();
    if (data.updated > 0 && !chaptersView.classList.contains("hidden") && anilistLinked.classList.contains("hidden")) {
      await loadSeriesDetail();
    }
  } catch (e) {
    // hors ligne ou serveur occupé : on réessaiera au prochain retour sur l'appli
  } finally {
    anilistSyncing = false;
  }
}
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") syncAnilist();
});

// --- Notes AniList : champ texte du panneau AniList (champ « Notes » de ta liste), enregistré avec le reste ---
const anilistNotesInput = document.getElementById("anilist-notes-input");
const anilistNotesCount = document.getElementById("anilist-notes-count");
let savedNotes = ""; // dernière valeur connue côté AniList : seule une note modifiée est envoyée

function updateNotesCount() {
  anilistNotesCount.textContent = `${anilistNotesInput.value.length}/${anilistNotesInput.maxLength}`;
}
anilistNotesInput.addEventListener("input", updateNotesCount);

function renderAnilistSection(s) {
  if (s.anilist_id) {
    anilistActionBtn.textContent = "✓ " + (s.anilist_title || "AniList");
    anilistActionBtn.title = s.anilist_title || "";
    anilistActionBtn.classList.add("linked");
    anilistActionBtn.dataset.linked = "1";
    anilistLinkedTitle.textContent = s.anilist_title || s.anilist_id;
    anilistStatusSelect.value = s.anilist_status || "CURRENT";
    anilistProgressInput.value = s.anilist_progress ?? "";
    anilistScoreInput.value = s.anilist_score ?? "";
    savedNotes = s.anilist_notes || "";
    anilistNotesInput.value = savedNotes;
    updateNotesCount();
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
  currentAnilistProgress = s.anilist_id ? (s.anilist_progress || 0) : null;
  updateAlignBanner();
  // Repliée par défaut à chaque (re)chargement de la fiche.
  anilistLinked.classList.add("hidden");
}

anilistActionBtn.addEventListener("click", () => {
  if (anilistActionBtn.dataset.linked === "1") {
    anilistLinked.classList.toggle("hidden");
  } else {
    openModal(anilistModal);
  }
});
anilistModalClose.addEventListener("click", () => closeModal(anilistModal));

seriesCategoryModalClose.addEventListener("click", () => closeModal(seriesCategoryModal));

anilistSearchBtn.addEventListener("click", async () => {
  const q = anilistSearchInput.value.trim();
  if (!q) return;
  anilistSearchBtn.disabled = true;
  anilistSearchBtn.textContent = "...";
  try {
    const res = await fetch(`/api/anilist/search?q=${encodeURIComponent(q)}`);
    const results = await res.json().catch(() => null);
    anilistSearchResults.innerHTML = "";
    if (!res.ok || !Array.isArray(results)) {
      const msg = results && typeof results.detail === "string" ? results.detail : "Recherche AniList impossible pour l'instant.";
      anilistSearchResults.innerHTML = `<li class="error">⚠️ ${escapeHtml(msg)}</li>`;
      return;
    }
    if (results.length === 0) {
      anilistSearchResults.innerHTML = '<li class="section-label">Aucun résultat sur AniList.</li>';
      return;
    }
    for (const r of results) {
      const li = document.createElement("li");
      li.className = "anilist-result-row";
      li.innerHTML = `
        <img src="${escapeHtml(r.cover_url)}" alt="" loading="lazy">
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
        closeModal(anilistModal);
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
  const typedNotes = anilistNotesInput.value.trim();
  try {
    const payload = {
      status: anilistStatusSelect.value,
      progress: anilistProgressInput.value !== "" ? parseInt(anilistProgressInput.value, 10) : null,
      score: anilistScoreInput.value !== "" ? parseFloat(anilistScoreInput.value) : null,
      start_date: anilistStartInput.value || null,
      end_date: anilistEndInput.value || null,
    };
    // La note n'est envoyée que si elle a changé : enregistrer autre chose n'écrase pas une note modifiée ailleurs.
    // Une chaîne vide efface la note sur AniList.
    if (typedNotes !== savedNotes) payload.notes = typedNotes;
    const res = await fetch(`/api/series/${currentSeriesId}/anilist/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Enregistrement refusé");
    renderAnilistSection(data);
    // Le panneau reste ouvert : le message « Enregistré ✓ » ou l'erreur s'y affiche (il était invisible quand il se refermait).
    anilistLinked.classList.remove("hidden");
    if (data.anilist_last_error) {
      // Erreur côté AniList (jeton refusé, réseau...) : le texte tapé n'est jamais perdu.
      anilistNotesInput.value = typedNotes;
      updateNotesCount();
    } else {
      anilistStatusText.textContent = "Enregistré ✓";
    }
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

async function startRefreshAll() {
  const res = await fetch("/api/series/refresh-all", { method: "POST" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    alert(typeof data.detail === "string" ? data.detail : "Actualisation impossible pour l'instant.");
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
    refreshAllLabel.textContent = "↻ Actualiser toutes les séries";
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
genreSelect.addEventListener("change", loadLibrary);
hideReadCheckbox.addEventListener("change", loadLibrary);
searchInput.addEventListener("input", () => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(loadLibrary, 300);
});

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

// ----- Retour par balayage vers la droite (fiche série et popups) -----
let swipeStart = null;

document.addEventListener("touchstart", (e) => {
  swipeStart = null;
  if (!layers.length || e.touches.length !== 1) return;
  const t = e.touches[0];
  if (t.clientX > window.innerWidth * 0.4) return;
  if (e.target.closest("input, textarea, select")) return;
  swipeStart = { x: t.clientX, y: t.clientY };
}, { passive: true });

document.addEventListener("touchend", (e) => {
  if (!swipeStart) return;
  const t = e.changedTouches[0];
  const dx = t.clientX - swipeStart.x;
  const dy = t.clientY - swipeStart.y;
  const fromEdge = swipeStart.x <= 24;
  swipeStart = null;
  if (dx < 80 || Math.abs(dy) > dx * 0.5 || !layers.length) return;
  if (fromEdge) {
    // Depuis le bord, le navigateur gère parfois déjà le geste (popstate) : on vérifie avant d'agir.
    const before = lastPopAt;
    setTimeout(() => { if (lastPopAt === before && layers.length) history.back(); }, 350);
  } else {
    history.back();
  }
}, { passive: true });

document.addEventListener("touchcancel", () => { swipeStart = null; }, { passive: true });

async function init() {
  // Un rechargement peut laisser une entrée d'historique orpheline : on repart d'une base propre.
  const shared = new URLSearchParams(location.search);
  const sharedText = [shared.get("url"), shared.get("text"), shared.get("title")].filter(Boolean).join("\n");
  history.replaceState(null, "", location.pathname);

  const saved = getSavedFilters();
  if (saved.sort) sortSelect.value = saved.sort;
  if (saved.search) {
    searchInput.value = saved.search;
    searchBar.classList.remove("hidden");
  }
  if (saved.hideRead) hideReadCheckbox.checked = saved.hideRead;
  if (saved.categoryId) activeCategoryId = saved.categoryId;

  await loadGenreSelect();
  await loadStatuses();
  if (saved.genre) genreSelect.value = saved.genre;
  if (saved.status) statusSelect.value = saved.status;

  await loadCategorySelect();
  await loadLibrary();

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }

  // Lien partagé depuis une autre appli (menu « Partager » d'Android) : on ouvre la popup pré-remplie.
  if (sharedText) openAddModal(sharedText);
}

init();

// --- Statuts de série : couleur selon l'état ---
function statusClass(status) {
  const t = (status || "").toLowerCase();
  if (t.includes("cours")) return "status-ongoing";
  if (t.includes("termin") || t.includes("fini")) return "status-completed";
  if (t.includes("pause") || t.includes("hiatus")) return "status-paused";
  if (t.includes("abandon") || t.includes("annul") || t.includes("stopp")) return "status-dropped";
  return "status-other";
}

// --- Aperçu de lecture (Réglages) : temps passé à lire et classement des séries ---
const readingView = document.getElementById("reading-view");
topViews["reading-view"] = readingView; // ouvert depuis Réglages, pas dans la barre du bas
let readingPeriod = "week";
const READING_PERIODS = [["week", "Semaine"], ["month", "Mois"], ["all", "Tout"]];
const READING_PERIOD_LABELS = { week: "7 derniers jours", month: "30 derniers jours", all: "Depuis le début" };

document.getElementById("open-reading-btn").addEventListener("click", () => {
  goToTopView("reading-view");
  navButtons.forEach((b) => b.classList.toggle("active", b.dataset.view === "settings-view"));
  lastTopView = "settings-view";
  loadReadingOverview();
});
document.getElementById("reading-back-btn").addEventListener("click", () => goToTopView("settings-view"));

function fmtReadingTime(minutes) {
  const m = Math.round(minutes);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  return rest ? `${h} h ${String(rest).padStart(2, "0")}` : `${h} h`;
}

// Grand chiffre : « 2 h 35 » avec des unités plus discrètes que les nombres.
function fmtBigTime(minutes) {
  const m = Math.round(minutes);
  const part = (n, unit) => `<span class="rv-num">${n}</span><span class="rv-unit">${unit}</span>`;
  if (m < 60) return part(m, "min");
  const h = Math.floor(m / 60);
  const rest = m % 60;
  return rest ? part(h, "h") + part(String(rest).padStart(2, "0"), "min") : part(h, "h");
}

// Chaque série garde toujours la même teinte, déduite de son titre.
function seriesHue(title) {
  let h = 0;
  for (const ch of title || "") h = (h * 31 + ch.charCodeAt(0)) % 360;
  return h;
}

function renderReadingOverview(d) {
  const plural = (n, one, many) => `${n} ${n > 1 ? many : one}`;
  const chips = READING_PERIODS.map(
    ([key, label]) => `<button type="button" class="tab${key === d.period ? " active" : ""}" data-period="${key}">${label}</button>`,
  ).join("");

  let list;
  if (!d.series.length) {
    list = `<p class="rv-empty">Rien lu sur cette période.</p>`;
  } else {
    const max = Math.max(1, d.series[0].minutes);
    const rows = d.series.map((s) => {
      const width = 8 + Math.round((34 * s.minutes) / max); // la plus lue occupe 42 % de la ligne
      return `<div class="rv-row" style="--w:${width}%;--hue:${seriesHue(s.title)}">
        <div class="rv-bar"></div>
        <img class="rv-cover" src="${escapeHtml(s.cover_url)}" alt="" loading="lazy">
        <div class="rv-text">
          <div class="rv-title">${escapeHtml(s.title)}</div>
          <div class="rv-time">${fmtReadingTime(s.minutes)}<span> · ${plural(s.count, "chapitre", "chapitres")}</span></div>
        </div>
      </div>`;
    });
    const more = d.more > 0 ? `<p class="rv-more">+ ${plural(d.more, "autre série", "autres séries")}</p>` : "";
    list = `<div class="rv-list">${rows.join("")}</div>${more}`;
  }

  const since = d.since
    ? `, calculée depuis ${new Date(d.since + "T12:00:00").toLocaleDateString("fr-FR", { month: "long", year: "numeric" })}`
    : "";
  return `
    <div class="rv-hero">
      <div class="rv-total">${fmtBigTime(d.total_minutes)}</div>
      <div class="rv-caption">${READING_PERIOD_LABELS[d.period]} · ${plural(d.chapters, "chapitre", "chapitres")} · ${plural(d.series_count, "série", "séries")}</div>
    </div>
    <div class="rv-periods">${chips}</div>
    ${list}
    <p class="rv-foot">Estimation de ${d.minutes_per_chapter} min par chapitre lu${since}.</p>
  `;
}

async function loadReadingOverview() {
  const box = document.getElementById("reading-content");
  try {
    const tzOffset = -new Date().getTimezoneOffset();
    const res = await fetch(`/api/stats/reading?period=${readingPeriod}&tz_offset=${tzOffset}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    box.innerHTML = renderReadingOverview(await res.json());
    box.querySelectorAll("[data-period]").forEach((btn) =>
      btn.addEventListener("click", () => {
        readingPeriod = btn.dataset.period;
        loadReadingOverview();
      }),
    );
  } catch (e) {
    box.innerHTML = '<p class="error">Impossible de charger les statistiques.</p>';
  }
}

// ======================================================================
// Réglages : liste des rubriques, puis une page par rubrique
// ======================================================================
const settingsHome = document.getElementById("settings-home");
const settingsTitle = document.getElementById("settings-title");
const settingsBackBtn = document.getElementById("settings-back-btn");
const settingsPageEls = document.querySelectorAll(".settings-page");

const SETTINGS_PAGE_LOADERS = {
  display: () => loadDisplayPage(),
  categories: () => loadCategoryManageList(),
  updates: () => loadUpdateSettings(),
  anilist: () => loadSettingsAnilistStatus(),
  storage: () => loadStorage(),
  backup: () => loadBackups(),
};

// name = null : retour à la liste des rubriques.
function showSettingsPage(name) {
  let title = "Réglages";
  settingsPageEls.forEach((page) => {
    const active = page.dataset.page === name;
    page.classList.toggle("hidden", !active);
    if (active) title = page.dataset.title;
  });
  settingsHome.classList.toggle("hidden", Boolean(name));
  settingsBackBtn.classList.toggle("hidden", !name);
  settingsTitle.textContent = title;
  window.scrollTo(0, 0);
  if (name && SETTINGS_PAGE_LOADERS[name]) SETTINGS_PAGE_LOADERS[name]();
}

function openSettingsPage(name) {
  goToTopView("settings-view");
  navButtons.forEach((b) => b.classList.toggle("active", b.dataset.view === "settings-view"));
  lastTopView = "settings-view";
  showSettingsPage(name);
}

settingsHome.addEventListener("click", (e) => {
  const row = e.target.closest("[data-page]");
  if (row) showSettingsPage(row.dataset.page);
});
settingsBackBtn.addEventListener("click", () => showSettingsPage(null));

function formatBytes(n) {
  if (!n) return "0 o";
  const units = ["o", "Ko", "Mo", "Go", "To"];
  let value = n;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toLocaleString("fr-FR", { maximumFractionDigits: value < 10 && i > 0 ? 1 : 0 })} ${units[i]}`;
}

const plural = (n, one, many) => `${n.toLocaleString("fr-FR")} ${n > 1 ? many : one}`;

// ----------------------------------------------------------------------
// Affichage de la bibliothèque (propre à l'appareil : stocké dans le navigateur)
// ----------------------------------------------------------------------
const DISPLAY_KEY = "stickscans_display";
const DISPLAY_DEFAULTS = { mode: "grid", cols: 0, badge: true, lastChapter: true, singleLine: false };
const displayMode = document.getElementById("display-mode");
const displayCols = document.getElementById("display-cols");
const displayColsSection = document.getElementById("display-cols-section");
const displayBadge = document.getElementById("display-badge");
const displayLastChapter = document.getElementById("display-lastchapter");
const displaySingleLine = document.getElementById("display-singleline");
const displayPreviewGrid = document.getElementById("display-preview-grid");

function getDisplayPrefs() {
  try {
    return { ...DISPLAY_DEFAULTS, ...(JSON.parse(localStorage.getItem(DISPLAY_KEY)) || {}) };
  } catch (e) {
    return { ...DISPLAY_DEFAULTS };
  }
}

function applyDisplayPrefs() {
  const p = getDisplayPrefs();
  for (const g of [grid, displayPreviewGrid]) {
    g.classList.toggle("list", p.mode === "list");
    g.classList.toggle("custom-cols", p.mode === "grid" && p.cols > 0);
    g.style.setProperty("--cols", p.cols > 0 ? String(p.cols) : "");
  }
  document.body.classList.toggle("no-unread-badge", !p.badge);
  document.body.classList.toggle("no-last-chapter", !p.lastChapter);
  document.body.classList.toggle("single-line-title", p.singleLine);
}

function updateDisplayPrefs(patch) {
  try {
    localStorage.setItem(DISPLAY_KEY, JSON.stringify({ ...getDisplayPrefs(), ...patch }));
  } catch (e) {}
  applyDisplayPrefs();
  loadDisplayPage();
}

function setSegmented(container, value) {
  container.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.value === String(value)));
}

function renderDisplayPreview() {
  const cover = (hue) =>
    "data:image/svg+xml;utf8," +
    encodeURIComponent(`<svg xmlns='http://www.w3.org/2000/svg' width='200' height='300'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='hsl(${hue},65%,55%)'/><stop offset='1' stop-color='hsl(${hue + 50},60%,28%)'/></linearGradient></defs><rect width='200' height='300' fill='url(#g)'/></svg>`);
  const samples = [["Solo Leveling", "Ch. 201", 3], ["Tower of God", "Ch. 640", 0], ["Omniscient Reader", "Ch. 245", 12],
                   ["The Beginning After the End", "Ch. 215", 1], ["Pick Me Up!", "Ch. 120", 0], ["Return of the Mount Hua Sect", "Ch. 184", 5]];
  displayPreviewGrid.innerHTML = samples.map(([title, chapter, unread], i) => `
    <div class="card">
      <div class="cover-wrap">
        <img src="${cover(i * 60)}" alt="">
        <div class="badge-stack">${unread ? `<span class="badge">${unread}</span>` : ""}</div>
      </div>
      <div class="info"><div class="title">${title}</div><div class="chapter">${chapter}</div></div>
    </div>`).join("");
}

function loadDisplayPage() {
  const p = getDisplayPrefs();
  setSegmented(displayMode, p.mode);
  setSegmented(displayCols, p.cols);
  displayColsSection.classList.toggle("hidden", p.mode === "list");
  displayBadge.checked = p.badge;
  displayLastChapter.checked = p.lastChapter;
  displaySingleLine.checked = p.singleLine;
  if (!displayPreviewGrid.children.length) renderDisplayPreview();
}

displayMode.addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (b) updateDisplayPrefs({ mode: b.dataset.value });
});
displayCols.addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (b) updateDisplayPrefs({ cols: Number(b.dataset.value) });
});
displayBadge.addEventListener("change", () => updateDisplayPrefs({ badge: displayBadge.checked }));
displayLastChapter.addEventListener("change", () => updateDisplayPrefs({ lastChapter: displayLastChapter.checked }));
displaySingleLine.addEventListener("change", () => updateDisplayPrefs({ singleLine: displaySingleLine.checked }));

// ----------------------------------------------------------------------
// Mises à jour : quelles séries ignorer lors d'une vérification groupée (réglage enregistré sur le serveur)
// ----------------------------------------------------------------------
const UPDATE_TOGGLES = [
  [document.getElementById("upd-auto-enabled"), "auto_enabled"],
  [document.getElementById("upd-skip-completed"), "skip_completed"],
  [document.getElementById("upd-skip-unread"), "skip_unread"],
  [document.getElementById("upd-skip-neverread"), "skip_never_read"],
];
const updMsg = document.getElementById("upd-msg");

async function loadUpdateSettings(keepMessage = false) {
  try {
    const s = await (await fetch("/api/settings/updates")).json();
    UPDATE_TOGGLES.forEach(([el, key]) => (el.checked = Boolean(s[key])));
    if (!keepMessage) updMsg.textContent = "";
    loadSiteStatus();
  } catch (e) {
    updMsg.textContent = "⚠️ Impossible de lire les réglages.";
  }
}

UPDATE_TOGGLES.forEach(([el, key]) =>
  el.addEventListener("change", async () => {
    try {
      const res = await fetch("/api/settings/updates", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [key]: el.checked }),
      });
      if (!res.ok) throw new Error();
      updMsg.textContent = "Enregistré ✓";
      loadSiteStatus();
    } catch (e) {
      updMsg.textContent = "⚠️ Réglage non enregistré.";
      loadUpdateSettings(true); // l'interrupteur revient à son état réel, le message d'erreur reste visible
    }
  }),
);

const siteStatusBox = document.getElementById("site-status-box");
const siteClearPauseBtn = document.getElementById("site-clear-pause-btn");

function renderSiteStatus(st) {
  const lines = [];
  const pause = sitePauseText(st);
  lines.push(pause ? `<strong class="warn-text">⏸ ${escapeHtml(pause)}</strong>` : "<strong>✓ Requêtes autorisées</strong>");
  lines.push(`${st.requests_today} requête${st.requests_today > 1 ? "s" : ""} aujourd'hui sur ${st.daily_limit} maximum${st.shared ? ", toutes instances du serveur confondues" : ""}.`);
  if (st.due_now) lines.push(`${st.due_now} série${st.due_now > 1 ? "s" : ""} à vérifier dès que possible.`);
  else if (st.next_check_at) lines.push(`Prochaine vérification : ${formatFuture(st.next_check_at)}.`);
  if (st.last_block_at) {
    const when = new Date(st.last_block_at).toLocaleString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    lines.push(`Dernier refus du site : ${escapeHtml(when)} (${escapeHtml(st.last_block_reason || "?")}).`);
  }
  siteStatusBox.innerHTML = lines.map((l) => `<p>${l}</p>`).join("");
  siteClearPauseBtn.classList.toggle("hidden", !st.blocked);
}

async function loadSiteStatus() {
  try {
    renderSiteStatus(await (await fetch("/api/site-status")).json());
  } catch (e) {
    siteStatusBox.textContent = "⚠️ État du site indisponible.";
  }
}

siteClearPauseBtn.addEventListener("click", async () => {
  if (!confirm("Lever la pause maintenant ? À faire seulement si le site t'a débloqué : un nouveau refus entraînerait une pause plus longue.")) return;
  try {
    renderSiteStatus(await (await fetch("/api/site-status/clear-pause", { method: "POST" })).json());
  } catch (e) {
    siteStatusBox.textContent = "⚠️ Impossible de lever la pause.";
  }
});

// ----------------------------------------------------------------------
// Stockage : espace utilisé et nettoyage
// ----------------------------------------------------------------------
const storageTotal = document.getElementById("storage-total");
const storageBar = document.getElementById("storage-bar");
const storageList = document.getElementById("storage-list");
const storageDisk = document.getElementById("storage-disk");
const storageMsg = document.getElementById("storage-msg");

async function loadStorage() {
  let info;
  try {
    info = await (await fetch("/api/storage")).json();
  } catch (e) {
    storageTotal.textContent = "—";
    storageMsg.textContent = "⚠️ Impossible de lire le stockage.";
    return;
  }
  const db = info.database;
  const known = db.bytes + info.backups.bytes + info.logs.bytes;
  const other = Math.max(0, info.data.bytes - known);
  const cache = info.page_cache;
  const parts = [
    ["seg-db", "Base de données", `${plural(db.series, "série", "séries")} · ${plural(db.chapters, "chapitre", "chapitres")}`, db.bytes],
    ["seg-backup", "Sauvegardes", plural(info.backups.count, "copie", "copies"), info.backups.bytes],
    ["seg-logs", "Journaux", plural(info.logs.files, "fichier", "fichiers"), info.logs.bytes],
    ["seg-cache", "Cache des pages", cache.active ? plural(cache.files, "page", "pages") : "Désactivé", cache.bytes],
  ];
  if (other > 0) parts.push(["seg-other", "Autres fichiers", "", other]);
  const total = parts.reduce((sum, p) => sum + p[3], 0);

  storageTotal.textContent = formatBytes(total);
  storageBar.innerHTML = parts
    .filter((p) => p[3] > 0)
    .map((p) => `<i class="${p[0]}" style="width:${Math.max(1.5, (p[3] / Math.max(1, total)) * 100)}%"></i>`)
    .join("");
  storageList.innerHTML = parts
    .map((p) => `<li><span class="info-dot ${p[0]}"></span><span class="info-name">${escapeHtml(p[1])}<small>${escapeHtml(p[2])}</small></span><span class="info-size">${formatBytes(p[3])}</span></li>`)
    .join("");
  storageDisk.textContent = info.disk
    ? `Disque : ${formatBytes(info.disk.free)} libres sur ${formatBytes(info.disk.total)}.`
    : "";

  document.getElementById("clear-cache-info").textContent = cache.active
    ? `${formatBytes(cache.bytes)} · ${plural(cache.files, "page", "pages")}`
    : "Cache désactivé";
  document.getElementById("clear-logs-info").textContent = formatBytes(info.logs.bytes);
  document.getElementById("clear-checks-info").textContent = plural(db.check_runs, "vérification enregistrée", "vérifications enregistrées");
}

async function storageAction(button, url, confirmText, describe) {
  if (confirmText && !confirm(confirmText)) return;
  button.disabled = true;
  storageMsg.textContent = "…";
  try {
    const res = await fetch(url, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Échec");
    storageMsg.textContent = describe(data);
  } catch (e) {
    storageMsg.textContent = "⚠️ " + e.message;
  } finally {
    button.disabled = false;
    loadStorage();
  }
}

document.getElementById("clear-cache-btn").addEventListener("click", (e) =>
  storageAction(e.currentTarget, "/api/storage/clear-page-cache", "", (d) =>
    d.files ? `Cache vidé : ${plural(d.files, "page supprimée", "pages supprimées")}, ${formatBytes(d.bytes)} libérés.` : "Le cache est déjà vide."));
document.getElementById("clear-logs-btn").addEventListener("click", (e) =>
  storageAction(e.currentTarget, "/api/storage/clear-logs", "Effacer les journaux de vérification ?", (d) =>
    `Journaux effacés : ${formatBytes(d.bytes)} libérés.`));
document.getElementById("clear-checks-btn").addEventListener("click", (e) =>
  storageAction(e.currentTarget, "/api/storage/clear-check-history",
    "Effacer le détail des vérifications passées ? Tes séries, chapitres et ton historique de lecture ne sont pas touchés.", (d) =>
    `${plural(d.runs, "vérification effacée", "vérifications effacées")}.`));
document.getElementById("optimize-db-btn").addEventListener("click", (e) =>
  storageAction(e.currentTarget, "/api/storage/optimize", "", (d) =>
    `Base optimisée : ${formatBytes(d.before)} → ${formatBytes(d.after)}.`));

document.getElementById("clear-app-cache-btn").addEventListener("click", async () => {
  if (!confirm("Vider le cache de l'application et la recharger ? Tes données et tes réglages ne sont pas touchés.")) return;
  try {
    if ("serviceWorker" in navigator) {
      const registrations = await navigator.serviceWorker.getRegistrations();
      await Promise.all(registrations.map((r) => r.unregister()));
    }
    if (window.caches) {
      const keys = await caches.keys();
      await Promise.all(keys.map((k) => caches.delete(k)));
    }
  } catch (e) {}
  location.reload();
});
document.getElementById("reset-prefs-btn").addEventListener("click", () => {
  if (!confirm("Réinitialiser l'affichage, les filtres et les préférences de cet appareil ?")) return;
  try {
    ["stickscans_filters", DISPLAY_KEY, "historyStatsOpen"].forEach((k) => localStorage.removeItem(k));
  } catch (e) {}
  location.reload();
});

// ----------------------------------------------------------------------
// Sauvegarde et restauration
// ----------------------------------------------------------------------
const backupEnabled = document.getElementById("backup-enabled");
const backupKeep = document.getElementById("backup-keep");
const backupList = document.getElementById("backup-list");
const backupMsg = document.getElementById("backup-msg");
const backupNowBtn = document.getElementById("backup-now-btn");

function renderBackups(data) {
  backupEnabled.checked = data.settings.enabled;
  if (![...backupKeep.options].some((o) => o.value === String(data.settings.keep))) {
    const opt = document.createElement("option");
    opt.value = String(data.settings.keep);
    opt.textContent = String(data.settings.keep);
    backupKeep.appendChild(opt);
  }
  backupKeep.value = String(data.settings.keep);
  backupKeep.disabled = !data.settings.enabled;
  if (data.backups.length === 0) {
    backupList.innerHTML = '<li class="backup-empty">Aucune sauvegarde pour l\'instant.</li>';
    return;
  }
  backupList.innerHTML = data.backups.map((b) => {
    const when = new Date(b.modified).toLocaleString("fr-FR", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
    const name = escapeHtml(b.name);
    return `<li class="backup-row" data-name="${name}">
      <div class="backup-info">
        <div class="backup-head"><strong>${escapeHtml(b.label)}</strong><em>${formatBytes(b.size)}</em></div>
        <span>${escapeHtml(when)}</span>
      </div>
      <div class="backup-actions">
        <button type="button" class="mini-btn" data-act="restore">Restaurer</button>
        <a class="mini-btn" href="/api/backups/${encodeURIComponent(b.name)}/download" download title="Télécharger">⬇</a>
        <button type="button" class="mini-btn danger-btn" data-act="delete" title="Supprimer">🗑</button>
      </div>
    </li>`;
  }).join("");
}

async function loadBackups() {
  try {
    renderBackups(await (await fetch("/api/backups")).json());
  } catch (e) {
    backupMsg.textContent = "⚠️ Impossible de lire les sauvegardes.";
  }
}

async function saveBackupSettings(patch) {
  try {
    const res = await fetch("/api/settings/backups", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (!res.ok) throw new Error();
    backupMsg.textContent = "Enregistré ✓";
  } catch (e) {
    backupMsg.textContent = "⚠️ Réglage non enregistré.";
  }
  loadBackups();
}
backupEnabled.addEventListener("change", () => saveBackupSettings({ enabled: backupEnabled.checked }));
backupKeep.addEventListener("change", () => saveBackupSettings({ keep: Number(backupKeep.value) }));

backupNowBtn.addEventListener("click", async () => {
  backupNowBtn.disabled = true;
  backupMsg.textContent = "Sauvegarde en cours…";
  try {
    const res = await fetch("/api/backups", { method: "POST" });
    if (!res.ok) throw new Error();
    renderBackups(await res.json());
    backupMsg.textContent = "Sauvegarde créée ✓";
  } catch (e) {
    backupMsg.textContent = "⚠️ La sauvegarde a échoué.";
  } finally {
    backupNowBtn.disabled = false;
  }
});

backupList.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-act]");
  if (!btn) return;
  const name = btn.closest(".backup-row").dataset.name;
  const url = `/api/backups/${encodeURIComponent(name)}`;
  if (btn.dataset.act === "delete") {
    if (!confirm("Supprimer cette sauvegarde ?")) return;
    try {
      const res = await fetch(url, { method: "DELETE" });
      if (!res.ok) throw new Error();
      renderBackups(await res.json());
      backupMsg.textContent = "Sauvegarde supprimée.";
    } catch (err) {
      backupMsg.textContent = "⚠️ Suppression impossible.";
    }
  } else if (btn.dataset.act === "restore") {
    if (!confirm("Restaurer cette sauvegarde ? Toutes tes données actuelles seront remplacées. Une copie de sécurité de l'état actuel est faite avant.")) return;
    backupMsg.textContent = "Restauration…";
    try {
      const res = await fetch(`${url}/restore`, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Restauration impossible");
      alert("Sauvegarde restaurée. L'application va se recharger.");
      location.reload();
    } catch (err) {
      backupMsg.textContent = "⚠️ " + err.message;
    }
  }
});

applyDisplayPrefs();

syncAnilist();
