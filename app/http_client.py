"""
Récupération d'une page série par simple requête HTTP (requests), sans navigateur.
Même interface que les autres clients : fetch_html(url, timeout_ms) -> str.

Règles :
- User-Agent honnête (identifie l'appli, pas un navigateur) ; contact facultatif via FETCH_CONTACT ;
- aucun contournement : sur 403 / 429 / page de challenge, on s'arrête et on met le site en pause
  (FETCH_BLOCK_COOLDOWN_MINUTES, défaut 60) : plus aucune requête n'est envoyée pendant ce temps ;
- on ne renvoie le HTML que si la vraie page série est là (h2[itemprop*="headline"]).
"""
import os
import re
import threading
import time

import requests

from .playwright_client import FetchError

CONTACT = os.environ.get("FETCH_CONTACT", "").strip()
USER_AGENT = "ScanMangaMetadataCollector/1.0" + (f" (+{CONTACT})" if CONTACT else "")
COOLDOWN_SECONDS = max(1, int(os.environ.get("FETCH_BLOCK_COOLDOWN_MINUTES", "60") or 60)) * 60
CHALLENGE_MARKERS = ("cf-chl", "Just a moment", "captcha-delivery", "Attention Required", "ddos-guard")
READY_RE = re.compile(r'<h2[^>]*itemprop="[^"]*headline')

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"})
_lock = threading.Lock()
_blocked_until = 0.0


def _block(reason: str) -> FetchError:
    global _blocked_until
    _blocked_until = time.time() + COOLDOWN_SECONDS
    return FetchError(f"{reason} : collecte suspendue {COOLDOWN_SECONDS // 60} min, aucun contournement tenté")


def fetch_html(url: str, timeout_ms: int = 30000) -> str:
    with _lock:
        remaining = _blocked_until - time.time()
        if remaining > 0:
            raise FetchError(f"Site en pause après un blocage (encore {int(remaining // 60) + 1} min)")
        try:
            resp = _session.get(url, timeout=(10, timeout_ms / 1000))
        except requests.RequestException as e:
            raise FetchError(f"Site injoignable : {e}") from e

    if resp.status_code in (403, 429):
        raise _block(f"HTTP {resp.status_code}")
    if resp.status_code == 404:
        raise FetchError("HTTP 404 : fiche introuvable (URL changée ?)")
    if resp.status_code != 200:
        raise FetchError(f"HTTP {resp.status_code}")

    html = resp.content.decode("utf-8", errors="replace")
    if any(m in html[:5000] for m in CHALLENGE_MARKERS) and not READY_RE.search(html):
        raise _block("Page de challenge reçue")
    if not READY_RE.search(html):
        raise FetchError(f"Page reçue ({len(html)} octets) sans titre de série : structure du site changée ?")
    return html
