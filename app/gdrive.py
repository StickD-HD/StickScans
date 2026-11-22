"""
Sauvegarde de la base sur Google Drive.

- Connexion par le « flux appareil » de Google : l'appli affiche un code, on le saisit sur google.com/device depuis
  n'importe quel appareil. Pas d'adresse de retour à déclarer, quel que soit le domaine de l'appli.
- Accès limité au strict nécessaire (portée drive.file) : l'appli ne voit et ne modifie QUE les fichiers qu'elle a
  créés elle-même (un dossier « StickScans » et les copies dedans), jamais le reste du Drive.
- Une copie est envoyée chaque nuit après la sauvegarde locale (au plus une fois toutes les 20 h), ou à la demande.
  Seules les N dernières copies sont gardées sur le Drive.
- Les copies envoyées ne contiennent aucun secret : jeton AniList et accès Google en sont retirés.

Réglages (table app_settings) : gdrive_client_id, gdrive_client_secret, gdrive_refresh_token, gdrive_folder_id,
gdrive_email, gdrive_keep, gdrive_last_upload, gdrive_last_error.
"""
import logging
import re
import sqlite3
import tempfile
import threading
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from . import database

logger = logging.getLogger("manhwa-tracker.gdrive")

SCOPE = "https://www.googleapis.com/auth/drive.file"
DEVICE_URL = "https://oauth2.googleapis.com/device/code"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API = "https://www.googleapis.com/drive/v3"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files"
FOLDER_NAME = "StickScans"
FOLDER_MIME = "application/vnd.google-apps.folder"
FILE_RE = re.compile(r"^stickscans_\d{4}-\d{2}-\d{2}_\d{4}\.db$")
DEFAULT_KEEP = 7
UPLOAD_EVERY = timedelta(hours=20)
TIMEOUT = 30

# Réglages jamais envoyés sur le Drive, et conservés tels quels lors d'une restauration depuis le Drive.
SECRET_KEYS = ("anilist_token", "gdrive_client_id", "gdrive_client_secret", "gdrive_refresh_token",
               "gdrive_folder_id", "gdrive_email", "gdrive_keep", "gdrive_last_upload", "gdrive_last_error")
STRIPPED_KEYS = ("anilist_token", "gdrive_client_secret", "gdrive_refresh_token")


class DriveError(Exception):
    """Erreur affichable telle quelle."""


_lock = threading.Lock()
_pending: dict | None = None        # connexion en cours (flux appareil)
_access: dict = {"token": None, "expires": 0.0}


def _get(key):
    return database.get_setting(key)


def get_keep() -> int:
    try:
        return min(30, max(1, int(_get("gdrive_keep") or DEFAULT_KEEP)))
    except ValueError:
        return DEFAULT_KEEP


def set_keep(keep: int):
    database.set_setting("gdrive_keep", str(min(30, max(1, int(keep)))))


def is_configured() -> bool:
    return bool(_get("gdrive_client_id") and _get("gdrive_client_secret"))


def is_connected() -> bool:
    return bool(is_configured() and _get("gdrive_refresh_token"))


def get_status() -> dict:
    pending = None
    if _pending and _pending["expires_at"] > time.time():
        pending = {"user_code": _pending["user_code"], "verification_url": _pending["verification_url"],
                   "interval": _pending["interval"]}
    client_id = _get("gdrive_client_id") or ""
    return {
        "configured": is_configured(),
        "client_id_hint": (client_id[:12] + "…") if client_id else "",
        "connected": is_connected(),
        "email": _get("gdrive_email"),
        "keep": get_keep(),
        "last_upload": _get("gdrive_last_upload"),
        "last_error": _get("gdrive_last_error"),
        "pending": pending,
    }


def save_client(client_id: str, client_secret: str):
    client_id, client_secret = client_id.strip(), client_secret.strip()
    if not client_id.endswith(".apps.googleusercontent.com"):
        raise DriveError("L'ID client doit se terminer par .apps.googleusercontent.com")
    if not client_secret:
        raise DriveError("Le code secret du client est vide")
    if client_id != _get("gdrive_client_id"):
        # Autre identifiant : l'ancienne connexion ne vaut plus rien.
        _forget_connection()
    database.set_setting("gdrive_client_id", client_id)
    database.set_setting("gdrive_client_secret", client_secret)


def _forget_connection():
    global _pending
    _pending = None
    _access.update(token=None, expires=0.0)
    for key in ("gdrive_refresh_token", "gdrive_folder_id", "gdrive_email", "gdrive_last_error"):
        database.delete_setting(key)


def _post(url, data) -> dict:
    try:
        r = requests.post(url, data=data, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise DriveError(f"Google injoignable ({e.__class__.__name__})") from e
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.status_code >= 400:
        body.setdefault("error", f"http_{r.status_code}")
    return body


# --- Connexion (flux appareil) ---

def start_connect() -> dict:
    global _pending
    if not is_configured():
        raise DriveError("Renseigne d'abord l'ID client et le code secret Google")
    body = _post(DEVICE_URL, {"client_id": _get("gdrive_client_id"), "scope": SCOPE})
    if "device_code" not in body:
        raise DriveError(_explain(body.get("error"), body.get("error_description")))
    _pending = {
        "device_code": body["device_code"],
        "user_code": body["user_code"],
        "verification_url": body.get("verification_url") or body.get("verification_uri") or "https://www.google.com/device",
        "interval": int(body.get("interval", 5)),
        "expires_at": time.time() + int(body.get("expires_in", 1800)),
    }
    return get_status()


def poll_connect() -> dict:
    """Un essai : « pending » tant que le code n'a pas été saisi, puis « connected », « denied » ou « expired »."""
    global _pending
    if not _pending or _pending["expires_at"] <= time.time():
        _pending = None
        return {"state": "expired", **get_status()}
    body = _post(TOKEN_URL, {
        "client_id": _get("gdrive_client_id"), "client_secret": _get("gdrive_client_secret"),
        "device_code": _pending["device_code"], "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    })
    error = body.get("error")
    if error in ("authorization_pending", "slow_down"):
        if error == "slow_down":
            _pending["interval"] += 5
        return {"state": "pending", **get_status()}
    _pending = None
    if error == "access_denied":
        return {"state": "denied", **get_status()}
    if error == "expired_token":
        return {"state": "expired", **get_status()}
    if error or "refresh_token" not in body:
        raise DriveError(_explain(error, body.get("error_description")))
    database.set_setting("gdrive_refresh_token", body["refresh_token"])
    database.delete_setting("gdrive_last_error")
    _access.update(token=body.get("access_token"), expires=time.time() + int(body.get("expires_in", 3600)) - 60)
    try:
        about = _api("GET", f"{API}/about", params={"fields": "user(emailAddress)"})
        email = (about.get("user") or {}).get("emailAddress")
        if email:
            database.set_setting("gdrive_email", email)
    except DriveError:
        pass  # l'adresse n'est qu'indicative
    return {"state": "connected", **get_status()}


def disconnect():
    token = _get("gdrive_refresh_token")
    if token:
        try:
            requests.post(REVOKE_URL, params={"token": token}, timeout=10)
        except requests.RequestException:
            pass  # révocation au mieux : l'accès est oublié ici de toute façon
    _forget_connection()


def _explain(error, description=None) -> str:
    known = {
        "invalid_client": "ID client ou code secret Google refusé : vérifie-les (client de type « TV et appareils à "
                          "entrée limitée »)",
        "unauthorized_client": "Ce client Google n'accepte pas cette connexion : crée un client de type « TV et "
                               "appareils à entrée limitée »",
        "invalid_grant": "L'accès au Drive a été retiré ou a expiré : reconnecte Google Drive",
        "invalid_scope": "Google refuse l'accès demandé (Drive) pour ce client",
        "access_denied": "Accès refusé sur la page Google",
    }
    return known.get(error) or (description or f"Erreur Google ({error or 'inconnue'})")


# --- Appels à l'API Drive ---

def _access_token() -> str:
    if _access["token"] and _access["expires"] > time.time():
        return _access["token"]
    if not is_connected():
        raise DriveError("Google Drive n'est pas connecté")
    body = _post(TOKEN_URL, {
        "client_id": _get("gdrive_client_id"), "client_secret": _get("gdrive_client_secret"),
        "refresh_token": _get("gdrive_refresh_token"), "grant_type": "refresh_token",
    })
    if "access_token" not in body:
        if body.get("error") == "invalid_grant":
            database.delete_setting("gdrive_refresh_token")
        raise DriveError(_explain(body.get("error"), body.get("error_description")))
    _access.update(token=body["access_token"], expires=time.time() + int(body.get("expires_in", 3600)) - 60)
    return _access["token"]


def _api(method, url, *, raw=False, **kwargs):
    headers = {"Authorization": f"Bearer {_access_token()}", **kwargs.pop("headers", {})}
    try:
        r = requests.request(method, url, headers=headers, timeout=kwargs.pop("timeout", TIMEOUT), **kwargs)
    except requests.RequestException as e:
        raise DriveError(f"Google Drive injoignable ({e.__class__.__name__})") from e
    if r.status_code == 401:
        _access.update(token=None, expires=0.0)
    if r.status_code == 404:
        raise FileNotFoundError(url)
    if r.status_code >= 400:
        try:
            message = r.json().get("error", {}).get("message")
        except ValueError:
            message = None
        raise DriveError(f"Google Drive a refusé la demande ({r.status_code}{' : ' + message if message else ''})")
    if raw:
        return r
    return r.json() if r.content else {}


def _folder_id() -> str:
    folder = _get("gdrive_folder_id")
    if folder:
        try:
            meta = _api("GET", f"{API}/files/{folder}", params={"fields": "id,trashed"})
            if not meta.get("trashed"):
                return folder
        except FileNotFoundError:
            pass
    # Dossier jamais créé, supprimé ou mis à la corbeille : on en crée un nouveau.
    created = _api("POST", f"{API}/files", params={"fields": "id"},
                   json={"name": FOLDER_NAME, "mimeType": FOLDER_MIME})
    database.set_setting("gdrive_folder_id", created["id"])
    return created["id"]


def list_files() -> list[dict]:
    folder = _get("gdrive_folder_id")
    if not folder or not is_connected():
        return []
    try:
        data = _api("GET", f"{API}/files", params={
            "q": f"'{folder}' in parents and trashed = false",
            "orderBy": "createdTime desc", "pageSize": 100,
            "fields": "files(id,name,size,createdTime)",
        })
    except FileNotFoundError:
        return []
    return [
        {"id": f["id"], "name": f["name"], "size": int(f.get("size") or 0), "created": f.get("createdTime")}
        for f in data.get("files", []) if FILE_RE.match(f.get("name", ""))
    ]


def _clean_copy(dest: Path):
    """Copie cohérente de la base, sans aucun secret."""
    with closing(sqlite3.connect(database.DB_PATH)) as src, closing(sqlite3.connect(dest)) as dst:
        src.backup(dst)
        dst.execute(f"DELETE FROM app_settings WHERE key IN ({','.join('?' * len(STRIPPED_KEYS))})", STRIPPED_KEYS)
        dst.commit()
        dst.execute("VACUUM")


def upload_now() -> dict:
    """Envoie une copie de la base sur le Drive, puis ne garde que les N dernières."""
    if not _lock.acquire(blocking=False):
        raise DriveError("Un envoi vers Google Drive est déjà en cours")
    try:
        folder = _folder_id()
        with tempfile.TemporaryDirectory(prefix="stickscans-drive-") as tmpdir:
            path = Path(tmpdir) / "copie.db"
            _clean_copy(path)
            data = path.read_bytes()
        name = f"stickscans_{datetime.now():%Y-%m-%d_%H%M}.db"
        start = _api("POST", UPLOAD_API, raw=True, params={"uploadType": "resumable", "fields": "id"},
                     headers={"X-Upload-Content-Type": "application/octet-stream",
                              "X-Upload-Content-Length": str(len(data))},
                     json={"name": name, "parents": [folder]})
        location = start.headers.get("Location")
        if not location:
            raise DriveError("Google Drive n'a pas accepté l'envoi")
        _api("PUT", location, data=data, headers={"Content-Type": "application/octet-stream"}, timeout=300)
        for old in list_files()[get_keep():]:
            try:
                _api("DELETE", f"{API}/files/{old['id']}", raw=True)
            except (FileNotFoundError, DriveError) as e:
                logger.warning("Ancienne copie Drive non supprimée (%s) : %s", old["name"], e)
        database.set_setting("gdrive_last_upload", datetime.now(timezone.utc).isoformat(timespec="seconds"))
        database.delete_setting("gdrive_last_error")
        logger.info("Copie envoyée sur Google Drive : %s (%d octets)", name, len(data))
        return {"name": name, "size": len(data)}
    except (DriveError, FileNotFoundError) as e:
        message = str(e) if isinstance(e, DriveError) else "Dossier Google Drive introuvable"
        database.set_setting("gdrive_last_error", message)
        logger.warning("Envoi vers Google Drive impossible : %s", message)
        raise DriveError(message) from e
    finally:
        _lock.release()


def upload_if_due():
    """Appelé après la sauvegarde quotidienne : au plus un envoi toutes les 20 h. N'échoue jamais."""
    if not is_connected():
        return
    last = _get("gdrive_last_upload")
    try:
        if last and datetime.now(timezone.utc) - datetime.fromisoformat(last) < UPLOAD_EVERY:
            return
    except ValueError:
        pass
    try:
        upload_now()
    except Exception:  # noqa: BLE001 - déjà journalisé ; une tâche planifiée ne doit pas planter
        logger.exception("Envoi automatique vers Google Drive en échec")


def download(file_id: str, dest: Path):
    if file_id not in {f["id"] for f in list_files()}:
        raise FileNotFoundError(file_id)
    r = _api("GET", f"{API}/files/{file_id}", raw=True, params={"alt": "media"}, timeout=300)
    dest.write_bytes(r.content)


def preserved_settings() -> dict:
    """Réglages à remettre après une restauration depuis le Drive (les copies n'en contiennent pas les secrets)."""
    return {key: database.get_setting(key) for key in SECRET_KEYS}


def restore_settings(values: dict):
    for key, value in values.items():
        if value is None:
            database.delete_setting(key)
        else:
            database.set_setting(key, value)
