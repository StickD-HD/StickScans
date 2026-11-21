// Socle commun : session, navigation entre écrans, couches « retour », menus, formats de dates et de tailles, balayage.
// Fichier 1/15 : chargé dans l'ordre par index.html ; tous partagent la même portée globale.

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
const logoutOthersBtn = document.getElementById("logout-others-btn");
if (logoutOthersBtn) {
  logoutOthersBtn.addEventListener("click", async () => {
    if (!confirm("Déconnecter tous les autres appareils ? Ils devront se reconnecter avec le mot de passe. Cet appareil reste connecté.")) return;
    const res = await _originalFetch("/api/auth/logout-others", { method: "POST" });
    alert(res.ok ? "Les autres appareils sont déconnectés." : "Échec : réessaie.");
  });
}
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
let currentSeriesId = null;
let activeCategoryId = "";
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

// --- Statuts de série : couleur selon l'état ---
function statusClass(status) {
  const t = (status || "").toLowerCase();
  if (t.includes("cours")) return "status-ongoing";
  if (t.includes("termin") || t.includes("fini")) return "status-completed";
  if (t.includes("pause") || t.includes("hiatus")) return "status-paused";
  if (t.includes("abandon") || t.includes("annul") || t.includes("stopp")) return "status-dropped";
  return "status-other";
}

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

// Toucher le fond sombre d'une popup la ferme.
function closeOnBackdrop(m) {
  m.addEventListener("click", (e) => { if (e.target === m) closeModal(m); });
}
