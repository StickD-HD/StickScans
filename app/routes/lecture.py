"""Chapitres lus / non lus, nouveautés, historique et statistiques de lecture."""
from fastapi import APIRouter, BackgroundTasks, HTTPException

from .. import anilist, database
from ..parse_series import number_to_float
from .common import READING_MINUTES_PER_CHAPTER, _page
from .models import BulkReadRequest, HistoryRemoveRequest, MarkReadUpToRequest, ToggleReadRequest

router = APIRouter()


@router.get("/api/series/{series_id}/chapters")
def list_chapters(series_id: int):
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    return database.get_chapters_for_series(series_id)


@router.post("/api/series/{series_id}/mark-read-up-to")
def mark_read_up_to(series_id: int, payload: MarkReadUpToRequest, background_tasks: BackgroundTasks):
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    try:
        number_float = number_to_float(payload.number, strict=True)
    except ValueError:
        raise HTTPException(400, "Numéro de chapitre invalide")
    database.mark_read_up_to(series_id, number_float)
    background_tasks.add_task(anilist.push_progress, series_id)  # la réponse n'attend pas AniList
    return database.get_series_by_id(series_id)


@router.post("/api/series/{series_id}/mark-all-read")
def mark_all_read(series_id: int, background_tasks: BackgroundTasks):
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    database.mark_all_read(series_id)
    background_tasks.add_task(anilist.push_progress, series_id)
    return database.get_series_by_id(series_id)


@router.post("/api/series/{series_id}/reset-progress")
def reset_progress(series_id: int):
    """Remet tous les chapitres en « non lu ». AniList n'est pas touché : une progression n'y recule jamais
    automatiquement."""
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    database.mark_all_unread(series_id)
    return database.get_series_by_id(series_id)


@router.post("/api/chapters/{chapter_id}/toggle-read")
def toggle_chapter_read(chapter_id: int, payload: ToggleReadRequest, background_tasks: BackgroundTasks):
    database.set_chapter_read(chapter_id, payload.is_read)
    series_id = database.get_series_id_for_chapter(chapter_id)
    if series_id:
        background_tasks.add_task(anilist.push_progress, series_id)
    return {"ok": True}


@router.post("/api/chapters/bulk-read")
def bulk_toggle_read(payload: BulkReadRequest, background_tasks: BackgroundTasks):
    database.set_chapters_read(payload.chapter_ids, payload.is_read)
    for series_id in database.get_series_ids_for_chapters(payload.chapter_ids):
        background_tasks.add_task(anilist.push_progress, series_id)
    return {"ok": True}


@router.get("/api/updates")
def list_updates(limit: int = 100, offset: int = 0):
    limit, offset = _page(limit, offset)
    return database.get_recent_updates(limit=limit, offset=offset)


@router.get("/api/history")
def list_history(limit: int = 200, offset: int = 0):
    limit, offset = _page(limit, offset)
    return database.get_reading_history(limit=limit, offset=offset)


@router.post("/api/history/remove")
def remove_history_entries(payload: HistoryRemoveRequest):
    database.remove_from_history(payload.chapter_ids)
    return {"ok": True}


@router.delete("/api/history")
def clear_history():
    database.clear_reading_history()
    return {"ok": True}


@router.get("/api/stats")
def get_stats(tz_offset: int = 0):
    return database.get_reading_stats(tz_offset_minutes=tz_offset)


@router.get("/api/stats/reading")
def reading_overview_stats(period: str = "week", tz_offset: int = 0):
    return database.get_reading_summary(
        period=period, tz_offset_minutes=tz_offset, minutes_per_chapter=READING_MINUTES_PER_CHAPTER
    )
