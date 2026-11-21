"""
Réglages communs des tests.

Aucun test n'envoie de requête vers scan-manga.com ni vers AniList : tout ce qui sortirait sur le réseau est remplacé.
La base et les journaux sont créés dans un dossier temporaire, jamais dans data/ (ni dans celui du dépôt, ni dans
celui d'une instance).
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Pas de cache de pages partagé pendant les tests, quelle que soit la configuration de la machine.
os.environ.pop("SCRAPE_CACHE_DIR", None)
os.environ.pop("SCRAPE_CACHE_MODE", None)

# Le chemin de la base doit être redirigé AVANT d'importer scraper (son journal se place à côté de la base).
from app import database  # noqa: E402

_SESSION_DIR = Path(tempfile.mkdtemp(prefix="stickscans-tests-"))
database.DB_PATH = _SESSION_DIR / "data" / "manhwa.db"

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Base vide et neuve pour chaque test."""
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "manhwa.db")
    database.init_db()
    return database


@pytest.fixture
def series_html() -> str:
    return (FIXTURES / "serie_exemple.html").read_text(encoding="utf-8")


def make_parsed(chapters, **extra) -> dict:
    """Résultat de parse_series_page minimal, pour alimenter la base dans les tests."""
    parsed = {
        "title": "Série test",
        "alt_names": [],
        "cover_url": "https://www.scan-manga.com/img/cover.jpg",
        "synopsis": None,
        "status": "En cours",
        "author": None,
        "category": None,
        "year": None,
        "editor": None,
        "team": None,
        "popularity": None,
        "genres": [],
        "last_chapter_number": None,
        "last_chapter_url": None,
        "chapters": chapters,
    }
    parsed.update(extra)
    return parsed


def site_chapter(number) -> dict:
    n = str(number)
    return {"number": n, "url": f"https://www.scan-manga.com/lecture-en-ligne/Serie-Chapitre-{n}-FR_1.html",
            "link_type": "site"}


def nolink_chapter(number) -> dict:
    return {"number": str(number), "url": "", "link_type": "aucun"}
