"""Couvertures en cache sur le serveur : téléchargement, miniature, adresse servie, ménage, prudence."""
import io

import pytest
from PIL import Image

from app import covers, main, site_guard
from conftest import make_parsed, site_chapter


def png_bytes(w=600, h=900):
    out = io.BytesIO()
    Image.new("RGB", (w, h), (200, 30, 60)).save(out, "PNG")
    return out.getvalue()


class FakeResp:
    def __init__(self, status=200, data=b""):
        self.status_code = status
        self.raw = io.BytesIO(data)
        self.raw.read = (lambda f: (lambda n=-1, decode_content=True: f(n)))(self.raw.read)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


@pytest.fixture
def series(db, monkeypatch):
    monkeypatch.setattr(covers, "_failed", {})
    monkeypatch.setattr(covers, "_host_paused", {})
    monkeypatch.setattr(covers, "_last_request", {})
    monkeypatch.setattr(covers, "GAP_SECONDS", {})
    monkeypatch.setattr(covers, "DEFAULT_GAP", 0)
    parsed = make_parsed([site_chapter(1)])
    parsed["cover_url"] = "https://static.scan-manga.com/img/manga/a.jpg"
    return db.insert_series("https://www.scan-manga.com/a.html", parsed)


def test_mise_en_cache_et_adresse_servie(db, series, monkeypatch):
    calls = []
    monkeypatch.setattr(covers.requests, "get", lambda url, **k: calls.append(url) or FakeResp(200, png_bytes()))
    assert db.get_series_by_id(series)["cover_url"].startswith("https://")  # pas encore en cache
    assert covers.cache_missing() == 1
    url = db.get_series_by_id(series)["cover_url"]
    assert url.startswith("/covers/") and url.endswith(".webp")
    path = covers.path_for(url.rsplit("/", 1)[1])
    with Image.open(path) as img:
        assert img.width == covers.WIDTH and img.format == "WEBP"
    assert covers.cache_missing() == 0 and len(calls) == 1  # déjà en cache : rien de redemandé
    assert main.cover_file(path.name).headers["cache-control"].endswith("immutable")
    assert covers.path_for("../manhwa.db") is None


def test_menage_des_couvertures_inutiles(db, series, monkeypatch):
    monkeypatch.setattr(covers.requests, "get", lambda url, **k: FakeResp(200, png_bytes()))
    covers.cache_missing()
    old = list(covers.covers_dir().glob("*.webp"))
    with db.get_conn() as conn:
        conn.execute("UPDATE series SET cover_url = 'https://static.scan-manga.com/img/manga/b.jpg'")
    covers.cache_missing()
    now = list(covers.covers_dir().glob("*.webp"))
    assert len(now) == 1 and now != old


def test_refus_du_site_et_pause(db, series, monkeypatch):
    calls = []
    monkeypatch.setattr(covers.requests, "get", lambda url, **k: calls.append(url) or FakeResp(403))
    assert covers.cache_missing() == 0
    monkeypatch.setattr(covers, "_failed", {})
    covers.cache_missing()
    assert len(calls) == 1  # domaine en pause 24 h après le refus
    monkeypatch.setattr(covers, "_host_paused", {})
    monkeypatch.setattr(site_guard, "status", lambda: {"blocked": True})
    covers.cache_missing()
    assert len(calls) == 1  # site en pause : aucune image demandée
