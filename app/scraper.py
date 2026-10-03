"""
Logique de vérification : appelle Byparr, parse, met à jour la base (métadonnées + chapitres).
Garde aussi un état de progression en mémoire, consultable via get_progress().
"""
from urllib.parse import urlparse

SCAN_MANGA_HOSTS = {"scan-manga.com", "www.scan-manga.com", "m.scan-manga.com"}


def normalize_series_url(url: str) -> str | None:
    """Accepte les liens normaux et mobiles (m.) de scan-manga.com et les ramène à la version www.
    Renvoie None si ce n'est pas un lien scan-manga.com."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https") or (parsed.hostname or "").lower() not in SCAN_MANGA_HOSTS:
        return None
    if not parsed.path or parsed.path == "/":
        return None
    return "https://www.scan-manga.com" + parsed.path + (f"?{parsed.query}" if parsed.query else "")


import time
import random
import logging
import threading

from . import database
from .byparr_client import fetch_html, ByparrError
from .parse_series import parse_series_page

logger = logging.getLogger("manhwa-tracker.scraper")

MIN_DELAY_SECONDS = 3
MAX_DELAY_SECONDS = 8

_progress_lock = threading.Lock()
_progress = {
    "is_running": False,
    "total": 0,
    "completed": 0,
    "current_title": None,
}


def get_progress() -> dict:
    with _progress_lock:
        return dict(_progress)


def _set_progress(**kwargs):
    with _progress_lock:
        _progress.update(kwargs)


def check_one_series(series: dict) -> dict:
    try:
        html = fetch_html(series["url"])
        parsed = parse_series_page(html)
        new_chapters = database.update_series_result(series["id"], parsed)
        if new_chapters:
            logger.info(
                "Nouveau(x) chapitre(s) pour %s : %s",
                parsed.get("title"),
                ", ".join(c["number"] for c in new_chapters),
            )
        else:
            logger.info("Vérifié : %s (rien de nouveau)", parsed.get("title"))
    except ByparrError as e:
        database.update_series_error(series["id"], str(e))
        logger.error("Échec sur %s : %s", series["url"], e)

    return database.get_series_by_id(series["id"])


def check_all_series():
    with _progress_lock:
        if _progress["is_running"]:
            logger.info("Vérification déjà en cours, on ignore ce déclenchement")
            return
        _progress.update({"is_running": True, "total": 0, "completed": 0, "current_title": None})

    try:
        all_series = database.get_all_series()
        _set_progress(total=len(all_series))
        logger.info("Début de la vérification planifiée (%d séries)", len(all_series))

        for i, series in enumerate(all_series):
            _set_progress(current_title=series.get("title"))
            check_one_series(series)
            _set_progress(completed=i + 1)
            if i < len(all_series) - 1:
                time.sleep(random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS))

        logger.info("Vérification planifiée terminée")
    finally:
        _set_progress(is_running=False, current_title=None)


def fetch_and_parse_new_url(url: str) -> dict:
    html = fetch_html(url)
    return parse_series_page(html)
