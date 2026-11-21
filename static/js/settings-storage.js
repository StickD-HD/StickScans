// Réglages › Stockage : espace utilisé et nettoyage.
// Fichier 13/15 : chargé dans l'ordre par index.html ; tous partagent la même portée globale.

// ----------------------------------------------------------------------
// Stockage : espace utilisé et nettoyage
// ----------------------------------------------------------------------
const storageTotal = document.getElementById("storage-total");
const storageBar = document.getElementById("storage-bar");
const storageList = document.getElementById("storage-list");
const storageDisk = document.getElementById("storage-disk");
const storageMsg = document.getElementById("storage-msg");

async function loadStorage() {
  let info;
  try {
    info = await (await fetch("/api/storage")).json();
  } catch (e) {
    storageTotal.textContent = "—";
    storageMsg.textContent = "⚠️ Impossible de lire le stockage.";
    return;
  }
  const db = info.database;
  const known = db.bytes + info.backups.bytes + info.logs.bytes;
  const other = Math.max(0, info.data.bytes - known);
  const cache = info.page_cache;
  const parts = [
    ["seg-db", "Base de données", `${plural(db.series, "série", "séries")} · ${plural(db.chapters, "chapitre", "chapitres")}`, db.bytes],
    ["seg-backup", "Sauvegardes", plural(info.backups.count, "copie", "copies"), info.backups.bytes],
    ["seg-logs", "Journaux", plural(info.logs.files, "fichier", "fichiers"), info.logs.bytes],
    ["seg-cache", "Cache des pages", cache.active ? plural(cache.files, "page", "pages") : "Désactivé", cache.bytes],
  ];
  if (other > 0) parts.push(["seg-other", "Autres fichiers", "", other]);
  const total = parts.reduce((sum, p) => sum + p[3], 0);

  storageTotal.textContent = formatBytes(total);
  storageBar.innerHTML = parts
    .filter((p) => p[3] > 0)
    .map((p) => `<i class="${p[0]}" style="width:${Math.max(1.5, (p[3] / Math.max(1, total)) * 100)}%"></i>`)
    .join("");
  storageList.innerHTML = parts
    .map((p) => `<li><span class="info-dot ${p[0]}"></span><span class="info-name">${escapeHtml(p[1])}<small>${escapeHtml(p[2])}</small></span><span class="info-size">${formatBytes(p[3])}</span></li>`)
    .join("");
  storageDisk.textContent = info.disk
    ? `Disque : ${formatBytes(info.disk.free)} libres sur ${formatBytes(info.disk.total)}.`
    : "";

  document.getElementById("clear-cache-info").textContent = cache.active
    ? `${formatBytes(cache.bytes)} · ${plural(cache.files, "page", "pages")}`
    : "Cache désactivé";
  document.getElementById("clear-logs-info").textContent = formatBytes(info.logs.bytes);
  document.getElementById("clear-checks-info").textContent = plural(db.check_runs, "vérification enregistrée", "vérifications enregistrées");
}

async function storageAction(button, url, confirmText, describe) {
  if (confirmText && !confirm(confirmText)) return;
  button.disabled = true;
  storageMsg.textContent = "…";
  try {
    const res = await fetch(url, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Échec");
    storageMsg.textContent = describe(data);
  } catch (e) {
    storageMsg.textContent = "⚠️ " + e.message;
  } finally {
    button.disabled = false;
    loadStorage();
  }
}

document.getElementById("clear-cache-btn").addEventListener("click", (e) =>
  storageAction(e.currentTarget, "/api/storage/clear-page-cache", "", (d) =>
    d.files ? `Cache vidé : ${plural(d.files, "page supprimée", "pages supprimées")}, ${formatBytes(d.bytes)} libérés.` : "Le cache est déjà vide."));
document.getElementById("clear-logs-btn").addEventListener("click", (e) =>
  storageAction(e.currentTarget, "/api/storage/clear-logs", "Effacer les journaux de vérification ?", (d) =>
    `Journaux effacés : ${formatBytes(d.bytes)} libérés.`));
document.getElementById("clear-checks-btn").addEventListener("click", (e) =>
  storageAction(e.currentTarget, "/api/storage/clear-check-history",
    "Effacer le détail des vérifications passées ? Tes séries, chapitres et ton historique de lecture ne sont pas touchés.", (d) =>
    `${plural(d.runs, "vérification effacée", "vérifications effacées")}.`));
document.getElementById("optimize-db-btn").addEventListener("click", (e) =>
  storageAction(e.currentTarget, "/api/storage/optimize", "", (d) =>
    `Base optimisée : ${formatBytes(d.before)} → ${formatBytes(d.after)}.`));

document.getElementById("clear-app-cache-btn").addEventListener("click", async () => {
  if (!confirm("Vider le cache de l'application et la recharger ? Tes données et tes réglages ne sont pas touchés.")) return;
  try {
    if ("serviceWorker" in navigator) {
      const registrations = await navigator.serviceWorker.getRegistrations();
      await Promise.all(registrations.map((r) => r.unregister()));
    }
    if (window.caches) {
      const keys = await caches.keys();
      await Promise.all(keys.map((k) => caches.delete(k)));
    }
  } catch (e) {}
  location.reload();
});
document.getElementById("reset-prefs-btn").addEventListener("click", () => {
  if (!confirm("Réinitialiser l'affichage, les filtres et les préférences de cet appareil ?")) return;
  try {
    ["stickscans_filters", DISPLAY_KEY, "historyStatsOpen"].forEach((k) => localStorage.removeItem(k));
  } catch (e) {}
  location.reload();
});
