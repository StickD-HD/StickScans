// États de lecture : onglets de la bibliothèque, bouton de la fiche, choix pour plusieurs séries.
// L'état vient du serveur (champ « state ») : choisi à la main, sinon statut AniList (pause, abandon, terminé),
// sinon déduit de ta lecture. « reading_state » vaut null quand l'état est automatique.

const READING_STATES = [
  { key: "reading", label: "En cours", hint: "Tu la lis en ce moment" },
  { key: "planning", label: "À lire", hint: "Pas encore commencée" },
  { key: "paused", label: "En pause", hint: "Mise de côté pour l'instant" },
  { key: "completed", label: "Terminé", hint: "Lue jusqu'au bout" },
  { key: "dropped", label: "Abandonné", hint: "Tu ne la suis plus" },
];
const STATE_LABEL = Object.fromEntries(READING_STATES.map((s) => [s.key, s.label]));
const STATE_TAB_KEY = "stickscans_state_tab";
const stateTabs = document.getElementById("state-tabs");
const stateModal = document.getElementById("state-modal");
const stateOptions = document.getElementById("state-options");
let activeStateTab = "";
try { activeStateTab = localStorage.getItem(STATE_TAB_KEY) || ""; } catch (e) {}

// --- Onglets de la bibliothèque (Tout · En cours · À lire · …, avec le nombre de séries) ---
function renderStateTabs(allSeries) {
  const counts = {};
  for (const s of allSeries) counts[s.state] = (counts[s.state] || 0) + 1;
  if (activeStateTab && !counts[activeStateTab]) activeStateTab = ""; // onglet vidé : retour à « Tout »
  const tabs = [{ key: "", label: "Tout", n: allSeries.length },
    ...READING_STATES.filter((st) => counts[st.key]).map((st) => ({ key: st.key, label: st.label, n: counts[st.key] }))];
  stateTabs.innerHTML = tabs.map((t) => `<button type="button" class="state-tab${t.key === activeStateTab ? " active" : ""}${t.key ? " state-" + t.key : ""}" data-state="${t.key}">${escapeHtml(t.label)}<span>${t.n}</span></button>`).join("");
  stateTabs.classList.toggle("hidden", allSeries.length === 0);
}

function filterByState(allSeries) {
  return activeStateTab ? allSeries.filter((s) => s.state === activeStateTab) : allSeries;
}

stateTabs.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-state]");
  if (!btn || btn.dataset.state === activeStateTab) return;
  activeStateTab = btn.dataset.state;
  try { localStorage.setItem(STATE_TAB_KEY, activeStateTab); } catch (err) {}
  if (librarySelecting) setLibrarySelecting(false);
  if (lastLibraryText) renderLibrary(lastLibraryText, true);
  btn.scrollIntoView({ inline: "nearest", block: "nearest" });
});

// --- Feuille de choix : une série (fiche) ou plusieurs (sélection) ---
let statePick = null; // (state ou null) => Promise

function openStateSheet({ title, manual, effective, auto, onPick, fromSheet }) {
  statePick = onPick;
  document.getElementById("state-modal-title").textContent = title;
  const autoLabel = auto ? `selon ta lecture (actuellement « ${STATE_LABEL[auto]} »)` : "selon la lecture de chaque série";
  stateOptions.innerHTML = READING_STATES.map((st) => `
      <button type="button" data-pick="${st.key}" class="state-option state-${st.key}${manual === st.key ? " current" : ""}">
        <span class="state-dot"></span><span class="state-text"><strong>${st.label}</strong><small>${st.hint}</small></span>
        ${manual === st.key ? icon("check") : ""}
      </button>`).join("") + `
      <button type="button" data-pick="" class="state-option state-auto${effective !== undefined && !manual ? " current" : ""}">
        <span class="state-dot"></span><span class="state-text"><strong>Automatique</strong><small>${escapeHtml(autoLabel)}</small></span>
        ${effective !== undefined && !manual ? icon("check") : ""}
      </button>`;
  if (fromSheet) swapModal(fromSheet, stateModal);
  else openModal(stateModal);
}

stateOptions.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-pick]");
  if (!btn || !statePick) return;
  const pick = btn.dataset.pick || null;
  stateOptions.querySelectorAll("button").forEach((b) => (b.disabled = true));
  try {
    await statePick(pick);
    closeModal(stateModal);
  } catch (err) {
    toast(err.message || "Changement impossible pour l'instant", "error");
  } finally {
    stateOptions.querySelectorAll("button").forEach((b) => (b.disabled = false));
  }
});
document.getElementById("state-modal-close").addEventListener("click", () => closeModal(stateModal));
closeOnBackdrop(stateModal);

// --- Bouton de la fiche ---
const stateBtn = document.getElementById("state-btn");
let stateSeries = null;

function renderStateButton(s) {
  stateSeries = s;
  stateBtn.className = `state-${s.state || "planning"}`;
  document.getElementById("state-btn-label").textContent = STATE_LABEL[s.state] || "À lire";
  stateBtn.title = s.reading_state ? "État choisi par toi : toucher pour changer" : "État automatique (selon ta lecture) : toucher pour changer";
}

stateBtn.addEventListener("click", () => {
  if (!stateSeries) return;
  const s = stateSeries;
  openStateSheet({
    title: "État de lecture",
    manual: s.reading_state,
    effective: s.state,
    auto: s.auto_state,
    onPick: async (state) => {
      const res = await fetch(`/api/series/${s.id}/state`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ state }),
      });
      if (!res.ok) throw new Error("Changement impossible pour l'instant");
      const updated = await res.json();
      if (currentSeriesId === s.id) {
        renderStateButton(updated);
        const entry = detailCache.get(s.id);
        if (entry) detailCache.set(s.id, { ...entry, series: updated });
      }
      toast(state ? `État : ${STATE_LABEL[state]}` : `État automatique : ${STATE_LABEL[updated.state]}`, "ok");
    },
  });
});

// --- Plusieurs séries (sélection dans la bibliothèque) ---
function openBulkStateSheet() {
  const n = librarySelected.size;
  openStateSheet({
    title: `État de ${n} série${n > 1 ? "s" : ""}`,
    manual: null,
    effective: undefined,
    auto: null,
    fromSheet: bulkModal,
    onPick: async (state) => {
      const count = await runBulk("set_state", { state });
      toast(`${count} série${count > 1 ? "s" : ""} : ${state ? STATE_LABEL[state] : "état automatique"}`, "ok");
      setLibrarySelecting(false);
      loadLibrary();
    },
  });
}
