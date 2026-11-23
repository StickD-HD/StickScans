"""Lecture d'une fiche série (app/parse_series.py)."""
import pytest

from app.parse_series import extract_chapters, number_to_float, parse_series_page


@pytest.mark.parametrize("text, expected", [
    ("12", 12.0),
    ("12.5", 12.5),
    ("49-1", 49.01),     # sous-chapitre
    ("49-150", 49.99),   # sous-chapitre plafonné à .99 pour rester avant le chapitre suivant
    (" 7 ", 7.0),
    ("abc", 0.0),        # illisible : rangé en dernier, sans planter
])
def test_number_to_float(text, expected):
    assert number_to_float(text) == pytest.approx(expected)


def test_number_to_float_strict_refuse_un_numero_illisible():
    with pytest.raises(ValueError):
        number_to_float("abc", strict=True)


def test_fiche_complete(series_html):
    data = parse_series_page(series_html)
    assert data["title"] == "Série Test"
    assert data["alt_names"] == ["Test Series", "테스트 시리즈"]  # virgule finale retirée, doublon ignoré
    assert data["cover_url"] == "https://www.scan-manga.com/img/manga/serie-test.jpg"
    assert data["author"] == "Auteur A et Auteur B"
    assert data["genres"] == ["Action", "Fantasy"]  # infobulles retirées
    assert data["category"] == "Manhwa"
    assert data["year"] == "2021"
    assert data["editor"] == "Kakao"
    assert data["status"] == "En cours"
    assert data["team"] == "Team Un, Team Deux"  # une team par lien, séparées
    assert data["popularity"] == 1234
    assert data["last_chapter_number"] == "12"
    assert data["last_chapter_url"].endswith("Chapitre-12-FR_501.html")


def test_synopsis_nettoye(series_html):
    synopsis = parse_series_page(series_html)["synopsis"]
    assert "texte caché" not in synopsis
    assert not synopsis.endswith("£")
    assert synopsis == "Première ligne du résumé.\nDeuxième ligne.\n\nFin du résumé."


def test_liste_des_chapitres(series_html):
    chapters = parse_series_page(series_html)["chapters"]
    by_number = {c["number"]: c for c in chapters}
    # Du plus récent au plus ancien ; le bonus sans numéro est ignoré.
    assert [c["number"] for c in chapters] == ["12", "11.5", "11", "10", "9-1"]
    assert by_number["12"]["link_type"] == "site"
    assert by_number["11.5"]["url"] == "https://www.scan-manga.com/lecture-en-ligne/Serie-Test-Chapitre-11.5-FR_500.html"
    assert by_number["9-1"]["link_type"] == "site"
    # Chapitre licencié : le lien vers la plateforme officielle n'est volontairement pas conservé.
    assert by_number["11"] == {"number": "11", "url": "", "link_type": "aucun"}
    assert by_number["10"] == {"number": "10", "url": "", "link_type": "aucun"}


def test_lien_de_lecture_prioritaire_sur_absence_de_lien():
    # Le même chapitre listé deux fois (sans lien, puis avec) : on garde le lien de lecture.
    html = """
      <li class="chapitre"><div class="chapitre_nom">Chapitre 5</div></li>
      <a href="https://www.scan-manga.com/lecture-en-ligne/X-Chapitre-5-FR_1.html">Lire</a>
    """
    assert extract_chapters(html) == [
        {"number": "5", "url": "https://www.scan-manga.com/lecture-en-ligne/X-Chapitre-5-FR_1.html", "link_type": "site"}
    ]


def test_fiche_tronquee_refusee(series_html):
    # Libellés présents mais valeurs absentes : la page est refusée pour ne pas effacer les données en base.
    truncated = series_html.replace('class="contenu_texte_fiche_technique"', 'class="autre_chose"')
    with pytest.raises(ValueError):
        parse_series_page(truncated)


def test_sans_bouton_dernier_chapitre(series_html):
    without_button = series_html.replace(".ReadLast", ".Autre")
    data = parse_series_page(without_button)
    assert data["last_chapter_number"] == "12"  # repris du plus haut chapitre de la liste


def test_couverture_douteuse_ignoree(series_html):
    html = series_html.replace(
        "https://www.scan-manga.com/img/manga/serie-test.jpg", "javascript:alert(1)"
    )
    assert parse_series_page(html)["cover_url"] is None


# --- Vraie fiche du site (Absolute Regression, novembre 2026) ---

@pytest.fixture
def real_html() -> str:
    from conftest import FIXTURES
    return (FIXTURES / "scan_manga_reelle.html").read_text(encoding="utf-8")


def test_vraie_fiche_est_reconnue(real_html):
    from app.fetcher import CHALLENGE_MARKERS, READY_RE
    assert READY_RE.search(real_html)  # sinon fetch_html refuserait la page (« structure du site changée ? »)
    assert not any(m in real_html[:5000] for m in CHALLENGE_MARKERS)


def test_vraie_fiche_metadonnees(real_html):
    data = parse_series_page(real_html)
    assert data["title"] == "Absolute Regression"
    assert data["alt_names"] == ["Hồi Quy Tuyệt Đối"]
    assert data["cover_url"] == "https://static.scan-manga.com/img/manga/Absolute_Regression_1_2175.jpg"
    assert data["status"] == "En cours"
    assert data["author"] == "Jin-Hwan Park et JP et Jang Yeonghun"
    assert data["category"] == "Manhwa Shonen"
    assert data["year"] == "2024"
    assert data["editor"] == "Naver et Studio JHS"
    assert data["genres"] == ["Action", "Arts martiaux", "Aventure", "Fantaisie", "Historique", "Webcomic"]
    assert data["synopsis"].startswith("Le jeune maître du culte démoniaque")


def test_vraie_fiche_team_et_plateforme(real_html):
    data = parse_series_page(real_html)
    assert data["team"] == "Poséidon Scans"   # case « Plateforme » : lien /team-…
    assert data["platform"] == "Webtoons"     # case « Plateforme » : lien /plateforme-…


def test_vraie_fiche_popularite(real_html):
    # 245 « J'aime » ; avant la correction, la note (4.9/5) et les votes (250) donnaient 495250.
    assert parse_series_page(real_html)["popularity"] == 245


def test_vraie_fiche_chapitres(real_html):
    data = parse_series_page(real_html)
    chapters = {c["number"]: c for c in data["chapters"]}
    assert data["last_chapter_number"] == "127"
    assert data["last_chapter_url"] == "https://www.scan-manga.com/lecture-en-ligne/Absolute-Regression-Chapitre-127-FR_585095.html"
    assert [c["number"] for c in data["chapters"]][:3] == ["127", "126", "125"]
    assert len(chapters) == 17
    assert all(chapters[str(n)]["link_type"] == "site" for n in range(116, 128))
    # Chapitres licenciés : lien webtoons.com volontairement pas conservé.
    assert all(chapters[n] == {"number": n, "url": "", "link_type": "aucun"} for n in ("115", "114", "113", "2", "1"))


def test_team_principale_parmi_plusieurs(real_html):
    """Plusieurs teams dans « Plateforme » : la principale est celle qui a publié le dernier chapitre (même adresse
    /team-…), avec son nom complet ; la liste complète reste disponible."""
    assert new_team_html_present(real_html)
    many = real_html.replace(
        '<a itemprop="name" href="https://www.scan-manga.com/team-1206/Poseidon-Scans.html" style="font-size:70%">Poséidon Scans</a>',
        '<a href="https://www.scan-manga.com/team-11/Astral-Scans.html">Astral Scans</a>'
        '<a href="https://www.scan-manga.com/team-22/Flame-Scans-FR.html">Flame Scans FR</a>'
        '<a itemprop="name" href="https://www.scan-manga.com/team-1206/Poseidon-Scans.html" style="font-size:70%">Poséidon Scans</a>'
        '<a href="https://www.scan-manga.com/team-33/Reaper-Scans.html">Reaper Scans</a>')
    data = parse_series_page(many)
    assert data["team"] == "Astral Scans, Flame Scans FR, Poséidon Scans, Reaper Scans"
    assert data["main_team"] == "Poséidon Scans"


def test_team_principale_inconnue(series_html):
    # Le dernier chapitre ne cite aucune team : pas de team principale (l'appli affiche alors la liste complète).
    assert parse_series_page(series_html)["main_team"] is None


def new_team_html_present(html: str) -> bool:
    return '<a itemprop="name" href="https://www.scan-manga.com/team-1206/Poseidon-Scans.html" style="font-size:70%">Poséidon Scans</a>' in html
