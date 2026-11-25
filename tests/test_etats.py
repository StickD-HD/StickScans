"""État de lecture : automatique selon la lecture, choix manuel, reprise en lisant, et suivi AniList."""
import pytest
from fastapi import BackgroundTasks, HTTPException

from app import anilist
from app.routes import lecture, models, series as series_routes
from conftest import make_parsed, site_chapter


@pytest.fixture
def sid(db):
    return db.insert_series("https://www.scan-manga.com/e.html", make_parsed([site_chapter(n) for n in range(1, 11)]))


def state(db, sid):
    return db.get_series_by_id(sid)["state"]


def test_etat_automatique(db, sid):
    assert state(db, sid) == "planning"  # rien lu : à lire
    db.mark_read_up_to(sid, 3.0)
    assert state(db, sid) == "reading"
    db.mark_all_read(sid)
    assert state(db, sid) == "reading"  # tout lu mais la série continue : à jour, toujours en cours
    with db.get_conn() as conn:
        conn.execute("UPDATE series SET status = 'Terminé' WHERE id = ?", (sid,))
    assert state(db, sid) == "completed"
    assert {s["id"]: s["state"] for s in db.get_all_series()}[sid] == "completed"  # aussi dans la liste


def test_choix_manuel_puis_reprise_en_lisant(db, sid):
    tasks = BackgroundTasks()
    series_routes.set_series_state(sid, models.ReadingStateRequest(state="paused"), tasks)
    assert state(db, sid) == "paused"
    assert [t.func for t in tasks.tasks] == [anilist.push_state]
    lecture.mark_read_up_to(sid, models.MarkReadUpToRequest(number="2"), BackgroundTasks())
    assert state(db, sid) == "reading"  # lire un chapitre reprend la série
    series_routes.set_series_state(sid, models.ReadingStateRequest(state="completed"), BackgroundTasks())
    lecture.mark_read_up_to(sid, models.MarkReadUpToRequest(number="3"), BackgroundTasks())
    assert state(db, sid) == "completed"  # « terminé » choisi à la main n'est pas effacé par une lecture
    series_routes.set_series_state(sid, models.ReadingStateRequest(state=None), BackgroundTasks())
    assert state(db, sid) == "reading"  # retour en automatique
    with pytest.raises(HTTPException):
        series_routes.set_series_state(sid, models.ReadingStateRequest(state="n'importe"), BackgroundTasks())


def test_etat_groupe(db, sid):
    other = db.insert_series("https://www.scan-manga.com/f.html", make_parsed([site_chapter(1)]))
    series_routes.bulk_series(models.BulkSeriesRequest(series_ids=[sid, other], action="set_state", state="dropped"),
                              BackgroundTasks())
    assert state(db, sid) == state(db, other) == "dropped"


def test_suivi_anilist_dans_les_deux_sens(db, sid, monkeypatch):
    db.set_series_anilist_link(sid, 42, "Liée")
    db.set_setting("anilist_token", "jeton")
    pushed = []
    monkeypatch.setattr(anilist, "push_update", lambda series_id, **kw: pushed.append(kw))
    # appli -> AniList
    db.set_reading_state(sid, "paused")
    anilist.push_state(sid)
    assert pushed == [{"status": "PAUSED"}]
    # AniList -> appli : statut AniList affiché quand rien n'est choisi à la main
    db.set_reading_state(sid, None)
    db.set_series_anilist_data(sid, status="DROPPED", progress=0, score=None, start_date=None, end_date=None,
                               cover_url=None, notes=None)
    assert state(db, sid) == "dropped"
    # un changement de statut sur AniList efface le choix manuel lors de la synchro
    db.set_reading_state(sid, "completed")
    monkeypatch.setattr(anilist, "_fetch_collection", lambda user: {42: {"status": "PAUSED", "progress": 0}})
    db.set_setting("anilist_user_name", "moi")
    anilist.sync_all(force=True)
    assert db.get_series_by_id(sid)["reading_state"] is None and state(db, sid) == "paused"
