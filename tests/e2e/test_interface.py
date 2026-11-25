"""
Parcours de l'interface dans un vrai navigateur (Chromium via Playwright) : bibliothèque, filtres, recherche, fiche,
sélection de chapitres, nouveautés, historique, réglages, aperçu de lecture, vérifications, ajout.

Ignoré si Playwright n'est pas installé (c'est le cas sur le serveur : `outils/maj.sh` ne lance que les tests du
serveur). Sur GitHub, le job « interface » l'installe et le lance à chaque envoi. En local :
    pip install playwright && python -m playwright install chromium && python -m pytest tests/e2e
Aucune requête vers scan-manga ni AniList : base de test préparée à la main, tout ce qui sort de 127.0.0.1 est bloqué.
"""
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
expect = sync_api.expect  # attend (jusqu'à 10 s) que la condition soit vraie : pas de pause fixe, robuste sur une machine lente
expect.set_options(timeout=10_000)
SHOTS = Path(__file__).resolve().parent / "captures"  # capture de l'écran quand un test échoue

ROOT = Path(__file__).resolve().parents[2]
PYTHON = os.environ.get("E2E_PYTHON", sys.executable)  # Python qui a les dépendances de l'appli

SEED = r'''
import sys; sys.path.insert(0, ".")
from datetime import datetime, timedelta, timezone
from app import database
database.init_db()
def chap(n, link=True):
    return {"number": str(n), "url": f"https://www.scan-manga.com/lecture-en-ligne/S-Chapitre-{n}-FR_1.html" if link else "",
            "link_type": "site" if link else "aucun"}
def parsed(title, status, chapters, **kw):
    d = {"title": title, "alt_names": [], "cover_url": "", "synopsis": "Résumé de " + title, "status": status,
         "author": "Auteur", "category": "Manhwa", "year": "2024", "editor": "Naver", "team": "Team X",
         "platform": "Webtoons", "popularity": 100, "genres": ["Action", "Fantaisie"],
         "last_chapter_number": chapters[0]["number"], "last_chapter_url": chapters[0]["url"], "chapters": chapters}
    d.update(kw); return d
a = database.insert_series("https://www.scan-manga.com/a.html", parsed("Alpha", "En cours", [chap(n) for n in range(30, 0, -1)]))
b = database.insert_series("https://www.scan-manga.com/b.html", parsed("Beta", "Terminé", [chap(n, n > 5) for n in range(10, 0, -1)]))
c = database.insert_series("https://www.scan-manga.com/c.html", parsed("Gamma", "En pause", [chap(n) for n in range(5, 0, -1)]))
database.update_series_result(a, parsed("Alpha", "En cours", [chap(n) for n in range(32, 0, -1)]))
database.mark_read_up_to(a, 14.0); database.mark_all_read(b)
cat = database.create_category("Favoris"); database.add_series_to_category(a, cat)
run = database.start_check_run("auto", 2); database.add_check_item(run, a, "Alpha", 1.2, True, ["31", "32"], None)
database.add_check_item(run, c, "Gamma", 0.4, False, [], "HTTP 404 : fiche introuvable"); database.finish_check_run(run, 70.0)
database.set_next_check(a, datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=2), "window")
'''


@pytest.fixture(scope="module")
def base_url(tmp_path_factory):
    work = tmp_path_factory.mktemp("appli")
    for name in ("app", "static"):
        shutil.copytree(ROOT / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
    env = {**os.environ, "AUTH_SECRET": "e2e", "AUTH_PASSWORD": "", "ANILIST_SYNC_MINUTES": "0"}
    subprocess.run([PYTHON, "-c", SEED], cwd=work, env=env, check=True)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = subprocess.Popen([PYTHON, "-m", "uvicorn", "app.main:app", "--port", str(port)], cwd=work, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/api/auth/status")
            break
        except OSError:
            time.sleep(0.1)
    yield url
    server.terminate()
    server.wait(10)


@pytest.fixture
def page(base_url, request):
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 402, "height": 874})
        pg.route("**/*", lambda r: r.abort() if "127.0.0.1" not in r.request.url and not r.request.url.startswith("data:") else r.continue_())
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("dialog", lambda d: d.accept())
        pg.errors = errors
        pg.goto(base_url + "/")
        pg.wait_for_selector("#grid .card:not(.skeleton)")
        yield pg
        if getattr(request.node, "rep_call", None) is not None and request.node.rep_call.failed:
            SHOTS.mkdir(exist_ok=True)
            pg.screenshot(path=str(SHOTS / f"{request.node.name}.png"), full_page=True)
        browser.close()
        assert errors == [], f"erreurs JavaScript : {errors}"


def test_bibliotheque_filtres_recherche(page):
    grid = page.locator("#grid .card")
    expect(grid).to_have_count(3)
    page.click("#filter-toggle-btn")
    page.select_option("#status-select", "Terminé")
    expect(grid).to_have_count(1)
    expect(grid).to_contain_text("Beta")
    expect(page.locator("#filter-badge")).to_have_text("1")
    page.select_option("#status-select", "")
    page.click("#filter-modal-close")
    page.click("#search-toggle-btn")
    page.fill("#search-input", "gam")
    expect(grid).to_have_count(1)
    expect(grid).to_contain_text("Gamma")


def test_fiche_et_chapitres(page):
    page.click("#grid .card:has-text('Alpha')")
    expect(page.locator("#detail-title")).to_have_text("Alpha")
    # text_content : la ligne peut être masquée si la place manque à côté de la couverture (selon les polices)
    expect(page.locator("#detail-progress")).to_contain_text("14 / 32", use_inner_text=False)
    expect(page.locator("#chapters-list li")).to_have_count(32)
    # appui long (clic droit à la souris) : sélection avec ce chapitre, puis « Lu »
    page.click("#chapters-list li:has-text('Chapitre 20')", button="right")
    expect(page.locator("#selection-count")).to_have_text("1 sélectionné")
    expect(page.locator("#bulk-upto-btn")).to_be_visible()  # un seul chapitre : « Lu jusqu'ici » proposé
    page.click("#bulk-upto-btn")
    expect(page.locator("#detail-progress")).to_contain_text("20 / 32", use_inner_text=False)
    page.click("#back-btn")
    expect(page.locator("#library-view")).to_be_visible()


def test_nouveautes_historique(page):
    page.click(".nav-btn[data-view='updates-view']")
    expect(page.locator("#updates-list")).to_contain_text("Chapitres 31 à 32")  # même série, même jour : une ligne
    page.click(".nav-btn[data-view='history-view']")
    expect(page.locator("#history-list")).to_contain_text("Alpha")


def test_reglages_et_ecrans_secondaires(page):
    page.click(".nav-btn[data-view='settings-view']")
    for name, check in [("display", "#display-mode"), ("categories", "#category-manage-list"),
                        ("storage", "#storage-list"), ("backup", "#backup-list")]:
        page.click(f"#settings-home [data-page='{name}']")
        expect(page.locator(check)).to_be_visible()
        page.click("#settings-back-btn")
        expect(page.locator("#settings-home")).to_be_visible()
    page.click("#open-reading-btn")
    expect(page.locator("#reading-content .rv-hero")).to_be_visible()
    page.click("#reading-back-btn")
    page.click("#open-checks-btn")
    expect(page.locator("#checks-list .run-row").first).to_be_visible()
    page.click("#checks-back-btn")


def test_ajout_et_selection_de_series(page):
    page.click("#home-menu-btn")
    page.click("#add-btn")
    page.fill("#add-url", "https://m.scan-manga.com/x.html\nhttps://exemple.fr\n")
    expect(page.locator("#add-count")).to_contain_text("1")
    page.click("#add-cancel")
    expect(page.locator("#add-modal")).to_be_hidden()
    page.click("#home-menu-btn")
    page.click("#library-select-btn")
    page.click("#grid .card:has-text('Gamma')")
    expect(page.locator("#library-selection-count")).to_have_text("1 sélectionnée")
    page.click("#library-actions-btn")
    page.click("[data-bulk='mark_read']")
    expect(page.locator("#library-toolbar")).to_be_hidden()


def test_etats_de_lecture(page):
    tabs = page.locator("#state-tabs .state-tab")
    expect(tabs.first).to_contain_text("Tout")
    # Alpha : commencée -> en cours ; Beta : tout lu et terminée sur le site -> terminé
    # (les autres tests du fichier partagent la même base : on ne compte pas Gamma, qu'ils peuvent modifier)
    expect(page.locator("#state-tabs [data-state='reading']")).to_be_visible()
    expect(page.locator("#state-tabs [data-state='completed']")).to_contain_text("1")
    page.click("#grid .card:has-text('Alpha')")
    expect(page.locator("#state-btn-label")).to_have_text("En cours")
    page.click("#state-btn")
    page.click("#state-options [data-pick='paused']")
    expect(page.locator("#state-btn-label")).to_have_text("En pause")
    page.click("#back-btn")
    page.click("#state-tabs [data-state='paused']")
    expect(page.locator("#grid .card")).to_have_count(1)
    expect(page.locator("#grid .card")).to_contain_text("Alpha")
    # plusieurs séries d'un coup
    page.click("#state-tabs [data-state='']")
    page.click("#home-menu-btn")
    page.click("#library-select-btn")
    page.click("#library-select-all-btn")
    page.click("#library-actions-btn")
    page.click("[data-bulk='state']")
    page.click("#state-options [data-pick='dropped']")
    expect(page.locator("#state-tabs [data-state='dropped']")).to_contain_text("3")
