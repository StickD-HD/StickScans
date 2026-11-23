"""Routes de l'appli (app/routes/), appelées directement : ni serveur, ni site, ni AniList."""
import pytest
from fastapi import BackgroundTasks, HTTPException
from pydantic import ValidationError

from app import anilist, scraper
from app.routes import compte, lecture, models, sauvegardes, series, verifications
from conftest import as_page, make_parsed, site_chapter


@pytest.fixture
def series_id(db):
    return db.insert_series("https://www.scan-manga.com/s.html", make_parsed([site_chapter(n) for n in range(1, 11)]))


def test_marquer_lu_n_attend_pas_anilist(db, series_id, monkeypatch):
    monkeypatch.setattr(anilist, "push_progress", lambda sid: pytest.fail("ne doit pas être appelé pendant la requête"))
    tasks = BackgroundTasks()
    result = lecture.mark_read_up_to(series_id, models.MarkReadUpToRequest(number="5"), tasks)
    assert result["unread_count"] == 5
    assert [(t.func, t.args) for t in tasks.tasks] == [(anilist.push_progress, (series_id,))]


def test_cocher_plusieurs_chapitres_un_envoi_par_serie(db, series_id):
    ids = [c["id"] for c in db.get_chapters_for_series(series_id)][:3]
    tasks = BackgroundTasks()
    lecture.bulk_toggle_read(models.BulkReadRequest(chapter_ids=ids, is_read=True), tasks)
    assert len(tasks.tasks) == 1


@pytest.mark.parametrize("value, ok", [("2026-11-21", True), ("", True), (None, True), ("21/11/2026", False), ("2026-1-2", False)])
def test_format_des_dates_anilist(value, ok):
    if ok:
        models.AnilistUpdateRequest(start_date=value)
    else:
        with pytest.raises(ValidationError):
            models.AnilistUpdateRequest(start_date=value)


@pytest.fixture
def check_running():
    scraper._set_progress(is_running=True)
    yield
    scraper._set_progress(is_running=False)


def test_restauration_refusee_pendant_une_verification(db, check_running):
    with pytest.raises(HTTPException) as info:
        sauvegardes.restore_backup("manhwa_2026-11-21.db")
    assert info.value.status_code == 409


def test_optimisation_refusee_pendant_une_verification(db, check_running):
    with pytest.raises(HTTPException) as info:
        sauvegardes.optimize_storage()
    assert info.value.status_code == 409


def test_aucune_verification_pendant_une_restauration(db, series_id, monkeypatch):
    monkeypatch.setattr(scraper, "fetch_page", as_page(lambda *a, **k: pytest.fail("aucune requête pendant la maintenance")))
    with scraper.maintenance():
        scraper.run_due_checks()
        scraper.check_all_series("manuel")
        result = scraper.check_one_series(db.get_series_by_id(series_id))
    assert "réessaie" in result["check_error"]
    assert db.list_check_runs() == []
    # Après la maintenance, tout redevient possible.
    with scraper.maintenance():
        pass


def test_maintenance_refusee_pendant_une_verification(check_running):
    with pytest.raises(RuntimeError):
        with scraper.maintenance():
            pass


def test_version_deployee(tmp_path, monkeypatch):
    monkeypatch.setattr(compte, "VERSION_FILE", tmp_path / "VERSION")
    assert compte.app_version() == {"commit": None, "date": None, "subject": None}  # lancé hors déploiement
    (tmp_path / "VERSION").write_text("abc1234|2026-11-21 21:10|Message avec | dedans\n", encoding="utf-8")
    assert compte.app_version() == {"commit": "abc1234", "date": "2026-11-21 21:10", "subject": "Message avec | dedans"}


def test_ecran_verifications(db, series_id):
    from datetime import timedelta
    other = db.insert_series("https://www.scan-manga.com/fini.html", make_parsed([site_chapter(1)], title="Finie", status="Terminé"))
    db.set_next_check(series_id, scraper.utc_now() + timedelta(hours=3), "window")
    data = verifications.checks_overview()
    assert [q["title"] for q in data["queue"]] == ["Série test", "Finie"]  # séries ignorées à la fin
    assert data["queue"][0]["reason"] == "window" and data["queue"][1]["skipped"] == "terminée"
    assert len(data["history"]["per_day"]) == 7 and data["errors"] == []
    assert data["site"]["auto_enabled"] is True


def test_changer_l_adresse_refus(db, series_id):
    db.insert_series("https://www.scan-manga.com/autre.html", make_parsed([site_chapter(1)], title="Autre"))
    for url, code in (("https://exemple.fr/serie.html", 400), ("https://www.scan-manga.com/autre.html", 409)):
        with pytest.raises(HTTPException) as info:
            series.change_url(series_id, models.ChangeUrlRequest(url=url))
        assert info.value.status_code == code
