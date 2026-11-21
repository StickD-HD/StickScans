"""
Récupération d'une page série de scan-manga.com par simple requête HTTP (requests), sans navigateur.
Interface : fetch_html(url, timeout_ms, max_wait) -> str ; erreurs : FetchError (et ses sous-classes).

Règles :
- User-Agent honnête (identifie l'appli, pas un navigateur) ; contact facultatif via FETCH_CONTACT ;
- chaque requête attend la permission de site_guard : écart de 45 à 90 s entre deux requêtes (toutes instances
  confondues), plafond quotidien, pause après un refus ;
- aucun contournement : sur 403 / 429 / page de challenge, on s'arrête et tout le serveur se met en pause
  (2 h, puis 6 h, 24 h, 72 h), en respectant aussi l'en-tête Retry-After du site ;
- on ne renvoie le HTML que si la vraie page série est là (h2[itemprop*="headline"]).
"""
import os
import re
import time
from email.utils import parsedate_to_datetime

import requests

from . import site_guard

CONTACT = os.environ.get("FETCH_CONTACT", "").strip()
USER_AGENT = "ScanMangaMetadataCollector/1.0" + (f" (+{CONTACT})" if CONTACT else "")
CHALLENGE_MARKERS = ("cf-chl", "Just a moment", "captcha-delivery", "Attention Required", "ddos-guard")
READY_RE = re.compile(r'<h2[^>]*itemprop="[^"]*headline')
DEFAULT_TIMEOUT_MS = 30000

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"})


class FetchError(Exception):
    pass


class BlockedError(FetchError):
    """Aucune requête ne doit partir : le site a refusé (ou la pause qui suit un refus est en cours)."""


class QuotaReached(BlockedError):
    """Plafond quotidien de requêtes atteint : on reprend le lendemain."""


class SiteBusy(FetchError):
    """Une autre requête vient de partir et l'attente dépasserait max_wait : rien n'a été envoyé."""


def format_wait(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds} s"
    minutes = (seconds + 59) // 60
    if minutes < 60:
        return f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d}" if minutes else f"{hours} h"


def _retry_after(resp) -> float | None:
    """Durée demandée par le site (en secondes ou en date HTTP), si elle est indiquée."""
    raw = (resp.headers.get("Retry-After") or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return float(raw)
    try:
        return max(0.0, parsedate_to_datetime(raw).timestamp() - time.time())
    except (TypeError, ValueError):
        return None


def _wait_for_slot(max_wait: float) -> None:
    deadline = time.monotonic() + max_wait
    while True:
        answer, seconds = site_guard.reserve()
        if answer == "ok":
            return
        if answer == "blocked":
            raise BlockedError(f"Site en pause après un refus (encore {format_wait(seconds)})")
        if answer == "quota":
            raise QuotaReached(
                f"Limite de {site_guard.DAILY_LIMIT} requêtes par jour atteinte : reprise dans {format_wait(seconds)}"
            )
        if time.monotonic() + seconds > deadline:
            raise SiteBusy(f"Une autre vérification utilise le site : réessaie dans {format_wait(seconds)}")
        time.sleep(seconds + 0.05)


def fetch_html(url: str, timeout_ms: int = DEFAULT_TIMEOUT_MS, max_wait: float | None = None) -> str:
    """max_wait : attente maximale (en secondes) de son tour avant d'envoyer la requête."""
    _wait_for_slot(site_guard.MAX_GAP_SECONDS + 15 if max_wait is None else max_wait)
    try:
        resp = _session.get(url, timeout=(10, min(timeout_ms, DEFAULT_TIMEOUT_MS) / 1000))
    except requests.RequestException as e:
        raise FetchError(f"Site injoignable : {e}") from e

    if resp.status_code in (403, 429):
        pause = site_guard.record_block(f"HTTP {resp.status_code}", _retry_after(resp))
        raise BlockedError(
            f"HTTP {resp.status_code} : le site refuse les requêtes, pause de {format_wait(pause)} (aucun contournement tenté)"
        )
    if resp.status_code == 404:
        raise FetchError("HTTP 404 : fiche introuvable (URL changée ?)")
    if resp.status_code != 200:
        raise FetchError(f"HTTP {resp.status_code}")

    html = resp.content.decode("utf-8", errors="replace")
    if any(m in html[:5000] for m in CHALLENGE_MARKERS) and not READY_RE.search(html):
        pause = site_guard.record_block("page de protection", _retry_after(resp))
        raise BlockedError(f"Page de protection reçue : pause de {format_wait(pause)} (aucun contournement tenté)")
    site_guard.record_success()
    if not READY_RE.search(html):
        raise FetchError(f"Page reçue ({len(html)} octets) sans titre de série : structure du site changée ?")
    return html
