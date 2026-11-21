"""
Logique de vérification : récupère la page (fetcher), parse, met à jour la base (métadonnées + chapitres),
puis planifie la prochaine vérification de la série (schedule.py).

- run_due_checks() : lancé toutes les 10 minutes ; ne vérifie que les séries dont l'heure est venue.
- check_all_series() : « Actualiser toutes les séries » ; même chemin, mêmes limites, pour toutes les séries.
- check_one_series() : bouton « Actualiser » d'une fiche.
L'espacement des requêtes, le plafond quotidien et la pause après un refus sont gérés par fetcher / site_guard,
pour toutes les instances du serveur à la fois.
Garde aussi un état de progression en mémoire, consultable via get_progress().
"""
import logging
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from urllib.parse import urlparse

from . import database, schedule, scrape_cache, site_guard
from .fetcher import BlockedError, SiteBusy, fetch_html, format_wait
from .parse_series import parse_series_page

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


logger = logging.getLogger("manhwa-tracker.scraper")

# Journal des vérifications : un fichier texte lisible, aussi consultable depuis l'appli.
# Il se trouve dans le dossier data/ (donc visible depuis l'hôte : ./data/logs/scrape.log).
LOG_FILE = database.DB_PATH.parent / "logs" / "scrape.log"
checks_log = logging.getLogger("manhwa-tracker.checks")

# Attente maximale de son tour (une autre instance peut être en train d'interroger le site).
QUEUE_MAX_WAIT_SECONDS = 15 * 60


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


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


_progress_lock = threading.Lock()
_progress = {
    "is_running": False,
    "total": 0,
    "completed": 0,
    "current_title": None,
}


_maintenance = False   # import, restauration ou optimisation de la base en cours
_single_checks = 0     # vérifications d'une seule série en cours (bouton « Actualiser »)
BUSY_MESSAGE = "Une vérification est en cours : réessaie quand elle est terminée."


@contextmanager
def maintenance():
    """Réserve la base pour une opération qui la remplace ou la réécrit (import, restauration, optimisation) :
    refusée (RuntimeError) si une vérification tourne ; tant qu'elle dure, aucune vérification ne démarre."""
    global _maintenance
    with _progress_lock:
        if _progress["is_running"] or _maintenance or _single_checks:
            raise RuntimeError(BUSY_MESSAGE)
        _maintenance = True
    try:
        yield
    finally:
        with _progress_lock:
            _maintenance = False


def get_progress() -> dict:
    with _progress_lock:
        return dict(_progress)


def _set_progress(**kwargs):
    with _progress_lock:
        _progress.update(kwargs)


def plan_next(series: dict, ok: bool, now: datetime | None = None) -> None:
    """Planifie la prochaine vérification automatique d'une série qui vient d'être vérifiée (ou ajoutée)."""
    now = now or utc_now()
    if ok:
        added_at = database.parse_utc(series["added_at"]) if series.get("added_at") else now
        hours, reason = schedule.interval(database.get_discovery_times(series["id"]), added_at, now)
    else:
        hours, reason = schedule.ERROR_HOURS, "error"
    database.set_next_check(series["id"], now + schedule.jittered(hours), reason)


def _check(series: dict, run_id: int | None, use_cache: bool = False, max_wait: float | None = None) -> dict:
    """Vérifie une série, mesure la durée, l'enregistre dans le journal (base + fichier) et planifie la suivante.

    use_cache : réutiliser la copie récente d'une autre instance au lieu de solliciter le site.
    Une pause du site (refus, plafond quotidien, tour pas encore venu) n'est jamais inscrite comme erreur de la série :
    elle n'y est pour rien, et elle reste à vérifier."""
    started = time.monotonic()
    title = series.get("title") or series["url"]
    new_numbers: list[str] = []
    error = None
    paused = False
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
            html = fetch_html(series["url"], max_wait=max_wait)
        try:
            parsed = parse_series_page(html)
        except Exception:
            if source != "cache":
                raise
            # copie illisible : on retente avec la vraie page du site
            source = "site"
            html = fetch_html(series["url"], max_wait=max_wait)
            parsed = parse_series_page(html)
        title = parsed.get("title") or title
        new_numbers = [c["number"] for c in database.update_series_result(series["id"], parsed)]
        if source == "site":
            scrape_cache.write(series["url"], html)  # sans effet hors des modes « write » et « both »
    except Exception as e:  # une série en échec (réseau, page illisible) ne doit pas bloquer les autres
        error = str(e) or e.__class__.__name__
        paused = isinstance(e, (BlockedError, SiteBusy))
        if not paused:
            database.update_series_error(series["id"], error)
    duration = time.monotonic() - started

    if not paused:
        plan_next(series, ok=error is None)

    if error:
        checks_log.error("%s %7s  %s — %s", "PAUSE   " if paused else "ERREUR  ", format_duration(duration), title, error)
    elif source == "cache":
        detail = f"chapitre(s) {', '.join(new_numbers)}" if new_numbers else "rien de nouveau"
        checks_log.info("COPIE    %7s  %s — %s (copie de %d min, site non sollicité)", format_duration(duration), title, detail, round(cache_age / 60))
    elif new_numbers:
        checks_log.info("NOUVEAU  %7s  %s — chapitre(s) %s", format_duration(duration), title, ", ".join(new_numbers))
    else:
        checks_log.info("OK       %7s  %s — rien de nouveau", format_duration(duration), title)

    if run_id is not None:
        database.add_check_item(run_id, series["id"], title, duration, error is None, new_numbers, error, source)
    return {"ok": error is None, "duration": duration, "new": len(new_numbers), "source": source,
            "blocked": paused, "error": error}


def check_one_series(series: dict) -> dict:
    """Vérification manuelle d'une seule série (bouton « Actualiser ») : toujours la vraie page du site.
    Renvoie la série à jour ; check_error contient le message si la vérification n'a pas pu se faire."""
    global _single_checks
    with _progress_lock:
        if _maintenance:
            current = database.get_series_by_id(series["id"])
            current["check_error"] = "Opération sur la base en cours (import, restauration…) : réessaie dans un instant."
            return current
        _single_checks += 1
    try:
        return _check_one(series)
    finally:
        with _progress_lock:
            _single_checks -= 1


def _check_one(series: dict) -> dict:
    run_id = database.start_check_run("série", 1)
    started = time.monotonic()
    checks_log.info("=== Vérification [série] : %s ===", series.get("title") or series["url"])
    result = _check(series, run_id)
    database.finish_check_run(run_id, time.monotonic() - started,
                              status="interrompue" if result["blocked"] else "terminée")
    updated = database.get_series_by_id(series["id"])
    updated["check_error"] = result["error"]
    return updated


COMPLETED_STATUSES = {"terminé", "terminée", "completed"}
SKIP_LABELS = {
    "skip_completed": "terminée(s)",
    "skip_unread": "avec des chapitres non lus",
    "skip_never_read": "jamais lue(s)",
}


def skip_reason(series: dict, rules: dict) -> str | None:
    """Clé du réglage qui fait ignorer cette série lors d'une vérification groupée, ou None si elle doit être vérifiée.
    Une vérification d'une seule série (bouton « Actualiser » de sa fiche) ne passe jamais par ici."""
    if rules.get("skip_completed") and (series.get("status") or "").strip().lower() in COMPLETED_STATUSES:
        return "skip_completed"
    unread = series.get("unread_count") or 0
    read = (series.get("total_chapters") or 0) - unread
    if rules.get("skip_unread") and unread > 0:
        return "skip_unread"
    if rules.get("skip_never_read") and read <= 0:
        return "skip_never_read"
    return None


def _split_skipped(candidates: list[dict]) -> tuple[list[dict], str]:
    rules = database.get_update_settings()
    queue, skipped = [], {}
    for series in candidates:
        reason = skip_reason(series, rules)
        if reason:
            skipped[reason] = skipped.get(reason, 0) + 1
        else:
            queue.append(series)
    n_skipped = sum(skipped.values())
    detail = ""
    if n_skipped:
        detail = " (%d ignorée(s) par les réglages : %s)" % (
            n_skipped, ", ".join(f"{n} {SKIP_LABELS[k]}" for k, n in skipped.items()))
    return queue, detail


def site_pause_message() -> str | None:
    """Message affichable si aucune requête ne peut partir en ce moment (pause après un refus ou plafond atteint)."""
    st = site_guard.status()
    if st["blocked"]:
        return f"Le site est en pause après un refus (encore {format_wait(st['remaining_seconds'])}) : aucune requête n'est envoyée."
    if st["quota_reached"]:
        return f"La limite de {st['daily_limit']} requêtes par jour est atteinte : reprise demain."
    return None


def _run_queue(select, trigger: str) -> None:
    """select() -> (séries à vérifier, détail des séries ignorées) ; appelée une fois la vérification réservée."""
    with _progress_lock:
        if _progress["is_running"] or _maintenance:
            logger.info("Vérification ou opération sur la base déjà en cours, on ignore ce déclenchement")
            return
        _progress.update({"is_running": True, "total": 0, "completed": 0, "current_title": None})

    started = time.monotonic()
    try:
        queue, skipped_detail = select()
        if not queue:
            return
        _set_progress(total=len(queue))
        run_id = database.start_check_run(trigger, len(queue))
        checks_log.info("=== Vérification [%s] : début, %d série(s)%s ===", trigger, len(queue), skipped_detail)

        ok = errors = new_chapters = from_cache = 0
        interrupted = None
        slowest = (0.0, "")
        scrape_cache.purge_old()
        for i, series in enumerate(queue):
            _set_progress(current_title=series.get("title"))
            result = _check(series, run_id, use_cache=True, max_wait=QUEUE_MAX_WAIT_SECONDS)
            if result["blocked"]:
                # Le site refuse, le plafond est atteint ou il est occupé : inutile d'insister avec les séries restantes,
                # elles restent « à vérifier » et repasseront dès que possible.
                interrupted = result["error"]
                errors += 1
                break
            from_cache += 1 if result["source"] == "cache" else 0
            ok += 1 if result["ok"] else 0
            errors += 0 if result["ok"] else 1
            new_chapters += result["new"]
            if result["duration"] > slowest[0]:
                slowest = (result["duration"], series.get("title") or series["url"])
            _set_progress(completed=i + 1)

        if interrupted:
            checks_log.error("=== Vérification [%s] interrompue : %s. Les séries restantes repasseront dès que possible ===",
                             trigger, interrupted)
        total_duration = time.monotonic() - started
        database.finish_check_run(run_id, total_duration, status="interrompue" if interrupted else "terminée")
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
        _set_progress(is_running=False, current_title=None, total=0, completed=0)


_last_pause_logged = None


def run_due_checks() -> None:
    """Toutes les 10 minutes : vérifie les séries dont l'heure est venue (rien du tout si les vérifications
    automatiques sont désactivées ou si le site est en pause)."""
    global _last_pause_logged
    if not database.auto_checks_enabled():
        return
    pause = site_pause_message()
    if pause:
        key = pause.split("(")[0]
        if key != _last_pause_logged:  # une seule ligne dans le journal par pause, pas une toutes les 10 minutes
            checks_log.info("=== %s ===", pause)
            _last_pause_logged = key
        return
    _last_pause_logged = None
    _run_queue(lambda: _split_skipped(database.get_due_series(utc_now())), "auto")


def check_all_series(trigger: str = "manuel") -> None:
    """« Actualiser toutes les séries » : toutes les séries non ignorées par les réglages, avec les mêmes limites
    (requêtes espacées, copie récente d'une autre instance réutilisée)."""
    _run_queue(lambda: _split_skipped(database.get_all_series()), trigger)


def fetch_and_parse_new_url(url: str) -> dict:
    html = fetch_html(url)
    return parse_series_page(html)
