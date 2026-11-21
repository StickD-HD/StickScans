"""Vérifications groupées (app/scraper.py). Le site n'est jamais contacté : fetch_html est remplacé."""
import pytest

from app import scraper
from app.fetcher import BlockedError
from conftest import make_parsed, site_chapter


@pytest.fixture
def no_pause(monkeypatch):
    monkeypatch.setattr(scraper, "MIN_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(scraper, "MAX_DELAY_SECONDS", 0.0)


ALL_OFF = {"skip_completed": False, "skip_unread": False, "skip_never_read": False}


@pytest.mark.parametrize("series, rules, expected", [
    ({"status": "Terminé", "total_chapters": 5, "unread_count": 0}, {**ALL_OFF, "skip_completed": True}, "skip_completed"),
    ({"status": "terminée", "total_chapters": 5, "unread_count": 0}, {**ALL_OFF, "skip_completed": True}, "skip_completed"),
    ({"status": "En cours", "total_chapters": 5, "unread_count": 0}, {**ALL_OFF, "skip_completed": True}, None),
    ({"status": "En cours", "total_chapters": 5, "unread_count": 2}, {**ALL_OFF, "skip_unread": True}, "skip_unread"),
    ({"status": "En cours", "total_chapters": 5, "unread_count": 5}, {**ALL_OFF, "skip_never_read": True}, "skip_never_read"),
    ({"status": "En cours", "total_chapters": 5, "unread_count": 4}, {**ALL_OFF, "skip_never_read": True}, None),
    ({"status": "Terminé", "total_chapters": 5, "unread_count": 5}, ALL_OFF, None),
])
def test_series_ignorees(series, rules, expected):
    assert scraper.skip_reason(series, rules) == expected


def _two_series(db):
    a = db.insert_series("https://www.scan-manga.com/a.html", make_parsed([site_chapter(1)], title="A"))
    b = db.insert_series("https://www.scan-manga.com/b.html", make_parsed([site_chapter(1)], title="B"))
    return a, b


def test_blocage_du_site_arrete_la_verification(db, no_pause, monkeypatch):
    _two_series(db)
    calls = []

    def blocked(url, *args, **kwargs):
        calls.append(url)
        raise BlockedError("HTTP 403")

    monkeypatch.setattr(scraper, "fetch_html", blocked)
    scraper.check_all_series("auto")

    assert len(calls) == 1  # aucune autre série n'est demandée après un refus
    run = db.list_check_runs()[0]
    assert run["status"] == "interrompue"
    # Un blocage pendant une vérification groupée n'est pas inscrit comme erreur de la série.
    assert all(s["last_error"] is None for s in db.get_all_series())
    assert scraper.get_progress()["is_running"] is False


def test_verification_complete(db, no_pause, monkeypatch, series_html):
    _two_series(db)
    monkeypatch.setattr(scraper, "fetch_html", lambda url, *a, **k: series_html)
    scraper.check_all_series("manuel")

    run = db.get_check_run(db.list_check_runs()[0]["id"])
    assert run["status"] == "terminée"
    assert run["ok_count"] == 2 and run["error_count"] == 0
    assert db.get_recent_updates()  # la fiche d'exemple apporte de nouveaux chapitres


def test_page_illisible_n_ecrase_rien(db, no_pause, monkeypatch, series_html):
    a, _ = _two_series(db)
    truncated = series_html.replace('class="contenu_texte_fiche_technique"', 'class="autre_chose"')
    monkeypatch.setattr(scraper, "fetch_html", lambda url, *a, **k: truncated)
    scraper.check_all_series("manuel")

    s = db.get_series_by_id(a)
    assert s["title"] == "A" and s["status"] == "En cours"  # données conservées
    assert "tronquée" in s["last_error"]
