// Démarrage de l'appli (chargé en dernier : tous les autres fichiers sont prêts).
// Fichier 15/15 : chargé dans l'ordre par index.html ; tous partagent la même portée globale.

async function init() {
  // Un rechargement peut laisser une entrée d'historique orpheline : on repart d'une base propre.
  const shared = new URLSearchParams(location.search);
  const sharedText = [shared.get("url"), shared.get("text"), shared.get("title")].filter(Boolean).join("\n");
  history.replaceState(null, "", location.pathname);

  // Tout de suite : la dernière bibliothèque affichée sur cet appareil (même sans réseau), en attendant la vraie.
  try {
    const last = localStorage.getItem(LIBRARY_CACHE_PREFIX + "last");
    if (last) renderLibrary(last);
  } catch (e) {}

  const saved = getSavedFilters();
  if (saved.sort) sortSelect.value = saved.sort;
  if (!sortSelect.value) sortSelect.value = "last_checked_at"; // tri enregistré qui n'existe plus
  if (saved.anilist) anilistFilterSelect.value = saved.anilist;
  if (saved.search) {
    searchInput.value = saved.search;
    searchBar.classList.remove("hidden");
  }
  if (saved.hideRead) hideReadCheckbox.checked = saved.hideRead;
  if (saved.categoryId) activeCategoryId = saved.categoryId;

  // Les trois listes (genres, statuts, catégories) en même temps plutôt qu'à la suite ; sans réseau, on continue.
  await Promise.allSettled([loadGenreSelect(), loadStatuses(), loadCategorySelect()]);
  if (saved.genre) genreSelect.value = saved.genre;
  if (saved.status) statusSelect.value = saved.status;

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
