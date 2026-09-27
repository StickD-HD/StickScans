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


def extract_chapters(html: str) -> list[dict]:
    seen = {}
    for full_url, number in CHAPTER_LINK_RE.findall(html):
        if number not in seen:
            seen[number] = full_url
    chapters = [{"number": num, "url": url} for num, url in seen.items()]
    chapters.sort(key=lambda c: float(c["number"]), reverse=True)
    return chapters


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
