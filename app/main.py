import logging
import os
import sqlite3
import tempfile
import threading

from fastapi import UploadFile, File
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field

from . import anilist, auth, database
from . import scraper as scraper_module
from .parse_series import number_to_float
from . import backup as backup_files
from . import storage
from .backup import replace_database, run_backup
from . import fetcher
from .fetcher import FetchError
from . import site_guard
from .scraper import (normalize_series_url, check_all_series, check_one_series, fetch_and_parse_new_url, get_progress,
                      maintenance, plan_next, run_due_checks, site_pause_message)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("manhwa-tracker")

STATIC_DIR = Path(__file__).parent.parent / "static"
# Écrit par outils/deploy.sh dans le dossier de l'instance : « commit|date|message » de la version qui tourne.
VERSION_FILE = Path(__file__).parent.parent / "VERSION"

scheduler = BackgroundScheduler()

DUE_CHECK_EVERY_MINUTES = 10
LEGACY_CHECK_SETTINGS = (
    "CHECK_INTERVAL_HOURS", "CHECK_OFFSET_MINUTES", "CHECK_MIN_DELAY_SECONDS", "CHECK_MAX_DELAY_SECONDS",
    "FETCH_BLOCK_COOLDOWN_MINUTES", "FETCH_BACKEND",
)


def _backup_settings() -> dict:
    """Sauvegarde automatique : activée par défaut, 7 copies quotidiennes gardées (1 à 30)."""
    try:
        keep = int(database.get_setting("backup_keep") or 7)
    except ValueError:
        keep = 7
    return {"enabled": database.get_setting("backup_enabled") != "0", "keep": min(30, max(1, keep))}


def scheduled_backup(overwrite: bool = True):
    cfg = _backup_settings()
    if cfg["enabled"]:
        run_backup(overwrite=overwrite, keep=cfg["keep"])


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
    scheduled_backup(overwrite=False)  # au démarrage : on garde la copie du jour si elle existe déjà
    # Chaque série a sa propre heure de vérification (selon son rythme de sortie, voir schedule.py) : toutes les
    # 10 minutes, on regarde simplement lesquelles sont dues. Les anciens réglages globaux n'ont plus d'effet.
    for old in LEGACY_CHECK_SETTINGS:
        if os.environ.get(old, "").strip():
            logger.warning("%s n'est plus utilisé (fréquence par série, voir README) : tu peux le retirer du fichier .env", old)
    check_trigger = IntervalTrigger(minutes=DUE_CHECK_EVERY_MINUTES, jitter=60)
    scheduler.add_job(
        run_due_checks, check_trigger, id="run_due_checks",
        next_run_time=datetime.now(timezone.utc) + timedelta(minutes=2),
    )
    scheduler.add_job(scheduled_backup, CronTrigger(hour=3, minute=0), id="daily_backup")
    # ANILIST_SYNC_MINUTES : fréquence de la copie de l'état AniList dans l'appli (défaut 15 ; 0 = désactivée).
    sync_minutes = int(os.environ.get("ANILIST_SYNC_MINUTES", "15") or 0)
    if sync_minutes > 0:
        scheduler.add_job(
            anilist.sync_all, IntervalTrigger(minutes=sync_minutes), id="anilist_sync",
            kwargs={"force": True}, next_run_time=datetime.now(timezone.utc) + timedelta(seconds=20),
        )
    scheduler.start()
    logger.info("Planificateur démarré (séries dues regardées toutes les %d min, sauvegarde quotidienne à 3h)",
                DUE_CHECK_EVERY_MINUTES)
    yield
    # Arrêt (systemctl restart / stop) : on interrompt toute attente de tour, on laisse finir la série en cours
    # (au plus le délai d'une requête), puis on s'arrête sans attendre la fin de la file.
    fetcher.STOP.set()
    scheduler.shutdown(wait=False)
    if not scraper_module.wait_until_idle(timeout=40):
        logger.warning("Vérification encore en cours à l'arrêt : elle sera notée « interrompue » au prochain démarrage")


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


# En-têtes de sécurité, sur toutes les réponses (l'appli est exposée sur Internet). La politique de contenu (CSP)
# n'autorise que les scripts servis par l'appli elle-même : même si un titre ou un synopsis venu du site contenait
# du code et qu'un affichage oubliait de l'échapper, le navigateur refuserait de l'exécuter.
# Images : https (couvertures scan-manga et AniList) et data: (aperçu de l'affichage).
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "font-src 'self'",
    "img-src 'self' https: data:",
    "connect-src 'self'",
    "manifest-src 'self'",
    "worker-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])
SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


@app.middleware("http")
async def never_serve_stale_pages(request: Request, call_next):
    """Pages et fichiers de l'appli : toujours revérifiés auprès du serveur (jamais de vieille copie).
    Sans ça, un cache intermédiaire (Cloudflare, par exemple) continue de servir l'ancienne version
    de app.js / style.css pendant des heures après une mise à jour."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "private, no-cache"
    return response


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
    # AAAA-MM-JJ, ou "" pour effacer la date sur AniList ; absent (None) = date inchangée
    start_date: str | None = Field(default=None, pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    end_date: str | None = Field(default=None, pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    notes: str | None = Field(default=None, max_length=500)  # "" = effacer la note


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
    _set_session_cookie(response, request)
    return {"ok": True, "next": auth.safe_next_url(payload.next)}


def _set_session_cookie(response: Response, request: Request):
    response.set_cookie(
        auth.COOKIE_NAME,
        auth.create_session_token(),
        max_age=auth.SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=auth.COOKIE_SECURE or request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https" or request.url.scheme == "https",
        path="/",
    )


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"ok": True}


@app.post("/api/auth/logout-others")
def logout_others(request: Request, response: Response):
    """Déconnecte tous les autres appareils (téléphone perdu, ordinateur prêté...) ; celui-ci reste connecté."""
    if not auth.is_enabled():
        raise HTTPException(400, "Pas d'authentification configurée")
    auth.revoke_all_sessions()
    _set_session_cookie(response, request)  # nouvelle session pour cet appareil, de la nouvelle génération
    logger.warning("Toutes les autres sessions ont été déconnectées (depuis %s)", auth.client_ip(request))
    return {"ok": True}


@app.get("/api/auth/status")
def auth_status(request: Request):
    return {
        "enabled": auth.is_enabled(),
        "authenticated": (not auth.is_enabled()) or auth.verify_session_token(request.cookies.get(auth.COOKIE_NAME)),
    }


@app.get("/api/version")
def app_version():
    try:
        commit, date, subject = (VERSION_FILE.read_text(encoding="utf-8").strip().split("|", 2) + ["", ""])[:3]
    except OSError:
        return {"commit": None, "date": None, "subject": None}
    return {"commit": commit or None, "date": date or None, "subject": subject or None}


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


@app.post("/api/series")
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
    return database.get_series_by_id(series_id)


@app.post("/api/series/refresh-all")
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
        source.backup(target)
        # Point 7 : Nettoyage du jeton AniList pour l'export
        target.execute("DELETE FROM app_settings WHERE key = 'anilist_token'")
        target.commit()
    finally:
        target.close()
        source.close()
        
    local_now = datetime.now(timezone.utc) + timedelta(minutes=tz_offset)
    filename = f"stickscans-{local_now:%Y-%m-%d_%H-%M}.db"
    
    return FileResponse(
        tmp.name,
        media_type="application/octet-stream",
        filename=filename,
        background=BackgroundTask(os.remove, tmp.name),
    )

MAX_IMPORT_BYTES = 200 * 1024 * 1024


@app.post("/api/database/import")
def import_database(file: UploadFile = File(...)):
    if not (file.filename or "").endswith(".db"):
        raise HTTPException(400, "Le fichier doit être un .db")
    tmp_path = database.DB_PATH.with_suffix(".tmp")
    try:
        # 1. Réception du fichier dans un fichier temporaire (taille limitée)
        size = 0
        with open(tmp_path, "wb") as buffer:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_IMPORT_BYTES:
                    raise HTTPException(413, "Fichier trop volumineux")
                buffer.write(chunk)
        # 2. Contrôle d'intégrité, copie de sécurité de la base actuelle, puis remplacement ;
        # 3. mise à niveau du schéma si la base importée vient d'une version plus ancienne.
        # Aucune vérification ne peut démarrer pendant ce temps.
        with maintenance():
            safe = replace_database(tmp_path)
            database.init_db()
            auth.forget_generation_cache()
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    finally:
        tmp_path.unlink(missing_ok=True)

    return {"status": "ok", "backup": safe.name if safe else None}
    
SKIP_SHORT_LABELS = {"skip_completed": "terminée", "skip_unread": "chapitres non lus", "skip_never_read": "jamais lue"}


@app.get("/api/checks/overview")
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


@app.post("/api/series/{series_id}/mark-all-read")
def mark_all_read(series_id: int, background_tasks: BackgroundTasks):
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    database.mark_all_read(series_id)
    background_tasks.add_task(anilist.push_progress, series_id)
    return database.get_series_by_id(series_id)


@app.post("/api/series/{series_id}/reset-progress")
def reset_progress(series_id: int):
    """Remet tous les chapitres en « non lu ». AniList n'est pas touché : une progression n'y recule jamais
    automatiquement."""
    if not database.get_series_by_id(series_id):
        raise HTTPException(404, "Série introuvable")
    database.mark_all_unread(series_id)
    return database.get_series_by_id(series_id)


@app.post("/api/chapters/{chapter_id}/toggle-read")
def toggle_chapter_read(chapter_id: int, payload: ToggleReadRequest, background_tasks: BackgroundTasks):
    database.set_chapter_read(chapter_id, payload.is_read)
    series_id = database.get_series_id_for_chapter(chapter_id)
    if series_id:
        background_tasks.add_task(anilist.push_progress, series_id)
    return {"ok": True}


@app.post("/api/chapters/bulk-read")
def bulk_toggle_read(payload: BulkReadRequest, background_tasks: BackgroundTasks):
    database.set_chapters_read(payload.chapter_ids, payload.is_read)
    for series_id in database.get_series_ids_for_chapters(payload.chapter_ids):
        background_tasks.add_task(anilist.push_progress, series_id)
    return {"ok": True}


# Nouveautés et historique se chargent par pages (« voir plus ») : limit = taille de la page, offset = déjà chargés.
def _page(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 1000), max(offset, 0)


@app.get("/api/updates")
def list_updates(limit: int = 100, offset: int = 0):
    limit, offset = _page(limit, offset)
    return database.get_recent_updates(limit=limit, offset=offset)


@app.get("/api/history")
def list_history(limit: int = 200, offset: int = 0):
    limit, offset = _page(limit, offset)
    return database.get_reading_history(limit=limit, offset=offset)


@app.post("/api/history/remove")
def remove_history_entries(payload: HistoryRemoveRequest):
    database.remove_from_history(payload.chapter_ids)
    return {"ok": True}


@app.delete("/api/history")
def clear_history():
    database.clear_reading_history()
    return {"ok": True}


# ----- Réglages : mises à jour, stockage, sauvegardes -----

class UpdateSettingsRequest(BaseModel):
    auto_enabled: bool | None = None
    skip_completed: bool | None = None
    skip_unread: bool | None = None
    skip_never_read: bool | None = None


class BackupSettingsRequest(BaseModel):
    enabled: bool | None = None
    keep: int | None = Field(default=None, ge=1, le=30)


@contextmanager
def _exclusive():
    """Opération qui réécrit ou remplace la base : refusée pendant une vérification, et aucune ne démarre pendant elle."""
    try:
        with maintenance():
            yield
    except RuntimeError as e:
        if str(e) == scraper_module.BUSY_MESSAGE:
            raise HTTPException(409, str(e))
        raise


def _updates_settings() -> dict:
    return {**database.get_update_settings(), "auto_enabled": database.auto_checks_enabled()}


@app.get("/api/settings/updates")
def get_updates_settings():
    return _updates_settings()


@app.put("/api/settings/updates")
def put_updates_settings(payload: UpdateSettingsRequest):
    values = payload.model_dump()
    if values.pop("auto_enabled") is not None:
        database.set_setting("auto_checks_enabled", "1" if payload.auto_enabled else "0")
    database.set_update_settings(values)
    return _updates_settings()


@app.get("/api/site-status")
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


@app.post("/api/site-status/clear-pause")
def clear_site_pause():
    site_guard.clear_block()
    return get_site_status()


@app.get("/api/storage")
def get_storage():
    return storage.get_storage_info()


@app.post("/api/storage/clear-page-cache")
def clear_page_cache():
    return storage.clear_page_cache()


@app.post("/api/storage/clear-logs")
def clear_logs():
    return storage.clear_logs()


@app.post("/api/storage/clear-check-history")
def clear_check_history():
    with _exclusive():
        return database.clear_check_history()


@app.post("/api/storage/optimize")
def optimize_storage():
    with _exclusive():
        return storage.optimize_database()


@app.get("/api/backups")
def list_backups():
    return {"settings": _backup_settings(), "backups": backup_files.list_backups()}


@app.put("/api/settings/backups")
def put_backup_settings(payload: BackupSettingsRequest):
    if payload.enabled is not None:
        database.set_setting("backup_enabled", "1" if payload.enabled else "0")
    if payload.keep is not None:
        database.set_setting("backup_keep", str(payload.keep))
    return _backup_settings()


@app.post("/api/backups")
def create_backup():
    backup_files.create_manual_backup()
    return {"settings": _backup_settings(), "backups": backup_files.list_backups()}


@app.get("/api/backups/{name}/download")
def download_backup(name: str):
    try:
        path = backup_files.backup_path(name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, "Sauvegarde introuvable")
    return FileResponse(path, filename=name, media_type="application/octet-stream")


@app.delete("/api/backups/{name}")
def delete_backup(name: str):
    try:
        backup_files.delete_backup(name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, "Sauvegarde introuvable")
    return {"settings": _backup_settings(), "backups": backup_files.list_backups()}


@app.post("/api/backups/{name}/restore")
def restore_backup(name: str):
    try:
        with _exclusive():
            safe = backup_files.restore_backup(name)
            database.init_db()  # met le schéma à niveau si la sauvegarde vient d'une version plus ancienne
            auth.forget_generation_cache()
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, "Sauvegarde introuvable")
    return {"status": "ok", "backup": safe.name if safe else None}


@app.get("/api/stats")
def get_stats(tz_offset: int = 0):
    return database.get_reading_stats(tz_offset_minutes=tz_offset)


# READING_MINUTES_PER_CHAPTER : durée estimée de lecture d'un chapitre (défaut 5 min), pour l'aperçu de lecture.
READING_MINUTES_PER_CHAPTER = max(1, int(os.environ.get("READING_MINUTES_PER_CHAPTER", "5") or 5))


@app.get("/api/stats/reading")
def reading_overview_stats(period: str = "week", tz_offset: int = 0):
    return database.get_reading_summary(
        period=period, tz_offset_minutes=tz_offset, minutes_per_chapter=READING_MINUTES_PER_CHAPTER
    )


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
        anilist.check_token()
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    anilist.sync_all(force=True)  # « Vérifier » recopie aussi l'état AniList de toutes les séries
    return anilist.get_status()


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
    try:
        return anilist.search_media(q)
    except RuntimeError as e:
        raise HTTPException(502, str(e))


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
        notes=payload.notes,
    )
    return database.get_series_by_id(series_id)


@app.delete("/api/series/{series_id}/anilist")
def unlink_anilist(series_id: int):
    anilist.unlink_series(series_id)
    return database.get_series_by_id(series_id)


@app.post("/api/anilist/sync")
def sync_anilist():
    """Appelé par l'appli à l'ouverture et au retour au premier plan (au plus une synchro par minute)."""
    return anilist.sync_all()


@app.post("/api/series/{series_id}/anilist/align-local")
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