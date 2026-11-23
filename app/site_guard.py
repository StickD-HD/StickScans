"""
Garde du site : décide QUAND une requête vers scan-manga.com a le droit de partir.

L'état est partagé par toutes les instances du serveur : fichier site_state.json dans le dossier du cache des pages
(SCRAPE_CACHE_DIR), sinon dans data/. Un verrou de fichier évite que deux instances le modifient en même temps.

- Écart entre deux requêtes, toutes instances confondues : tiré au hasard entre FETCH_MIN_GAP_SECONDS et
  FETCH_MAX_GAP_SECONDS (défaut 45 à 90 s, jamais moins de 20 s).
- Plafond de requêtes par jour (UTC), toutes instances confondues : FETCH_DAILY_LIMIT (défaut 300).
- Après un refus du site (403, 429, page de protection) : pause de 2 h, puis 6 h, 24 h et 72 h aux refus suivants
  (ou la durée demandée par le site si elle est plus longue). Le compteur de refus ne repart à zéro qu'après une
  requête réussie au moins 48 h après le dernier refus. La pause survit aux redémarrages.

Ce module ne fait aucune requête : fetcher.py lui demande la permission avant chaque requête et lui rapporte le résultat.
"""
import fcntl
import json
import os
import random
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

MIN_GAP_FLOOR_SECONDS = 20.0
MIN_GAP_SECONDS = max(MIN_GAP_FLOOR_SECONDS, float(os.environ.get("FETCH_MIN_GAP_SECONDS", "45") or 45))
MAX_GAP_SECONDS = max(MIN_GAP_SECONDS, float(os.environ.get("FETCH_MAX_GAP_SECONDS", "90") or 90))
DAILY_LIMIT = max(1, int(os.environ.get("FETCH_DAILY_LIMIT", "300") or 300))
BACKOFF_HOURS = (2, 6, 24, 72)
STRIKE_RESET_SECONDS = 48 * 3600
MAX_RETRY_AFTER_SECONDS = 7 * 86400

HISTORY_DAYS = 14   # requêtes par jour gardées pour l'écran Vérifications
BLOCKS_KEPT = 20    # derniers refus du site gardés

STATE_FILE = "site_state.json"
_thread_lock = threading.Lock()


def state_dir() -> Path:
    """Dossier partagé entre instances s'il existe (celui du cache des pages), sinon le dossier data/ de l'instance."""
    from . import database, scrape_cache
    return scrape_cache.CACHE_DIR if scrape_cache.CACHE_DIR is not None else database.DB_PATH.parent


@contextmanager
def _state():
    """Lit l'état sous verrou (threads de l'instance + autres instances), puis l'enregistre en fin de bloc."""
    folder = state_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / STATE_FILE
    # Verrou ouvert en LECTURE seule : ça suffit pour flock, et ça marche même si le fichier a été créé par un autre
    # utilisateur (un outil lancé en root, par exemple) ; l'ouvrir en écriture échouerait pour le service.
    with _thread_lock:
        lock_fd = os.open(folder / (STATE_FILE + ".lock"), os.O_RDONLY | os.O_CREAT, 0o644)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(state, dict):
                    state = {}
            except (OSError, ValueError):
                state = {}
            yield state
            # Fichier temporaire propre à cet appel, lisible par tous, puis remplacement atomique : un autre
            # utilisateur peut toujours relire l'état, et un fichier temporaire abandonné ne bloque personne.
            fd, tmp = tempfile.mkstemp(prefix=STATE_FILE + ".", suffix=".tmp", dir=folder)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(json.dumps(state))
                os.chmod(tmp, 0o644)
                os.replace(tmp, path)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
        finally:
            os.close(lock_fd)  # libère aussi le verrou


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def _seconds_to_next_day(ts: float) -> float:
    return 86400 - (ts % 86400)


# Demande faite par toi (ajout d'une série, « Actualiser », nouvelle adresse) : elle passe devant les vérifications
# automatiques, avec seulement 20 s minimum depuis la requête précédente (rythme d'une personne qui navigue) ; les
# vérifications automatiques reprennent ensuite après un écart normal (45 à 90 s). Pause et plafond quotidien inchangés.
INTERACTIVE_MIN_GAP_SECONDS = max(MIN_GAP_FLOOR_SECONDS, float(os.environ.get("FETCH_INTERACTIVE_GAP_SECONDS", "20") or 20))


def reserve(now: float | None = None, interactive: bool = False) -> tuple[str, float]:
    """Demande le droit d'envoyer UNE requête maintenant. Renvoie (réponse, secondes) :
    - ("ok", 0)        : autorisé, la requête est comptée ;
    - ("wait", s)      : une autre requête vient de partir, réessayer dans s secondes ;
    - ("blocked", s)   : site en pause après un refus, encore s secondes ;
    - ("quota", s)     : plafond quotidien atteint, reprise dans s secondes."""
    now = time.time() if now is None else now
    with _state() as st:
        blocked_until = float(st.get("blocked_until") or 0)
        if blocked_until > now:
            return "blocked", blocked_until - now
        today = _day(now)
        if st.get("day") != today:
            st["day"] = today
            st["requests_today"] = 0
        if int(st.get("requests_today") or 0) >= DAILY_LIMIT:
            return "quota", _seconds_to_next_day(now)
        next_slot = float(st.get("next_slot") or 0)
        if interactive:
            ready_at = float(st.get("last_request_at") or 0) + INTERACTIVE_MIN_GAP_SECONDS
            if ready_at > now:
                return "wait", ready_at - now
            st["next_slot"] = max(next_slot, now + random.uniform(MIN_GAP_SECONDS, MAX_GAP_SECONDS))
        elif next_slot > now:
            return "wait", next_slot - now
        else:
            st["next_slot"] = now + random.uniform(MIN_GAP_SECONDS, MAX_GAP_SECONDS)
        st["requests_today"] = int(st.get("requests_today") or 0) + 1
        st["last_request_at"] = now
        per_day = st.get("per_day") if isinstance(st.get("per_day"), dict) else {}
        per_day[today] = int(per_day.get(today) or 0) + 1
        st["per_day"] = {d: per_day[d] for d in sorted(per_day)[-HISTORY_DAYS:]}
        return "ok", 0.0


def record_block(reason: str, retry_after: float | None = None, now: float | None = None) -> float:
    """Le site a refusé : met tout le monde en pause. Renvoie la durée de la pause en secondes."""
    now = time.time() if now is None else now
    with _state() as st:
        strikes = int(st.get("strikes") or 0) + 1
        duration = BACKOFF_HOURS[min(strikes, len(BACKOFF_HOURS)) - 1] * 3600.0
        if retry_after:
            duration = max(duration, min(float(retry_after), MAX_RETRY_AFTER_SECONDS))
        st.update(blocked_until=now + duration, strikes=strikes, last_block_at=now, last_block_reason=reason)
        blocks = st.get("blocks") if isinstance(st.get("blocks"), list) else []
        blocks.append({"at": now, "reason": reason, "seconds": duration, "strike": strikes})
        st["blocks"] = blocks[-BLOCKS_KEPT:]
        return duration


def record_success(now: float | None = None) -> None:
    now = time.time() if now is None else now
    with _state() as st:
        st["last_success_at"] = now
        if st.get("strikes") and now - float(st.get("last_block_at") or 0) > STRIKE_RESET_SECONDS:
            st["strikes"] = 0


def clear_block() -> None:
    """Lève la pause à la main (par exemple après un déblocage par le site). Le compteur de refus est gardé :
    un nouveau refus entraînerait une pause plus longue."""
    with _state() as st:
        st["blocked_until"] = 0


def _iso(ts) -> str | None:
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat(timespec="seconds") if ts else None


def status(now: float | None = None) -> dict:
    now = time.time() if now is None else now
    with _state() as st:
        blocked_until = float(st.get("blocked_until") or 0)
        blocked = blocked_until > now
        requests_today = int(st.get("requests_today") or 0) if st.get("day") == _day(now) else 0
        return {
            "blocked": blocked,
            "blocked_until": _iso(blocked_until) if blocked else None,
            "remaining_seconds": round(blocked_until - now) if blocked else 0,
            "strikes": int(st.get("strikes") or 0),
            "last_block_at": _iso(st.get("last_block_at")),
            "last_block_reason": st.get("last_block_reason"),
            "last_success_at": _iso(st.get("last_success_at")),
            "requests_today": requests_today,
            "daily_limit": DAILY_LIMIT,
            "quota_reached": requests_today >= DAILY_LIMIT,
            "min_gap_seconds": MIN_GAP_SECONDS,
            "max_gap_seconds": MAX_GAP_SECONDS,
            "shared": str(state_dir()) != str(_data_dir()),
        }


def history(days: int = 7, now: float | None = None) -> dict:
    """Requêtes vers le site jour par jour (UTC, toutes instances confondues) et derniers refus du site."""
    now = time.time() if now is None else now
    with _state() as st:
        per_day = st.get("per_day") if isinstance(st.get("per_day"), dict) else {}
        blocks = st.get("blocks") if isinstance(st.get("blocks"), list) else []
    dates = [_day(now - 86400 * i) for i in range(days - 1, -1, -1)]
    return {
        "per_day": [{"date": d, "count": int(per_day.get(d) or 0)} for d in dates],
        "daily_limit": DAILY_LIMIT,
        "blocks": [
            {"at": _iso(b.get("at")), "reason": b.get("reason"), "seconds": b.get("seconds"), "strike": b.get("strike")}
            for b in reversed(blocks)
        ],
    }


def _data_dir() -> Path:
    from . import database
    return database.DB_PATH.parent
