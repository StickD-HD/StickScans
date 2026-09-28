import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import anilist, database
from .backup import run_backup
from .byparr_client import ByparrError
from .scraper import check_all_series, check_one_series, fetch_and_parse_new_url, get_progress

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("manhwa-tracker")

STATIC_DIR = Path(__file__).parent.parent / "static"

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    run_backup()
    scheduler.add_job(check_all_series, "interval", hours=1, id="check_all_series")
    scheduler.add_job(run_backup, CronTrigger(hour=3, minute=0), id="daily_backup")
    scheduler.start()
    logger.info("Planificateur démarré (vérification toutes les heures, sauvegarde quotidienne à 3h)")
    yield
    scheduler.shutdown()


app = FastAPI(title="Stickscans", lifespan=lifespan)


class AddSeriesRequest(BaseModel):
    url: str
    category_ids: list[int] = []


class MarkReadUpToRequest(BaseModel):
    number: str


class ToggleReadRequest(BaseModel):
    is_read: bool


class BulkReadRequest(BaseModel):
    chapter_ids: list[int]
    is_read: bool


class UpdateSeriesRequest(BaseModel):
    cover_url: str | None = None
    title: str | None = None


class CategoryRequest(BaseModel):
    name: str


class AnilistTokenRequest(BaseModel):
    token: str


class AnilistClientIdRequest(BaseModel):
    client_id: str


class AnilistLinkRequest(BaseModel):
    anilist_id: int
    title: str


class AnilistUpdateRequest(BaseModel):
    status: str | None = None
    progress: int | None = None
    score: float | None = None
    start_date: str | None = None
    end_date: str | None = None


@app.get("/api/series")
def list_series(sort: str = "last_checked_at", hide_fully_read: bool = False,
                 genre: str | None = None, status: str | None = None, search: str | None = None,
                 category_id: int | None = None):
    return database.get_all_series(sort=sort, hide_fully_read=hide_fully_read,
                                     genre=genre, status=status, search=search, category_id=category_id)


@app.get("/api/genres")
def list_genres():
    return database.get_all_genres()


@app.get("/api/statuses")
def list_statuses():
    return database.get_all_statuses()


@app.get("/api/categories")
def list_categories():
    return database.get_all_categories()


@app.post("/api/categories")
def create_category(payload: CategoryRequest):
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "Nom de catégorie vide")
    category_id = database.create_category(name)
    return {"id": category_id, "name": name}


@app.patch("/api/categories/{category_id}")
def rename_category(category_id: int, payload: CategoryRequest):
    database.rename_category(category_id, payload.name.strip())
    return {"ok": True}


@app.delete("/api/categories/{category_id}")
def delete_category(category_id: int):
    database.delete_category(category_id)
    return {"ok": True}


@app.post("/api/series/{series_id}/categories/{category_id}")
def add_series_to_category(series_id: int, category_id: int):
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    database.add_series_to_category(series_id, category_id)
    return {"ok": True}


@app.delete("/api/series/{series_id}/categories/{category_id}")
def remove_series_from_category(series_id: int, category_id: int):
    database.remove_series_from_category(series_id, category_id)
    return {"ok": True}


@app.get("/api/series/{series_id}")
def get_series(series_id: int):
    series = database.get_series_by_id(series_id)
    if not series:
        raise HTTPException(404, "Série introuvable")
    return series


@app.patch("/api/series/{series_id}")
def update_series(series_id: int, payload: UpdateSeriesRequest):
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    database.update_series_manual(series_id, cover_url=payload.cover_url, title=payload.title)
    return database.get_series_by_id(series_id)


@app.post("/api/series/{series_id}/unlock/{field}")
def unlock_field(series_id: int, field: str):
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    database.unlock_field(series_id, field)
    return database.get_series_by_id(series_id)


@app.post("/api/series")
def add_series(payload: AddSeriesRequest):
    url = payload.url.strip()
    if not url.startswith("https://www.scan-manga.com/"):
        raise HTTPException(400, "L'URL doit être une page série de scan-manga.com")

    if database.get_series_by_url(url):
        raise HTTPException(409, "Cette série est déjà dans ta bibliothèque")

    try:
        parsed = fetch_and_parse_new_url(url)
    except ByparrError as e:
        raise HTTPException(502, f"Échec de la récupération : {e}")

    if not parsed.get("title"):
        raise HTTPException(422, "Impossible d'extraire les infos de cette page (structure inattendue ?)")

    series_id = database.insert_series(url, parsed)
    for category_id in payload.category_ids:
        database.add_series_to_category(series_id, category_id)
    return database.get_series_by_id(series_id)


@app.post("/api/series/refresh-all")
def refresh_all(background_tasks: BackgroundTasks):
    background_tasks.add_task(check_all_series)
    return {"ok": True, "message": "Vérification lancée en arrière-plan"}


@app.get("/api/refresh-status")
def refresh_status():
    return get_progress()


@app.post("/api/series/{series_id}/recheck")
def recheck_series(series_id: int):
    series = database.get_series_by_id(series_id)
    if not series:
        raise HTTPException(404, "Série introuvable")
    return check_one_series(series)


@app.get("/api/series/{series_id}/chapters")
def list_chapters(series_id: int):
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    return database.get_chapters_for_series(series_id)


@app.post("/api/series/{series_id}/mark-read-up-to")
def mark_read_up_to(series_id: int, payload: MarkReadUpToRequest):
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    try:
        number_float = float(payload.number)
    except ValueError:
        raise HTTPException(400, "Numéro de chapitre invalide")
    database.mark_read_up_to(series_id, number_float)
    anilist.push_progress(series_id)
    return database.get_series_by_id(series_id)


@app.post("/api/series/{series_id}/mark-all-read")
def mark_all_read(series_id: int):
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    database.mark_all_read(series_id)
    anilist.push_progress(series_id)
    return database.get_series_by_id(series_id)


@app.post("/api/chapters/{chapter_id}/toggle-read")
def toggle_chapter_read(chapter_id: int, payload: ToggleReadRequest):
    database.set_chapter_read(chapter_id, payload.is_read)
    series_id = database.get_series_id_for_chapter(chapter_id)
    if series_id:
        anilist.push_progress(series_id)
    return {"ok": True}


@app.post("/api/chapters/bulk-read")
def bulk_toggle_read(payload: BulkReadRequest):
    database.set_chapters_read(payload.chapter_ids, payload.is_read)
    for series_id in database.get_series_ids_for_chapters(payload.chapter_ids):
        anilist.push_progress(series_id)
    return {"ok": True}


@app.get("/api/updates")
def list_updates(limit: int = 100):
    return database.get_recent_updates(limit=limit)


@app.get("/api/history")
def list_history(limit: int = 200):
    return database.get_reading_history(limit=limit)


@app.delete("/api/history")
def clear_history():
    database.clear_reading_history()
    return {"ok": True}


@app.get("/api/stats")
def get_stats():
    return database.get_reading_stats()


@app.get("/api/settings/anilist")
def get_anilist_setting():
    return anilist.get_status()


@app.post("/api/settings/anilist")
def set_anilist_setting(payload: AnilistTokenRequest):
    try:
        return anilist.save_token(payload.token)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@app.delete("/api/settings/anilist")
def delete_anilist_setting():
    anilist.remove_token()
    return anilist.get_status()


@app.post("/api/settings/anilist/check")
def check_anilist_setting():
    try:
        return anilist.check_token()
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@app.post("/api/settings/anilist/client-id")
def set_anilist_client_id(payload: AnilistClientIdRequest):
    client_id = payload.client_id.strip()
    if client_id and not client_id.isdigit():
        raise HTTPException(400, "L'ID du client AniList est un nombre")
    if client_id:
        database.set_setting("anilist_client_id", client_id)
    else:
        database.delete_setting("anilist_client_id")
    return {"ok": True}


@app.get("/api/anilist/search")
def search_anilist(q: str):
    return anilist.search_media(q)


@app.post("/api/series/{series_id}/anilist/link")
def link_anilist(series_id: int, payload: AnilistLinkRequest):
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    anilist.link_series(series_id, payload.anilist_id, payload.title)
    return database.get_series_by_id(series_id)


@app.post("/api/series/{series_id}/anilist/update")
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
    )
    return database.get_series_by_id(series_id)


@app.delete("/api/series/{series_id}/anilist")
def unlink_anilist(series_id: int):
    anilist.unlink_series(series_id)
    return database.get_series_by_id(series_id)


@app.delete("/api/series/{series_id}")
def remove_series(series_id: int):
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    database.delete_series(series_id)
    return {"ok": True}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/manifest.json")
def manifest():
    return FileResponse(STATIC_DIR / "manifest.json")


@app.get("/sw.js")
def service_worker():
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")