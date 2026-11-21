"""Garde du site et requêtes (app/site_guard.py, app/fetcher.py). Aucune vraie requête n'est envoyée."""
import json

import pytest

from app import fetcher, site_guard


@pytest.fixture
def guard(db):
    """État du site neuf, dans le dossier temporaire de la base du test."""
    return site_guard


def test_ecart_minimal_jamais_sous_20_secondes():
    assert site_guard.MIN_GAP_SECONDS >= 20
    assert site_guard.MAX_GAP_SECONDS >= site_guard.MIN_GAP_SECONDS


def test_une_requete_a_la_fois(guard):
    assert guard.reserve(now=1000.0) == ("ok", 0.0)
    answer, wait = guard.reserve(now=1001.0)
    assert answer == "wait" and guard.MIN_GAP_SECONDS - 1 <= wait <= guard.MAX_GAP_SECONDS
    assert guard.reserve(now=1000.0 + guard.MAX_GAP_SECONDS + 1)[0] == "ok"


def test_plafond_quotidien(guard, monkeypatch):
    monkeypatch.setattr(guard, "DAILY_LIMIT", 2)
    t = 1_000_000.0
    assert guard.reserve(now=t)[0] == "ok"
    assert guard.reserve(now=t + 100)[0] == "ok"
    assert guard.reserve(now=t + 200)[0] == "quota"
    assert guard.reserve(now=t + 86400)[0] == "ok"  # le lendemain, le compteur repart


def test_pause_de_plus_en_plus_longue(guard):
    t = 1_000_000.0
    durations = []
    for i in range(5):
        durations.append(guard.record_block("HTTP 403", now=t))
        t += durations[-1] + 60
    assert [d / 3600 for d in durations] == [2, 6, 24, 72, 72]


def test_pause_bloque_toutes_les_requetes(guard):
    guard.record_block("HTTP 403", now=1000.0)
    answer, remaining = guard.reserve(now=1000.0 + 3600)
    assert answer == "blocked" and remaining == pytest.approx(3600)
    assert guard.reserve(now=1000.0 + 2 * 3600 + 1)[0] == "ok"


def test_duree_demandee_par_le_site_respectee(guard):
    assert guard.record_block("HTTP 429", retry_after=5 * 3600, now=0.0) == 5 * 3600
    assert guard.record_block("HTTP 429", retry_after=60, now=10 * 3600.0) == 6 * 3600  # jamais moins que l'échelle


def test_compteur_de_refus_remis_a_zero_seulement_apres_48h_sans_refus(guard):
    guard.record_block("HTTP 403", now=0.0)
    guard.record_success(now=3 * 3600.0)
    assert guard.status(now=3 * 3600.0)["strikes"] == 1
    guard.record_success(now=49 * 3600.0)
    assert guard.status(now=49 * 3600.0)["strikes"] == 0


def test_pause_levee_a_la_main_garde_le_compteur(guard):
    guard.record_block("HTTP 403", now=0.0)
    guard.clear_block()
    assert guard.reserve(now=10.0)[0] == "ok"
    assert guard.record_block("HTTP 403", now=20.0) == 6 * 3600  # 2e refus


def test_etat_enregistre_sur_disque(guard):
    """La pause survit à un redémarrage et se partage avec les autres instances : elle est dans un fichier."""
    guard.record_block("HTTP 403", now=0.0)
    saved = json.loads((guard.state_dir() / guard.STATE_FILE).read_text())
    assert saved["strikes"] == 1 and saved["blocked_until"] == 2 * 3600


# --- fetcher ---

class FakeResponse:
    def __init__(self, status, text="", headers=None):
        self.status_code = status
        self.content = text.encode()
        self.headers = headers or {}


@pytest.fixture
def no_gap(guard, monkeypatch):
    monkeypatch.setattr(site_guard, "MIN_GAP_SECONDS", 0.0)
    monkeypatch.setattr(site_guard, "MAX_GAP_SECONDS", 0.0)


def test_refus_du_site_met_tout_en_pause(no_gap, monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return FakeResponse(403, headers={"Retry-After": "120"})

    monkeypatch.setattr(fetcher._session, "get", get)
    with pytest.raises(fetcher.BlockedError, match="pause de 2 h"):
        fetcher.fetch_html("https://www.scan-manga.com/a.html")
    with pytest.raises(fetcher.BlockedError, match="en pause"):
        fetcher.fetch_html("https://www.scan-manga.com/b.html")
    assert len(calls) == 1  # la seconde requête n'est jamais partie


def test_page_de_protection_compte_comme_un_refus(no_gap, monkeypatch):
    monkeypatch.setattr(fetcher._session, "get", lambda url, **kw: FakeResponse(200, "<title>Just a moment...</title>"))
    with pytest.raises(fetcher.BlockedError):
        fetcher.fetch_html("https://www.scan-manga.com/a.html")
    assert site_guard.status()["blocked"]


def test_page_normale(no_gap, monkeypatch, series_html):
    monkeypatch.setattr(fetcher._session, "get", lambda url, **kw: FakeResponse(200, series_html))
    assert fetcher.fetch_html("https://www.scan-manga.com/a.html") == series_html
    st = site_guard.status()
    assert st["requests_today"] == 1 and not st["blocked"]


def test_erreur_404_ne_met_pas_en_pause(no_gap, monkeypatch):
    monkeypatch.setattr(fetcher._session, "get", lambda url, **kw: FakeResponse(404))
    with pytest.raises(fetcher.FetchError) as info:
        fetcher.fetch_html("https://www.scan-manga.com/a.html")
    assert not isinstance(info.value, fetcher.BlockedError)
    assert not site_guard.status()["blocked"]


def test_tour_pas_encore_venu(guard, monkeypatch):
    monkeypatch.setattr(fetcher._session, "get", lambda url, **kw: pytest.fail("aucune requête ne doit partir"))
    guard.reserve()  # une autre instance vient d'envoyer sa requête
    with pytest.raises(fetcher.SiteBusy):
        fetcher.fetch_html("https://www.scan-manga.com/a.html", max_wait=0)
