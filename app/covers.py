"""
Couvertures gardées sur le serveur, en petit format.

Chaque couverture (Scan-Manga ou AniList) est téléchargée une seule fois, réduite à la taille affichée (320 px de
large, WebP) et rangée dans data/covers/. L'appli l'affiche ensuite depuis le serveur : quelques Ko au lieu de
100 à 300, gardés par le navigateur, et plus de dépendance aux autres sites pour l'affichage.

Tant qu'une couverture n'est pas encore en cache, l'adresse d'origine reste utilisée : rien ne casse.

Prudence avec Scan-Manga (static.scan-manga.com) : au plus une image toutes les 20 s, rien pendant une pause du site
(garde du site), et arrêt pour 24 h au premier refus. Ce ne sont pas des pages : la garde du site ne les compte pas
dans son quota. Les images AniList partent à 1 s d'intervalle.
"""
import hashlib
import io
import logging
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import database, site_guard

logger = logging.getLogger("manhwa-tracker.covers")

WIDTH = 320
QUALITY = 78
MAX_BYTES = 8 * 1024 * 1024
NAME_RE = re.compile(r"^[0-9a-f]{20}\.webp$")
GAP_SECONDS = {"scan-manga.com": 20.0}
DEFAULT_GAP = 1.0
RETRY_FAILED_AFTER = 6 * 3600
HOST_PAUSE_AFTER_REFUSAL = 24 * 3600
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/142.0 Safari/537.36")

_lock = threading.Lock()
_failed: dict[str, float] = {}        # adresse -> moment de l'échec
_host_paused: dict[str, float] = {}   # domaine -> fin de la pause
_last_request: dict[str, float] = {}  # domaine -> dernière requête


def covers_dir() -> Path:
    return database.DB_PATH.parent / "covers"


def _name(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:20] + ".webp"


def local_url(url: str | None) -> str | None:
    """Adresse à afficher : la copie du serveur si elle existe, sinon l'adresse d'origine."""
    if not url or url.startswith("/"):
        return url
    name = _name(url)
    return f"/covers/{name}" if (covers_dir() / name).exists() else url


def path_for(name: str) -> Path | None:
    if not NAME_RE.match(name):
        return None
    path = covers_dir() / name
    return path if path.exists() else None


def _domain(url: str) -> str:
    host = urlparse(url).hostname or ""
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _wanted_urls() -> set[str]:
    """Couvertures affichées aujourd'hui : celle choisie pour chaque série (AniList ou Scan-Manga)."""
    with database.get_conn() as conn:
        rows = conn.execute(
            "SELECT CASE WHEN cover_locked = 0 AND anilist_cover_url IS NOT NULL THEN anilist_cover_url "
            "ELSE cover_url END AS u FROM series"
        ).fetchall()
    return {r["u"] for r in rows if r["u"] and r["u"].startswith("https://")}


def _download(url: str) -> bytes:
    domain = _domain(url)
    gap = GAP_SECONDS.get(domain, DEFAULT_GAP)
    wait = _last_request.get(domain, 0) + gap - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_request[domain] = time.time()
    resp = requests.get(url, timeout=(10, 30), headers={"User-Agent": USER_AGENT, "Accept": "image/*"}, stream=True)
    if resp.status_code in (403, 429):
        _host_paused[domain] = time.time() + HOST_PAUSE_AFTER_REFUSAL
        raise PermissionError(f"HTTP {resp.status_code}")
    resp.raise_for_status()
    data = resp.raw.read(MAX_BYTES + 1, decode_content=True)
    if len(data) > MAX_BYTES:
        raise ValueError("image trop lourde")
    return data


def _thumbnail(data: bytes) -> bytes:
    from PIL import Image
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        if img.width > WIDTH:
            img = img.resize((WIDTH, round(img.height * WIDTH / img.width)), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, "WEBP", quality=QUALITY, method=4)
        return out.getvalue()


def cache_missing(limit: int | None = None) -> int:
    """Met en cache les couvertures manquantes et retire celles qui ne servent plus. Renvoie le nombre ajouté."""
    if not _lock.acquire(blocking=False):
        return 0
    added = 0
    try:
        folder = covers_dir()
        folder.mkdir(parents=True, exist_ok=True)
        wanted = _wanted_urls()
        keep = {_name(u) for u in wanted}
        for f in folder.glob("*.webp"):
            if f.name not in keep:
                f.unlink(missing_ok=True)
        now = time.time()
        for url in sorted(wanted):
            if limit is not None and added >= limit:
                break
            target = folder / _name(url)
            if target.exists() or now - _failed.get(url, 0) < RETRY_FAILED_AFTER:
                continue
            domain = _domain(url)
            if _host_paused.get(domain, 0) > time.time():
                continue
            if domain == "scan-manga.com" and site_guard.status().get("blocked"):
                continue  # le site est en pause après un refus : on ne lui demande rien, même pas une image
            try:
                thumb = _thumbnail(_download(url))
                tmp = target.with_suffix(".tmp")
                tmp.write_bytes(thumb)
                tmp.replace(target)
                added += 1
            except Exception as e:  # noqa: BLE001 - une image ratée ne doit pas arrêter les autres
                _failed[url] = time.time()
                logger.info("Couverture non mise en cache (%s) : %s", url, e)
        if added:
            logger.info("%d couverture(s) mise(s) en cache", added)
        return added
    finally:
        _lock.release()


def cache_in_background():
    threading.Thread(target=cache_missing, name="couvertures", daemon=True).start()


def folder_size() -> tuple[int, int]:
    folder = covers_dir()
    if not folder.exists():
        return 0, 0
    files = list(folder.glob("*.webp"))
    return len(files), sum(f.stat().st_size for f in files)
