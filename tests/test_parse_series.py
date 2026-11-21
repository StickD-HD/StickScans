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
