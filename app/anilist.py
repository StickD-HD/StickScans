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
import time
from datetime import datetime, timezone

import requests

from . import database

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
    entry = ((data.get("data", {}) or {}).get("Media", {}) or {}).get("mediaListEntry") or {}
    return {
        "status": entry.get("status"),
        "progress": entry.get("progress"),
        "score": entry.get("score"),
        "start_date": _from_fuzzy_date(entry.get("startedAt")),
        "end_date": _from_fuzzy_date(entry.get("completedAt")),
    }


def link_series(series_id: int, media_id: int, title: str):
    database.set_series_anilist_link(series_id, media_id, title)
    try:
        entry = fetch_entry(media_id)
        database.set_series_anilist_data(series_id, **entry)
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
    """Appelé automatiquement à chaque chapitre marqué lu : pousse seulement la progression,
    et ne fixe le statut sur CURRENT que si aucun statut n'est encore connu localement."""
    series = database.get_series_by_id(series_id)
    if not series or not series.get("anilist_id") or not _token():
        return
    progress = database.get_max_read_chapter_number(series_id)
    if progress is None:
        return
    status = "CURRENT" if not series.get("anilist_status") else None
    push_update(series_id, status=status, progress=progress)