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


import os
import time
import random
import logging
import threading
from logging.handlers import RotatingFileHandler

from . import database, scrape_cache
from .byparr_client import fetch_html
from .parse_series import parse_series_page

logger = logging.getLogger("manhwa-tracker.scraper")

# Journal des vérifications : un fichier texte lisible, aussi consultable depuis l'appli.
# Il se trouve dans le dossier data/ (donc visible depuis l'hôte : ./data/logs/scrape.log).
LOG_FILE = database.DB_PATH.parent / "logs" / "scrape.log"
checks_log = logging.getLogger("manhwa-tracker.checks")


def _setup_checks_log():
    checks_log.setLevel(logging.INFO)  # le fichier doit toujours contenir le détail, quelle que soit la config globale
    if checks_log.handlers:
        return
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    except OSError:
        return
    formatter = logging.Formatter("%(asctime)s UTC | %(message)s", "%Y-%m-%d %H:%M:%S")
    formatter.converter = time.gmtime  # heures du fichier en UTC, indiquées explicitement
    handler.setFormatter(formatter)
    checks_log.addHandler(handler)


_setup_checks_log()


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    seconds = int(round(seconds))
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}min{sec:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}min"


# Pause aléatoire entre deux séries (pour ne pas enchaîner les requêtes vers le site).
# Réglable avec CHECK_MIN_DELAY_SECONDS / CHECK_MAX_DELAY_SECONDS (défaut : 3 à 8 s).
MIN_DELAY_SECONDS = max(0.0, float(os.environ.get("CHECK_MIN_DELAY_SECONDS", "3")))
MAX_DELAY_SECONDS = max(MIN_DELAY_SECONDS, float(os.environ.get("CHECK_MAX_DELAY_SECONDS", "8")))

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


def _check(series: dict, run_id: int | None, use_cache: bool = False) -> dict:
    """Vérifie une série, mesure la durée, l'enregistre dans le journal (base + fichier).

    use_cache : réutiliser la copie récente d'une autre instance (vérifications automatiques seulement ;
    un clic manuel va toujours chercher la page sur le site)."""
    started = time.monotonic()
    title = series.get("title") or series["url"]
    new_numbers: list[str] = []
    error = None
    source = "site"
    cache_age = 0.0
    try:
        html = None
        if use_cache:
            cached = scrape_cache.read(series["url"])
            if cached:
                html, cache_age = cached
                source = "cache"
        if html is None:
            html = fetch_html(series["url"])
        try:
            parsed = parse_series_page(html)
        except Exception:
            if source != "cache":
                raise
            # copie illisible : on retente avec la vraie page du site
            source = "site"
            html = fetch_html(series["url"])
            parsed = parse_series_page(html)
        title = parsed.get("title") or title
        new_numbers = [c["number"] for c in database.update_series_result(series["id"], parsed)]
        if source == "site":
            scrape_cache.write(series["url"], html)  # sans effet hors du mode « write »
    except Exception as e:  # une série en échec (réseau, Byparr, page illisible) ne doit pas bloquer les autres
        error = str(e) or e.__class__.__name__
        database.update_series_error(series["id"], error)
    duration = time.monotonic() - started

    if error:
        checks_log.error("ERREUR   %7s  %s — %s", format_duration(duration), title, error)
    elif source == "cache":
        detail = f"chapitre(s) {', '.join(new_numbers)}" if new_numbers else "rien de nouveau"
        checks_log.info("COPIE    %7s  %s — %s (copie de %d min, site non sollicité)", format_duration(duration), title, detail, round(cache_age / 60))
    elif new_numbers:
        checks_log.info("NOUVEAU  %7s  %s — chapitre(s) %s", format_duration(duration), title, ", ".join(new_numbers))
    else:
        checks_log.info("OK       %7s  %s — rien de nouveau", format_duration(duration), title)

    if run_id is not None:
        database.add_check_item(run_id, series["id"], title, duration, error is None, new_numbers, error, source)
    return {"ok": error is None, "duration": duration, "new": len(new_numbers), "source": source}


def check_one_series(series: dict) -> dict:
    """Vérification manuelle d'une seule série (bouton « Actualiser »)."""
    run_id = database.start_check_run("série", 1)
    started = time.monotonic()
    checks_log.info("=== Vérification [série] : %s ===", series.get("title") or series["url"])
    _check(series, run_id)
    database.finish_check_run(run_id, time.monotonic() - started)
    return database.get_series_by_id(series["id"])


def check_all_series(trigger: str = "auto"):
    with _progress_lock:
        if _progress["is_running"]:
            logger.info("Vérification déjà en cours, on ignore ce déclenchement")
            return
        _progress.update({"is_running": True, "total": 0, "completed": 0, "current_title": None})

    run_id = None
    started = time.monotonic()
    try:
        all_series = database.get_all_series()
        _set_progress(total=len(all_series))
        run_id = database.start_check_run(trigger, len(all_series))
        checks_log.info("=== Vérification [%s] : début, %d série(s) ===", trigger, len(all_series))

        ok = errors = new_chapters = from_cache = 0
        slowest = (0.0, "")
        use_cache = trigger == "auto" and scrape_cache.MODE == "read"
        scrape_cache.purge_old()
        for i, series in enumerate(all_series):
            _set_progress(current_title=series.get("title"))
            result = _check(series, run_id, use_cache=use_cache)
            from_cache += 1 if result["source"] == "cache" else 0
            ok += 1 if result["ok"] else 0
            errors += 0 if result["ok"] else 1
            new_chapters += result["new"]
            if result["duration"] > slowest[0]:
                slowest = (result["duration"], series.get("title") or series["url"])
            _set_progress(completed=i + 1)
            # La pause ne sert qu'entre deux vraies requêtes vers le site : rien à attendre après une copie.
            if i < len(all_series) - 1 and result["source"] != "cache":
                time.sleep(random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS))

        total_duration = time.monotonic() - started
        database.finish_check_run(run_id, total_duration)
        checks_log.info(
            "=== Fin [%s] en %s : %d OK, %d erreur(s), %d nouveau(x) chapitre(s)%s%s ===",
            trigger, format_duration(total_duration), ok, errors, new_chapters,
            f", {from_cache} série(s) reprise(s) sans solliciter le site" if from_cache else "",
            f" — plus lente : {slowest[1]} ({format_duration(slowest[0])})" if slowest[0] else "",
        )
    except Exception:
        logger.exception("La vérification a été interrompue par une erreur inattendue")
        checks_log.error("=== Vérification [%s] interrompue par une erreur inattendue ===", trigger)
    finally:
        _set_progress(is_running=False, current_title=None)


def fetch_and_parse_new_url(url: str) -> dict:
    html = fetch_html(url)
    return parse_series_page(html)
