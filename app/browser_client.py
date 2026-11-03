"""
Client navigateur : récupère le HTML d'une page protégée par Cloudflare avec un vrai Chrome
piloté par Playwright. Remplace byparr_client (même fonction : fetch_html(url) -> str).

Un seul navigateur, géré par un thread dédié : l'API synchrone de Playwright est liée au thread
qui l'a créé, alors que l'appli appelle fetch_html depuis plusieurs threads (planificateur,
requêtes web). Les appels sont mis en file et exécutés un par un. Le navigateur est fermé après
une période d'inactivité pour libérer la mémoire.
"""
import atexit
import logging
import os
import queue
import threading
import time
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path

from playwright.sync_api import sync_playwright

from .database import DB_PATH

logger = logging.getLogger("manhwa-tracker.browser")

DEFAULT_TIMEOUT_MS = 60000
PROFILE_DIR = Path(os.environ.get("BROWSER_PROFILE_DIR") or DB_PATH.parent / "browser-profile")
DEBUG_DIR = DB_PATH.parent / "debug"
HEADLESS = os.environ.get("BROWSER_HEADLESS", "false").lower() == "true"
BLOCK_MEDIA = os.environ.get("BROWSER_BLOCK_MEDIA", "true").lower() == "true"
IDLE_CLOSE_SECONDS = int(os.environ.get("BROWSER_IDLE_SECONDS", "180"))
CHALLENGE_TITLES = ("just a moment", "un instant", "attention required", "checking your browser")
MAX_DEBUG_FILES = 10


class FetchError(Exception):
    pass


def _filter_route(route):
    if route.request.resource_type in ("image", "media", "font"):
        route.abort()
    else:
        route.continue_()


def _is_challenge(page) -> bool:
    try:
        title = (page.title() or "").lower()
    except Exception:  # navigation en cours (le challenge recharge la page)
        return True
    return any(marker in title for marker in CHALLENGE_TITLES)


def _save_debug(page):
    """Capture d'écran en cas d'échec : data/debug/<timestamp>.png (les 10 dernières sont gardées)."""
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(DEBUG_DIR / f"{int(time.time())}.png"))
        for old in sorted(DEBUG_DIR.glob("*.png"))[:-MAX_DEBUG_FILES]:
            old.unlink(missing_ok=True)
    except Exception:
        pass


class _BrowserWorker(threading.Thread):
    def __init__(self):
        super().__init__(name="browser-worker", daemon=True)
        self._jobs: queue.Queue = queue.Queue()
        self._pw = None
        self._ctx = None

    # --- API appelée depuis les autres threads ---
    def submit(self, url: str, timeout_ms: int) -> Future:
        future: Future = Future()
        self._jobs.put((url, timeout_ms, future))
        return future

    def stop(self):
        self._jobs.put(None)

    # --- Tout le reste s'exécute dans ce thread ---
    def run(self):
        while True:
            try:
                job = self._jobs.get(timeout=IDLE_CLOSE_SECONDS)
            except queue.Empty:
                self._close()  # inactif : on libère la mémoire
                continue
            if job is None:
                self._close()
                return
            url, timeout_ms, future = job
            try:
                future.set_result(self._fetch(url, timeout_ms))
            except Exception as e:
                future.set_exception(e)

    def _open(self):
        if self._ctx is not None:
            return
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        # Verrous laissés par un Chrome tué brutalement (arrêt du conteneur) : sinon « profil déjà utilisé »
        for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            (PROFILE_DIR / name).unlink(missing_ok=True)
        self._pw = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            channel="chrome",
            headless=HEADLESS,
            locale="fr-FR",
            viewport={"width": 1366, "height": 768},
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        if BLOCK_MEDIA:
            self._ctx.route("**/*", _filter_route)
        logger.info("Navigateur démarré")

    def _close(self):
        if self._ctx is None and self._pw is None:
            return
        try:
            if self._ctx:
                self._ctx.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._ctx = self._pw = None
        logger.info("Navigateur fermé")

    def _fetch(self, url: str, timeout_ms: int) -> str:
        page = None
        for attempt in (1, 2):  # si Chrome est mort entre-temps, on le relance une fois
            try:
                self._open()
                page = self._ctx.new_page()
                break
            except Exception:
                self._close()
                if attempt == 2:
                    raise
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            deadline = time.monotonic() + timeout_ms / 1000
            while _is_challenge(page):
                if time.monotonic() > deadline:
                    raise FetchError("Challenge Cloudflare non résolu (voir data/debug/)")
                page.wait_for_timeout(1000)
            return page.content()
        except Exception:
            _save_debug(page)
            raise
        finally:
            try:
                page.close()
            except Exception:
                pass


_worker: _BrowserWorker | None = None
_worker_lock = threading.Lock()


def _get_worker() -> _BrowserWorker:
    global _worker
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            _worker = _BrowserWorker()
            _worker.start()
        return _worker


def _shutdown():
    worker = _worker
    if worker is not None and worker.is_alive():
        worker.stop()
        worker.join(timeout=10)


atexit.register(_shutdown)


def fetch_html(url: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> str:
    future = _get_worker().submit(url, timeout_ms)
    try:
        return future.result(timeout=timeout_ms / 1000 + 120)
    except FetchError:
        raise
    except FutureTimeout as e:
        raise FetchError("Le navigateur n'a pas répondu à temps") from e
    except Exception as e:
        message = (str(e).splitlines() or [e.__class__.__name__])[0]
        raise FetchError(f"Échec du navigateur : {message}") from e