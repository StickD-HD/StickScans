"""
Sauvegarde quotidienne de la base SQLite. Garde les 7 dernieres copies.
"""
import sqlite3
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
    
    with sqlite3.connect(DB_PATH) as src, sqlite3.connect(dest) as dst:
        src.backup(dst)
        
    logger.info("Sauvegarde creee : %s", dest.name)

    backups = sorted(BACKUP_DIR.glob("manhwa_*.db"))
    for old in backups[:-KEEP_LAST]:
        old.unlink(missing_ok=True)
        logger.info("Ancienne sauvegarde supprimee : %s", old.name)