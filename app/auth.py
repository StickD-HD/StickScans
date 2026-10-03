"""
Authentification mono-utilisateur par cookie de session signé (HMAC-SHA256).

Configuration (variables d'environnement) :
- AUTH_PASSWORD      : mot de passe. Si absent ou vide, l'authentification est DÉSACTIVÉE.
- AUTH_USERNAME      : identifiant (défaut : "admin").
- AUTH_SECRET        : clé de signature des sessions. Si absente, une clé aléatoire est
                       générée et conservée dans data/auth_secret (les sessions survivent
                       aux redémarrages du conteneur).
- AUTH_SESSION_DAYS  : durée d'une session en jours (défaut : 30).
- AUTH_COOKIE_SECURE : "true" pour n'envoyer le cookie qu'en HTTPS (à activer derrière un
                       reverse proxy HTTPS).
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
from pathlib import Path

logger = logging.getLogger("manhwa-tracker.auth")

COOKIE_NAME = "stickscans_session"

AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "")
SESSION_DAYS = int(os.environ.get("AUTH_SESSION_DAYS", "30"))
COOKIE_SECURE = os.environ.get("AUTH_COOKIE_SECURE", "false").lower() in ("1", "true", "yes")

SECRET_PATH = Path(__file__).parent.parent / "data" / "auth_secret"

# Limitation des tentatives : MAX_FAILURES échecs par IP sur WINDOW_SECONDS => blocage.
MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60

PUBLIC_PATHS = {
    "/login",
    "/api/auth/login",
    "/api/auth/status",
    "/manifest.json",
    "/sw.js",
    "/static/style.css",
}
PUBLIC_PREFIXES = ("/static/icons/",)


def is_enabled() -> bool:
    return bool(AUTH_PASSWORD)


def _load_secret() -> bytes:
    env_secret = os.environ.get("AUTH_SECRET")
    if env_secret:
        return env_secret.encode()
    try:
        if SECRET_PATH.exists():
            return SECRET_PATH.read_text().strip().encode()
        SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
        new_secret = secrets.token_hex(32)
        SECRET_PATH.write_text(new_secret)
        try:
            os.chmod(SECRET_PATH, 0o600)
        except OSError:
            pass
        return new_secret.encode()
    except OSError:
        # Pas de stockage disponible : clé en mémoire (les sessions sauteront au redémarrage).
        logger.warning("Impossible de persister la clé de session, clé temporaire utilisée")
        return secrets.token_hex(32).encode()


_SECRET = _load_secret()


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str) -> str:
    return _b64e(hmac.new(_SECRET, payload.encode(), hashlib.sha256).digest())


def check_credentials(username: str, password: str) -> bool:
    # On compare des empreintes pour que la durée du test ne dépende pas de la longueur.
    def digest(value: str) -> bytes:
        return hashlib.sha256(value.encode()).digest()

    user_ok = hmac.compare_digest(digest(username), digest(AUTH_USERNAME))
    pass_ok = hmac.compare_digest(digest(password), digest(AUTH_PASSWORD))
    return user_ok and pass_ok


def create_session_token() -> str:
    payload = _b64e(json.dumps({"u": AUTH_USERNAME, "exp": int(time.time()) + SESSION_DAYS * 86400}).encode())
    return f"{payload}.{_sign(payload)}"


def verify_session_token(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    payload, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(payload)):
        return False
    try:
        data = json.loads(_b64d(payload))
    except (ValueError, json.JSONDecodeError):
        return False
    return data.get("u") == AUTH_USERNAME and data.get("exp", 0) > time.time()


def safe_next_url(next_url: str | None) -> str:
    """N'autorise que les chemins relatifs internes (évite les redirections ouvertes)."""
    if next_url and next_url.startswith("/") and not next_url.startswith("//") and "\\" not in next_url:
        return next_url
    return "/"


_attempts_lock = threading.Lock()
_failures: dict[str, list[float]] = {}


def is_rate_limited(ip: str) -> bool:
    now = time.time()
    with _attempts_lock:
        recent = [t for t in _failures.get(ip, []) if now - t < WINDOW_SECONDS]
        _failures[ip] = recent
        return len(recent) >= MAX_FAILURES


def register_failure(ip: str) -> None:
    with _attempts_lock:
        _failures.setdefault(ip, []).append(time.time())


def clear_failures(ip: str) -> None:
    with _attempts_lock:
        _failures.pop(ip, None)
