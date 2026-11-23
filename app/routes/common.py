"""Outils partagés par les routes : verrou des opérations sur la base, réglages de sauvegarde, pagination."""
from contextlib import contextmanager
import logging
import os

from fastapi import HTTPException

from .. import database
from .. import scraper as scraper_module
from ..backup import run_backup
from ..scraper import maintenance

logger = logging.getLogger("manhwa-tracker")


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


# READING_MINUTES_PER_CHAPTER : durée estimée de lecture d'un chapitre (défaut 5 min), pour l'aperçu de lecture.
READING_MINUTES_PER_CHAPTER = max(1, int(os.environ.get("READING_MINUTES_PER_CHAPTER", "5") or 5))


# Nouveautés et historique se chargent par pages (« voir plus ») : limit = taille de la page, offset = déjà chargés.
def _page(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 1000), max(offset, 0)
