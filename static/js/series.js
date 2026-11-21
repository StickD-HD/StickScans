// Fiche d'une série : informations, chapitres (lecture, sélection), catégories, panneau AniList, alignement.
// Fichier 3/15 : chargé dans l'ordre par index.html ; tous partagent la même portée globale.

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
  missing: "page introuvable",
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
let currentChapters = [];
let currentAnilistProgress = null; // progression AniList de la série ouverte (null = non liée)
let selectionMode = false;
let selectedChapterIds = new Set();

setupPopover(detailMenuBtn, detailMenu);

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
  renderUrlChange(s);
  detailTeam.textContent = s.team ? "Team trad : " + s.team : "";
  document.getElementById("detail-platform").textContent = s.platform ? "Plateforme officielle : " + s.platform : "";
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
  scheduleAnilistRefresh();
}

// La progression part vers AniList en arrière-plan (la réponse n'attend plus AniList) : quelques secondes plus tard,
// on relit seulement la partie AniList de la fiche pour y voir la nouvelle progression, ou l'erreur éventuelle.
// Rien n'est fait si le panneau AniList est ouvert (saisie possible) ou si une autre fiche a été ouverte entre-temps.
let anilistRefreshTimer = null;
function scheduleAnilistRefresh() {
  if (currentAnilistProgress === null) return; // série non liée à AniList
  clearTimeout(anilistRefreshTimer);
  const seriesId = currentSeriesId;
  anilistRefreshTimer = setTimeout(async () => {
    if (currentSeriesId !== seriesId || !anilistLinked.classList.contains("hidden")) return;
    try {
      const res = await fetch(`/api/series/${seriesId}`);
      if (res.ok && currentSeriesId === seriesId && anilistLinked.classList.contains("hidden")) {
        renderAnilistSection(await res.json());
      }
    } catch (e) {}
  }, 4000);
}

async function markReadUpTo(number) {
  await fetch(`/api/series/${currentSeriesId}/mark-read-up-to`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ number: String(number) }),
  });
  loadChapters();
  scheduleAnilistRefresh();
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
  scheduleAnilistRefresh();
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
let savedDates = { start: "", end: "" }; // idem pour les dates : une date vidée est effacée sur AniList

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
    savedDates = { start: s.anilist_start_date || "", end: s.anilist_end_date || "" };
    anilistStartInput.value = savedDates.start;
    anilistEndInput.value = savedDates.end;
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
    };
    // Dates envoyées seulement si elles ont changé ; "" (champ vidé) efface la date sur AniList.
    if (anilistStartInput.value !== savedDates.start) payload.start_date = anilistStartInput.value;
    if (anilistEndInput.value !== savedDates.end) payload.end_date = anilistEndInput.value;
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

closeOnBackdrop(anilistModal);
closeOnBackdrop(seriesCategoryModal);


// --- Fiche déplacée ou disparue du site : nouvelle adresse (chapitres lus et historique gardés) ---
const urlChange = document.getElementById("url-change");
const urlChangeText = document.getElementById("url-change-text");
const urlChangeInput = document.getElementById("url-change-input");
const urlChangeBtn = document.getElementById("url-change-btn");
const urlChangeError = document.getElementById("url-change-error");
const URL_CHANGE_HELP = "Colle la nouvelle adresse de la fiche sur scan-manga : tes chapitres lus et ton historique sont gardés.";

function showUrlChange(text, warn) {
  urlChangeText.textContent = text;
  urlChange.classList.toggle("warn", warn);
  urlChangeError.classList.add("hidden");
  urlChange.classList.remove("hidden");
}

// Affichée d'office quand la page est introuvable sur le site ; sinon, seulement depuis le menu.
function renderUrlChange(s) {
  urlChangeInput.value = "";
  if (s.missing_since) {
    const since = new Date(s.missing_since.replace(" ", "T") + "Z").toLocaleDateString("fr-FR", { day: "numeric", month: "long" });
    showUrlChange(`⚠ Page introuvable sur scan-manga depuis le ${since}. La série a peut-être changé d'adresse. ${URL_CHANGE_HELP}`, true);
  } else {
    urlChange.classList.add("hidden");
  }
}

document.getElementById("change-url-menu-btn").addEventListener("click", () => {
  showUrlChange(URL_CHANGE_HELP, false);
  urlChangeInput.focus();
});

urlChangeBtn.addEventListener("click", async () => {
  const url = urlChangeInput.value.trim();
  if (!url) return;
  urlChangeBtn.disabled = true;
  urlChangeBtn.textContent = "Vérification…";
  urlChangeError.classList.add("hidden");
  try {
    const res = await fetch(`/api/series/${currentSeriesId}/url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Adresse refusée");
    await loadSeriesDetail();
    await loadChapters();
    const n = (data.new_chapters || []).length;
    alert(`Adresse mise à jour.${n ? ` ${n} nouveau${n > 1 ? "x" : ""} chapitre${n > 1 ? "s" : ""}.` : ""}`);
  } catch (e) {
    urlChangeError.textContent = "⚠ " + e.message;
    urlChangeError.classList.remove("hidden");
  } finally {
    urlChangeBtn.disabled = false;
    urlChangeBtn.textContent = "Remplacer";
  }
});
