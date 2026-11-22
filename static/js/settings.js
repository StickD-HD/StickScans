// Réglages : liste des rubriques et navigation entre les pages.
// Fichier 8/15 : chargé dans l'ordre par index.html ; tous partagent la même portée globale.

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
  backup: () => { loadBackups(); loadGdrive(); },
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

// Ouvre une page de Réglages (Affichage, Catégories...) comme une couche : « Retour », balayage et retour Android
// ramènent à la liste des rubriques.
function openSettingsSubpage(name) {
  showSettingsPage(name);
  pushLayer({ settingsPage: true, view: settingsView, close: () => showSettingsPage(null) });
}

function openSettingsPage(name) {
  dropAllLayers();
  goToTopView("settings-view");
  navButtons.forEach((b) => b.classList.toggle("active", b.dataset.view === "settings-view"));
  lastTopView = "settings-view";
  openSettingsSubpage(name);
}

settingsHome.addEventListener("click", (e) => {
  const row = e.target.closest("[data-page]");
  if (row) openSettingsSubpage(row.dataset.page);
});
settingsBackBtn.addEventListener("click", () => {
  const top = layers[layers.length - 1];
  if (top && top.settingsPage) closeTopLayer();
  else showSettingsPage(null);
});

// Version qui tourne (écrite par outils/deploy.sh), en bas de la liste des rubriques.
fetch("/api/version").then((r) => r.json()).then((v) => {
  if (!v.commit) return;
  const when = v.date ? new Date(v.date.replace(" ", "T")).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" }) : "";
  const el = document.getElementById("app-version");
  el.textContent = `Version ${v.commit}${when ? " du " + when : ""}`;
  el.title = v.subject || "";
}).catch(() => {});
