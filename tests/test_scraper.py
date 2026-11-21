"""Vérifications (app/scraper.py). Le site n'est jamais contacté : fetch_html est remplacé."""
from datetime import timedelta

import pytest

from app import scraper, site_guard
from app.fetcher import BlockedError, QuotaReached
from conftest import make_parsed, site_chapter

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


@pytest.fixture
def fetched(monkeypatch, series_html):
    """Remplace le site par la fiche d'exemple et note les URL demandées."""
    calls = []

    def fake(url, *args, **kwargs):
        calls.append(url)
        return series_html

    monkeypatch.setattr(scraper, "fetch_html", fake)
    return calls


def test_blocage_du_site_arrete_la_verification(db, monkeypatch):
    _two_series(db)
    calls = []

    def blocked(url, *args, **kwargs):
        calls.append(url)
        raise BlockedError("HTTP 403")

    monkeypatch.setattr(scraper, "fetch_html", blocked)
    scraper.check_all_series("manuel")

    assert len(calls) == 1  # aucune autre série n'est demandée après un refus
    assert db.list_check_runs()[0]["status"] == "interrompue"
    # La pause n'est pas la faute des séries : pas d'erreur, et elles restent à vérifier.
    assert all(s["last_error"] is None and s["next_check_at"] is None for s in db.get_all_series())
    assert scraper.get_progress()["is_running"] is False


def test_plafond_atteint_arrete_aussi(db, monkeypatch):
    _two_series(db)
    monkeypatch.setattr(scraper, "fetch_html", lambda *a, **k: (_ for _ in ()).throw(QuotaReached("limite")))
    scraper.check_all_series("manuel")
    assert db.list_check_runs()[0]["status"] == "interrompue"


def test_verification_complete_et_planification(db, fetched):
    _two_series(db)
    scraper.check_all_series("manuel")

    run = db.get_check_run(db.list_check_runs()[0]["id"])
    assert run["status"] == "terminée"
    assert run["ok_count"] == 2 and run["error_count"] == 0
    assert db.get_recent_updates()  # la fiche d'exemple apporte de nouveaux chapitres
    for s in db.get_all_series():
        # Nouveaux chapitres à l'instant : prochaine vérification dans environ 12 h.
        delay = db.parse_utc(s["next_check_at"]) - scraper.utc_now()
        assert timedelta(hours=10) < delay < timedelta(hours=14)
        assert s["check_reason"] == "between"


def test_page_illisible_n_ecrase_rien(db, monkeypatch, series_html):
    a, _ = _two_series(db)
    truncated = series_html.replace('class="contenu_texte_fiche_technique"', 'class="autre_chose"')
    monkeypatch.setattr(scraper, "fetch_html", lambda url, *a, **k: truncated)
    scraper.check_all_series("manuel")

    s = db.get_series_by_id(a)
    assert s["title"] == "A" and s["status"] == "En cours"  # données conservées
    assert "tronquée" in s["last_error"]
    assert s["check_reason"] == "error"  # revue plus tard, sans insister


def test_seules_les_series_dues_sont_verifiees(db, fetched):
    a, b = _two_series(db)
    db.set_next_check(b, scraper.utc_now() + timedelta(hours=5), "window")
    scraper.run_due_checks()
    assert fetched == ["https://www.scan-manga.com/a.html"]
    scraper.run_due_checks()  # a vient d'être planifiée plus tard : plus rien à faire
    assert len(fetched) == 1
    assert len(db.list_check_runs()) == 1  # pas de vérification vide dans le journal


def test_verifications_automatiques_desactivees(db, fetched):
    _two_series(db)
    db.set_setting("auto_checks_enabled", "0")
    scraper.run_due_checks()
    assert fetched == [] and db.list_check_runs() == []


def test_rien_pendant_une_pause_du_site(db, fetched):
    _two_series(db)
    site_guard.record_block("HTTP 403")
    scraper.run_due_checks()
    assert fetched == [] and db.list_check_runs() == []


def test_actualiser_une_serie_pendant_une_pause(db, monkeypatch):
    a, _ = _two_series(db)
    monkeypatch.setattr(scraper, "fetch_html", lambda *a, **k: (_ for _ in ()).throw(BlockedError("Site en pause")))
    result = scraper.check_one_series(db.get_series_by_id(a))
    assert result["check_error"] == "Site en pause"
    assert result["last_error"] is None  # pas de pastille d'erreur sur la série pour autant


def test_ajout_planifie_la_premiere_verification(db):
    a, _ = _two_series(db)
    scraper.plan_next(db.get_series_by_id(a), ok=True)
    assert db.get_series_by_id(a)["next_check_at"] is not None
    assert [s["id"] for s in db.get_due_series(scraper.utc_now())] != [a]
