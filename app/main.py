"""
Point d'entrée de l'appli : création, démarrage (tâches planifiées), sécurité (connexion, en-têtes, cache), pages
et fichiers. Les routes de l'API sont rangées par thème dans app/routes/.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import logging
import os
from pathlib import Path
from urllib.parse import quote

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from . import anilist, auth, covers, database, fetcher
from . import scraper as scraper_module
from .routes import anilist_api, compte, lecture, sauvegardes, series, verifications
from .routes.common import scheduled_backup
from .scraper import run_due_checks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("manhwa-tracker")

STATIC_DIR = Path(__file__).parent.parent / "static"


def _asset_version() -> str:
    """Empreinte des fichiers de l'interface : change dès qu'un fichier change (donc à chaque mise à jour)."""
    import hashlib
    h = hashlib.sha1()
    for f in sorted(STATIC_DIR.rglob("*")):
        if f.is_file():
            st = f.stat()
            h.update(f"{f.relative_to(STATIC_DIR)}:{st.st_size}:{st.st_mtime_ns}".encode())
    return h.hexdigest()[:10]


ASSET_VERSION = _asset_version()
_versioned_pages: dict[str, str] = {}


def _versioned_page(name: str) -> HTMLResponse:
    """La page avec ses scripts, styles et icônes appelés en ?v=<version> : au lancement de l'appli, seule la page
    est redemandée au serveur, tout le reste vient directement du cache du navigateur (aucun aller-retour)."""
    if name not in _versioned_pages:
        import re
        html = (STATIC_DIR / name).read_text(encoding="utf-8")
        _versioned_pages[name] = re.sub(
            r'((?:src|href)=")(/static/(?!fonts/)[^"?#]+)"', rf'\1\2?v={ASSET_VERSION}"', html)
    return HTMLResponse(_versioned_pages[name])

scheduler = BackgroundScheduler()

DUE_CHECK_EVERY_MINUTES = 10
LEGACY_CHECK_SETTINGS = (
    "CHECK_INTERVAL_HOURS", "CHECK_OFFSET_MINUTES", "CHECK_MIN_DELAY_SECONDS", "CHECK_MAX_DELAY_SECONDS",
    "FETCH_BLOCK_COOLDOWN_MINUTES", "FETCH_BACKEND",
)


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
    # Couvertures : mises en cache sur le serveur (petit format) au fil de l'eau, celles qui manquent toutes les 30 min.
    scheduler.add_job(covers.cache_missing, IntervalTrigger(minutes=30), id="covers",
                      next_run_time=datetime.now(timezone.utc) + timedelta(seconds=30))
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
# Réponses compressées (listes de séries, chapitres, scripts, styles) : 4 à 8 fois moins de données à faire passer
# par le tunnel, donc des écrans qui s'affichent plus vite sur le téléphone.
app.add_middleware(GZipMiddleware, minimum_size=1000)


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
    path = request.url.path
    if path.startswith("/static/") and request.query_params.get("v") == ASSET_VERSION:
        # Fichier appelé avec la version en cours (?v=…) : son contenu ne changera jamais sous cette adresse, le
        # navigateur le garde sans plus rien demander. Une mise à jour change la version, donc l'adresse.
        response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
    elif not path.startswith(("/api/", "/covers/")):
        response.headers["Cache-Control"] = "private, no-cache"
    return response


@app.get("/login")
def login_page(request: Request):
    if not auth.is_enabled() or auth.verify_session_token(request.cookies.get(auth.COOKIE_NAME)):
        return RedirectResponse("/", status_code=303)
    return _versioned_page("login.html")


    


# ----- Réglages : mises à jour, stockage, sauvegardes -----


# --- API : une route par thème, dans app/routes/ ---
for _module in (compte, series, sauvegardes, verifications, lecture, anilist_api):
    app.include_router(_module.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return _versioned_page("index.html")


@app.get("/covers/{name}")
def cover_file(name: str):
    """Couverture en cache. Son nom dépend de l'adresse d'origine : il change si la couverture change, donc le
    navigateur peut la garder indéfiniment."""
    path = covers.path_for(name)
    if not path:
        raise HTTPException(404, "Couverture introuvable")
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "private, max-age=31536000, immutable"})


@app.get("/manifest.json")
def manifest():
    return FileResponse(STATIC_DIR / "manifest.json")


@app.get("/sw.js")
def service_worker():
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")