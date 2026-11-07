"""
Sauvegardes de la base SQLite :
- sauvegarde quotidienne (7 dernières copies conservées) ;
- copie de sécurité avant un import de base (5 dernières conservées) ;
- validation et remplacement de la base lors d'un import.
"""
import logging
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "manhwa.db"
BACKUP_DIR = Path(__file__).parent.parent / "data" / "backups"
KEEP_LAST = 7
KEEP_SAFETY = 5
REQUIRED_TABLES = {"series", "chapters"}

logger = logging.getLogger("manhwa-tracker.backup")


def _copy_to(dest: Path) -> None:
    """Copie cohérente de la base (API de sauvegarde SQLite), écrite dans un fichier temporaire puis
    renommée : un arrêt en cours de copie ne laisse jamais un fichier de sauvegarde à moitié écrit."""
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        with closing(sqlite3.connect(DB_PATH)) as src, closing(sqlite3.connect(tmp)) as dst:
            src.backup(dst)
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)


def run_backup(overwrite: bool = True):
    """Sauvegarde du jour. overwrite=False (au démarrage de l'appli) : si la copie du jour existe déjà,
    on la garde telle quelle, pour qu'un redémarrage ne remplace jamais une bonne copie par un état abîmé."""
    if not DB_PATH.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKUP_DIR / f"manhwa_{datetime.now():%Y-%m-%d}.db"
    if dest.exists() and not overwrite:
        logger.info("Sauvegarde du jour déjà présente, conservée : %s", dest.name)
        return

    _copy_to(dest)
    logger.info("Sauvegarde creee : %s", dest.name)

    backups = sorted(BACKUP_DIR.glob("manhwa_*.db"))
    for old in backups[:-KEEP_LAST]:
        old.unlink(missing_ok=True)
        logger.info("Ancienne sauvegarde supprimee : %s", old.name)


def safety_copy(label: str = "avant-import") -> Path | None:
    """Copie de la base actuelle sous un nom à part (jamais écrasée par la sauvegarde quotidienne)."""
    if not DB_PATH.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKUP_DIR / f"{label}_{datetime.now():%Y-%m-%d_%H%M%S}.db"
    _copy_to(dest)
    logger.info("Copie de sécurité créée : %s", dest.name)
    for old in sorted(BACKUP_DIR.glob(f"{label}_*.db"))[:-KEEP_SAFETY]:
        old.unlink(missing_ok=True)
    return dest


def validate_database(path: Path) -> None:
    """Lève ValueError (message affichable) si le fichier n'est pas une base StickScans saine."""
    try:
        with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as conn:
            if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Le fichier est endommagé (contrôle d'intégrité SQLite échoué).")
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    except sqlite3.DatabaseError as e:
        raise ValueError("Le fichier n'est pas une base SQLite lisible.") from e
    missing = REQUIRED_TABLES - tables
    if missing:
        raise ValueError(f"Ce n'est pas une base StickScans complète (tables manquantes : {', '.join(sorted(missing))}).")


def replace_database(new_file: Path) -> Path | None:
    """Valide new_file, garde une copie de sécurité de la base actuelle, puis la remplace.
    Renvoie le chemin de la copie de sécurité. En cas d'erreur de validation (ValueError), rien n'est modifié."""
    validate_database(new_file)
    safe = safety_copy()
    new_file.replace(DB_PATH)
    # Les fichiers WAL/SHM de l'ancienne base ne doivent pas être rejoués sur la nouvelle.
    for suffix in ("-wal", "-shm"):
        DB_PATH.with_name(DB_PATH.name + suffix).unlink(missing_ok=True)
    return safe
