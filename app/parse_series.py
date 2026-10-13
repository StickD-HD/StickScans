"""
Parseur pour une page série de scan-manga.com.
Extrait : titre, titres alternatifs, couverture, statut, synopsis, auteur, année, éditeur,
team, popularité, catégorie, genres, dernier chapitre, et la liste complète des chapitres.
"""
import re
from bs4 import BeautifulSoup

CHAPTER_LINK_RE = re.compile(
    r'(https://www\.scan-manga\.com/lecture-en-ligne/[^"\']*-Chapitre-([0-9]+(?:\.[0-9]+)?)-FR[^"\']*\.html)'
)
ALT_NAME_RE = re.compile(r"alternativeHeadline['\"]?>([^<]+)")


CHAPTER_NAME_RE = re.compile(r"Chapitre\s+([0-9]+(?:[.\-][0-9]+)?)", re.IGNORECASE)
LINK_RANK = {"aucun": 0, "site": 1}


def number_to_float(number, strict: bool = False) -> float:
    """Valeur numérique d'un numéro de chapitre, pour trier. « 49-1 » (sous-chapitre) vaut 49,01."""
    text = str(number).strip()
    match = re.fullmatch(r"(\d+)-(\d+)", text)
    if match:
        return int(match.group(1)) + min(int(match.group(2)), 99) / 100
    try:
        return float(text)
    except ValueError:
        if strict:
            raise
        return 0.0


def extract_chapters(html: str) -> list[dict]:
    """Liste de TOUS les chapitres de la page, avec le type de lien :
    - "site"  : lien de lecture sur scan-manga.com ;
    - "aucun" : chapitre listé mais sans lien de lecture scan-manga (y compris les chapitres licenciés,
                dont le lien pointe vers une plateforme officielle : on ne le garde volontairement pas).
    """
    best: dict[str, dict] = {}

    def put(number: str, url: str, link_type: str):
        current = best.get(number)
        if current is None or LINK_RANK[link_type] > LINK_RANK[current["link_type"]]:
            best[number] = {"number": number, "url": url, "link_type": link_type}

    # 1) liens de lecture scan-manga (comportement d'origine)
    for full_url, number in CHAPTER_LINK_RE.findall(html):
        put(number, full_url, "site")

    # 2) la liste complète de la page, avec ou sans lien
    try:
        soup = BeautifulSoup(html, "html.parser")
        for li in soup.select("li.chapitre"):
            name = li.select_one(".chapitre_nom")
            match = CHAPTER_NAME_RE.search(name.get_text(" ", strip=True)) if name else None
            if not match:
                continue
            number = match.group(1)
            hrefs = [a["href"].strip() for a in li.find_all("a", href=True)]
            site = next((h for h in hrefs if "/lecture-en-ligne/" in h), None)
            if site:
                put(number, site if site.startswith("http") else "https://www.scan-manga.com" + site, "site")
            else:
                put(number, "", "aucun")
    except Exception:
        pass  # structure inattendue : on garde au moins les chapitres avec lien de lecture

    return sorted(best.values(), key=lambda c: number_to_float(c["number"]), reverse=True)


def extract_alt_names(html: str) -> list[str]:
    names = []
    for raw in ALT_NAME_RE.findall(html):
        name = raw.strip().strip(",").strip()
        if name and name not in names:
            names.append(name)
    return names


def _clean_synopsis(tag):
    if not tag:
        return None
    for hidden in tag.select('[style*="visibility:hidden"], [style*="display:none"]'):
        hidden.decompose()
    for br in tag.find_all("br"):
        br.replace_with("\n")
    text = tag.get_text().strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text or None


def parse_series_page(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.select_one('h2[itemprop*="headline"]')
    title = title_tag.get_text(strip=True) if title_tag else None

    alt_names = extract_alt_names(html)

    cover_tag = soup.select_one('meta[property="og:image"]')
    cover_url = cover_tag["content"] if cover_tag else None

    synopsis = _clean_synopsis(soup.select_one('p[itemprop="description"]'))

    status = author = category = year = editor = team = None
    popularity = None
    genres = []

    labels = soup.select(".contenu_titres_fiche_technique li")
    values = soup.select(".contenu_texte_fiche_technique li")
    for label_tag, value_tag in zip(labels, values):
        label_text = label_tag.get_text(strip=True).lower()

        if "auteur" in label_text:
            authors = [a.get_text(strip=True) for a in value_tag.select("a")]
            author = " et ".join(authors) if authors else (value_tag.get_text(strip=True) or None)
        elif "genre" in label_text:
            for a in value_tag.select("a.infoBulle"):
                span = a.find("span")
                if span:
                    span.extract()
                name = a.get_text(strip=True)
                if name:
                    genres.append(name)
        elif "gorie" in label_text:
            category = value_tag.get_text(strip=True) or None
        elif label_text in ("année", "annee"):
            year = value_tag.get_text(strip=True) or None
        elif "diteur" in label_text:
            editor = value_tag.get_text(strip=True) or None
        elif "statut" in label_text:
            status = value_tag.get_text(strip=True) or None
        elif label_text == "team":
            team = value_tag.get_text(strip=True) or None
        elif "popularit" in label_text:
            digits = re.sub(r"\D", "", value_tag.get_text(strip=True))
            popularity = int(digits) if digits else None

    last_chapter_url = None
    last_chapter_number = None
    match = re.search(r"\$\('\.ReadLast'\)\.prop\('href',\s*'([^']+)'\)", html)
    if match:
        last_chapter_url = match.group(1)
        num_match = re.search(r"-Chapitre-([0-9]+(?:\.[0-9]+)?)-", last_chapter_url)
        if num_match:
            last_chapter_number = num_match.group(1)

    chapters = extract_chapters(html)

    # Séries sans bouton « dernier chapitre » : on prend le chapitre le plus élevé de la liste
    if last_chapter_number is None and chapters:
        top = chapters[0]
        last_chapter_number = top["number"]
        last_chapter_url = top["url"] or None

    return {
        "title": title,
        "alt_names": alt_names,
        "cover_url": cover_url,
        "synopsis": synopsis,
        "status": status,
        "author": author,
        "category": category,
        "year": year,
        "editor": editor,
        "team": team,
        "popularity": popularity,
        "genres": genres,
        "last_chapter_number": last_chapter_number,
        "last_chapter_url": last_chapter_url,
        "chapters": chapters,
    }
