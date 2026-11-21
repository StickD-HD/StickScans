// Réglages › Aperçu de lecture : temps passé et séries les plus lues.
// Fichier 7/15 : chargé dans l'ordre par index.html ; tous partagent la même portée globale.

// --- Aperçu de lecture (Réglages) : temps passé à lire et classement des séries ---
const readingView = document.getElementById("reading-view");
topViews["reading-view"] = readingView; // ouvert depuis Réglages, pas dans la barre du bas
let readingPeriod = "week";
const READING_PERIODS = [["week", "Semaine"], ["month", "Mois"], ["all", "Tout"]];
const READING_PERIOD_LABELS = { week: "7 derniers jours", month: "30 derniers jours", all: "Depuis le début" };

document.getElementById("open-reading-btn").addEventListener("click", () => {
  openSettingsSubview("reading-view");
  loadReadingOverview();
});
document.getElementById("reading-back-btn").addEventListener("click", () => closeTopLayer());

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
