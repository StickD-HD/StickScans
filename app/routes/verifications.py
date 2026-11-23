"""Vérifications du site : lancements, détail, réglages des mises à jour, état et pause du site."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import database
from .. import scraper as scraper_module
from .. import site_guard
from ..scraper import check_one_series, get_progress
from .models import UpdateSettingsRequest

router = APIRouter()


SKIP_SHORT_LABELS = {"skip_completed": "terminée", "skip_unread": "chapitres non lus", "skip_never_read": "jamais lue"}


@router.get("/api/checks/overview")
def checks_overview():
    """Écran Vérifications : état du site, requêtes par jour, file d'attente des séries, erreurs récentes."""
    rules = database.get_update_settings()
    queue = []
    for s in database.get_all_series():
        reason = scraper_module.skip_reason(s, rules)
        queue.append({
            "series_id": s["id"],
            "title": s.get("title") or s["url"],
            "next_check_at": s.get("next_check_at"),
            "reason": s.get("check_reason"),
            "skipped": SKIP_SHORT_LABELS.get(reason),
            "last_checked_at": s.get("last_checked_at"),
            "last_error": s.get("last_error"),
        })
    # À vérifier d'abord (jamais planifiées en tête), puis les séries ignorées par les réglages.
    queue.sort(key=lambda q: (q["skipped"] is not None, q["next_check_at"] or "", q["title"].lower()))
    return {
        "site": {**site_guard.status(), "auto_enabled": database.auto_checks_enabled()},
        "history": site_guard.history(days=7),
        "queue": queue,
        "errors": database.get_recent_check_errors(),
    }


@router.get("/api/checks/log")
def checks_log_file():
    if not scraper_module.LOG_FILE.exists():
        raise HTTPException(404, "Aucun journal pour l'instant")
    return FileResponse(scraper_module.LOG_FILE, media_type="text/plain; charset=utf-8", filename="scrape.log")


@router.get("/api/checks")
def checks_list(limit: int = 60):
    return database.list_check_runs(limit=min(max(limit, 1), 200))


@router.get("/api/checks/{run_id}")
def checks_detail(run_id: int):
    run = database.get_check_run(run_id)
    if not run:
        raise HTTPException(404, "Vérification introuvable")
    return run


@router.get("/api/refresh-status")
def refresh_status():
    return get_progress()


@router.post("/api/series/{series_id}/recheck")
def recheck_series(series_id: int):
    series = database.get_series_by_id(series_id)
    if not series:
        raise HTTPException(404, "Série introuvable")
    return check_one_series(series)


def _updates_settings() -> dict:
    return {**database.get_update_settings(), "auto_enabled": database.auto_checks_enabled()}


@router.get("/api/settings/updates")
def get_updates_settings():
    return _updates_settings()


@router.put("/api/settings/updates")
def put_updates_settings(payload: UpdateSettingsRequest):
    values = payload.model_dump()
    if values.pop("auto_enabled") is not None:
        database.set_setting("auto_checks_enabled", "1" if payload.auto_enabled else "0")
    database.set_update_settings(values)
    return _updates_settings()


@router.get("/api/site-status")
def get_site_status():
    """État des requêtes vers le site (partagé par toutes les instances du serveur) et file des vérifications."""
    now = scraper_module.utc_now()
    due = database.get_due_series(now)
    upcoming = sorted(s["next_check_at"] for s in database.get_all_series() if s.get("next_check_at"))
    return {
        **site_guard.status(),
        "auto_enabled": database.auto_checks_enabled(),
        "due_now": len(due),
        "next_check_at": upcoming[0] if upcoming else None,
    }


@router.post("/api/site-status/clear-pause")
def clear_site_pause():
    site_guard.clear_block()
    return get_site_status()
