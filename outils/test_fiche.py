"""
Teste la lecture d'une ou deux fiches scan-manga.com et affiche ce qui en est extrait. N'écrit RIEN dans les bases.

    /opt/stickscans/venv/bin/python /git/StickScans/outils/test_fiche.py URL [URL2]

Les requêtes passent par les mêmes règles que les instances (état partagé dans SCRAPE_CACHE_DIR, lu dans
/etc/stickscans-*.env) : pause en cours après un refus du site, espacement de 45 à 90 s, plafond quotidien.
Sans dossier partagé trouvé, le script refuse de tourner plutôt que d'interroger le site sans ces protections.
"""
import glob
import json
import os
import sys
from pathlib import Path


def shared_dir() -> str | None:
    if os.environ.get("SCRAPE_CACHE_DIR"):
        return os.environ["SCRAPE_CACHE_DIR"]
    for env_file in sorted(glob.glob("/etc/stickscans-*.env")):
        for line in Path(env_file).read_text(encoding="utf-8").splitlines():
            if line.startswith("SCRAPE_CACHE_DIR="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return None


urls = sys.argv[1:3]
if not urls:
    sys.exit(__doc__)
folder = shared_dir()
if not folder:
    sys.exit("SCRAPE_CACHE_DIR introuvable (ni dans l'environnement, ni dans /etc/stickscans-*.env) : "
             "sans lui, ce test ne verrait pas la pause et l'espacement partagés par les instances.")
os.environ["SCRAPE_CACHE_DIR"] = folder  # à définir AVANT d'importer l'appli

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.fetcher import FetchError, fetch_html  # noqa: E402
from app.parse_series import parse_series_page  # noqa: E402

for url in urls:
    print(f"\n=== {url}")
    try:
        data = parse_series_page(fetch_html(url, max_wait=300))  # attend son tour si une instance vient de passer
    except (FetchError, ValueError) as e:
        print("ÉCHEC :", e)
        continue
    chapters = data.pop("chapters")
    synopsis = data.pop("synopsis") or ""
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"synopsis : {len(synopsis)} caractères, fin « {synopsis[-40:]} »")
    with_link = sum(1 for c in chapters if c["link_type"] == "site")
    print(f"chapitres : {len(chapters)} dont {with_link} avec lien (le plus récent : {chapters[0]['number'] if chapters else '-'})")
