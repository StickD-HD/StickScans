"""Bibliothèque : séries (liste, fiche, ajout, adresse, retrait, actions groupées), genres, statuts, catégories."""
import sqlite3
import threading

from fastapi import APIRouter, BackgroundTasks, HTTPException

from .. import anilist, covers, database
from .. import scraper as scraper_module
from ..fetcher import FetchError
from ..scraper import (
    check_all_series,
    fetch_and_parse_new_url,
    get_progress,
    normalize_series_url,
    plan_next,
    site_pause_message,
)
from .common import READING_MINUTES_PER_CHAPTER
from .models import (AddSeriesRequest, BulkIdsRequest, BulkSeriesRequest, CategoryRequest, ChangeUrlRequest,
                     ReadingStateRequest)

router = APIRouter()


@router.get("/api/series")
def list_series(sort: str = "last_checked_at", hide_fully_read: bool = False,
                 genre: str | None = None, status: str | None = None, search: str | None = None,
                 category_id: int | None = None, anilist: str | None = None):
    return database.get_all_series(sort=sort, hide_fully_read=hide_fully_read, genre=genre, status=status,
                                     search=search, category_id=category_id, anilist=anilist)


@router.get("/api/genres")
def list_genres():
    return database.get_all_genres()


@router.get("/api/statuses")
def list_statuses():
    return database.get_all_statuses()


@router.get("/api/categories")
def list_categories():
    return database.get_all_categories()


@router.post("/api/categories")
def create_category(payload: CategoryRequest):
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "Nom de catégorie vide")
    category_id = database.create_category(name)
    return {"id": category_id, "name": name}


@router.patch("/api/categories/{category_id}")
def rename_category(category_id: int, payload: CategoryRequest):
    database.rename_category(category_id, payload.name.strip())
    return {"ok": True}


@router.delete("/api/categories/{category_id}")
def delete_category(category_id: int):
    database.delete_category(category_id)
    return {"ok": True}


@router.post("/api/series/{series_id}/categories/{category_id}")
def add_series_to_category(series_id: int, category_id: int):
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    database.add_series_to_category(series_id, category_id)
    return {"ok": True}


@router.delete("/api/series/{series_id}/categories/{category_id}")
def remove_series_from_category(series_id: int, category_id: int):
    database.remove_series_from_category(series_id, category_id)
    return {"ok": True}


@router.get("/api/series/{series_id}")
def get_series(series_id: int):
    series = database.get_series_by_id(series_id)
    if not series:
        raise HTTPException(404, "Série introuvable")
    # Pour le temps de lecture estimé affiché sur la fiche (même réglage que l'aperçu de lecture)
    return {**series, "minutes_per_chapter": READING_MINUTES_PER_CHAPTER}


@router.post("/api/series")
def add_series(payload: AddSeriesRequest):
    url = normalize_series_url(payload.url)
    if not url:
        raise HTTPException(400, "L'URL doit être une page série de scan-manga.com")

    if database.get_series_by_url(url):
        raise HTTPException(409, "Cette série est déjà dans ta bibliothèque")

    try:
        parsed = fetch_and_parse_new_url(url)
    except FetchError as e:
        raise HTTPException(502, f"Échec de la récupération : {e}")

    if not parsed.get("title"):
        raise HTTPException(422, "Impossible d'extraire les infos de cette page (structure inattendue ?)")

    try:
        series_id = database.insert_series(url, parsed)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Cette série est déjà dans ta bibliothèque")
    for category_id in payload.category_ids:
        database.add_series_to_category(series_id, category_id)
    series = database.get_series_by_id(series_id)
    plan_next(series, ok=True)  # la page vient d'être lue : inutile de la redemander tout de suite
    covers.cache_in_background()
    return database.get_series_by_id(series_id)


@router.post("/api/series/{series_id}/url")
def change_url(series_id: int, payload: ChangeUrlRequest):
    """Nouvelle adresse pour une fiche déplacée sur le site : chapitres lus et historique sont gardés."""
    series = database.get_series_by_id(series_id)
    if not series:
        raise HTTPException(404, "Série introuvable")
    url = normalize_series_url(payload.url)
    if not url:
        raise HTTPException(400, "L'adresse doit être une page série de scan-manga.com")
    other = database.get_series_by_url(url)
    if other and other["id"] != series_id:
        raise HTTPException(409, f"Cette adresse est déjà celle de « {other.get('title') or url} » dans ta bibliothèque")
    try:
        result = scraper_module.change_series_url(series, url)
    except FetchError as e:
        raise HTTPException(502, f"Nouvelle adresse illisible : {e}")
    except ValueError as e:
        raise HTTPException(422, str(e))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Cette adresse est déjà suivie par une autre série")
    return {**database.get_series_by_id(series_id), **result}


@router.post("/api/series/refresh-all")
def refresh_all():
    pause = site_pause_message()
    if pause:
        raise HTTPException(409, pause)
    if get_progress()["is_running"]:
        raise HTTPException(409, "Une vérification est déjà en cours.")
    # Fil à part, et non une tâche de la requête : le serveur attend la fin des requêtes avant de s'arrêter,
    # et une actualisation complète dure de longues minutes (requêtes espacées de 45 à 90 s).
    threading.Thread(target=check_all_series, args=("manuel",), name="actualisation-manuelle", daemon=True).start()
    return {"ok": True, "message": "Vérification lancée en arrière-plan"}


@router.put("/api/series/{series_id}/state")
def set_series_state(series_id: int, payload: ReadingStateRequest, background_tasks: BackgroundTasks):
    """État de lecture choisi à la main (ou None : automatique, selon ta lecture). Suivi sur AniList si liée."""
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    if payload.state is not None and payload.state not in database.READING_STATES:
        raise HTTPException(400, "État inconnu")
    database.set_reading_state(series_id, payload.state)
    background_tasks.add_task(anilist.push_state, series_id)
    return database.get_series_by_id(series_id)


BULK_ACTIONS = {"mark_read", "mark_unread", "delete", "add_category", "remove_category", "set_state"}


@router.post("/api/series/bulk")
def bulk_series(payload: BulkSeriesRequest, background_tasks: BackgroundTasks):
    if payload.action not in BULK_ACTIONS:
        raise HTTPException(400, "Action inconnue")
    if payload.action in ("add_category", "remove_category"):
        if not any(c["id"] == payload.category_id for c in database.get_all_categories()):
            raise HTTPException(404, "Catégorie introuvable")
    if payload.action == "set_state" and payload.state is not None and payload.state not in database.READING_STATES:
        raise HTTPException(400, "État inconnu")
    done = 0
    for series_id in dict.fromkeys(payload.series_ids):  # sans doublons, dans l'ordre
        series = database.get_series_by_id(series_id)
        if not series:
            continue
        if payload.action == "set_state":
            database.set_reading_state(series_id, payload.state)
            if series.get("anilist_id"):
                background_tasks.add_task(anilist.push_state, series_id)
        elif payload.action == "mark_read":
            database.resume_reading_state(series_id)
            database.mark_all_read(series_id)
            if series.get("anilist_id"):
                background_tasks.add_task(anilist.push_progress, series_id)
        elif payload.action == "mark_unread":
            database.mark_all_unread(series_id)  # comme pour une série seule, AniList n'est pas reculé
        elif payload.action == "delete":
            database.delete_series(series_id)
        elif payload.action == "add_category":
            database.add_series_to_category(series_id, payload.category_id)
        else:
            database.remove_series_from_category(series_id, payload.category_id)
        done += 1
    return {"ok": True, "count": done}


@router.post("/api/series/bulk/categories")
def bulk_series_categories(payload: BulkIdsRequest):
    """Pour chaque catégorie : combien des séries sélectionnées y sont déjà (case cochée, partielle ou vide)."""
    ids = set(payload.series_ids)
    result = []
    for c in database.get_all_categories():
        members = database.get_category_series_ids(c["id"])
        result.append({"id": c["id"], "name": c["name"], "count": len(ids & members), "total": len(ids)})
    return result


@router.delete("/api/series/{series_id}")
def remove_series(series_id: int):
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    database.delete_series(series_id)
    return {"ok": True}
