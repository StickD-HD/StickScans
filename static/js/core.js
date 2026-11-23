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
    toast(res.ok ? "Les autres appareils sont déconnectés." : "Échec : réessaie.", res.ok ? "ok" : "error");
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
// Chaque écran secondaire (fiche série, popups, pages de Réglages, Vérifications, Aperçu de lecture) est une
// « couche » liée à une entrée d'historique : le geste retour d'Android, le balayage vers la droite et les boutons
// « Retour » ferment la couche du dessus. close() ne touche qu'à l'affichage ; view = élément qui glisse sous le doigt.
const layers = [];
let lastPopAt = 0;
let silentPops = 0; // retours d'historique lancés par l'appli après avoir déjà fermé la couche elle-même

function pushLayer(layer) {
  layers.push(layer);
  history.pushState({ layer: layers.length }, "");
}

window.addEventListener("popstate", (e) => {
  lastPopAt = Date.now();
  if (silentPops > 0) {
    silentPops--;
    return; // la couche est déjà fermée : on remettait seulement l'historique en accord
  }
  const depth = (e.state && e.state.layer) || 0;
  while (layers.length > depth) layers.pop().close();
});

// Ferme la couche du dessus TOUT DE SUITE, puis met l'historique à jour (sans attendre le navigateur, parfois lent
// à répondre dans l'appli installée sur iPhone).
function closeTopLayer() {
  const top = layers.pop();
  if (!top) return false;
  top.close();
  silentPops++;
  history.back();
  return true;
}

// Changement d'onglet (barre du bas) : les couches ouvertes sont abandonnées sans être rejouées.
function dropAllLayers() {
  if (!layers.length) return;
  const n = layers.length;
  layers.length = 0;
  silentPops++;
  history.go(-n);
}

// Le défilement est géré par l'appli (retour d'une fiche à l'endroit exact) : le navigateur ne doit pas le
// remettre à sa façon en revenant en arrière dans l'historique.
if ("scrollRestoration" in history) history.scrollRestoration = "manual";

// --- Mouvement : feuilles du bas qui montent et redescendent, écrans qui apparaissent en fondu ---
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const SHEET_CLOSE_MS = 200;

// Ferme une feuille en la faisant redescendre (« hidden » n'est posé qu'à la fin). Si elle a déjà été poussée hors
// de l'écran par un geste (transformation en cours), elle disparaît tout de suite.
function hideSheet(el) {
  if (el.classList.contains("hidden") || el.classList.contains("closing")) return;
  const content = el.firstElementChild;
  if (reduceMotion.matches || (content && content.style.transform)) {
    el.classList.add("hidden");
    return;
  }
  el.classList.add("closing");
  el._closeTimer = setTimeout(() => {
    el.classList.remove("closing");
    el.classList.add("hidden");
  }, SHEET_CLOSE_MS);
}

function openModal(el) {
  if (el.classList.contains("closing")) {
    // Rouverte pendant qu'elle se refermait : on repart d'une feuille fermée.
    clearTimeout(el._closeTimer);
    el.classList.remove("closing");
    el.classList.add("hidden");
  }
  if (!el.classList.contains("hidden")) return;
  prepareSheet(el);
  el.classList.remove("hidden");
  pushLayer({ el, view: el.firstElementChild, close: () => hideSheet(el) });
}

function closeModal(el) {
  const top = layers[layers.length - 1];
  if (top && top.el === el) closeTopLayer();
  else hideSheet(el);
}

// Rejoue l'animation d'entrée d'un écran (onglet, fiche, page de Réglages).
// Désactivé : les écrans s'affichent instantanément (gardé pour ne pas toucher aux appels).
const SCREEN_ANIMATIONS = false;
function playEnter(el, cls = "view-enter") {
  if (!SCREEN_ANIMATIONS || !el || reduceMotion.matches) return;
  el.classList.remove("view-enter", "view-push");
  void el.offsetWidth; // redémarre l'animation
  el.classList.add(cls);
}
document.addEventListener("animationend", (e) => {
  if (e.target.classList && (e.animationName === "view-enter" || e.animationName === "view-push")) {
    e.target.classList.remove("view-enter", "view-push");
  }
});

// Poignée en haut de chaque feuille, et feuille qu'on tire vers le bas pour la fermer (depuis la poignée ou le
// titre, ou n'importe où quand son contenu est en haut de son défilement).
function prepareSheet(el) {
  const content = el.firstElementChild;
  if (!content || el._sheetReady) return;
  el._sheetReady = true;
  if (!content.querySelector(".sheet-handle")) {
    const handle = document.createElement("div");
    handle.className = "sheet-handle";
    content.prepend(handle);
  }
  let drag = null;
  content.addEventListener("touchstart", (e) => {
    drag = null;
    if (e.touches.length !== 1 || e.target.closest("input, textarea, select")) return;
    const top = content.getBoundingClientRect().top;
    const t = e.touches[0];
    const nearTop = t.clientY - top < 64;
    if (!nearTop && content.scrollTop > 0) return;
    drag = { y: t.clientY, x: t.clientX, t: Date.now(), dy: 0, active: false };
  }, { passive: true });
  content.addEventListener("touchmove", (e) => {
    if (!drag) return;
    const t = e.touches[0];
    const dy = t.clientY - drag.y;
    if (!drag.active) {
      if (Math.abs(dy) < 8) return;
      if (dy < 0 || Math.abs(t.clientX - drag.x) > Math.abs(dy)) { drag = null; return; }
      if (content.scrollTop > 0) { drag = null; return; }
      drag.active = true;
      content.classList.add("dragging");
    }
    e.preventDefault();
    drag.dy = Math.max(0, dy);
    content.style.transform = `translateY(${drag.dy}px)`;
  }, { passive: false });
  const end = () => {
    const d = drag;
    drag = null;
    if (!d || !d.active) return;
    content.classList.remove("dragging");
    const speed = d.dy / Math.max(1, Date.now() - d.t);
    if (d.dy > 110 || (d.dy > 40 && speed > 0.5)) {
      content.style.transition = "transform 0.18s ease-in";
      content.style.transform = "translateY(100%)";
      setTimeout(() => {
        closeModal(el);
        content.style.transition = "";
        content.style.transform = "";
      }, 180);
    } else {
      content.style.transition = "transform 0.22s cubic-bezier(0.2, 0.9, 0.3, 1)";
      content.style.transform = "";
      setTimeout(() => { content.style.transition = ""; }, 230);
    }
  };
  content.addEventListener("touchend", end, { passive: true });
  content.addEventListener("touchcancel", end, { passive: true });
}

// Images (couvertures) : apparaissent en fondu une fois chargées, sur un fond qui pulse en attendant.
document.addEventListener("load", (e) => { if (e.target.tagName === "IMG") e.target.classList.add("loaded"); }, true);
document.addEventListener("error", (e) => { if (e.target.tagName === "IMG") e.target.classList.add("loaded"); }, true);

// Image déjà en cache : affichée tout de suite, sans fondu (retour à la bibliothèque, changement de filtre).
function markCached(root) {
  root.querySelectorAll("img:not(.loaded)").forEach((img) => {
    if (img.complete && img.naturalWidth) img.classList.add("loaded");
  });
}

// En-tête : une fine ombre apparaît dès qu'on a fait défiler la page.
let scrolledFlag = false;
window.addEventListener("scroll", () => {
  const s = window.scrollY > 4;
  if (s !== scrolledFlag) {
    scrolledFlag = s;
    document.body.classList.toggle("scrolled", s);
  }
}, { passive: true });

// Écran secondaire ouvert depuis Réglages (Vérifications, Aperçu de lecture) : retour vers Réglages.
function openSettingsSubview(viewId) {
  goToTopView(viewId);
  navButtons.forEach((b) => b.classList.toggle("active", b.dataset.view === "settings-view"));
  lastTopView = "settings-view";
  window.scrollTo(0, 0);
  pushLayer({
    view: topViews[viewId],
    close: () => {
      goToTopView("settings-view");
      window.scrollTo(0, 0);
    },
  });
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
  playEnter(topViews[viewId]);
}

navButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    dropAllLayers();
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

// ----- Retour par balayage vers la droite (tous les écrans qui ont un bouton « Retour », et les popups) -----
// L'écran suit le doigt ; au-delà d'un tiers de l'écran (ou d'un geste rapide), il part et la couche se ferme tout de
// suite. Dès que le geste est reconnu comme horizontal, le défilement vertical est bloqué : le navigateur ne peut plus
// « voler » le geste en faisant défiler la page (c'est ce qui le rendait capricieux).
const SWIPE_DECIDE_PX = 10;
let swipe = null;

function swipeTarget() {
  const top = layers[layers.length - 1];
  return top ? top.view || null : null;
}

document.addEventListener("touchstart", (e) => {
  swipe = null;
  if (!layers.length || e.touches.length !== 1) return;
  if (e.target.closest("input, textarea, select, .no-swipe")) return;
  const t = e.touches[0];
  swipe = { x: t.clientX, y: t.clientY, t: Date.now(), dx: 0, horizontal: null, el: swipeTarget() };
}, { passive: true });

document.addEventListener("touchmove", (e) => {
  if (!swipe || e.touches.length !== 1) return;
  const t = e.touches[0];
  const dx = t.clientX - swipe.x;
  const dy = t.clientY - swipe.y;
  if (swipe.horizontal === null) {
    if (Math.abs(dx) < SWIPE_DECIDE_PX && Math.abs(dy) < SWIPE_DECIDE_PX) return;
    swipe.horizontal = dx > 0 && dx > Math.abs(dy) * 1.2;
    if (!swipe.horizontal) {
      swipe = null; // geste vertical (défilement) ou vers la gauche : on laisse faire
      return;
    }
    if (swipe.el) swipe.el.classList.add("swiping");
  }
  e.preventDefault(); // geste horizontal reconnu : pas de défilement en même temps
  swipe.dx = Math.max(0, dx);
  if (swipe.el) swipe.el.style.transform = `translateX(${swipe.dx}px)`;
}, { passive: false });

function endSwipe(cancelled) {
  const s = swipe;
  swipe = null;
  if (!s || !s.horizontal) return;
  const el = s.el;
  const speed = s.dx / Math.max(1, Date.now() - s.t); // px/ms
  const go = !cancelled && lastPopAt < s.t && (s.dx > window.innerWidth / 3 || (s.dx > 50 && speed > 0.35));
  if (!el) {
    if (go) closeTopLayer();
    return;
  }
  el.classList.remove("swiping");
  el.classList.add("swipe-settle");
  el.style.transform = go ? "translateX(100%)" : "translateX(0)";
  const done = () => {
    el.classList.remove("swipe-settle");
    if (go && layers.length && swipeTarget() === el) closeTopLayer();
    el.style.transform = "";
  };
  setTimeout(done, go ? 160 : 180);
}

document.addEventListener("touchend", () => endSwipe(false), { passive: true });
document.addEventListener("touchcancel", () => endSwipe(true), { passive: true });

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


// --- Icônes : une icône du jeu défini en tête de index.html ---
function icon(name) {
  return `<svg class="ico" aria-hidden="true"><use href="#i-${name}"/></svg>`;
}

// --- Messages discrets (à la place des alertes du navigateur) ---
// kind : "ok" (vert d'eau), "error" (orange) ou rien (neutre). Les confirmations restent celles du navigateur.
const toastBox = document.createElement("div");
toastBox.id = "toasts";
toastBox.setAttribute("role", "status");
toastBox.setAttribute("aria-live", "polite");
document.body.appendChild(toastBox);

function toast(message, kind = "", duration = 3600) {
  const el = document.createElement("div");
  el.className = "toast" + (kind ? " " + kind : "");
  el.textContent = message;
  toastBox.appendChild(el);
  requestAnimationFrame(() => el.classList.add("show"));
  const close = () => {
    el.classList.remove("show");
    setTimeout(() => el.remove(), 250);
  };
  el.addEventListener("click", close);
  setTimeout(close, duration);
}

// --- Couverture introuvable : à la place de l'icône « image cassée » du navigateur, un fond neutre avec un livre ---
const BLANK_IMAGE = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
document.addEventListener("error", (e) => {
  const img = e.target;
  if (img instanceof HTMLImageElement && !img.classList.contains("img-missing")) {
    img.classList.add("img-missing");
    img.src = BLANK_IMAGE;
  }
}, true);

// --- Clavier : les cartes et les lignes cliquables (role="button") s'activent avec Entrée ou Espace ---
document.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" && e.key !== " ") return;
  const el = e.target;
  if (el instanceof HTMLElement && el.getAttribute("role") === "button" && el.tagName !== "BUTTON") {
    e.preventDefault();
    el.click();
  }
});

// --- Pas de zoom par pincement : Safari (iPhone) ignore user-scalable=no de la balise viewport, on bloque donc
// directement ses gestes de zoom. Le défilement et le balayage de retour ne sont pas concernés.
for (const type of ["gesturestart", "gesturechange", "gestureend"]) {
  document.addEventListener(type, (e) => e.preventDefault(), { passive: false });
}
