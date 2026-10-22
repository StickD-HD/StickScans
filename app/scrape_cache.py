"""
Copie partagée des pages de séries entre plusieurs instances StickScans d'un même serveur.

Principe : l'instance « principale » enregistre chaque page qu'elle récupère sur le site ; une instance
« secondaire » réutilise cette copie (si elle est assez récente) au lieu de redemander la page au site.
Le partage est à SENS UNIQUE : l'instance secondaire ne peut que lire. Les séries qu'elle suit seule sont
récupérées normalement.

Réglages (variables d'environnement) :
- SCRAPE_CACHE_MODE            : "off" (défaut), "write" (principale), "read" (secondaire) ou "both" (les deux instances lisent ET écrivent).
- SCRAPE_CACHE_DIR             : dossier de la copie (le même pour les deux instances).
- SCRAPE_CACHE_MAX_AGE_MINUTES : âge maximal d'une copie réutilisable (défaut : 30).
"""
import gzip
import hashlib
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger("manhwa-tracker.cache")

# Activation automatique : si un dossier est monté sur /app/cache, le partage est actif (mode "both").
# Les variables SCRAPE_CACHE_* restent possibles pour un réglage manuel.
_default_dir = Path("/app/cache")
CACHE_DIR = Path(os.environ["SCRAPE_CACHE_DIR"]) if os.environ.get("SCRAPE_CACHE_DIR") else (_default_dir if _default_dir.is_dir() else None)
MODE = os.environ.get("SCRAPE_CACHE_MODE", "").strip().lower() or ("both" if CACHE_DIR else "off")
if MODE not in ("off", "read", "write", "both"):
    MODE = "off"
MAX_AGE_SECONDS = max(1, int(os.environ.get("SCRAPE_CACHE_MAX_AGE_MINUTES", "40") or 40)) * 60
ORPHAN_DAYS = 3  # une copie plus ancienne n'est plus utile (série supprimée, par exemple)


def is_active() -> bool:
    return MODE in ("read", "write", "both") and CACHE_DIR is not None


def _path_for(url: str) -> Path:
    name = hashlib.sha256(url.strip().encode()).hexdigest()[:32] + ".html.gz"
    return CACHE_DIR / name


def read(url: str) -> tuple[str, float] | None:
    """Renvoie (html, âge en secondes) si une copie assez récente existe, sinon None."""
    if MODE not in ("read", "both") or CACHE_DIR is None:
        return None
    try:
        path = _path_for(url)
        age = time.time() - path.stat().st_mtime
        if age > MAX_AGE_SECONDS or age < -60:  # trop vieille (ou horloge incohérente)
            return None
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return f.read(), max(0.0, age)
    except (OSError, EOFError, UnicodeError):
        return None  # absente, illisible ou en cours d'écriture : on ira sur le site


def write(url: str, html: str) -> None:
    if MODE not in ("write", "both") or CACHE_DIR is None:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _path_for(url)
        tmp = path.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as f:
            f.write(html)
        os.replace(tmp, path)  # remplacement atomique : l'autre instance ne lit jamais un fichier à moitié écrit
    except OSError as e:
        logger.warning("Copie de page non enregistrée : %s", e)


def purge_old() -> None:
    if MODE not in ("write", "both") or CACHE_DIR is None or not CACHE_DIR.exists():
        return
    limit = time.time() - ORPHAN_DAYS * 86400
    for path in CACHE_DIR.glob("*.html.gz"):
        try:
            if path.stat().st_mtime < limit:
                path.unlink()
        except OSError:
            pass
