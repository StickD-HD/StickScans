// Réglages › Mises à jour : vérifications automatiques, état du site, séries ignorées.
// Fichier 11/15 : chargé dans l'ordre par index.html ; tous partagent la même portée globale.

// ----------------------------------------------------------------------
// Mises à jour : quelles séries ignorer lors d'une vérification groupée (réglage enregistré sur le serveur)
// ----------------------------------------------------------------------
const UPDATE_TOGGLES = [
  [document.getElementById("upd-auto-enabled"), "auto_enabled"],
  [document.getElementById("upd-skip-completed"), "skip_completed"],
  [document.getElementById("upd-skip-unread"), "skip_unread"],
  [document.getElementById("upd-skip-neverread"), "skip_never_read"],
];
const updMsg = document.getElementById("upd-msg");

async function loadUpdateSettings(keepMessage = false) {
  try {
    const s = await (await fetch("/api/settings/updates")).json();
    UPDATE_TOGGLES.forEach(([el, key]) => (el.checked = Boolean(s[key])));
    if (!keepMessage) updMsg.textContent = "";
    loadSiteStatus();
  } catch (e) {
    updMsg.textContent = "⚠️ Impossible de lire les réglages.";
  }
}

UPDATE_TOGGLES.forEach(([el, key]) =>
  el.addEventListener("change", async () => {
    try {
      const res = await fetch("/api/settings/updates", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [key]: el.checked }),
      });
      if (!res.ok) throw new Error();
      updMsg.textContent = "Enregistré ✓";
      loadSiteStatus();
    } catch (e) {
      updMsg.textContent = "⚠️ Réglage non enregistré.";
      loadUpdateSettings(true); // l'interrupteur revient à son état réel, le message d'erreur reste visible
    }
  }),
);

const siteStatusBox = document.getElementById("site-status-box");
const siteClearPauseBtn = document.getElementById("site-clear-pause-btn");

function renderSiteStatus(st) {
  const lines = [];
  const pause = sitePauseText(st);
  lines.push(pause ? `<strong class="warn-text">⏸ ${escapeHtml(pause)}</strong>` : "<strong>✓ Requêtes autorisées</strong>");
  lines.push(`${st.requests_today} requête${st.requests_today > 1 ? "s" : ""} aujourd'hui sur ${st.daily_limit} maximum${st.shared ? ", toutes instances du serveur confondues" : ""}.`);
  if (st.due_now) lines.push(`${st.due_now} série${st.due_now > 1 ? "s" : ""} à vérifier dès que possible.`);
  else if (st.next_check_at) lines.push(`Prochaine vérification : ${formatFuture(st.next_check_at)}.`);
  if (st.last_block_at) {
    const when = new Date(st.last_block_at).toLocaleString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    lines.push(`Dernier refus du site : ${escapeHtml(when)} (${escapeHtml(st.last_block_reason || "?")}).`);
  }
  siteStatusBox.innerHTML = lines.map((l) => `<p>${l}</p>`).join("");
  siteClearPauseBtn.classList.toggle("hidden", !st.blocked);
}

async function loadSiteStatus() {
  try {
    renderSiteStatus(await (await fetch("/api/site-status")).json());
  } catch (e) {
    siteStatusBox.textContent = "⚠️ État du site indisponible.";
  }
}

siteClearPauseBtn.addEventListener("click", async () => {
  if (!confirm("Lever la pause maintenant ? À faire seulement si le site t'a débloqué : un nouveau refus entraînerait une pause plus longue.")) return;
  try {
    renderSiteStatus(await (await fetch("/api/site-status/clear-pause", { method: "POST" })).json());
  } catch (e) {
    siteStatusBox.textContent = "⚠️ Impossible de lever la pause.";
  }
});
