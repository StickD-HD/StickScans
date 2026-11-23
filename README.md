# StickScans

Suivi personnel des séries de [scan-manga.com](https://www.scan-manga.com) : l'appli repère les nouveaux chapitres,
garde ta progression et ton historique de lecture, et peut se synchroniser avec AniList.
Elle s'utilise dans le navigateur ou s'installe sur le téléphone (PWA). FastAPI + SQLite, sans Docker.

## Respect du site

Simples requêtes HTTP, avec un User-Agent honnête : aucun navigateur automatisé, aucun contournement.

- Chaque série est vérifiée **à son rythme** : toutes les 3 h quand une sortie est attendue, toutes les 12 h sinon,
  toutes les 48 h si elle ne sort plus rien (environ 4 fois par jour pour une série hebdomadaire).
- Pour tout le serveur : **45 à 90 s entre deux requêtes** et **300 requêtes par jour au plus**.
- Si le site refuse (403, 429, page de protection), **tout s'arrête** : pause de 2 h, puis 6 h, 24 h et 72 h.
  La pause est visible et peut être levée dans **Réglages › Mises à jour**, où l'on peut aussi tout couper.
- Une fiche **déplacée** sur le site (redirection) prend sa nouvelle adresse toute seule. Une fiche **introuvable**
  est signalée sur sa page, revue toutes les 48 h, et sa nouvelle adresse peut être collée à la main
  (menu ⋮ › Changer l'adresse) : chapitres lus et historique sont gardés.

## Installation (Debian, en root)

```bash
apt install -y git python3 python3-venv
git clone https://github.com/StickD-HD/StickScans /git/StickScans
git -C /git/StickScans config user.name "TonPseudoGitHub"
git -C /git/StickScans config user.email "ton@mail"

useradd --system --home /opt/stickscans --shell /usr/sbin/nologin stickscans
python3 -m venv /opt/stickscans/venv
mkdir -p /opt/stickscans/cache /opt/stickscans/moi/data

cp /git/StickScans/.env.example /etc/stickscans-moi.env    # puis adapte-le (port, mot de passe)
chmod 600 /etc/stickscans-moi.env

cp /git/StickScans/outils/stickscans@.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable stickscans@moi

bash /git/StickScans/outils/maj.sh                          # installe, teste, déploie et démarre
```

`moi` est le nom de l'instance (une par personne). Pour en ajouter une : crée `/opt/stickscans/<nom>/data`,
écris `/etc/stickscans-<nom>.env` avec un autre `PORT`, `systemctl enable stickscans@<nom>`, puis relance `maj.sh`.

## Mise à jour

```bash
bash /git/StickScans/outils/maj.sh /root/lot.zip     # applique un zip de modifications (déposé hors du dépôt)
bash /git/StickScans/outils/maj.sh                   # ou : modifications faites directement dans /git/StickScans
```

Le script installe les dépendances, lance les tests, commite, pousse sur GitHub, déploie le commit sur toutes les
instances, les redémarre et vérifie qu'elles répondent. **Si un test échoue, rien n'est commité ni déployé.**
Un zip peut contenir `MESSAGE.txt` (message du commit) et `SUPPRIMER.txt` (fichiers à supprimer, un par ligne).

Revenir à une version précédente (commits listés par `git -C /git/StickScans log --oneline`) :
```bash
bash /git/StickScans/outils/deploy.sh <commit> && systemctl restart stickscans@moi
```
La version qui tourne est affichée en bas de **Réglages**.

## Au quotidien

```bash
systemctl status stickscans@moi                    # état
systemctl restart stickscans@moi                   # redémarrage
journalctl -u stickscans@moi -n 50 --no-pager      # erreurs de l'appli
tail -30 /opt/stickscans/moi/data/logs/scrape.log  # journal des vérifications
```

Tester la lecture d'une fiche sans rien enregistrer (mêmes limites que les instances) :
```bash
/opt/stickscans/venv/bin/python /git/StickScans/outils/test_fiche.py https://www.scan-manga.com/...
```

## Réglages (`/etc/stickscans-<nom>.env`)

Pas de commentaire en fin de ligne dans ce fichier : systemd l'inclurait dans la valeur.

| Variable | Rôle | Défaut |
|---|---|---|
| `PORT` | port de l'instance | obligatoire |
| `AUTH_USERNAME` / `AUTH_PASSWORD` | identifiants de connexion | `admin` / vide |
| `AUTH_REQUIRED` | refuse de démarrer sans mot de passe | `false` |
| `AUTH_COOKIE_SECURE` | cookie seulement en HTTPS (accès par Cloudflare) | `false` |
| `TRUST_CF_CONNECTING_IP` | vraie adresse des visiteurs derrière Cloudflare (sinon 5 mauvais mots de passe tapés par n'importe qui bloquent tout le monde 15 min) | `false` |
| `HOST` | `127.0.0.1` si le tunnel ou le proxy tourne sur cette machine | `0.0.0.0` |
| `SCRAPE_CACHE_DIR` | dossier partagé par les instances (pages, limites, pause) : le même pour toutes | aucun |

Réglages plus rares : `FETCH_MIN_GAP_SECONDS` / `FETCH_MAX_GAP_SECONDS` (45 / 90, jamais moins de 20),
`FETCH_DAILY_LIMIT` (300), `FETCH_CONTACT` (adresse ajoutée au User-Agent), `SCRAPE_CACHE_MAX_AGE_MINUTES` (90),
`AUTH_SESSION_DAYS` (30), `ANILIST_SYNC_MINUTES` (15, 0 = jamais), `READING_MINUTES_PER_CHAPTER` (5).

## Sauvegardes

Chaque nuit à 3 h et à chaque démarrage, dans `data/backups/` de l'instance (7 copies par défaut). Tout se gère dans
**Réglages › Sauvegarde et restauration** : copie manuelle, téléchargement, restauration, export et import.
Ces copies sont sur le même disque que la base : garde aussi un export ailleurs de temps en temps.

## Développement

- `app/` (Python) : `main.py` (démarrage, sécurité, pages), `routes/` (l'API, un fichier par thème : `series`,
  `lecture`, `verifications`, `sauvegardes`, `anilist_api`, `compte`), `database.py`, `scraper.py` (vérifications),
  `schedule.py` (rythme des séries), `fetcher.py` + `site_guard.py` (requêtes et limites), `parse_series.py` (lecture
  des fiches), `covers.py` (couvertures en cache), `anilist.py`, `auth.py`, `backup.py`, `storage.py`, `scrape_cache.py`.
- `static/` : `index.html`, `style.css` et `js/`, un fichier par écran chargé dans l'ordre par `index.html`
  (`core.js` d'abord, `main.js` en dernier). Pas d'étape de compilation.
- `tests/` : `python -m pytest -q`, lancés aussi par GitHub à chaque envoi (`.github/workflows/tests.yml`, mail en cas
  d'échec). `tests/e2e/` parcourt l'interface dans un vrai navigateur : lancé par GitHub, ignoré sur le serveur
  (Playwright n'y est pas installé). Aucune requête vers le site ni vers AniList ; une vraie fiche du site sert de
  référence (`tests/fixtures/`). Si le site change de structure, enregistre une nouvelle fiche à la place.
- `outils/` : `maj.sh`, `deploy.sh`, le service systemd et `test_fiche.py`.
- Une instance = **un seul processus** : les vérifications sont planifiées dans l'appli et partiraient en double
  avec plusieurs workers.
