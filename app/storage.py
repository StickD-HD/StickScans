"""
Informations sur l'espace utilisé par l'appli (base, sauvegardes, journaux, cache des pages) et nettoyages.
Tout se trouve dans le dossier data/ de l'instance, sauf le cache des pages qui peut être partagé entre instances.
"""
import shutil
import sqlite3
from pathlib import Path

from . import backup, database, scrape_cache


def _tree(path: Path) -> tuple[int, int]:
    """(nombre de fichiers, octets) d'un dossier, sous-dossiers compris."""
    files = size = 0
    if path.exists():
        for f in path.rglob("*"):
            try:
                if f.is_file():
                    files += 1
                    size += f.stat().st_size
            except OSError:
                pass
    return files, size


def _logs_dir() -> Path:
    return database.DB_PATH.parent / "logs"


def _db_bytes() -> int:
    """Taille de la base, fichiers WAL et SHM compris."""
    total = 0
    for suffix in ("", "-wal", "-shm"):
        p = database.DB_PATH.with_name(database.DB_PATH.name + suffix)
        if p.exists():
            total += p.stat().st_size
    return total


def get_storage_info() -> dict:
    data_dir = database.DB_PATH.parent
    data_files, data_bytes = _tree(data_dir)
    log_files, log_bytes = _tree(_logs_dir())
    backups = backup.list_backups()
    try:
        usage = shutil.disk_usage(data_dir)
        disk = {"total": usage.total, "used": usage.used, "free": usage.free}
    except OSError:
        disk = None
    return {
        "database": {"bytes": _db_bytes(), **database.get_storage_counts()},
        "backups": {"count": len(backups), "bytes": sum(b["size"] for b in backups)},
        "logs": {"files": log_files, "bytes": log_bytes},
        "page_cache": scrape_cache.stats(),
        "data": {"files": data_files, "bytes": data_bytes},
        "disk": disk,
    }


def clear_page_cache() -> dict:
    files, freed = scrape_cache.clear()
    return {"files": files, "bytes": freed}


def clear_logs() -> dict:
    """Vide les journaux de vérification. Le fichier en cours (scrape.log) est ouvert par l'appli : on le vide
    sur place plutôt que de le supprimer, sinon l'appli continuerait d'écrire dans un fichier disparu."""
    files = freed = 0
    logs = _logs_dir()
    if logs.exists():
        for f in logs.iterdir():
            if not f.is_file():
                continue
            size = f.stat().st_size
            if f.name == "scrape.log":
                with open(f, "w", encoding="utf-8"):
                    pass
            else:
                f.unlink()
            files += 1
            freed += size
    return {"files": files, "bytes": freed}


def optimize_database() -> dict:
    """Compacte la base (VACUUM) : récupère l'espace des données supprimées. Renvoie les tailles avant et après."""
    before = _db_bytes()
    conn = sqlite3.connect(database.DB_PATH, timeout=30, isolation_level=None)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("VACUUM")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()
    return {"before": before, "after": _db_bytes()}
