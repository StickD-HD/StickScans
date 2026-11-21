"""Règles AniList (app/anilist.py). AniList n'est jamais contacté : les appels réseau sont remplacés."""
import pytest
import requests

from app import anilist
from conftest import make_parsed, site_chapter

MEDIA_ID = 4242


@pytest.fixture
def linked(db):
    """Série de 20 chapitres liée à AniList, avec un jeton configuré."""
    sid = db.insert_series("https://www.scan-manga.com/s.html", make_parsed([site_chapter(n) for n in range(1, 21)]))
    db.set_series_anilist_link(sid, MEDIA_ID, "Titre AniList")
    db.set_setting("anilist_token", "jeton-de-test")
    return sid


@pytest.fixture
def pushes(monkeypatch):
    """Enregistre les écritures vers AniList au lieu de les envoyer."""
    calls = []
    monkeypatch.setattr(anilist, "push_update", lambda series_id, **kw: calls.append(kw))
    return calls


def _remote(monkeypatch, progress, status="CURRENT"):
    entry = {"status": status, "progress": progress, "score": None, "start_date": None, "end_date": None,
             "cover_url": None, "notes": None}
    monkeypatch.setattr(anilist, "fetch_entry", lambda media_id: dict(entry))


def test_ne_recule_jamais(db, linked, pushes, monkeypatch):
    _remote(monkeypatch, progress=15)
    db.mark_read_up_to(linked, 10.0)
    anilist.push_progress(linked)
    assert pushes == []
    assert db.get_series_by_id(linked)["anilist_progress"] == 15  # l'appli reflète AniList


def test_avance_sans_toucher_au_statut(db, linked, pushes, monkeypatch):
    _remote(monkeypatch, progress=5, status="PAUSED")
    db.mark_read_up_to(linked, 12.0)
    anilist.push_progress(linked)
    assert pushes == [{"status": None, "progress": 12}]


@pytest.mark.parametrize("remote_status", [None, "PLANNING"])
def test_passe_en_cours_a_la_premiere_lecture(db, linked, pushes, monkeypatch, remote_status):
    _remote(monkeypatch, progress=0, status=remote_status)
    db.mark_read_up_to(linked, 1.0)
    anilist.push_progress(linked)
    assert pushes == [{"status": "CURRENT", "progress": 1}]


def test_sans_jeton_rien_n_est_envoye(db, linked, pushes, monkeypatch):
    db.delete_setting("anilist_token")
    monkeypatch.setattr(anilist, "fetch_entry", lambda media_id: pytest.fail("AniList ne doit pas être appelé"))
    db.mark_read_up_to(linked, 3.0)
    anilist.push_progress(linked)
    assert pushes == []


def test_liaison_sans_lecture_ajoute_en_a_lire(db, linked, pushes, monkeypatch):
    _remote(monkeypatch, progress=None, status=None)
    anilist.link_series(linked, MEDIA_ID, "Titre AniList")
    assert pushes == [{"status": "PLANNING"}]


def test_liaison_d_une_serie_deja_dans_la_liste(db, linked, pushes, monkeypatch):
    _remote(monkeypatch, progress=8, status="DROPPED")
    anilist.link_series(linked, MEDIA_ID, "Titre AniList")
    assert pushes == []  # une série déjà présente n'est jamais modifiée


def test_synchro_n_ecrit_jamais_sur_anilist(db, linked, pushes, monkeypatch):
    db.set_setting("anilist_user_name", "testeur")
    monkeypatch.setattr(anilist, "_fetch_collection", lambda user: {
        MEDIA_ID: {"status": "COMPLETED", "progress": 20, "score": 8.0, "start_date": "2026-01-02",
                   "end_date": None, "cover_url": None, "notes": "super"},
    })
    result = anilist.sync_all(force=True)
    assert result == {"synced": True, "updated": 1}
    s = db.get_series_by_id(linked)
    assert (s["anilist_status"], s["anilist_progress"], s["anilist_notes"]) == ("COMPLETED", 20, "super")
    assert pushes == []


def test_recherche_anilist_injoignable(monkeypatch, db):
    def down(*args, **kwargs):
        raise requests.ConnectionError("réseau coupé")

    monkeypatch.setattr(anilist.requests, "post", down)
    with pytest.raises(RuntimeError, match="joindre AniList"):
        anilist.search_media("solo leveling")


def test_deux_envois_simultanes_ne_doublent_pas(db, linked, monkeypatch):
    """Deux chapitres cochés coup sur coup : les envois passent l'un après l'autre, le second voit le premier."""
    import threading
    import time

    remote = {"progress": 0}
    pushed = []

    def fake_fetch(media_id):
        time.sleep(0.05)  # AniList répond lentement : sans verrou, les deux envois liraient 0
        return {"status": "CURRENT", "progress": remote["progress"], "score": None, "start_date": None,
                "end_date": None, "cover_url": None, "notes": None}

    def fake_push(series_id, **kw):
        pushed.append(kw["progress"])
        remote["progress"] = kw["progress"]

    monkeypatch.setattr(anilist, "fetch_entry", fake_fetch)
    monkeypatch.setattr(anilist, "push_update", fake_push)
    db.mark_read_up_to(linked, 12.0)
    threads = [threading.Thread(target=anilist.push_progress, args=(linked,)) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert pushed == [12]


def test_date_videe_effacee_sur_anilist(db, linked, monkeypatch):
    sent = {}

    class Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"data": {"SaveMediaListEntry": {"status": "CURRENT", "progress": 3, "score": 0, "notes": None,
                                                    "startedAt": {"year": None}, "completedAt": {"year": None}}}}

    def fake_post(url, json=None, **kw):
        sent.update(json["variables"])
        return Resp()

    monkeypatch.setattr(anilist.requests, "post", fake_post)
    anilist.push_update(linked, start_date="")
    assert sent["startedAt"] == {"year": None, "month": None, "day": None}
    assert "completedAt" not in sent  # date de fin non fournie : inchangée
    assert db.get_series_by_id(linked)["anilist_start_date"] is None
