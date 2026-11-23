"""Base de données (export, import), stockage et sauvegardes automatiques."""
from datetime import datetime, timedelta, timezone
import os
import sqlite3
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from .. import auth
from .. import backup as backup_files
from .. import database, storage
from ..backup import replace_database
from ..scraper import maintenance
from .common import _backup_settings, _exclusive
from .models import BackupSettingsRequest

router = APIRouter()


@router.get("/api/database/download")
def download_database(tz_offset: int = 0):
    """Télécharge une copie cohérente de la base (même si l'appli écrit au même moment)."""
    if not database.DB_PATH.exists():
        raise HTTPException(404, "Base de données introuvable")
    
    tmp = tempfile.NamedTemporaryFile(prefix="stickscans-", suffix=".db", delete=False)
    tmp.close()
    
    source = sqlite3.connect(database.DB_PATH)
    target = sqlite3.connect(tmp.name)
    try:
        source.backup(target)
        # Point 7 : Nettoyage du jeton AniList pour l'export
        target.execute("DELETE FROM app_settings WHERE key = 'anilist_token'")
        target.commit()
    finally:
        target.close()
        source.close()
        
    local_now = datetime.now(timezone.utc) + timedelta(minutes=tz_offset)
    filename = f"stickscans-{local_now:%Y-%m-%d_%H-%M}.db"
    
    return FileResponse(
        tmp.name,
        media_type="application/octet-stream",
        filename=filename,
        background=BackgroundTask(os.remove, tmp.name),
    )


MAX_IMPORT_BYTES = 200 * 1024 * 1024


@router.post("/api/database/import")
def import_database(file: UploadFile = File(...)):
    if not (file.filename or "").endswith(".db"):
        raise HTTPException(400, "Le fichier doit être un .db")
    tmp_path = database.DB_PATH.with_suffix(".tmp")
    try:
        # 1. Réception du fichier dans un fichier temporaire (taille limitée)
        size = 0
        with open(tmp_path, "wb") as buffer:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_IMPORT_BYTES:
                    raise HTTPException(413, "Fichier trop volumineux")
                buffer.write(chunk)
        # 2. Contrôle d'intégrité, copie de sécurité de la base actuelle, puis remplacement ;
        # 3. mise à niveau du schéma si la base importée vient d'une version plus ancienne.
        # Aucune vérification ne peut démarrer pendant ce temps.
        with maintenance():
            safe = replace_database(tmp_path)
            database.init_db()
            auth.forget_generation_cache()
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    finally:
        tmp_path.unlink(missing_ok=True)

    return {"status": "ok", "backup": safe.name if safe else None}


@router.get("/api/storage")
def get_storage():
    return storage.get_storage_info()


@router.post("/api/storage/clear-page-cache")
def clear_page_cache():
    return storage.clear_page_cache()


@router.post("/api/storage/clear-logs")
def clear_logs():
    return storage.clear_logs()


@router.post("/api/storage/clear-check-history")
def clear_check_history():
    with _exclusive():
        return database.clear_check_history()


@router.post("/api/storage/optimize")
def optimize_storage():
    with _exclusive():
        return storage.optimize_database()


@router.get("/api/backups")
def list_backups():
    return {"settings": _backup_settings(), "backups": backup_files.list_backups()}


@router.put("/api/settings/backups")
def put_backup_settings(payload: BackupSettingsRequest):
    if payload.enabled is not None:
        database.set_setting("backup_enabled", "1" if payload.enabled else "0")
    if payload.keep is not None:
        database.set_setting("backup_keep", str(payload.keep))
    return _backup_settings()


@router.post("/api/backups")
def create_backup():
    backup_files.create_manual_backup()
    return {"settings": _backup_settings(), "backups": backup_files.list_backups()}


@router.get("/api/backups/{name}/download")
def download_backup(name: str):
    try:
        path = backup_files.backup_path(name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, "Sauvegarde introuvable")
    return FileResponse(path, filename=name, media_type="application/octet-stream")


@router.delete("/api/backups/{name}")
def delete_backup(name: str):
    try:
        backup_files.delete_backup(name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, "Sauvegarde introuvable")
    return {"settings": _backup_settings(), "backups": backup_files.list_backups()}


@router.post("/api/backups/{name}/restore")
def restore_backup(name: str):
    try:
        with _exclusive():
            safe = backup_files.restore_backup(name)
            database.init_db()  # met le schéma à niveau si la sauvegarde vient d'une version plus ancienne
            auth.forget_generation_cache()
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError:
        raise HTTPException(404, "Sauvegarde introuvable")
    return {"status": "ok", "backup": safe.name if safe else None}
