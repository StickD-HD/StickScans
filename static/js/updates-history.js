// Onglets Nouveautés et Historique (statistiques de lecture comprises).
// Fichier 5/15 : chargé dans l'ordre par index.html ; tous partagent la même portée globale.

function renderGroupedList(container, items, dateField, labelFn, showTime = false) {
  container.innerHTML = "";
  if (items.length === 0) {
    container.innerHTML = '<p class="empty-msg">Rien pour l\'instant.</p>';
    return;
  }
  let lastBucket = null;
  for (const item of items) {
    const bucket = formatDateBucket(item[dateField]);
    if (bucket !== lastBucket) {
      const h2 = document.createElement("h2");
      h2.className = "date-bucket";
      h2.textContent = bucket;
      container.appendChild(h2);
      lastBucket = bucket;
    }
    const row = document.createElement("div");
    row.className = "update-row";
    row.innerHTML = `
      <img src="${escapeHtml(item.series_cover)}" alt="" loading="lazy">
      <span>${labelFn(item)}${showTime ? `<small class="update-time">${formatTimeLabel(item[dateField])}</small>` : ""}</span>
    `;
    row.addEventListener("click", () => openChaptersView(item.series_id));
    container.appendChild(row);
  }
}

async function loadUpdates() {
  fetch("/api/site-status").then((r) => r.json()).then((st) => {
    const banner = document.getElementById("updates-pause-banner");
    const text = sitePauseText(st);
    banner.textContent = text ? "⏸ " + text : "";
    banner.classList.toggle("hidden", !text);
  }).catch(() => {});
  const res = await fetch("/api/updates");
  const items = await res.json();
  renderGroupedList(
    document.getElementById("updates-list"),
    items,
    "discovered_at",
    (item) => `Chapitre ${escapeHtml(item.number)} de ${escapeHtml(item.series_title)}`,
    true
  );
}

// Regroupe les lectures d'une même série faites à moins de 30 min d'écart (une "session").
function groupHistory(items) {
  const parse = (s) => new Date(s.replace(" ", "T") + "Z").getTime();
  const groups = [];
  for (const item of items) {
    const last = groups[groups.length - 1];
    const lastTime = last ? parse(last.chapters[last.chapters.length - 1].read_at) : 0;
    if (last && last.series_id === item.series_id && lastTime - parse(item.read_at) <= 30 * 60 * 1000) {
      last.chapters.push(item);
    } else {
      groups.push({ series_id: item.series_id, series_title: item.series_title, series_cover: item.series_cover, read_at: item.read_at, chapters: [item] });
    }
  }
  return groups;
}

function renderHistoryList(container, items) {
  container.innerHTML = "";
  if (items.length === 0) {
    container.innerHTML = '<p class="empty-msg">Rien pour l\'instant.</p>';
    return;
  }
  let lastBucket = null;
  for (const group of groupHistory(items)) {
    const bucket = formatDateBucket(group.read_at);
    if (bucket !== lastBucket) {
      const h2 = document.createElement("h2");
      h2.className = "date-bucket";
      h2.textContent = bucket;
      container.appendChild(h2);
      lastBucket = bucket;
    }
    const numbers = group.chapters.map((c) => c.number_float);
    const first = group.chapters.find((c) => c.number_float === Math.min(...numbers));
    const lastCh = group.chapters.find((c) => c.number_float === Math.max(...numbers));
    const count = group.chapters.length;
    const label = count === 1
      ? `Chapitre ${escapeHtml(first.number)} de ${escapeHtml(group.series_title)}`
      : `Chapitres ${escapeHtml(first.number)} à ${escapeHtml(lastCh.number)} de ${escapeHtml(group.series_title)}`;
    const row = document.createElement("div");
    row.className = "update-row";
    row.innerHTML = `
      <img src="${escapeHtml(group.series_cover)}" alt="" loading="lazy">
      <span>${label}${count > 1 ? `<small class="update-time">${count} chapitres</small>` : ""}</span>
      <button class="history-remove-btn" title="Retirer de l'historique" aria-label="Retirer de l'historique">✕</button>
    `;
    row.addEventListener("click", () => openChaptersView(group.series_id));
    row.querySelector(".history-remove-btn").addEventListener("click", async (e) => {
      e.stopPropagation();
      const msg = count === 1
        ? "Retirer ce chapitre de l'historique ? (il reste marqué comme lu)"
        : `Retirer ces ${count} chapitres de l'historique ? (ils restent marqués comme lus)`;
      if (!confirm(msg)) return;
      await fetch("/api/history/remove", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chapter_ids: group.chapters.map((c) => c.chapter_id) }),
      });
      loadHistory();
    });
    container.appendChild(row);
  }
}

async function loadHistory() {
  const tzOffset = -new Date().getTimezoneOffset(); // minutes d'avance sur UTC (Paris été : 120)
  const [statsRes, itemsRes] = await Promise.all([fetch(`/api/stats?tz_offset=${tzOffset}`), fetch("/api/history")]);
  const stats = await statsRes.json();
  const items = await itemsRes.json();

  // Par défaut : seul le graphique des 7 jours est visible. Les autres stats s'ouvrent d'un appui.
  let statsOpen = false;
  try { statsOpen = localStorage.getItem("historyStatsOpen") === "1"; } catch (e) {}
  const statsDiv = document.getElementById("history-stats");
  const toggleHtml = `<button type="button" class="stats-toggle-link" aria-expanded="${statsOpen}">${statsOpen ? "Masquer ▴" : "Plus de stats ▾"}</button>`;
  statsDiv.innerHTML = `
    ${renderWeekChart(stats.last_7_days, toggleHtml)}
    <div class="stats-details${statsOpen ? "" : " hidden"}">
      <div class="stat-box"><strong>${stats.chapters_this_week}</strong><span>cette semaine</span></div>
      <div class="stat-box"><strong>${stats.chapters_this_month}</strong><span>ce mois-ci</span></div>
      <div class="stat-box"><strong>${stats.total_read}</strong><span>au total</span></div>
      <div class="stat-box"><strong>${stats.streak_days}</strong><span>${stats.streak_days > 1 ? "jours d'affilée" : "jour d'affilée"}</span></div>
      ${stats.top_series_title ? `<div class="stat-box"><strong>${escapeHtml(stats.top_series_title)}</strong><span>${stats.top_series_count} chapitres · plus lue</span></div>` : ""}
    </div>
  `;
  const toggleBtn = statsDiv.querySelector(".stats-toggle-link");
  const detailsDiv = statsDiv.querySelector(".stats-details");
  toggleBtn.addEventListener("click", () => {
    const nowHidden = detailsDiv.classList.toggle("hidden");
    toggleBtn.setAttribute("aria-expanded", String(!nowHidden));
    toggleBtn.textContent = nowHidden ? "Plus de stats ▾" : "Masquer ▴";
    try { localStorage.setItem("historyStatsOpen", nowHidden ? "0" : "1"); } catch (e) {}
  });

  renderHistoryList(document.getElementById("history-list"), items);
}

function renderWeekChart(days, toggleHtml = "") {
  const max = Math.max(1, ...days.map((d) => d.count));
  const letters = ["D", "L", "M", "M", "J", "V", "S"];
  const bars = days.map((d) => {
    const height = d.count === 0 ? 3 : Math.max(8, Math.round((d.count / max) * 44));
    const letter = letters[new Date(d.date + "T12:00:00").getDay()];
    return `<div class="week-col"><em>${d.count || ""}</em><i class="${d.count ? "on" : ""}" style="height:${height}px"></i><b>${letter}</b></div>`;
  }).join("");
  return `<div class="week-chart"><div class="week-head"><div class="week-title">Chapitres lus par jour · 7 derniers jours</div>${toggleHtml}</div><div class="week-bars">${bars}</div></div>`;
}

document.getElementById("clear-history-btn").addEventListener("click", async () => {
  if (!confirm("Effacer tout l'historique de lecture ? (les chapitres restent marqués comme lus, seul l'historique disparaît)")) return;
  await fetch("/api/history", { method: "DELETE" });
  loadHistory();
});
