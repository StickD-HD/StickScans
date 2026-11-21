"""Vérifications (app/scraper.py). Le site n'est jamais contacté : fetch_html est remplacé."""
from datetime import timedelta

import pytest

from app import scraper, site_guard
from app.fetcher import BlockedError, QuotaReached
from conftest import as_page, make_parsed, site_chapter

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

    monkeypatch.setattr(scraper, "fetch_page", as_page(fake))
    return calls


def test_blocage_du_site_arrete_la_verification(db, monkeypatch):
    _two_series(db)
    calls = []

    def blocked(url, *args, **kwargs):
        calls.append(url)
        raise BlockedError("HTTP 403")

    monkeypatch.setattr(scraper, "fetch_page", as_page(blocked))
    scraper.check_all_series("manuel")

    assert len(calls) == 1  # aucune autre série n'est demandée après un refus
    assert db.list_check_runs()[0]["status"] == "interrompue"
    # La pause n'est pas la faute des séries : pas d'erreur, et elles restent à vérifier.
    assert all(s["last_error"] is None and s["next_check_at"] is None for s in db.get_all_series())
    assert scraper.get_progress()["is_running"] is False


def test_plafond_atteint_arrete_aussi(db, monkeypatch):
    _two_series(db)
    monkeypatch.setattr(scraper, "fetch_page", as_page(lambda *a, **k: (_ for _ in ()).throw(QuotaReached("limite"))))
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
    monkeypatch.setattr(scraper, "fetch_page", as_page(lambda url, *a, **k: truncated))
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
    monkeypatch.setattr(scraper, "fetch_page", as_page(lambda *a, **k: (_ for _ in ()).throw(BlockedError("Site en pause"))))
    result = scraper.check_one_series(db.get_series_by_id(a))
    assert result["check_error"] == "Site en pause"
    assert result["last_error"] is None  # pas de pastille d'erreur sur la série pour autant


def test_ajout_planifie_la_premiere_verification(db):
    a, _ = _two_series(db)
    scraper.plan_next(db.get_series_by_id(a), ok=True)
    assert db.get_series_by_id(a)["next_check_at"] is not None
    assert [s["id"] for s in db.get_due_series(scraper.utc_now())] != [a]


def test_une_pause_n_est_pas_une_erreur_de_serie(db, monkeypatch):
    a, b = _two_series(db)
    monkeypatch.setattr(scraper, "fetch_page", as_page(lambda url, *a, **k: (_ for _ in ()).throw(
        BlockedError("HTTP 403") if url.endswith("a.html") else ValueError("page illisible"))))
    scraper.check_one_series(db.get_series_by_id(b))  # vraie erreur de la série B
    scraper.check_one_series(db.get_series_by_id(a))  # pause du site pendant la vérification de A
    errors = db.get_recent_check_errors()
    assert [e["series_title"] for e in errors] == ["B"]
    assert errors[0]["error"] == "page illisible"


# --- Fiches déplacées ou disparues ---

from app.fetcher import PageNotFound  # noqa: E402


def _read_some(db, sid):
    db.mark_read_up_to(sid, 1.0)


def test_fiche_disparue_marquee_et_revue_moins_souvent(db, monkeypatch, series_html):
    a, _ = _two_series(db)
    monkeypatch.setattr(scraper, "fetch_page", lambda url, *a, **k: (_ for _ in ()).throw(PageNotFound("HTTP 404")))
    scraper.check_one_series(db.get_series_by_id(a))
    s = db.get_series_by_id(a)
    assert s["missing_since"] is not None and s["check_reason"] == "missing"
    delay = db.parse_utc(s["next_check_at"]) - scraper.utc_now()
    assert delay > timedelta(hours=40)  # 48 h ± 10 %
    first_seen = s["missing_since"]
    scraper.check_one_series(db.get_series_by_id(a))
    assert db.get_series_by_id(a)["missing_since"] == first_seen  # la date de la première fois est gardée
    # La page revient : plus rien de signalé
    monkeypatch.setattr(scraper, "fetch_page", as_page(lambda url, *a, **k: series_html))
    scraper.check_one_series(db.get_series_by_id(a))
    s = db.get_series_by_id(a)
    assert s["missing_since"] is None and s["last_error"] is None


def test_le_site_redirige_vers_la_nouvelle_adresse(db, monkeypatch, series_html):
    a, _ = _two_series(db)
    _read_some(db, a)
    monkeypatch.setattr(scraper, "fetch_page", lambda url, *a, **k: (series_html, "https://m.scan-manga.com/nouvelle.html"))
    scraper.check_one_series(db.get_series_by_id(a))
    s = db.get_series_by_id(a)
    assert s["url"] == "https://www.scan-manga.com/nouvelle.html"
    assert db.get_reading_history()  # progression gardée


def test_redirection_vers_une_serie_deja_suivie(db, monkeypatch, series_html):
    a, _ = _two_series(db)
    monkeypatch.setattr(scraper, "fetch_page", lambda url, *a, **k: (series_html, "https://www.scan-manga.com/b.html"))
    scraper.check_one_series(db.get_series_by_id(a))
    assert db.get_series_by_id(a)["url"] == "https://www.scan-manga.com/a.html"  # adresse gardée, pas de doublon


def test_changer_l_adresse_a_la_main(db, monkeypatch, series_html):
    from app.parse_series import parse_series_page
    sid = db.insert_series("https://www.scan-manga.com/serie-test.html", parse_series_page(series_html))
    db.mark_read_up_to(sid, 11.5)
    db.set_series_missing(sid)
    # Même série à une nouvelle adresse : les liens de lecture ont changé, et un chapitre 13 est sorti.
    new_html = series_html.replace("Serie-Test-Chapitre-12-FR_501", "Serie-Test-V2-Chapitre-12-FR_901").replace(
        '<li class="chapitre">', '<li class="chapitre"><div class="chapitre_nom">Chapitre 13</div>'
        '<a href="https://www.scan-manga.com/lecture-en-ligne/Serie-Test-V2-Chapitre-13-FR_902.html">Lire</a></li>'
        '<li class="chapitre">', 1)
    monkeypatch.setattr(scraper, "fetch_page", lambda url, *a, **k: (new_html, url))
    result = scraper.change_series_url(db.get_series_by_id(sid), "https://www.scan-manga.com/serie-test-v2.html")

    s = db.get_series_by_id(sid)
    assert s["url"] == "https://www.scan-manga.com/serie-test-v2.html" and s["missing_since"] is None
    chapters = {c["number"]: c for c in db.get_chapters_for_series(sid)}
    assert chapters["11.5"]["is_read"] == 1 and chapters["12"]["is_read"] == 0   # progression gardée
    assert "V2-Chapitre-12-FR_901" in chapters["12"]["url"]                      # lien d'un chapitre existant mis à jour
    assert result["new_chapters"] == ["13"]                                      # seul le vrai nouveau chapitre
    assert [h["number"] for h in db.get_reading_history()] == ["11.5"]           # historique intact
