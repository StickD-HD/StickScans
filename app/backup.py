"""
Sauvegarde quotidienne de la base SQLite. Garde les 7 dernières copies.
"""
import shutil
import logging
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "manhwa.db"
BACKUP_DIR = Path(__file__).parent.parent / "data" / "backups"
KEEP_LAST = 7

logger = logging.getLogger("manhwa-tracker.backup")


def run_backup():
    if not DB_PATH.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKUP_DIR / f"manhwa_{datetime.now():%Y-%m-%d}.db"
    shutil.copy2(DB_PATH, dest)
    logger.info("Sauvegarde créée : %s", dest.name)

    backups = sorted(BACKUP_DIR.glob("manhwa_*.db"))
    for old in backups[:-KEEP_LAST]:
        old.unlink(missing_ok=True)
        logger.info("Ancienne sauvegarde supprimée : %s", old.name)
