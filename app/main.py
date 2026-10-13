import logging
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from pydantic import BaseModel

from . import anilist, auth, database
from . import scraper as scraper_module
from .parse_series import number_to_float
from .backup import run_backup
from .byparr_client import ByparrError
from .scraper import normalize_series_url, check_all_series, check_one_series, fetch_and_parse_new_url, get_progress

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("manhwa-tracker")

STATIC_DIR = Path(__file__).parent.parent / "static"

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if auth.AUTH_REQUIRED and not auth.is_enabled():
        raise RuntimeError("AUTH_REQUIRED=true mais AUTH_PASSWORD est vide : démarrage refusé (voir le fichier .env)")
    database.init_db()
    database.close_stale_check_runs()
    if auth.is_enabled():
        logger.info("Authentification activée (utilisateur : %s)", auth.AUTH_USERNAME)
    else:
        logger.warning("AUTH_PASSWORD non défini : l'application est accessible SANS authentification")
    run_backup()
    # CHECK_INTERVAL_HOURS : fréquence des vérifications (défaut : toutes les heures).
    # CHECK_OFFSET_MINUTES : si défini, les vérifications tombent à cette minute pile de l'heure
    # (ex. 30 => xx:30), pratique pour décaler deux instances qui partagent le même Byparr.
    interval_hours = max(1, int(os.environ.get("CHECK_INTERVAL_HOURS", "1") or 1))
    offset = os.environ.get("CHECK_OFFSET_MINUTES", "").strip()
    if offset:
        check_trigger = CronTrigger(hour="*" if interval_hours == 1 else f"*/{interval_hours}", minute=int(offset) % 60)
    else:
        check_trigger = IntervalTrigger(hours=interval_hours)
    scheduler.add_job(check_all_series, check_trigger, id="check_all_series")
    scheduler.add_job(run_backup, CronTrigger(hour=3, minute=0), id="daily_backup")
    scheduler.start()
    logger.info("Planificateur démarré (vérification : %s, sauvegarde quotidienne à 3h)", check_trigger)
    yield
    scheduler.shutdown()


app = FastAPI(title="Stickscans", lifespan=lifespan)


@app.middleware("http")
async def require_auth(request: Request, call_next):
    if not auth.is_enabled() or request.url.path in auth.PUBLIC_PATHS or request.url.path.startswith(auth.PUBLIC_PREFIXES):
        return await call_next(request)
    if auth.verify_session_token(request.cookies.get(auth.COOKIE_NAME)):
        return await call_next(request)
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Authentification requise"}, status_code=401)
    target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    return RedirectResponse(f"/login?next={quote(target, safe='')}", status_code=303)


class LoginRequest(BaseModel):
    username: str
    password: str
    next: str | None = None


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


class HistoryRemoveRequest(BaseModel):
    chapter_ids: list[int]


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


@app.get("/login")
def login_page(request: Request):
    if not auth.is_enabled() or auth.verify_session_token(request.cookies.get(auth.COOKIE_NAME)):
        return RedirectResponse("/", status_code=303)
    return FileResponse(STATIC_DIR / "login.html")


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request, response: Response):
    if not auth.is_enabled():
        return {"ok": True, "next": "/"}
    ip = auth.client_ip(request)
    if auth.is_rate_limited(ip):
        raise HTTPException(429, "Trop de tentatives, réessaie dans quelques minutes")
    if not auth.check_credentials(payload.username, payload.password):
        auth.register_failure(ip)
        logger.warning("Échec de connexion depuis %s", ip)
        raise HTTPException(401, "Identifiant ou mot de passe incorrect")
    auth.clear_failures(ip)
    response.set_cookie(
        auth.COOKIE_NAME,
        auth.create_session_token(),
        max_age=auth.SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=auth.COOKIE_SECURE,
        path="/",
    )
    return {"ok": True, "next": auth.safe_next_url(payload.next)}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/auth/status")
def auth_status(request: Request):
    return {
        "enabled": auth.is_enabled(),
        "authenticated": (not auth.is_enabled()) or auth.verify_session_token(request.cookies.get(auth.COOKIE_NAME)),
    }


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
    url = normalize_series_url(payload.url)
    if not url:
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
    background_tasks.add_task(check_all_series, "manuel")
    return {"ok": True, "message": "Vérification lancée en arrière-plan"}


@app.get("/api/database/download")
def download_database(tz_offset: int = 0):
    """Télécharge une copie cohérente de la base (même si l'appli écrit au même moment)."""
    if not database.DB_PATH.exists():
        raise HTTPException(404, "Base de données introuvable")
    tmp = tempfile.NamedTemporaryFile(prefix="stickscans-", suffix=".db", delete=False)
    tmp.close()
    source = sqlite3.connect(database.DB_PATH)
    target = sqlite3.connect(tmp.name)
    try:
        source.backup(target)  # copie intégrale et cohérente fournie par SQLite
    finally:
        target.close()
        source.close()
    local_now = datetime.now(timezone.utc) + timedelta(minutes=tz_offset)
    filename = f"stickscans-{local_now:%Y-%m-%d_%H-%M}.db"
    return FileResponse(
        tmp.name,
        media_type="application/octet-stream",
        filename=filename,
        background=BackgroundTask(os.remove, tmp.name),  # le fichier temporaire est supprimé après l'envoi
    )


@app.get("/api/checks/summary")
def checks_summary():
    return database.get_check_summary()


@app.get("/api/checks/log")
def checks_log_file():
    if not scraper_module.LOG_FILE.exists():
        raise HTTPException(404, "Aucun journal pour l'instant")
    return FileResponse(scraper_module.LOG_FILE, media_type="text/plain; charset=utf-8", filename="scrape.log")


@app.get("/api/checks")
def checks_list(limit: int = 60):
    return database.list_check_runs(limit=min(max(limit, 1), 200))


@app.get("/api/checks/{run_id}")
def checks_detail(run_id: int):
    run = database.get_check_run(run_id)
    if not run:
        raise HTTPException(404, "Vérification introuvable")
    return run


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
        number_float = number_to_float(payload.number, strict=True)
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


@app.post("/api/history/remove")
def remove_history_entries(payload: HistoryRemoveRequest):
    database.remove_from_history(payload.chapter_ids)
    return {"ok": True}


@app.delete("/api/history")
def clear_history():
    database.clear_reading_history()
    return {"ok": True}


@app.get("/api/stats")
def get_stats(tz_offset: int = 0):
    return database.get_reading_stats(tz_offset_minutes=tz_offset)


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