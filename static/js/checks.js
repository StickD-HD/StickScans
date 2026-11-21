// Réglages › Vérifications : journal des vérifications.
// Fichier 6/15 : chargé dans l'ordre par index.html ; tous partagent la même portée globale.

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

document.getElementById("open-checks-btn").addEventListener("click", () => {
  goToTopView("checks-view");
  navButtons.forEach((b) => b.classList.toggle("active", b.dataset.view === "settings-view"));
  lastTopView = "settings-view";
  loadChecks();
});
document.getElementById("checks-back-btn").addEventListener("click", () => goToTopView("settings-view"));
document.getElementById("checks-refresh-btn").addEventListener("click", loadChecks);
