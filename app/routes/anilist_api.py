"""AniList : jeton, recherche, liaison des séries, mises à jour et synchronisation."""
from fastapi import APIRouter, HTTPException

from .. import anilist, covers, database
from .models import AnilistClientIdRequest, AnilistLinkRequest, AnilistTokenRequest, AnilistUpdateRequest

router = APIRouter()


@router.get("/api/settings/anilist")
def get_anilist_setting():
    return anilist.get_status()


@router.post("/api/settings/anilist")
def set_anilist_setting(payload: AnilistTokenRequest):
    try:
        return anilist.save_token(payload.token)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@router.delete("/api/settings/anilist")
def delete_anilist_setting():
    anilist.remove_token()
    return anilist.get_status()


@router.post("/api/settings/anilist/check")
def check_anilist_setting():
    try:
        anilist.check_token()
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    anilist.sync_all(force=True)  # « Vérifier » recopie aussi l'état AniList de toutes les séries
    return anilist.get_status()


@router.post("/api/settings/anilist/client-id")
def set_anilist_client_id(payload: AnilistClientIdRequest):
    client_id = payload.client_id.strip()
    if client_id and not client_id.isdigit():
        raise HTTPException(400, "L'ID du client AniList est un nombre")
    if client_id:
        database.set_setting("anilist_client_id", client_id)
    else:
        database.delete_setting("anilist_client_id")
    return {"ok": True}


@router.get("/api/anilist/search")
def search_anilist(q: str):
    try:
        return anilist.search_media(q)
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@router.post("/api/series/{series_id}/anilist/link")
def link_anilist(series_id: int, payload: AnilistLinkRequest):
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    anilist.link_series(series_id, payload.anilist_id, payload.title)
    covers.cache_in_background()
    return database.get_series_by_id(series_id)


@router.post("/api/series/{series_id}/anilist/update")
def update_anilist(series_id: int, payload: AnilistUpdateRequest):
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    anilist.push_update(
        series_id,
        status=payload.status,
        progress=payload.progress,
        score=payload.score,
        start_date=payload.start_date,
        end_date=payload.end_date,
        notes=payload.notes,
    )
    return database.get_series_by_id(series_id)


@router.delete("/api/series/{series_id}/anilist")
def unlink_anilist(series_id: int):
    anilist.unlink_series(series_id)
    return database.get_series_by_id(series_id)


@router.post("/api/anilist/sync")
def sync_anilist():
    """Appelé par l'appli à l'ouverture et au retour au premier plan (au plus une synchro par minute)."""
    return anilist.sync_all()


@router.post("/api/series/{series_id}/anilist/align-local")
def align_local_with_anilist(series_id: int):
    """Marque comme lus ici (sans historique) les chapitres qu'AniList indique comme lus."""
    series = database.get_series_by_id(series_id)
    if not series:
        raise HTTPException(404, "Série introuvable")
    if not series.get("anilist_id"):
        raise HTTPException(400, "Cette série n'est pas liée à AniList")
    try:  # valeur à jour ; si AniList est injoignable, on se fie à la dernière valeur connue
        entry = anilist.fetch_entry(series["anilist_id"])
        database.set_series_anilist_data(series_id, **entry)
        progress = entry.get("progress")
    except Exception:
        progress = series.get("anilist_progress")
    if not progress:
        raise HTTPException(400, "AniList n'indique aucun chapitre lu pour cette série")
    changed = database.mark_read_through(series_id, float(progress))
    return {"progress": progress, "changed": changed, "series": database.get_series_by_id(series_id)}
