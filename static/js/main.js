// Démarrage de l'appli (chargé en dernier : tous les autres fichiers sont prêts).
// Fichier 15/15 : chargé dans l'ordre par index.html ; tous partagent la même portée globale.

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
applyDisplayPrefs();
syncAnilist();
