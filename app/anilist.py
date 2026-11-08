"""
Intégration AniList façon Mihon : recherche par titre + sélection de la bonne fiche,
puis lecture et modification en direct du statut, de la progression, de la note et des dates.
Envoi automatique de la progression à chaque chapitre marqué lu.
AniList ne fournit pas de jeton de rafraîchissement : le jeton dure 1 an puis doit être régénéré
(page Paramètres de l'appli).
"""
import base64
import json
import logging
import threading
import time
from datetime import datetime, timezone

import requests

from . import database
from .parse_series import safe_image_url

logger = logging.getLogger("manhwa-tracker.anilist")

API_URL = "https://graphql.anilist.co"

SEARCH_QUERY = """
query ($search: String) {
  Page(perPage: 8) {
    media(search: $search, type: MANGA, sort: SEARCH_MATCH) {
      id
      title { romaji english native }
      coverImage { medium }
      format
      startDate { year }
    }
  }
}
"""

VIEWER_QUERY = """
query {
  Viewer {
    id
    name
    avatar { medium }
    mediaListOptions { scoreFormat }
  }
}
"""

SCORE_FORMAT_QUERY = """
query {
  Viewer {
    mediaListOptions { scoreFormat }
  }
}
"""

ENTRY_QUERY = """
query ($id: Int, $scoreFormat: ScoreFormat) {
  Media(id: $id) {
    coverImage { large }
    mediaListEntry {
      status
      progress
      score(format: $scoreFormat)
      startedAt { year month day }
      completedAt { year month day }
    }
  }
}
"""

SAVE_ENTRY_MUTATION = """
mutation ($mediaId: Int, $progress: Int, $status: MediaListStatus, $score: Float,
          $startedAt: FuzzyDateInput, $completedAt: FuzzyDateInput) {
  SaveMediaListEntry(mediaId: $mediaId, progress: $progress, status: $status, score: $score,
                      startedAt: $startedAt, completedAt: $completedAt) {
    status
    progress
    score
    startedAt { year month day }
    completedAt { year month day }
  }
}
"""


def _token() -> str | None:
    return database.get_setting("anilist_token")


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    token = _token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


TOKEN_SETTING_KEYS = (
    "anilist_token",
    "anilist_user_name",
    "anilist_user_avatar",
    "anilist_score_format",
    "anilist_token_expires",
    "anilist_token_error",
)
INVALID_TOKEN_MESSAGE = "Jeton refusé par AniList (invalide ou expiré) : génère-en un nouveau."


def _clean_token(raw: str) -> str:
    """Accepte le jeton seul, ou l'URL complète contenant #access_token=..."""
    raw = (raw or "").strip().strip("\"'")
    if "access_token=" in raw:
        raw = raw.split("access_token=", 1)[1].split("&", 1)[0]
    return raw.strip()


def _token_expiry(token: str) -> int | None:
    """Les jetons AniList sont des JWT : la date d'expiration est dans le champ « exp »."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        exp = json.loads(base64.urlsafe_b64decode(payload)).get("exp")
        return int(exp) if exp else None
    except Exception:
        return None


def _fetch_viewer(token: str) -> dict:
    """Interroge AniList avec ce jeton. ValueError = jeton refusé, RuntimeError = réseau/réponse illisible."""
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    try:
        resp = requests.post(API_URL, json={"query": VIEWER_QUERY}, headers=headers, timeout=15)
    except requests.RequestException as e:
        raise RuntimeError(f"Impossible de joindre AniList : {e}") from e
    try:
        data = resp.json()
    except ValueError:
        raise RuntimeError(f"Réponse AniList illisible (HTTP {resp.status_code})")
    viewer = (data.get("data") or {}).get("Viewer")
    if not viewer:
        raise ValueError(INVALID_TOKEN_MESSAGE)
    return viewer


def _store_profile(viewer: dict):
    database.set_setting("anilist_user_name", viewer.get("name") or "")
    database.set_setting("anilist_user_avatar", (viewer.get("avatar") or {}).get("medium") or "")
    score_format = (viewer.get("mediaListOptions") or {}).get("scoreFormat")
    if score_format:
        database.set_setting("anilist_score_format", score_format)


def get_status() -> dict:
    """État du jeton, calculé localement (aucun appel réseau, sauf pour compléter un profil manquant)."""
    client_id = database.get_setting("anilist_client_id") or ""
    token = _token()
    if not token:
        return {"configured": False, "client_id": client_id}

    if not database.get_setting("anilist_user_name"):
        try:
            _store_profile(_fetch_viewer(token))
        except (ValueError, RuntimeError):
            pass

    exp_raw = database.get_setting("anilist_token_expires")
    exp = int(exp_raw) if exp_raw else _token_expiry(token)
    now = time.time()
    return {
        "configured": True,
        "client_id": client_id,
        "name": database.get_setting("anilist_user_name") or None,
        "avatar": database.get_setting("anilist_user_avatar") or None,
        "score_format": database.get_setting("anilist_score_format"),
        "expires_at": datetime.fromtimestamp(exp, tz=timezone.utc).strftime("%Y-%m-%d") if exp else None,
        "days_left": int((exp - now) // 86400) if exp else None,
        "expired": bool(exp and exp < now),
        "error": database.get_setting("anilist_token_error") or None,
    }


def save_token(raw_token: str) -> dict:
    token = _clean_token(raw_token)
    if not token:
        raise ValueError("Jeton vide")
    viewer = _fetch_viewer(token)  # valide le jeton avant de l'enregistrer
    exp = _token_expiry(token)
    database.set_setting("anilist_token", token)
    database.set_setting("anilist_token_expires", str(exp) if exp else "")
    database.delete_setting("anilist_token_error")
    _store_profile(viewer)
    return get_status()


def check_token() -> dict:
    token = _token()
    if token:
        try:
            _store_profile(_fetch_viewer(token))
            database.delete_setting("anilist_token_error")
        except ValueError as e:
            database.set_setting("anilist_token_error", str(e))
    return get_status()


def remove_token():
    for key in TOKEN_SETTING_KEYS:
        database.delete_setting(key)


def _to_fuzzy_date(date_str: str | None) -> dict | None:
    if not date_str:
        return {"year": None, "month": None, "day": None}
    y, m, d = date_str.split("-")
    return {"year": int(y), "month": int(m), "day": int(d)}


def _from_fuzzy_date(fuzzy: dict | None) -> str | None:
    if not fuzzy or not fuzzy.get("year"):
        return None
    y, m, d = fuzzy.get("year"), fuzzy.get("month") or 1, fuzzy.get("day") or 1
    return f"{y:04d}-{m:02d}-{d:02d}"


def get_score_format() -> str:
    cached = database.get_setting("anilist_score_format")
    if cached:
        return cached
    fmt = "POINT_10"
    try:
        resp = requests.post(API_URL, json={"query": SCORE_FORMAT_QUERY}, headers=_headers(), timeout=15)
        data = resp.json()
        fmt = data["data"]["Viewer"]["mediaListOptions"]["scoreFormat"]
        database.set_setting("anilist_score_format", fmt)
    except Exception as e:
        logger.error("Impossible de récupérer le format de note AniList : %s", e)
    return fmt


def search_media(query: str) -> list[dict]:
    resp = requests.post(
        API_URL, json={"query": SEARCH_QUERY, "variables": {"search": query}}, headers=_headers(), timeout=15
    )
    data = resp.json()
    results = []
    for m in data.get("data", {}).get("Page", {}).get("media", []) or []:
        t = m.get("title", {})
        title = t.get("english") or t.get("romaji") or t.get("native")
        results.append({
            "id": m["id"],
            "title": title,
            "cover_url": (m.get("coverImage") or {}).get("medium"),
            "format": m.get("format"),
            "year": (m.get("startDate") or {}).get("year"),
        })
    return results


def fetch_entry(media_id: int) -> dict:
    score_format = get_score_format()
    resp = requests.post(
        API_URL,
        json={"query": ENTRY_QUERY, "variables": {"id": media_id, "scoreFormat": score_format}},
        headers=_headers(),
        timeout=15,
    )
    data = resp.json()
    if resp.status_code != 200 or data.get("errors"):
        raise RuntimeError(str(data.get("errors", data)))
    media = (data.get("data") or {}).get("Media")
    if media is None:
        raise RuntimeError("Fiche AniList introuvable")
    entry = media.get("mediaListEntry") or {}
    return {
        "status": entry.get("status"),
        "progress": entry.get("progress"),
        "score": entry.get("score"),
        "start_date": _from_fuzzy_date(entry.get("startedAt")),
        "end_date": _from_fuzzy_date(entry.get("completedAt")),
        "cover_url": safe_image_url((media.get("coverImage") or {}).get("large")),
    }


def link_series(series_id: int, media_id: int, title: str):
    database.set_series_anilist_link(series_id, media_id, title)
    try:
        entry = fetch_entry(media_id)
        database.set_series_anilist_data(series_id, **entry)
        # Chapitres déjà lus dans l'appli : on les envoie tout de suite, mais seulement s'ils
        # sont en avance sur AniList (on ne fait jamais reculer une progression existante).
        local_progress = database.get_max_read_chapter_number(series_id)
        if local_progress and _token() and local_progress > (entry.get("progress") or 0):
            push_update(series_id, status=None if entry.get("status") else "CURRENT", progress=local_progress)
    except Exception as e:
        database.set_series_anilist_error(series_id, str(e))
        logger.error("Échec de récupération de la fiche AniList pour %s : %s", title, e)


def unlink_series(series_id: int):
    database.set_series_anilist_link(series_id, None, None)


def push_update(series_id: int, status=None, progress=None, score=None, start_date=None, end_date=None):
    """Pousse un changement vers AniList, puis resynchronise le miroir local avec la réponse complète."""
    series = database.get_series_by_id(series_id)
    if not series or not series.get("anilist_id"):
        return
    if not _token():
        database.set_series_anilist_error(series_id, "Aucun jeton AniList configuré (⚙ Paramètres)")
        return

    variables = {"mediaId": series["anilist_id"]}
    if status is not None:
        variables["status"] = status
    if progress is not None:
        variables["progress"] = progress
    if score is not None:
        variables["score"] = score
    if start_date is not None:
        variables["startedAt"] = _to_fuzzy_date(start_date)
    if end_date is not None:
        variables["completedAt"] = _to_fuzzy_date(end_date)

    try:
        resp = requests.post(
            API_URL, json={"query": SAVE_ENTRY_MUTATION, "variables": variables}, headers=_headers(), timeout=15
        )
        data = resp.json()
        if resp.status_code != 200 or "errors" in data:
            if resp.status_code == 401 or "Invalid token" in str(data):
                database.set_setting("anilist_token_error", INVALID_TOKEN_MESSAGE)
            raise RuntimeError(str(data.get("errors", data)))
        entry = data["data"]["SaveMediaListEntry"]
        database.set_series_anilist_data(
            series_id,
            status=entry.get("status"),
            progress=entry.get("progress"),
            score=entry.get("score"),
            start_date=_from_fuzzy_date(entry.get("startedAt")),
            end_date=_from_fuzzy_date(entry.get("completedAt")),
        )
        logger.info("AniList mis à jour pour %s", series["title"])
    except Exception as e:
        database.set_series_anilist_error(series_id, str(e))
        logger.error("Échec de la synchro AniList pour %s : %s", series["title"], e)


def push_progress(series_id: int):
    """Appelé automatiquement à chaque chapitre marqué lu : pousse la progression vers AniList, mais seulement
    si elle dépasse celle qu'AniList a RÉELLEMENT en ce moment (relue à chaque fois). Ainsi, lire ailleurs puis
    cocher un vieux chapitre ici ne fait jamais reculer AniList. Le statut passe à CURRENT seulement si aucun
    statut n'existe encore."""
    series = database.get_series_by_id(series_id)
    if not series or not series.get("anilist_id") or not _token():
        return
    progress = database.get_max_read_chapter_number(series_id)
    if progress is None:
        return
    try:
        remote = fetch_entry(series["anilist_id"])
    except Exception as e:
        database.set_series_anilist_error(series_id, f"Synchro AniList impossible : {e}")
        logger.error("Lecture de la progression AniList impossible pour %s : %s", series["title"], e)
        return
    database.set_series_anilist_data(series_id, **remote)  # l'appli reflète l'état réel d'AniList
    if progress <= (remote.get("progress") or 0):
        return
    push_update(series_id, status=None if remote.get("status") else "CURRENT", progress=progress)


# --- Synchro AniList -> StickScans (aucune écriture sur AniList) ---

COLLECTION_QUERY = """
query ($userName: String, $scoreFormat: ScoreFormat, $chunk: Int) {
  MediaListCollection(userName: $userName, type: MANGA, chunk: $chunk, perChunk: 500) {
    hasNextChunk
    lists {
      entries {
        mediaId
        media { coverImage { large } }
        status
        progress
        score(format: $scoreFormat)
        startedAt { year month day }
        completedAt { year month day }
      }
    }
  }
}
"""

SYNC_MIN_INTERVAL_SECONDS = 60
_sync_lock = threading.Lock()
_last_sync = 0.0


def _fetch_collection(user_name: str) -> dict[int, dict]:
    """Toute la liste de mangas de l'utilisateur en une ou quelques requêtes : {id AniList: entrée}."""
    score_format = get_score_format()
    entries: dict[int, dict] = {}
    chunk = 1
    while chunk <= 50:  # garde-fou : 50 x 500 entrées
        resp = requests.post(
            API_URL,
            json={"query": COLLECTION_QUERY,
                  "variables": {"userName": user_name, "scoreFormat": score_format, "chunk": chunk}},
            headers=_headers(),
            timeout=20,
        )
        if resp.status_code == 429:
            raise RuntimeError("Limite de requêtes AniList atteinte, nouvel essai plus tard")
        try:
            data = resp.json()
        except ValueError:
            raise RuntimeError(f"Réponse AniList illisible (HTTP {resp.status_code})")
        if resp.status_code == 401 or "Invalid token" in str(data.get("errors", "")):
            raise ValueError(INVALID_TOKEN_MESSAGE)
        if resp.status_code != 200 or data.get("errors"):
            raise RuntimeError(str(data.get("errors", data)))
        collection = (data.get("data") or {}).get("MediaListCollection")
        if collection is None:
            raise RuntimeError("Liste AniList introuvable")
        for lst in collection.get("lists") or []:
            for e in lst.get("entries") or []:
                entries[e["mediaId"]] = {
                    "status": e.get("status"),
                    "progress": e.get("progress"),
                    "score": e.get("score"),
                    "start_date": _from_fuzzy_date(e.get("startedAt")),
                    "end_date": _from_fuzzy_date(e.get("completedAt")),
                    "cover_url": safe_image_url(((e.get("media") or {}).get("coverImage") or {}).get("large")),
                }
        if not collection.get("hasNextChunk"):
            break
        chunk += 1
    return entries


def sync_all(force: bool = False) -> dict:
    """Recopie dans l'appli l'état AniList (statut, progression, note, dates) de toutes les séries liées, en
    une seule passe : ce qui est modifié ailleurs (site AniList, autre appli) apparaît dans StickScans.
    N'écrit JAMAIS sur AniList. Sans force, ignore les appels à moins d'une minute d'écart."""
    global _last_sync
    if not _token():
        return {"synced": False, "updated": 0, "reason": "no_token"}
    if not force and time.time() - _last_sync < SYNC_MIN_INTERVAL_SECONDS:
        return {"synced": False, "updated": 0, "reason": "recent"}
    if not _sync_lock.acquire(blocking=False):
        return {"synced": False, "updated": 0, "reason": "busy"}
    try:
        linked = [s for s in database.get_all_series() if s.get("anilist_id")]
        updated = 0
        if linked:
            user_name = database.get_setting("anilist_user_name")
            if not user_name:
                _store_profile(_fetch_viewer(_token()))
                user_name = database.get_setting("anilist_user_name")
            entries = _fetch_collection(user_name)
            for s in linked:
                entry = entries.get(s["anilist_id"], {})  # absent de la liste AniList : champs vidés
                # Série absente de la liste : on garde la couverture déjà connue plutôt que de l'effacer.
                cover = entry.get("cover_url") if entry else s.get("anilist_cover_url")
                new = (entry.get("status"), entry.get("progress"), entry.get("score"),
                       entry.get("start_date"), entry.get("end_date"), cover)
                old = (s.get("anilist_status"), s.get("anilist_progress"), s.get("anilist_score"),
                       s.get("anilist_start_date"), s.get("anilist_end_date"), s.get("anilist_cover_url"))
                if new != old:
                    database.set_series_anilist_data(
                        s["id"], status=new[0], progress=new[1], score=new[2], start_date=new[3], end_date=new[4],
                        cover_url=new[5],
                    )
                    updated += 1
                elif s.get("anilist_last_error"):
                    database.set_series_anilist_error(s["id"], None)
        _last_sync = time.time()
        database.delete_setting("anilist_token_error")
        if updated:
            logger.info("Synchro AniList : %d série(s) mise(s) à jour", updated)
        return {"synced": True, "updated": updated}
    except ValueError as e:  # jeton refusé
        database.set_setting("anilist_token_error", str(e))
        logger.error("Synchro AniList : %s", e)
        return {"synced": False, "updated": 0, "reason": "invalid_token", "error": str(e)}
    except Exception as e:
        logger.error("Synchro AniList impossible : %s", e)
        return {"synced": False, "updated": 0, "reason": "error", "error": str(e)}
    finally:
        _sync_lock.release()
