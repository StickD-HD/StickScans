// Réglages › AniList : jeton et compte.
// Fichier 12/15 : chargé dans l'ordre par index.html ; tous partagent la même portée globale.

const anilistConnected = document.getElementById("anilist-connected");
const anilistConnectForm = document.getElementById("anilist-connect-form");
const anilistAvatar = document.getElementById("anilist-avatar");
const anilistUsername = document.getElementById("anilist-username");
const anilistExpiry = document.getElementById("anilist-expiry");
const anilistTokenAlert = document.getElementById("anilist-token-alert");
const anilistCheckBtn = document.getElementById("anilist-check-btn");
const anilistChangeBtn = document.getElementById("anilist-change-btn");
const anilistDisconnectBtn = document.getElementById("anilist-disconnect-btn");
const anilistHelp = document.getElementById("anilist-help");
const anilistRedirectUrl = document.getElementById("anilist-redirect-url");
const anilistCopyRedirect = document.getElementById("anilist-copy-redirect");
const anilistClientIdInput = document.getElementById("anilist-client-id-input");
const anilistAuthorizeLink = document.getElementById("anilist-authorize-link");
const anilistTokenInput = document.getElementById("anilist-token-input");
const anilistTokenError = document.getElementById("anilist-token-error");
const anilistTokenSave = document.getElementById("anilist-token-save");
const anilistTokenCancel = document.getElementById("anilist-token-cancel");

let anilistEditing = false;
let anilistStatusCache = null;

function updateAuthorizeLink() {
  const id = anilistClientIdInput.value.trim();
  const valid = /^\d+$/.test(id);
  anilistAuthorizeLink.classList.toggle("disabled", !valid);
  if (valid) {
    anilistAuthorizeLink.href = `https://anilist.co/api/v2/oauth/authorize?client_id=${id}&response_type=token`;
  } else {
    anilistAuthorizeLink.removeAttribute("href");
  }
}

function showAnilistTokenError(message) {
  anilistTokenError.textContent = message || "";
  anilistTokenError.classList.toggle("hidden", !message);
}

function renderAnilistSettings(status) {
  anilistStatusCache = status;
  const connected = status.configured && !anilistEditing;
  anilistConnected.classList.toggle("hidden", !connected);
  anilistConnectForm.classList.toggle("hidden", connected);
  anilistTokenCancel.classList.toggle("hidden", !(status.configured && anilistEditing));
  showAnilistTokenError("");
  if (status.client_id && !anilistClientIdInput.value) anilistClientIdInput.value = status.client_id;
  updateAuthorizeLink();
  anilistHelp.open = !status.configured;
  if (!status.configured) return;

  anilistUsername.textContent = status.name || "Compte connecté";
  if (status.avatar) {
    anilistAvatar.src = status.avatar;
    anilistAvatar.classList.remove("hidden");
  } else {
    anilistAvatar.classList.add("hidden");
  }

  let expiryText = "Date d'expiration inconnue";
  let warn = false;
  if (status.expired) {
    expiryText = "Jeton expiré";
    warn = true;
  } else if (status.expires_at) {
    const date = new Date(status.expires_at + "T00:00:00Z").toLocaleDateString("fr-FR", {
      day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
    });
    expiryText = `Valable jusqu'au ${date} (${status.days_left} j)`;
    warn = status.days_left <= 30;
  }
  anilistExpiry.textContent = expiryText;
  anilistExpiry.classList.toggle("warn", warn);

  const alertText = status.error || (status.expired ? "Ton jeton a expiré : génère-en un nouveau." : "");
  anilistTokenAlert.textContent = alertText ? "⚠️ " + alertText : "";
  anilistTokenAlert.classList.toggle("hidden", !alertText);
}

async function loadSettingsAnilistStatus() {
  anilistEditing = false;
  try {
    const res = await fetch("/api/settings/anilist");
    renderAnilistSettings(await res.json());
  } catch (e) {
    anilistConnected.classList.add("hidden");
  }
}

async function saveAnilistToken() {
  const token = anilistTokenInput.value.trim();
  if (!token) {
    showAnilistTokenError("Colle ton jeton d'abord.");
    return;
  }
  anilistTokenSave.disabled = true;
  anilistTokenSave.textContent = "Vérification...";
  showAnilistTokenError("");
  try {
    const res = await fetch("/api/settings/anilist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur inconnue");
    anilistTokenInput.value = "";
    anilistEditing = false;
    renderAnilistSettings(data);
  } catch (e) {
    showAnilistTokenError(e.message);
  } finally {
    anilistTokenSave.disabled = false;
    anilistTokenSave.textContent = "Connecter";
  }
}

anilistTokenSave.addEventListener("click", saveAnilistToken);
anilistTokenInput.addEventListener("keydown", (e) => { if (e.key === "Enter") saveAnilistToken(); });

anilistTokenCancel.addEventListener("click", () => {
  anilistEditing = false;
  anilistTokenInput.value = "";
  if (anilistStatusCache) renderAnilistSettings(anilistStatusCache);
});

anilistChangeBtn.addEventListener("click", () => {
  anilistEditing = true;
  if (anilistStatusCache) renderAnilistSettings(anilistStatusCache);
  anilistTokenInput.focus();
});

anilistCheckBtn.addEventListener("click", async () => {
  anilistCheckBtn.disabled = true;
  anilistCheckBtn.textContent = "Vérification...";
  try {
    const res = await fetch("/api/settings/anilist/check", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur inconnue");
    renderAnilistSettings(data);
    if (!data.error && !data.expired) anilistTokenAlert.classList.add("hidden");
  } catch (e) {
    anilistTokenAlert.textContent = "⚠️ " + e.message;
    anilistTokenAlert.classList.remove("hidden");
  } finally {
    anilistCheckBtn.disabled = false;
    anilistCheckBtn.textContent = "Vérifier";
  }
});

anilistDisconnectBtn.addEventListener("click", async () => {
  if (!confirm("Déconnecter AniList ? Tes séries restent liées, mais plus rien ne sera envoyé tant qu'un nouveau jeton n'est pas configuré.")) return;
  const res = await fetch("/api/settings/anilist", { method: "DELETE" });
  anilistEditing = false;
  renderAnilistSettings(await res.json());
});

anilistClientIdInput.addEventListener("input", updateAuthorizeLink);
anilistClientIdInput.addEventListener("change", () => {
  fetch("/api/settings/anilist/client-id", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: anilistClientIdInput.value.trim() }),
  }).catch(() => {});
});

anilistCopyRedirect.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(anilistRedirectUrl.textContent.trim());
    anilistCopyRedirect.textContent = "Copié ✓";
  } catch (e) {
    const range = document.createRange();
    range.selectNodeContents(anilistRedirectUrl);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    anilistCopyRedirect.textContent = "Sélectionné";
  }
  setTimeout(() => { anilistCopyRedirect.textContent = "Copier"; }, 1600);
});
