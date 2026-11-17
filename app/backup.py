"""
Sauvegardes de la base SQLite :
- sauvegarde quotidienne (nombre de copies conservées réglable, 7 par défaut) ;
- sauvegarde manuelle à la demande (10 dernières conservées) ;
- copie de sécurité avant un import ou une restauration (5 dernières de chaque sorte conservées) ;
- liste, téléchargement, restauration et suppression des sauvegardes ;
- validation et remplacement de la base lors d'un import ou d'une restauration.
"""
import logging
import os
import re
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "manhwa.db"
BACKUP_DIR = Path(__file__).parent.parent / "data" / "backups"
KEEP_LAST = 7
KEEP_MANUAL = 10
KEEP_SAFETY = 5
REQUIRED_TABLES = {"series", "chapters"}

# Seuls ces noms de fichiers sont des sauvegardes de l'appli : toute autre demande est refusée
# (pas de chemin, pas de « .. »), ce qui protège les routes de téléchargement, de restauration et de suppression.
KINDS = {
    "manhwa": "Quotidienne",
    "manuelle": "Manuelle",
    "avant-import": "Avant un import",
    "avant-restauration": "Avant une restauration",
}
NAME_RE = re.compile(r"^(manhwa|manuelle|avant-import|avant-restauration)_\d{4}-\d{2}-\d{2}(_\d{6})?\.db$")

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


def run_backup(overwrite: bool = True, keep: int | None = None):
    """Sauvegarde du jour, en gardant les `keep` dernières (7 par défaut).
    overwrite=False (au démarrage de l'appli) : si la copie du jour existe déjà, on la garde telle quelle, pour
    qu'un redémarrage ne remplace jamais une bonne copie par un état abîmé."""
    if not DB_PATH.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKUP_DIR / f"manhwa_{datetime.now():%Y-%m-%d}.db"
    if dest.exists() and not overwrite:
        logger.info("Sauvegarde du jour déjà présente, conservée : %s", dest.name)
        return

    _copy_to(dest)
    logger.info("Sauvegarde creee : %s", dest.name)

    keep = KEEP_LAST if keep is None else max(1, int(keep))
    backups = sorted(BACKUP_DIR.glob("manhwa_*.db"))
    for old in backups[:-keep]:
        old.unlink(missing_ok=True)
        logger.info("Ancienne sauvegarde supprimee : %s", old.name)


def create_manual_backup() -> Path:
    """Sauvegarde à la demande, sous un nom à part (jamais écrasée par la sauvegarde quotidienne)."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKUP_DIR / f"manuelle_{datetime.now():%Y-%m-%d_%H%M%S}.db"
    _copy_to(dest)
    logger.info("Sauvegarde manuelle créée : %s", dest.name)
    for old in sorted(BACKUP_DIR.glob("manuelle_*.db"))[:-KEEP_MANUAL]:
        old.unlink(missing_ok=True)
    return dest


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


def list_backups() -> list[dict]:
    """Toutes les sauvegardes de l'appli, de la plus récente à la plus ancienne."""
    if not BACKUP_DIR.exists():
        return []
    found = []
    for f in BACKUP_DIR.glob("*.db"):
        m = NAME_RE.match(f.name)
        if not m or not f.is_file():
            continue
        st = f.stat()
        found.append({
            "name": f.name,
            "kind": m.group(1),
            "label": KINDS[m.group(1)],
            "size": st.st_size,
            "modified": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
        })
    return sorted(found, key=lambda b: (b["modified"], b["name"]), reverse=True)


def backup_path(name: str) -> Path:
    """Chemin d'une sauvegarde existante. ValueError : nom invalide ; FileNotFoundError : introuvable."""
    if not NAME_RE.match(name or ""):
        raise ValueError("Nom de sauvegarde invalide.")
    path = BACKUP_DIR / name
    if not path.is_file():
        raise FileNotFoundError(name)
    return path


def delete_backup(name: str) -> None:
    backup_path(name).unlink()
    logger.info("Sauvegarde supprimée : %s", name)


def restore_backup(name: str) -> Path | None:
    """Remplace la base actuelle par une sauvegarde, après une copie de sécurité de la base actuelle.
    La sauvegarde est contrôlée avant : si elle est abîmée (ValueError), rien n'est modifié."""
    source = backup_path(name)
    tmp = DB_PATH.with_name(DB_PATH.name + ".restore.tmp")
    try:
        shutil.copyfile(source, tmp)
        return replace_database(tmp, label="avant-restauration")
    finally:
        tmp.unlink(missing_ok=True)


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


def replace_database(new_file: Path, label: str = "avant-import") -> Path | None:
    """Valide new_file, garde une copie de sécurité de la base actuelle (sous le nom `label`), puis la remplace.
    Renvoie le chemin de la copie de sécurité. En cas d'erreur de validation (ValueError), rien n'est modifié."""
    validate_database(new_file)
    safe = safety_copy(label)
    new_file.replace(DB_PATH)
    # Les fichiers WAL/SHM de l'ancienne base ne doivent pas être rejoués sur la nouvelle.
    for suffix in ("-wal", "-shm"):
        DB_PATH.with_name(DB_PATH.name + suffix).unlink(missing_ok=True)
    return safe
