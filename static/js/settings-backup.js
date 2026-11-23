// Réglages › Sauvegarde et restauration, export et import de la base.
// Fichier 14/15 : chargé dans l'ordre par index.html ; tous partagent la même portée globale.

document.getElementById("download-db-btn").addEventListener("click", () => {
  const tzOffset = -new Date().getTimezoneOffset();
  window.location.href = `/api/database/download?tz_offset=${tzOffset}`;
});

const importDbBtn = document.getElementById("import-db-btn");
const importDbInput = document.getElementById("import-db-input");

if (importDbBtn && importDbInput) {
  importDbBtn.addEventListener("click", () => {
    importDbInput.click();
  });

  importDbInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!confirm("⚠️ ATTENTION : L'importation va écraser TOUTE ta bibliothèque et ton historique actuels. Es-tu sûr de vouloir continuer ?")) {
      e.target.value = ""; // Réinitialiser
      return;
    }

    importDbBtn.disabled = true;
    importDbBtn.textContent = "Importation en cours...";

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/database/import", {
        method: "POST",
        body: formData,
      });
      
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Erreur lors de l'importation");
      
      toast("Base importée : l'application se recharge…", "ok");
      setTimeout(() => location.reload(), 1200); // recharge la page pour afficher les nouvelles données
    } catch (err) {
      toast("Import impossible : " + err.message, "error", 7000);
    } finally {
      importDbBtn.disabled = false;
      importDbBtn.textContent = "Importer une base";
      e.target.value = "";
    }
  });
}

// ----------------------------------------------------------------------
// Sauvegarde et restauration
// ----------------------------------------------------------------------
const backupEnabled = document.getElementById("backup-enabled");
const backupKeep = document.getElementById("backup-keep");
const backupList = document.getElementById("backup-list");
const backupMsg = document.getElementById("backup-msg");
const backupNowBtn = document.getElementById("backup-now-btn");

function renderBackups(data) {
  backupEnabled.checked = data.settings.enabled;
  if (![...backupKeep.options].some((o) => o.value === String(data.settings.keep))) {
    const opt = document.createElement("option");
    opt.value = String(data.settings.keep);
    opt.textContent = String(data.settings.keep);
    backupKeep.appendChild(opt);
  }
  backupKeep.value = String(data.settings.keep);
  backupKeep.disabled = !data.settings.enabled;
  if (data.backups.length === 0) {
    backupList.innerHTML = '<li class="backup-empty">Aucune sauvegarde pour l\'instant.</li>';
    return;
  }
  backupList.innerHTML = data.backups.map((b) => {
    const when = new Date(b.modified).toLocaleString("fr-FR", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
    const name = escapeHtml(b.name);
    return `<li class="backup-row" data-name="${name}">
      <div class="backup-info">
        <div class="backup-head"><strong>${escapeHtml(b.label)}</strong><em>${formatBytes(b.size)}</em></div>
        <span>${escapeHtml(when)}</span>
      </div>
      <div class="backup-actions">
        <button type="button" class="mini-btn" data-act="restore">Restaurer</button>
        <a class="mini-btn" href="/api/backups/${encodeURIComponent(b.name)}/download" download title="Télécharger" aria-label="Télécharger">${icon("download")}</a>
        <button type="button" class="mini-btn danger-btn" data-act="delete" title="Supprimer" aria-label="Supprimer">${icon("trash")}</button>
      </div>
    </li>`;
  }).join("");
}

async function loadBackups() {
  try {
    renderBackups(await (await fetch("/api/backups")).json());
  } catch (e) {
    backupMsg.textContent = "⚠️ Impossible de lire les sauvegardes.";
  }
}

async function saveBackupSettings(patch) {
  try {
    const res = await fetch("/api/settings/backups", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (!res.ok) throw new Error();
    backupMsg.textContent = "Enregistré ✓";
  } catch (e) {
    backupMsg.textContent = "⚠️ Réglage non enregistré.";
  }
  loadBackups();
}
backupEnabled.addEventListener("change", () => saveBackupSettings({ enabled: backupEnabled.checked }));
backupKeep.addEventListener("change", () => saveBackupSettings({ keep: Number(backupKeep.value) }));

backupNowBtn.addEventListener("click", async () => {
  backupNowBtn.disabled = true;
  backupMsg.textContent = "Sauvegarde en cours…";
  try {
    const res = await fetch("/api/backups", { method: "POST" });
    if (!res.ok) throw new Error();
    renderBackups(await res.json());
    backupMsg.textContent = "Sauvegarde créée ✓";
  } catch (e) {
    backupMsg.textContent = "⚠️ La sauvegarde a échoué.";
  } finally {
    backupNowBtn.disabled = false;
  }
});

backupList.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-act]");
  if (!btn) return;
  const name = btn.closest(".backup-row").dataset.name;
  const url = `/api/backups/${encodeURIComponent(name)}`;
  if (btn.dataset.act === "delete") {
    if (!confirm("Supprimer cette sauvegarde ?")) return;
    try {
      const res = await fetch(url, { method: "DELETE" });
      if (!res.ok) throw new Error();
      renderBackups(await res.json());
      backupMsg.textContent = "Sauvegarde supprimée.";
    } catch (err) {
      backupMsg.textContent = "⚠️ Suppression impossible.";
    }
  } else if (btn.dataset.act === "restore") {
    if (!confirm("Restaurer cette sauvegarde ? Toutes tes données actuelles seront remplacées. Une copie de sécurité de l'état actuel est faite avant.")) return;
    backupMsg.textContent = "Restauration…";
    try {
      const res = await fetch(`${url}/restore`, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Restauration impossible");
      toast("Sauvegarde restaurée : l'application se recharge…", "ok");
      setTimeout(() => location.reload(), 1200);
    } catch (err) {
      backupMsg.textContent = "⚠️ " + err.message;
    }
  }
});
