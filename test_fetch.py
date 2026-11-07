"""
Test de récupération : télécharge 1 ou 2 fiches et affiche ce qui est extrait. N'écrit RIEN en base.

Usage (depuis la racine du projet, là où se trouve le dossier app/) :
    python3 test_fetch.py URL1 [URL2]
"""
import json
import sys
import time

from app.fetcher import FetchError, fetch_html
from app.parse_series import parse_series_page

urls = sys.argv[1:3]
if not urls:
    sys.exit(__doc__)

for i, url in enumerate(urls):
    if i:
        time.sleep(5)
    print(f"\n=== {url}")
    try:
        data = parse_series_page(fetch_html(url))
    except (FetchError, ValueError) as e:
        print("ÉCHEC :", e)
        continue
    chapters = data.pop("chapters")
    synopsis = data.pop("synopsis") or ""
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"synopsis : {len(synopsis)} caractères, fin « {synopsis[-40:]} »")
    print(f"chapitres : {len(chapters)} (le plus récent : {chapters[0]['number'] if chapters else '-'})")
