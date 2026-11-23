"""Actions groupées sur plusieurs séries, filtre « Suivi AniList » et page aux fichiers versionnés."""
import pytest
from fastapi import BackgroundTasks, HTTPException

from app import anilist, main
from conftest import make_parsed, site_chapter


@pytest.fixture
def three(db):
    ids = []
    for i in range(3):
        parsed = make_parsed([site_chapter(n) for n in range(1, 6)])
        parsed["title"] = f"Série {'CBA'[i]}"
        ids.append(db.insert_series(f"https://www.scan-manga.com/s{i}.html", parsed))
    return ids


def bulk(ids, action, category_id=None, tasks=None):
    return main.bulk_series(main.BulkSeriesRequest(series_ids=ids, action=action, category_id=category_id),
                            tasks or BackgroundTasks())


def test_tout_lu_puis_tout_non_lu(db, three):
    db.set_series_anilist_link(three[0], 42, "Liée")
    tasks = BackgroundTasks()
    assert bulk(three[:2], "mark_read", tasks=tasks)["count"] == 2
    assert [db.get_series_by_id(i)["unread_count"] for i in three] == [0, 0, 5]
    # AniList : un envoi, et seulement pour la série liée
    assert [(t.func, t.args) for t in tasks.tasks] == [(anilist.push_progress, (three[0],))]
    bulk(three, "mark_unread")
    assert [db.get_series_by_id(i)["unread_count"] for i in three] == [5, 5, 5]


def test_categories_groupees(db, three):
    cat = db.create_category("Favoris")
    db.add_series_to_category(three[0], cat)
    counts = main.bulk_series_categories(main.BulkIdsRequest(series_ids=three[:2]))
    assert counts == [{"id": cat, "name": "Favoris", "count": 1, "total": 2}]
    bulk(three[:2], "add_category", cat)
    assert db.get_category_series_ids(cat) == {three[0], three[1]}
    bulk(three, "remove_category", cat)
    assert db.get_category_series_ids(cat) == set()
    with pytest.raises(HTTPException):
        bulk(three, "add_category", 9999)


def test_suppression_groupee_et_action_inconnue(db, three):
    assert bulk(three[:2] + [9999], "delete")["count"] == 2
    assert [s["id"] for s in db.get_all_series()] == [three[2]]
    with pytest.raises(HTTPException):
        bulk(three, "formater")


def test_filtre_suivi_anilist(db, three):
    db.set_series_anilist_link(three[2], 1, "x")
    db.set_series_anilist_link(three[1], 2, "y")
    with db.get_conn() as conn:
        conn.execute("UPDATE series SET anilist_status = 'COMPLETED' WHERE id = ?", (three[2],))
        conn.execute("UPDATE series SET anilist_status = 'CURRENT' WHERE id = ?", (three[1],))
    ids = lambda f: sorted(s["id"] for s in db.get_all_series(anilist=f))
    assert ids("linked") == sorted(three[1:])
    assert ids("unlinked") == [three[0]]
    assert ids("COMPLETED") == [three[2]]
    assert ids("CURRENT") == [three[1]]
    assert ids("PAUSED") == []
    assert ids("n'importe quoi") == sorted(three)


def test_page_avec_fichiers_versionnes():
    html = main._versioned_page("index.html").body.decode()
    assert f'/static/style.css?v={main.ASSET_VERSION}"' in html
    assert f'/static/js/core.js?v={main.ASSET_VERSION}"' in html
    assert "/static/fonts/manrope-latin-wght-normal.woff2\"" in html  # police : adresse inchangée (appelée par le CSS)
