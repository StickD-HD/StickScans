// Page de connexion (fichier à part : la politique de sécurité du serveur interdit les scripts écrits dans la page).
const form = document.getElementById("login-form");
const errorEl = document.getElementById("login-error");
const submitBtn = document.getElementById("login-submit");
const next = new URLSearchParams(location.search).get("next") || "/";

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorEl.textContent = "";
  submitBtn.disabled = true;
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: document.getElementById("login-username").value,
        password: document.getElementById("login-password").value,
        next,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok) {
      location.replace(data.next || "/");
      return;
    }
    errorEl.textContent = data.detail || "Échec de la connexion";
  } catch (err) {
    errorEl.textContent = "Impossible de joindre le serveur";
  } finally {
    submitBtn.disabled = false;
  }
});
