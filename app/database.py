"""
Accès à la base SQLite.
- series                  : infos générales + métadonnées scrapées + miroir local AniList
- chapters                : un enregistrement par chapitre, statut lu/non-lu, date de lecture, date de découverte
- genres / series_genres  : genres du site (utilisés comme filtre)
- categories / series_categories : catégories créées par l'utilisateur (façon playlists)
- app_settings            : paramètres clé/valeur (jeton AniList, format de note, etc.)
"""
import sqlite3
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from pathlib import Path

from .parse_series import number_to_float, LINK_RANK

DB_PATH = Path(__file__).parent.parent / "data" / "manhwa.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS series (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    title TEXT,
    cover_url TEXT,
    status TEXT,
    last_chapter_number TEXT,
    last_chapter_url TEXT,
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_checked_at TEXT,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    number TEXT NOT NULL,
    number_float REAL NOT NULL,
    url TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    discovered_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(series_id, number)
);

CREATE TABLE IF NOT EXISTS genres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS series_genres (
    series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    genre_id INTEGER NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
    PRIMARY KEY (series_id, genre_id)
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS series_categories (
    series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (series_id, category_id)
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS check_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    duration_seconds REAL,
    trigger TEXT NOT NULL DEFAULT 'auto',
    status TEXT NOT NULL DEFAULT 'en cours',
    total INTEGER NOT NULL DEFAULT 0,
    ok_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    new_chapters INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS check_run_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES check_runs(id) ON DELETE CASCADE,
    series_id INTEGER,
    series_title TEXT,
    duration_seconds REAL,
    ok INTEGER NOT NULL DEFAULT 1,
    new_chapters TEXT,
    error TEXT,
    source TEXT NOT NULL DEFAULT 'site'
);
CREATE INDEX IF NOT EXISTS idx_check_run_items_run ON check_run_items(run_id);
"""

NEW_SERIES_COLUMNS = {
    "chapter_list_synced": "INTEGER NOT NULL DEFAULT 0",
    "synopsis": "TEXT",
    "author": "TEXT",
    "year": "TEXT",
    "editor": "TEXT",
    "team": "TEXT",
    "popularity": "INTEGER",
    "category": "TEXT",
    "cover_locked": "INTEGER NOT NULL DEFAULT 0",
    "title_locked": "INTEGER NOT NULL DEFAULT 0",
    "alt_names": "TEXT",
    "anilist_id": "INTEGER",
    "anilist_title": "TEXT",
    "anilist_last_error": "TEXT",
    "anilist_status": "TEXT",
    "anilist_progress": "INTEGER",
    "anilist_score": "REAL",
    "anilist_start_date": "TEXT",
    "anilist_end_date": "TEXT",
}

NEW_CHAPTERS_COLUMNS = {
    "read_at": "TEXT",
    "is_initial_fetch": "INTEGER NOT NULL DEFAULT 0",
    "link_type": "TEXT NOT NULL DEFAULT 'site'",
}


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Ajout d'un timeout de 15s pour �viter le verrouillage imm�diat
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    
    # Point 5 : Activation du mode WAL et optimisation
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON")
    
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        existing_series = {row["name"] for row in conn.execute("PRAGMA table_info(series)")}
        for col, coltype in NEW_SERIES_COLUMNS.items():
            if col not in existing_series:
                conn.execute(f"ALTER TABLE series ADD COLUMN {col} {coltype}")
        existing_chapters = {row["name"] for row in conn.execute("PRAGMA table_info(chapters)")}
        is_first_migration = "is_initial_fetch" not in existing_chapters
        for col, coltype in NEW_CHAPTERS_COLUMNS.items():
            if col not in existing_chapters:
                conn.execute(f"ALTER TABLE chapters ADD COLUMN {col} {coltype}")
        if is_first_migration:
            conn.execute("UPDATE chapters SET is_initial_fetch = 1")
        # Les liens vers les plateformes officielles ne sont pas conservés : ces chapitres n'ont « pas de lien »
        conn.execute("UPDATE chapters SET link_type = 'aucun', url = '' WHERE link_type = 'externe'")
        # Journal des vérifications : colonne « source » (site ou copie d'une autre instance)
        existing_items = {row["name"] for row in conn.execute("PRAGMA table_info(check_run_items)")}
        if "source" not in existing_items:
            conn.execute("ALTER TABLE check_run_items ADD COLUMN source TEXT NOT NULL DEFAULT 'site'")


# --- Journal des vérifications (durées, erreurs) ---

CHECK_LOG_RETENTION_DAYS = 30


def start_check_run(trigger: str, total: int) -> int:
    with get_conn() as conn:
        cur = conn.execute("INSERT INTO check_runs (trigger, total) VALUES (?, ?)", (trigger, total))
        return cur.lastrowid


def add_check_item(run_id: int, series_id: int, title: str | None, duration: float, ok: bool,
                   new_chapters: list[str], error: str | None, source: str = "site"):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO check_run_items (run_id, series_id, series_title, duration_seconds, ok, new_chapters, error, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, series_id, title, round(duration, 2), 1 if ok else 0, ", ".join(new_chapters) or None, error, source),
        )


def finish_check_run(run_id: int, duration: float):
    with get_conn() as conn:
        counts = conn.execute(
            """
            SELECT COALESCE(SUM(ok), 0) AS ok_count, COUNT(*) - COALESCE(SUM(ok), 0) AS error_count
            FROM check_run_items WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        new_total = sum(
            len(r["new_chapters"].split(", "))
            for r in conn.execute("SELECT new_chapters FROM check_run_items WHERE run_id = ? AND new_chapters IS NOT NULL", (run_id,))
        )
        conn.execute(
            """
            UPDATE check_runs
            SET finished_at = datetime('now'), duration_seconds = ?, status = 'terminée',
                ok_count = ?, error_count = ?, new_chapters = ?
            WHERE id = ?
            """,
            (round(duration, 1), counts["ok_count"], counts["error_count"], new_total, run_id),
        )
        conn.execute(
            f"DELETE FROM check_runs WHERE started_at < datetime('now', '-{CHECK_LOG_RETENTION_DAYS} days')"
        )


def close_stale_check_runs():
    """Au démarrage : une vérification restée 'en cours' a été coupée par un redémarrage."""
    with get_conn() as conn:
        conn.execute("UPDATE check_runs SET status = 'interrompue' WHERE status = 'en cours'")


def list_check_runs(limit: int = 60) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM check_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_check_run(run_id: int) -> dict | None:
    with get_conn() as conn:
        run = conn.execute("SELECT * FROM check_runs WHERE id = ?", (run_id,)).fetchone()
        if not run:
            return None
        items = conn.execute(
            "SELECT * FROM check_run_items WHERE run_id = ? ORDER BY duration_seconds DESC", (run_id,)
        ).fetchall()
        return {**dict(run), "items": [dict(i) for i in items]}


def get_check_summary() -> dict:
    with get_conn() as conn:
        last_run = conn.execute("SELECT * FROM check_runs ORDER BY id DESC LIMIT 1").fetchone()
        done = conn.execute(
            "SELECT id, started_at, duration_seconds, error_count, trigger FROM check_runs "
            "WHERE status = 'terminée' AND trigger = 'auto' ORDER BY id DESC LIMIT 24"
        ).fetchall()
        done = list(reversed([dict(r) for r in done]))
        avg_run = sum(r["duration_seconds"] for r in done) / len(done) if done else None
        item_stats = conn.execute(
            """
            SELECT COUNT(*) AS n, AVG(CASE WHEN i.source = 'cache' THEN NULL ELSE i.duration_seconds END) AS avg_s,
                   COALESCE(SUM(1 - i.ok), 0) AS errors, COALESCE(SUM(i.source = 'cache'), 0) AS from_cache
            FROM check_run_items i JOIN check_runs r ON r.id = i.run_id
            WHERE r.started_at >= datetime('now', '-1 day')
            """
        ).fetchone()
        slowest = conn.execute(
            """
            SELECT i.series_title, ROUND(AVG(i.duration_seconds), 1) AS avg_seconds, COUNT(*) AS checks
            FROM check_run_items i JOIN check_runs r ON r.id = i.run_id
            WHERE r.started_at >= datetime('now', '-7 days') AND i.series_title IS NOT NULL AND i.source != 'cache'
            GROUP BY i.series_id ORDER BY AVG(i.duration_seconds) DESC LIMIT 5
            """
        ).fetchall()
        return {
            "last_run": dict(last_run) if last_run else None,
            "avg_run_seconds": round(avg_run, 1) if avg_run is not None else None,
            "avg_series_seconds": round(item_stats["avg_s"], 1) if item_stats["avg_s"] is not None else None,
            "checks_24h": item_stats["n"],
            "errors_24h": item_stats["errors"],
            "from_cache_24h": item_stats["from_cache"],
            "recent_runs": done,
            "slowest_series": [dict(r) for r in slowest],
        }


# --- Genres (filtre, alimenté par le scraping) ---

def _upsert_genres(conn, series_id: int, genre_names: list[str]):
    conn.execute("DELETE FROM series_genres WHERE series_id = ?", (series_id,))
    for name in genre_names:
        name = name.strip()
        if not name:
            continue
        conn.execute("INSERT OR IGNORE INTO genres (name) VALUES (?)", (name,))
        genre_id = conn.execute("SELECT id FROM genres WHERE name = ?", (name,)).fetchone()[0]
        conn.execute(
            "INSERT OR IGNORE INTO series_genres (series_id, genre_id) VALUES (?, ?)",
            (series_id, genre_id),
        )


def get_all_genres() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT g.name FROM genres g
            JOIN series_genres sg ON sg.genre_id = g.id
            GROUP BY g.id
            ORDER BY g.name
            """
        ).fetchall()
        return [r["name"] for r in rows]


def get_genres_for_series(series_id: int) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT g.name FROM genres g
            JOIN series_genres sg ON sg.genre_id = g.id
            WHERE sg.series_id = ?
            ORDER BY g.name
            """,
            (series_id,),
        ).fetchall()
        return [r["name"] for r in rows]


def get_all_statuses() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT status FROM series WHERE status IS NOT NULL AND status != '' ORDER BY status"
        ).fetchall()
        return [r["status"] for r in rows]


# --- Catégories (créées par l'utilisateur, façon playlists) ---

def get_all_categories() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM categories ORDER BY position, id").fetchall()
        return [dict(r) for r in rows]


def create_category(name: str) -> int:
    with get_conn() as conn:
        max_pos = conn.execute("SELECT COALESCE(MAX(position), -1) FROM categories").fetchone()[0]
        cur = conn.execute("INSERT INTO categories (name, position) VALUES (?, ?)", (name, max_pos + 1))
        return cur.lastrowid


def rename_category(category_id: int, name: str):
    with get_conn() as conn:
        conn.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))


def delete_category(category_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))


def get_categories_for_series(series_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT c.* FROM categories c
            JOIN series_categories sc ON sc.category_id = c.id
            WHERE sc.series_id = ?
            ORDER BY c.position, c.id
            """,
            (series_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def add_series_to_category(series_id: int, category_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO series_categories (series_id, category_id) VALUES (?, ?)",
            (series_id, category_id),
        )


def remove_series_from_category(series_id: int, category_id: int):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM series_categories WHERE series_id = ? AND category_id = ?",
            (series_id, category_id),
        )


# --- Séries ---

def get_all_series(sort: str = "last_checked_at", hide_fully_read: bool = False,
                    genre: str | None = None, status: str | None = None,
                    search: str | None = None, category_id: int | None = None) -> list[dict]:
    order_map = {
        # Trie par date du dernier chapitre réellement découvert après l'ajout
        # (pas juste "dernière vérification", qui bouge pour toutes les séries à chaque passage).
        "last_checked_at": "COALESCE(MAX(CASE WHEN c.is_initial_fetch = 0 THEN c.discovered_at END), s.added_at) DESC",
        "title": "s.title COLLATE NOCASE ASC",
        "popularity": "s.popularity DESC",
        "year": "s.year DESC",
        "added_at": "s.added_at DESC",
    }
    order_clause = order_map.get(sort, "s.last_checked_at DESC")

    conditions = []
    params: list = []
    if status:
        conditions.append("s.status = ?")
        params.append(status)
    if search:
        conditions.append("(s.title LIKE ? OR s.alt_names LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if genre:
        conditions.append(
            "s.id IN (SELECT sg.series_id FROM series_genres sg JOIN genres g ON g.id = sg.genre_id WHERE g.name = ?)"
        )
        params.append(genre)
    if category_id:
        conditions.append("s.id IN (SELECT series_id FROM series_categories WHERE category_id = ?)")
        params.append(category_id)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    having_clause = "HAVING unread_count > 0" if hide_fully_read else ""

    query = f"""
        SELECT s.*,
               COUNT(c.id) AS total_chapters,
               COALESCE(SUM(CASE WHEN c.is_read = 0 THEN 1 ELSE 0 END), 0) AS unread_count
        FROM series s
        LEFT JOIN chapters c ON c.series_id = s.id
        {where_clause}
        GROUP BY s.id
        {having_clause}
        ORDER BY {order_clause}
    """
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_series_by_id(series_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT s.*,
                   COUNT(c.id) AS total_chapters,
                   COALESCE(SUM(CASE WHEN c.is_read = 0 THEN 1 ELSE 0 END), 0) AS unread_count
            FROM series s
            LEFT JOIN chapters c ON c.series_id = s.id
            WHERE s.id = ?
            GROUP BY s.id
            """,
            (series_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
    result["genres"] = get_genres_for_series(series_id)
    result["categories"] = get_categories_for_series(series_id)
    return result


def get_series_by_url(url: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM series WHERE url = ?", (url,)).fetchone()
        return dict(row) if row else None


def insert_series(url: str, parsed: dict) -> int:
    alt_names_str = ", ".join(parsed.get("alt_names") or []) or None
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO series (url, title, alt_names, cover_url, status, last_chapter_number, last_chapter_url,
                                 synopsis, author, year, editor, team, popularity, category, last_checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                url, parsed.get("title"), alt_names_str, parsed.get("cover_url"), parsed.get("status"),
                parsed.get("last_chapter_number"), parsed.get("last_chapter_url"),
                parsed.get("synopsis"), parsed.get("author"), parsed.get("year"),
                parsed.get("editor"), parsed.get("team"), parsed.get("popularity"), parsed.get("category"),
            ),
        )
        series_id = cur.lastrowid
        _upsert_genres(conn, series_id, parsed.get("genres") or [])
        _upsert_chapters(conn, series_id, parsed.get("chapters") or [], is_initial=True)
        return series_id


def update_series_result(series_id: int, parsed: dict) -> list[dict]:
    alt_names_str = ", ".join(parsed.get("alt_names") or []) or None
    with get_conn() as conn:
        current = conn.execute(
            "SELECT cover_locked, title_locked FROM series WHERE id = ?", (series_id,)
        ).fetchone()
        cover_locked = bool(current["cover_locked"]) if current else False
        title_locked = bool(current["title_locked"]) if current else False

        set_clauses = [
            "status = ?", "last_chapter_number = ?", "last_chapter_url = ?", "alt_names = ?",
            "synopsis = ?", "author = ?", "year = ?", "editor = ?", "team = ?",
            "popularity = ?", "category = ?", "last_checked_at = datetime('now')", "last_error = NULL",
        ]
        params = [
            parsed.get("status"), parsed.get("last_chapter_number"), parsed.get("last_chapter_url"), alt_names_str,
            parsed.get("synopsis"), parsed.get("author"), parsed.get("year"), parsed.get("editor"),
            parsed.get("team"), parsed.get("popularity"), parsed.get("category"),
        ]
        if not cover_locked:
            set_clauses.insert(0, "cover_url = ?")
            params.insert(0, parsed.get("cover_url"))
        if not title_locked:
            set_clauses.insert(0, "title = ?")
            params.insert(0, parsed.get("title"))

        params.append(series_id)
        conn.execute(f"UPDATE series SET {', '.join(set_clauses)} WHERE id = ?", params)

        _upsert_genres(conn, series_id, parsed.get("genres") or [])
        return _upsert_chapters(conn, series_id, parsed.get("chapters") or [], is_initial=False)


def update_series_manual(series_id: int, cover_url: str | None, title: str | None):
    with get_conn() as conn:
        if cover_url is not None:
            conn.execute("UPDATE series SET cover_url = ?, cover_locked = 1 WHERE id = ?", (cover_url, series_id))
        if title is not None:
            conn.execute("UPDATE series SET title = ?, title_locked = 1 WHERE id = ?", (title, series_id))


def unlock_field(series_id: int, field: str):
    col = {"cover": "cover_locked", "title": "title_locked"}.get(field)
    if not col:
        return
    with get_conn() as conn:
        conn.execute(f"UPDATE series SET {col} = 0 WHERE id = ?", (series_id,))


def _upsert_chapters(conn, series_id: int, chapters: list[dict], is_initial: bool = False) -> list[dict]:
    """Enregistre les chapitres vus sur la page et renvoie ceux qui sont VRAIMENT nouveaux.

    Un chapitre avec lien de lecture scan-manga est nouveau dès qu'il apparaît (comportement d'origine).
    Un chapitre sans lien de lecture scan-manga n'est nouveau que s'il dépasse le
    dernier chapitre connu ; les anciens chapitres qui apparaissent d'un coup (premier import de la
    liste complète) sont enregistrés sans bruit, pour ne pas inonder les Nouveautés.
    """
    row = conn.execute("SELECT chapter_list_synced FROM series WHERE id = ?", (series_id,)).fetchone()
    already_synced = bool(row["chapter_list_synced"]) if row else False
    stored = {
        r["number"]: r["link_type"] or "site"
        for r in conn.execute("SELECT number, link_type FROM chapters WHERE series_id = ?", (series_id,))
    }
    frontier = conn.execute("SELECT MAX(number_float) FROM chapters WHERE series_id = ?", (series_id,)).fetchone()[0]

    new_chapters = []
    for chap in chapters:
        number = chap["number"]
        url = chap.get("url") or ""
        link_type = chap.get("link_type") or ("site" if url else "aucun")
        number_float = number_to_float(number)

        if number in stored:
            # Un lien de meilleure qualité est apparu (ex. le chapitre devient lisible sur scan-manga) : on le garde
            if LINK_RANK.get(link_type, 0) > LINK_RANK.get(stored[number], 0):
                conn.execute(
                    "UPDATE chapters SET url = ?, link_type = ? WHERE series_id = ? AND number = ?",
                    (url, link_type, series_id, number),
                )
            continue

        silent = is_initial
        if not is_initial and link_type != "site":
            silent = (not already_synced) or frontier is None or number_float <= frontier
        cur = conn.execute(
            "INSERT OR IGNORE INTO chapters (series_id, number, number_float, url, link_type, is_initial_fetch) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (series_id, number, number_float, url, link_type, 1 if silent else 0),
        )
        if cur.rowcount > 0 and not silent:
            new_chapters.append({"number": number, "url": url})

    conn.execute("UPDATE series SET chapter_list_synced = 1 WHERE id = ?", (series_id,))
    return new_chapters


def update_series_error(series_id: int, error: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE series SET last_checked_at = datetime('now'), last_error = ? WHERE id = ?",
            (error, series_id),
        )


def delete_series(series_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM series WHERE id = ?", (series_id,))


# --- Chapitres ---

def get_chapters_for_series(series_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM chapters WHERE series_id = ? ORDER BY number_float DESC",
            (series_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def set_chapter_read(chapter_id: int, is_read: bool):
    with get_conn() as conn:
        if is_read:
            conn.execute(
                "UPDATE chapters SET is_read = 1, read_at = COALESCE(read_at, datetime('now')) WHERE id = ?",
                (chapter_id,),
            )
        else:
            conn.execute("UPDATE chapters SET is_read = 0, read_at = NULL WHERE id = ?", (chapter_id,))


def set_chapters_read(chapter_ids: list[int], is_read: bool):
    if not chapter_ids:
        return
    with get_conn() as conn:
        placeholders = ",".join("?" for _ in chapter_ids)
        if is_read:
            conn.execute(
                f"UPDATE chapters SET is_read = 1, read_at = COALESCE(read_at, datetime('now')) WHERE id IN ({placeholders})",
                chapter_ids,
            )
        else:
            conn.execute(
                f"UPDATE chapters SET is_read = 0, read_at = NULL WHERE id IN ({placeholders})",
                chapter_ids,
            )


def mark_read_up_to(series_id: int, number_float: float):
    with get_conn() as conn:
        # Chapitres précédents : marqués "lus" (pour la progression) mais SANS entrée dans
        # l'historique, sinon ajouter une série déjà lue y déversait tous les anciens chapitres.
        conn.execute(
            "UPDATE chapters SET is_read = 1 WHERE series_id = ? AND number_float < ?",
            (series_id, number_float),
        )
        # Le chapitre réellement lu : lui seul est noté dans l'historique.
        conn.execute(
            """
            UPDATE chapters
            SET is_read = 1, read_at = COALESCE(read_at, datetime('now'))
            WHERE series_id = ? AND number_float = ?
            """,
            (series_id, number_float),
        )


def mark_all_read(series_id: int):
    with get_conn() as conn:
        # "Tout marquer comme lu" = rattrapage : pas d'entrées dans l'historique.
        conn.execute("UPDATE chapters SET is_read = 1 WHERE series_id = ?", (series_id,))


# --- Mises à jour / Historique ---

def get_recent_updates(limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT c.id AS chapter_id, c.number, c.url, c.discovered_at,
                   s.id AS series_id, s.title AS series_title, s.cover_url AS series_cover
            FROM chapters c
            JOIN series s ON s.id = c.series_id
            WHERE c.is_initial_fetch = 0
            ORDER BY c.discovered_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_reading_history(limit: int = 200) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT c.id AS chapter_id, c.number, c.number_float, c.url, c.read_at,
                   s.id AS series_id, s.title AS series_title, s.cover_url AS series_cover
            FROM chapters c
            JOIN series s ON s.id = c.series_id
            WHERE c.read_at IS NOT NULL
            ORDER BY c.read_at DESC, c.number_float DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def remove_from_history(chapter_ids: list[int]):
    """Retire des entrées de l'historique. Les chapitres restent marqués comme lus."""
    if not chapter_ids:
        return
    with get_conn() as conn:
        placeholders = ",".join("?" for _ in chapter_ids)
        conn.execute(f"UPDATE chapters SET read_at = NULL WHERE id IN ({placeholders})", chapter_ids)


def clear_reading_history():
    with get_conn() as conn:
        conn.execute("UPDATE chapters SET read_at = NULL WHERE read_at IS NOT NULL")


def get_reading_stats(tz_offset_minutes: int = 0) -> dict:
    # tz_offset_minutes : décalage de l'utilisateur par rapport à UTC (Paris en été : +120),
    # pour que les "jours" correspondent à ses vraies journées.
    with get_conn() as conn:
        modifier = f"{tz_offset_minutes:+d} minutes"
        day_rows = conn.execute(
            "SELECT date(read_at, ?) AS d, COUNT(*) AS n FROM chapters WHERE read_at IS NOT NULL GROUP BY d",
            (modifier,),
        ).fetchall()
        per_day = {r["d"]: r["n"] for r in day_rows}
        today = (datetime.now(timezone.utc) + timedelta(minutes=tz_offset_minutes)).date()
        last_7_days = [
            {"date": (today - timedelta(days=i)).isoformat(), "count": per_day.get((today - timedelta(days=i)).isoformat(), 0)}
            for i in range(6, -1, -1)
        ]
        # Jours d'affilée : on compte en arrière depuis aujourd'hui (ou hier si rien n'est encore lu aujourd'hui).
        day = today if per_day.get(today.isoformat()) else today - timedelta(days=1)
        streak_days = 0
        while per_day.get(day.isoformat()):
            streak_days += 1
            day -= timedelta(days=1)

        chapters_this_week = conn.execute(
            "SELECT COUNT(*) FROM chapters WHERE read_at >= datetime('now', '-7 days')"
        ).fetchone()[0]
        chapters_this_month = conn.execute(
            "SELECT COUNT(*) FROM chapters WHERE read_at >= datetime('now', '-30 days')"
        ).fetchone()[0]
        total_read = conn.execute("SELECT COUNT(*) FROM chapters WHERE is_read = 1").fetchone()[0]
        top_series = conn.execute(
            """
            SELECT s.title, COUNT(*) AS read_count
            FROM chapters c JOIN series s ON s.id = c.series_id
            WHERE c.is_read = 1
            GROUP BY s.id
            ORDER BY read_count DESC
            LIMIT 1
            """
        ).fetchone()
        return {
            "chapters_this_week": chapters_this_week,
            "chapters_this_month": chapters_this_month,
            "total_read": total_read,
            "top_series_title": top_series["title"] if top_series else None,
            "top_series_count": top_series["read_count"] if top_series else 0,
            "streak_days": streak_days,
            "last_7_days": last_7_days,
        }


# --- Paramètres généraux (clé/valeur) ---

def get_setting(key: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def delete_setting(key: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))


# --- AniList ---

def set_series_anilist_link(series_id: int, anilist_id: int | None, title: str | None):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE series
            SET anilist_id = ?, anilist_title = ?, anilist_last_error = NULL,
                anilist_status = NULL, anilist_progress = NULL, anilist_score = NULL,
                anilist_start_date = NULL, anilist_end_date = NULL
            WHERE id = ?
            """,
            (anilist_id, title, series_id),
        )


def set_series_anilist_data(series_id: int, status=None, progress=None, score=None,
                             start_date=None, end_date=None):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE series
            SET anilist_status = ?, anilist_progress = ?, anilist_score = ?,
                anilist_start_date = ?, anilist_end_date = ?, anilist_last_error = NULL
            WHERE id = ?
            """,
            (status, progress, score, start_date, end_date, series_id),
        )


def set_series_anilist_error(series_id: int, error: str | None):
    with get_conn() as conn:
        conn.execute("UPDATE series SET anilist_last_error = ? WHERE id = ?", (error, series_id))


def get_max_read_chapter_number(series_id: int) -> int | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(number_float) AS m FROM chapters WHERE series_id = ? AND is_read = 1",
            (series_id,),
        ).fetchone()
        return int(row["m"]) if row and row["m"] is not None else None


def get_series_id_for_chapter(chapter_id: int) -> int | None:
    with get_conn() as conn:
        row = conn.execute("SELECT series_id FROM chapters WHERE id = ?", (chapter_id,)).fetchone()
        return row["series_id"] if row else None


def get_series_ids_for_chapters(chapter_ids: list[int]) -> set:
    if not chapter_ids:
        return set()
    with get_conn() as conn:
        placeholders = ",".join("?" for _ in chapter_ids)
        rows = conn.execute(
            f"SELECT DISTINCT series_id FROM chapters WHERE id IN ({placeholders})", chapter_ids
        ).fetchall()
        return {r["series_id"] for r in rows}