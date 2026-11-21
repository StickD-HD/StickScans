// Réglages › Vérifications : état du site, requêtes par jour, file d'attente, erreurs, refus et journal détaillé.
// Fichier 6/15 : chargé dans l'ordre par index.html ; tous partagent la même portée globale.


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

// Liste dépliable : les `shown` premières lignes, puis un bouton pour voir le reste.
function foldableList(rows, shown, moreLabel) {
  if (rows.length <= shown) return rows.join("");
  return rows.slice(0, shown).join("") +
    `<div class="hidden fold-rest">${rows.slice(shown).join("")}</div>` +
    `<button type="button" class="fold-btn">${moreLabel}</button>`;
}

function renderChecksOverview(d) {
  const st = d.site;
  const plural = (n, one, many) => `${n} ${n > 1 ? many : one}`;

  // État du site et requêtes du jour
  const pause = sitePauseText(st);
  const state = `<div class="checks-card">
    <p>${pause ? `<strong class="warn-text">⏸ ${escapeHtml(pause)}</strong>` : "<strong>✓ Requêtes autorisées</strong>"}</p>
    <p>${plural(st.requests_today, "requête", "requêtes")} aujourd'hui sur ${st.daily_limit} au maximum${st.shared ? ", toutes instances du serveur confondues" : ""}.</p>
  </div>`;

  // Requêtes par jour (7 jours)
  const days = d.history.per_day;
  const max = Math.max(1, ...days.map((x) => x.count));
  const letters = ["D", "L", "M", "M", "J", "V", "S"];
  const bars = days.map((x) => {
    const height = x.count === 0 ? 3 : Math.max(8, Math.round((x.count / max) * 44));
    const letter = letters[new Date(x.date + "T12:00:00").getDay()];
    return `<div class="week-col" title="${escapeHtml(x.date)} : ${x.count}"><em>${x.count || ""}</em><i class="${x.count ? "on" : ""}" style="height:${height}px"></i><b>${letter}</b></div>`;
  }).join("");
  const chart = `<div class="week-chart"><div class="week-title">Requêtes vers le site · 7 jours · max ${d.history.daily_limit} par jour</div><div class="week-bars">${bars}</div></div>`;

  // File d'attente
  const queueRows = d.queue.map((q) => {
    const when = q.skipped
      ? `<span class="q-skip">ignorée · ${escapeHtml(q.skipped)}</span>`
      : `${escapeHtml(q.next_check_at ? formatFuture(q.next_check_at) : "dès que possible")}${CHECK_REASON_LABELS[q.reason] ? `<small>${escapeHtml(CHECK_REASON_LABELS[q.reason])}</small>` : ""}`;
    return `<div class="q-row${q.last_error ? " bad" : ""}"><span class="q-title">${q.last_error ? "⚠ " : ""}${escapeHtml(q.title)}</span><span class="q-when">${when}</span></div>`;
  });
  const queue = `<section class="checks-block"><h2>Prochaines vérifications</h2>${
    queueRows.length ? foldableList(queueRows, 8, `Voir les ${queueRows.length} séries`) : '<p class="empty-msg">Aucune série.</p>'}</section>`;

  // Erreurs des séries (7 jours)
  const errorRows = d.errors.map((e) =>
    `<div class="q-row bad"><span class="q-title">${escapeHtml(e.series_title || "?")}<small class="run-error">${escapeHtml(e.error || "")}</small></span><span class="q-when">${escapeHtml(formatWhen(e.started_at))}</span></div>`);
  const errors = `<section class="checks-block"><h2>Erreurs des séries · 7 jours</h2>${
    errorRows.length ? foldableList(errorRows, 5, `Voir les ${errorRows.length} erreurs`) : '<p class="empty-msg">Aucune erreur ✓</p>'}</section>`;

  // Refus du site
  const blockRows = d.history.blocks.map((b) => {
    const when = new Date(b.at).toLocaleString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    return `<div class="q-row"><span class="q-title">${escapeHtml(b.reason || "?")}<small>refus n° ${b.strike} · pause de ${formatWait(b.seconds)}</small></span><span class="q-when">${escapeHtml(when)}</span></div>`;
  });
  const blocks = `<section class="checks-block"><h2>Refus du site</h2>${
    blockRows.length ? foldableList(blockRows, 3, `Voir les ${blockRows.length} refus`) : '<p class="empty-msg">Aucun refus enregistré ✓</p>'}</section>`;

  const box = document.getElementById("checks-overview");
  box.innerHTML = state + chart + queue + errors + blocks;
  box.querySelectorAll(".fold-btn").forEach((btn) => btn.addEventListener("click", () => {
    btn.previousElementSibling.classList.remove("hidden");
    btn.remove();
  }));
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
  const [overviewRes, listRes] = await Promise.all([fetch("/api/checks/overview"), fetch("/api/checks?limit=60")]);
  renderChecksOverview(await overviewRes.json());
  renderChecksList(await listRes.json());
}

document.getElementById("open-checks-btn").addEventListener("click", () => {
  openSettingsSubview("checks-view");
  loadChecks();
});
document.getElementById("checks-back-btn").addEventListener("click", () => closeTopLayer());
document.getElementById("checks-refresh-btn").addEventListener("click", loadChecks);
