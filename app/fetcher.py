"""
Point d'entrée unique pour récupérer le HTML d'une page. Choix par variable d'environnement :

- FETCH_BACKEND=byparr      (défaut, comportement d'origine)
- FETCH_BACKEND=playwright  navigateur local (voir playwright_client.py)
- FETCH_BACKEND=remote      appelle un petit service de récupération tournant sur une autre machine
                            (FETCH_REMOTE_URL=http://IP:8765, FETCH_REMOTE_TOKEN=...)
"""
import os

import requests

from .playwright_client import FetchError

BACKEND = os.environ.get("FETCH_BACKEND", "byparr").strip().lower()
REMOTE_URL = os.environ.get("FETCH_REMOTE_URL", "").rstrip("/")
REMOTE_TOKEN = os.environ.get("FETCH_REMOTE_TOKEN", "")


def _remote(url: str, timeout_ms: int) -> str:
    if not REMOTE_URL:
        raise FetchError("FETCH_REMOTE_URL n'est pas défini")
    try:
        resp = requests.get(
            f"{REMOTE_URL}/fetch",
            params={"url": url, "timeout_ms": timeout_ms},
            headers={"X-Token": REMOTE_TOKEN},
            timeout=(10, timeout_ms / 1000 + 30),
        )
    except requests.RequestException as e:
        raise FetchError(f"Service de récupération injoignable : {e}") from e
    if resp.status_code != 200:
        raise FetchError(f"Service de récupération : HTTP {resp.status_code} — {resp.text[:300]}")
    return resp.text


def fetch_html(url: str, timeout_ms: int = 90000) -> str:
    if BACKEND == "playwright":
        from .playwright_client import fetch_html as pw_fetch
        return pw_fetch(url, timeout_ms)
    if BACKEND == "remote":
        return _remote(url, timeout_ms)
    from .byparr_client import ByparrError, fetch_html as byparr_fetch
    try:
        return byparr_fetch(url, timeout_ms)
    except ByparrError as e:
        raise FetchError(str(e)) from e
