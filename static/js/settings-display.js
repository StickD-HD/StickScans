// Réglages › Affichage (préférences propres à l'appareil).
// Fichier 9/15 : chargé dans l'ordre par index.html ; tous partagent la même portée globale.

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
