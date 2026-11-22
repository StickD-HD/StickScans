"""Actions groupées sur plusieurs séries, filtre « Suivi AniList » et sauvegarde Google Drive (Google simulé)."""
import sqlite3
from contextlib import closing

import pytest
from fastapi import BackgroundTasks, HTTPException

from app import anilist, gdrive, main
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


# --- Google Drive ---

class FakeResponse:
    def __init__(self, status=200, body=None, content=b"", headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}
        self.content = content or (b"{}" if body is not None else b"")

    def json(self):
        if self._body is None:
            raise ValueError
        return self._body


class FakeGoogle:
    """Google simulé : connexion par code, dossier, envoi, liste, suppression, téléchargement."""

    def __init__(self):
        self.files = {}
        self.uploaded = {}
        self.polls = 0
        self.next_id = 0

    def post(self, url, data=None, params=None, timeout=None):
        if url == gdrive.DEVICE_URL:
            return FakeResponse(body={"device_code": "dc", "user_code": "ABCD-EFGH",
                                      "verification_url": "https://www.google.com/device", "interval": 5,
                                      "expires_in": 1800})
        if url == gdrive.TOKEN_URL and data["grant_type"].endswith("device_code"):
            self.polls += 1
            if self.polls == 1:
                return FakeResponse(428, {"error": "authorization_pending"})
            return FakeResponse(body={"access_token": "at", "refresh_token": "rt", "expires_in": 3600})
        if url == gdrive.TOKEN_URL:
            return FakeResponse(body={"access_token": "at2", "expires_in": 3600})
        return FakeResponse(body={})

    def request(self, method, url, headers=None, params=None, json=None, data=None, timeout=None):
        assert headers["Authorization"].startswith("Bearer ")
        if url.endswith("/about"):
            return FakeResponse(body={"user": {"emailAddress": "moi@gmail.com"}})
        if method == "POST" and url == f"{gdrive.API}/files":
            self.next_id += 1
            fid = f"dossier{self.next_id}"
            self.files[fid] = {"name": json["name"], "folder": True}
            return FakeResponse(body={"id": fid})
        if method == "POST" and url == gdrive.UPLOAD_API:
            self.pending = json
            return FakeResponse(body={}, headers={"Location": "https://upload/session"})
        if method == "PUT" and url == "https://upload/session":
            self.next_id += 1
            fid = f"f{self.next_id}"
            self.files[fid] = {"name": self.pending["name"], "created": f"2026-11-22T10:{self.next_id:02d}:00Z",
                               "size": len(data)}
            self.uploaded[fid] = data
            return FakeResponse(body={"id": fid})
        if method == "GET" and url == f"{gdrive.API}/files":
            files = [{"id": k, "name": v["name"], "size": str(v["size"]), "createdTime": v["created"]}
                     for k, v in self.files.items() if not v.get("folder")]
            files.sort(key=lambda f: f["createdTime"], reverse=True)
            return FakeResponse(body={"files": files})
        if method == "GET" and url.startswith(f"{gdrive.API}/files/"):
            fid = url.rsplit("/", 1)[1]
            if fid not in self.files:
                return FakeResponse(404, {"error": {"message": "not found"}})
            if params and params.get("alt") == "media":
                return FakeResponse(content=self.uploaded[fid])
            return FakeResponse(body={"id": fid, "trashed": False})
        if method == "DELETE":
            self.files.pop(url.rsplit("/", 1)[1], None)
            return FakeResponse(204)
        raise AssertionError((method, url))


@pytest.fixture
def google(db, monkeypatch):
    fake = FakeGoogle()
    monkeypatch.setattr(gdrive.requests, "post", fake.post)
    monkeypatch.setattr(gdrive.requests, "request", fake.request)
    monkeypatch.setattr(gdrive, "_pending", None)
    monkeypatch.setattr(gdrive, "_access", {"token": None, "expires": 0.0})
    return fake


def connect():
    gdrive.save_client("123-abc.apps.googleusercontent.com", "secret")
    assert gdrive.start_connect()["pending"]["user_code"] == "ABCD-EFGH"
    assert gdrive.poll_connect()["state"] == "pending"
    status = gdrive.poll_connect()
    assert status["state"] == "connected" and status["email"] == "moi@gmail.com"


def test_identifiant_client_controle(db):
    with pytest.raises(gdrive.DriveError):
        gdrive.save_client("pas-un-id", "s")
    with pytest.raises(gdrive.DriveError):
        gdrive.start_connect()


def test_envoi_sans_secret_et_rotation(google, tmp_path):
    db = gdrive.database
    db.set_setting("anilist_token", "jeton-anilist")
    connect()
    gdrive.set_keep(2)
    for _ in range(3):
        gdrive.upload_now()
    files = gdrive.list_files()
    assert len(files) == 2  # seules les 2 dernières copies restent
    copy = tmp_path / "copie.db"
    copy.write_bytes(google.uploaded[files[0]["id"]])
    with closing(sqlite3.connect(copy)) as conn:
        keys = {r[0] for r in conn.execute("SELECT key FROM app_settings")}
    assert not keys & {"anilist_token", "gdrive_refresh_token", "gdrive_client_secret"}
    assert gdrive.get_status()["last_upload"]


def test_envoi_automatique_au_plus_toutes_les_20h(google):
    connect()
    gdrive.upload_if_due()
    gdrive.upload_if_due()
    assert len(gdrive.list_files()) == 1


def test_restauration_depuis_le_drive_garde_les_acces(google, three, monkeypatch, tmp_path):
    from app import backup
    db = gdrive.database
    monkeypatch.setattr(backup, "DB_PATH", db.DB_PATH)
    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path / "backups")
    db.set_setting("anilist_token", "jeton-anilist")
    connect()
    gdrive.upload_now()
    file_id = gdrive.list_files()[0]["id"]
    db.delete_series(three[0])
    main.gdrive_restore(file_id)
    assert len(db.get_all_series()) == 3
    assert db.get_setting("anilist_token") == "jeton-anilist"
    assert gdrive.is_connected()
    with pytest.raises(HTTPException) as info:
        main.gdrive_restore("autre-fichier")
    assert info.value.status_code == 404


def test_deconnexion(google):
    connect()
    gdrive.disconnect()
    assert not gdrive.is_connected() and gdrive.is_configured()
