"""
Récupération d'une page via un vrai navigateur (Playwright + Chromium), en remplacement de Byparr.
Même interface : fetch_html(url, timeout_ms) -> str.

Choix volontaires :
- profil de navigateur PERSISTANT (data/browser-profile) : les cookies, dont celui d'un éventuel
  challenge déjà validé, sont conservés d'un appel à l'autre ;
- une seule page à la fois (verrou) ;
- on ne renvoie le HTML que si la vraie page série est là (titre h2[itemprop*="headline"]) ;
  sinon FetchError, pour ne jamais parser une page de challenge et écraser des données ;
- en cas d'échec, la page vue par le navigateur est sauvegardée dans data/logs/ (html + png).

Réglages (variables d'environnement) :
- PW_HEADLESS    : "true" (défaut) ou "false" (navigateur avec fenêtre ; dans Docker, via xvfb-run)
- PW_CHANNEL     : ex. "chrome" pour utiliser un Google Chrome installé au lieu du Chromium de Playwright
- PW_LOCALE      : défaut fr-FR        - PW_TIMEZONE : défaut Europe/Paris
- PW_BLOCK_MEDIA : "true" (défaut) bloque images/médias/polices pour économiser la bande passante
- DATA_DIR       : dossier de données (défaut : ../data par rapport à ce fichier)
"""
import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger("manhwa-tracker.playwright")

DATA_DIR = Path(os.environ.get("DATA_DIR") or Path(__file__).parent.parent / "data")
PROFILE_DIR = DATA_DIR / "browser-profile"
DEBUG_DIR = DATA_DIR / "logs"


def _flag(name: str, default: str) -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes")


HEADLESS = _flag("PW_HEADLESS", "true")
BLOCK_MEDIA = _flag("PW_BLOCK_MEDIA", "true")
CHANNEL = os.environ.get("PW_CHANNEL") or None
LOCALE = os.environ.get("PW_LOCALE", "fr-FR")
TIMEZONE = os.environ.get("PW_TIMEZONE", "Europe/Paris")
DEFAULT_TIMEOUT_MS = 60000
READY_SELECTOR = 'h2[itemprop*="headline"]'  # le même élément que parse_series_page utilise pour le titre

_lock = threading.Lock()


class FetchError(Exception):
    pass


def fetch_html(url: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> str:
    try:
        from playwright.sync_api import Error as PWError
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise FetchError("Playwright n'est pas installé (pip install playwright && playwright install chromium)") from e

    with _lock:
        try:
            return _fetch(url, timeout_ms, sync_playwright, PWError)
        except FetchError:
            raise
        except PWError as e:
            first_line = (str(e).splitlines() or [e.__class__.__name__])[0]
            hint = " (PW_HEADLESS=false demande un écran : lancer avec xvfb-run)" if "DISPLAY" in str(e) else ""
            raise FetchError(f"Erreur Playwright : {first_line}{hint}") from e


def _fetch(url: str, timeout_ms: int, sync_playwright, PWError) -> str:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_ms / 1000
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=HEADLESS,
            channel=CHANNEL,
            locale=LOCALE,
            timezone_id=TIMEZONE,
            viewport={"width": 1280, "height": 900},
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            if BLOCK_MEDIA:
                page.route(
                    "**/*",
                    lambda r: r.abort() if r.request.resource_type in ("image", "media", "font") else r.continue_(),
                )
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            except PWError as e:
                raise FetchError(f"Chargement impossible : {(str(e).splitlines() or [''])[0]}") from e
            first_status = resp.status if resp else None

            # Un éventuel challenge se résout tout seul en quelques secondes dans un vrai navigateur.
            while True:
                try:
                    if page.query_selector(READY_SELECTOR):
                        return page.content()
                except PWError:
                    pass  # navigation en cours (redirection du challenge) : on réessaie
                if time.monotonic() > deadline:
                    break
                page.wait_for_timeout(1000)

            try:
                title = page.title()
            except PWError:
                title = "?"
            _dump_debug(page)
            raise FetchError(
                f"Page série introuvable après {timeout_ms // 1000}s (HTTP {first_status}, titre « {title} »). "
                f"Probable challenge anti-bot non résolu : voir {DEBUG_DIR / 'fetch_debug.html'}"
            )
        finally:
            ctx.close()


def _dump_debug(page) -> None:
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        (DEBUG_DIR / "fetch_debug.html").write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(DEBUG_DIR / "fetch_debug.png"))
    except Exception as e:  # le diagnostic ne doit jamais masquer l'erreur d'origine
        logger.warning("Impossible de sauvegarder la page de diagnostic : %s", e)
