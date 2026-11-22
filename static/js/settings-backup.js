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

// ----------------------------------------------------------------------
// Google Drive : identifiant Google, connexion par code (google.com/device), envoi, copies, restauration
// ----------------------------------------------------------------------
const gdriveEls = {
  setup: document.getElementById("gdrive-setup"),
  connect: document.getElementById("gdrive-connect"),
  connected: document.getElementById("gdrive-connected"),
  clientId: document.getElementById("gdrive-client-id"),
  clientSecret: document.getElementById("gdrive-client-secret"),
  clientSave: document.getElementById("gdrive-client-save"),
  clientCancel: document.getElementById("gdrive-client-cancel"),
  codeBox: document.getElementById("gdrive-code-box"),
  userCode: document.getElementById("gdrive-user-code"),
  verifyLink: document.getElementById("gdrive-verify-link"),
  connectBtn: document.getElementById("gdrive-connect-btn"),
  email: document.getElementById("gdrive-email"),
  last: document.getElementById("gdrive-last"),
  keep: document.getElementById("gdrive-keep"),
  uploadBtn: document.getElementById("gdrive-upload-btn"),
  list: document.getElementById("gdrive-list"),
  error: document.getElementById("gdrive-error"),
  msg: document.getElementById("gdrive-msg"),
};
let gdriveEditing = false;
let gdrivePollTimer = null;

const frDate = (iso) => new Date(iso).toLocaleString("fr-FR", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

function gdriveShowError(message) {
  gdriveEls.error.textContent = message ? "⚠️ " + message : "";
  gdriveEls.error.classList.toggle("hidden", !message);
}

async function gdriveFetch(url, options = {}) {
  const res = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Action impossible pour l'instant");
  return data;
}

function renderGdrive(status) {
  const setup = !status.configured || gdriveEditing;
  gdriveEls.setup.classList.toggle("hidden", !setup);
  gdriveEls.connect.classList.toggle("hidden", setup || status.connected);
  gdriveEls.connected.classList.toggle("hidden", setup || !status.connected);
  gdriveEls.clientCancel.classList.toggle("hidden", !status.configured);
  document.getElementById("gdrive-help").open = !status.configured;

  const pending = status.pending;
  gdriveEls.codeBox.classList.toggle("hidden", !pending);
  gdriveEls.connectBtn.classList.toggle("hidden", Boolean(pending));
  if (pending) {
    gdriveEls.userCode.textContent = pending.user_code;
    gdriveEls.verifyLink.href = pending.verification_url;
    gdriveEls.verifyLink.textContent = pending.verification_url.replace(/^https?:\/\/(www\.)?/, "");
    scheduleGdrivePoll(pending.interval);
  }

  if (status.connected) {
    gdriveEls.email.textContent = status.email ? `Connecté : ${status.email}` : "Google Drive connecté";
    gdriveEls.last.textContent = status.last_upload ? `Dernier envoi : ${frDate(status.last_upload)}` : "Aucune copie envoyée pour l'instant.";
    if (![...gdriveEls.keep.options].some((o) => o.value === String(status.keep))) {
      gdriveEls.keep.add(new Option(String(status.keep), String(status.keep)));
    }
    gdriveEls.keep.value = String(status.keep);
  }
  gdriveShowError(status.last_error);
}

async function loadGdrive() {
  try {
    const status = await gdriveFetch("/api/gdrive");
    renderGdrive(status);
    if (status.connected) loadGdriveFiles();
  } catch (e) {
    gdriveShowError("Impossible de lire l'état de Google Drive.");
  }
}

async function loadGdriveFiles() {
  try {
    const files = await gdriveFetch("/api/gdrive/files");
    gdriveEls.list.innerHTML = files.length
      ? files.map((f) => `<li class="backup-row" data-id="${escapeHtml(f.id)}">
          <div class="backup-info">
            <div class="backup-head"><strong>Copie Drive</strong><em>${formatBytes(f.size)}</em></div>
            <span>${escapeHtml(frDate(f.created))}</span>
          </div>
          <div class="backup-actions"><button type="button" class="mini-btn" data-act="restore">Restaurer</button></div>
        </li>`).join("")
      : '<li class="backup-empty">Aucune copie sur le Drive pour l\'instant.</li>';
  } catch (e) {
    gdriveEls.list.innerHTML = `<li class="backup-empty">⚠️ ${escapeHtml(e.message)}</li>`;
  }
}

function scheduleGdrivePoll(seconds) {
  clearTimeout(gdrivePollTimer);
  gdrivePollTimer = setTimeout(pollGdrive, Math.max(3, seconds) * 1000);
}

async function pollGdrive() {
  // Réglages fermés : on arrête ; la vérification reprend à la réouverture de la page si le code est encore valide.
  if (!gdriveEls.codeBox.offsetParent) return;
  try {
    const status = await gdriveFetch("/api/gdrive/poll", { method: "POST" });
    if (status.state === "pending") {
      scheduleGdrivePoll(status.pending ? status.pending.interval : 5);
      return;
    }
    renderGdrive(status);
    if (status.state === "connected") {
      toast("Google Drive connecté", "ok");
      gdriveEls.msg.textContent = "";
      loadGdriveFiles();
    } else {
      gdriveShowError(status.state === "denied" ? "Accès refusé sur la page Google." : "Le code a expiré : recommence.");
    }
  } catch (e) {
    gdriveShowError(e.message);
    gdriveEls.codeBox.classList.add("hidden");
    gdriveEls.connectBtn.classList.remove("hidden");
  }
}

gdriveEls.clientSave.addEventListener("click", async () => {
  gdriveEls.clientSave.disabled = true;
  try {
    const status = await gdriveFetch("/api/gdrive/client", {
      method: "POST",
      body: JSON.stringify({ client_id: gdriveEls.clientId.value, client_secret: gdriveEls.clientSecret.value }),
    });
    gdriveEditing = false;
    gdriveEls.clientSecret.value = "";
    renderGdrive(status);
    gdriveEls.msg.textContent = "Identifiant enregistré ✓ Connecte maintenant ton compte.";
  } catch (e) {
    gdriveShowError(e.message);
  } finally {
    gdriveEls.clientSave.disabled = false;
  }
});
gdriveEls.clientCancel.addEventListener("click", () => { gdriveEditing = false; loadGdrive(); });
document.getElementById("gdrive-edit-client").addEventListener("click", () => {
  gdriveEditing = true;
  gdriveShowError("");
  loadGdrive();
});

gdriveEls.connectBtn.addEventListener("click", async () => {
  gdriveEls.connectBtn.disabled = true;
  gdriveShowError("");
  try {
    renderGdrive(await gdriveFetch("/api/gdrive/connect", { method: "POST" }));
  } catch (e) {
    gdriveShowError(e.message);
  } finally {
    gdriveEls.connectBtn.disabled = false;
  }
});
document.getElementById("gdrive-copy-code").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(gdriveEls.userCode.textContent);
    toast("Code copié", "ok");
  } catch (e) {
    toast("Copie impossible : recopie le code à la main.");
  }
});

gdriveEls.keep.addEventListener("change", async () => {
  try {
    renderGdrive(await gdriveFetch("/api/gdrive/settings", { method: "PUT", body: JSON.stringify({ keep: Number(gdriveEls.keep.value) }) }));
    gdriveEls.msg.textContent = "Enregistré ✓ (appliqué au prochain envoi)";
  } catch (e) {
    gdriveShowError(e.message);
  }
});

gdriveEls.uploadBtn.addEventListener("click", async () => {
  gdriveEls.uploadBtn.disabled = true;
  gdriveEls.msg.textContent = "Envoi en cours…";
  gdriveShowError("");
  try {
    renderGdrive(await gdriveFetch("/api/gdrive/upload", { method: "POST" }));
    gdriveEls.msg.textContent = "Copie envoyée sur Google Drive ✓";
    loadGdriveFiles();
  } catch (e) {
    gdriveEls.msg.textContent = "";
    gdriveShowError(e.message);
  } finally {
    gdriveEls.uploadBtn.disabled = false;
  }
});

document.getElementById("gdrive-disconnect-btn").addEventListener("click", async () => {
  if (!confirm("Déconnecter Google Drive ? Les copies déjà envoyées restent sur ton Drive.")) return;
  try {
    renderGdrive(await gdriveFetch("/api/gdrive", { method: "DELETE" }));
    gdriveEls.msg.textContent = "Google Drive déconnecté.";
  } catch (e) {
    gdriveShowError(e.message);
  }
});

gdriveEls.list.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-act='restore']");
  if (!btn) return;
  if (!confirm("Restaurer cette copie du Drive ? Toutes tes données actuelles seront remplacées. Une copie de sécurité de l'état actuel est faite avant ; tes accès AniList et Google sont gardés.")) return;
  gdriveEls.msg.textContent = "Restauration…";
  try {
    await gdriveFetch(`/api/gdrive/files/${encodeURIComponent(btn.closest(".backup-row").dataset.id)}/restore`, { method: "POST" });
    toast("Copie restaurée : l'application se recharge…", "ok");
    setTimeout(() => location.reload(), 1200);
  } catch (err) {
    gdriveEls.msg.textContent = "";
    gdriveShowError(err.message);
  }
});
