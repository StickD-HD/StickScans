# StickScans

Suivi personnel de séries de [scan-manga.com](https://www.scan-manga.com) : l'appli vérifie régulièrement les fiches
des séries que tu suis, détecte les nouveaux chapitres, garde ton état de lecture et peut synchroniser ta progression
avec AniList. Elle s'utilise depuis un navigateur (FastAPI + SQLite).

## Comment elle récupère les pages

Par de simples requêtes HTTP, avec un User-Agent qui s'identifie honnêtement. Aucun navigateur automatisé, aucun
contournement. Lis les conditions d'utilisation du site avant d'utiliser l'appli.

- **Chaque série à son rythme** : l'appli déduit le rythme de sortie de chaque série et la vérifie toutes les 3 h quand
  une sortie est attendue, toutes les 12 h sinon, toutes les 48 h si elle ne sort plus rien. Une série hebdomadaire
  est vérifiée environ 4 fois par jour (au lieu de 24), avec un délai moyen de 4 h avant qu'un chapitre apparaisse.
- **Requêtes espacées** de 45 à 90 s, et au plus 300 par jour, **pour toutes les instances du serveur ensemble**
  (état partagé dans `SCRAPE_CACHE_DIR`). Une page déjà récupérée par une instance depuis moins de 90 min est
  reprise par l'autre sans solliciter le site.
- **Refus du site** (403, 429, page de protection) : tout s'arrête et le serveur entier se met en pause 2 h, puis 6 h,
  24 h et 72 h aux refus suivants (ou plus si le site le demande). La pause survit aux redémarrages ; elle est visible
  et peut être levée dans **Réglages > Mises à jour**, où l'on peut aussi couper complètement les vérifications.

## Installation (Debian, sans Docker)

Tout se fait en root. Les chemins ci-dessous sont des exemples : `/git/StickScans` pour le dépôt,
`/opt/stickscans/<instance>` pour chaque instance qui tourne.

**1. Outils de base**
```bash
apt install -y git python3 python3-venv
git clone https://github.com/StickD-HD/StickScans /git/StickScans
```

**2. Utilisateur, dossiers et environnement Python**
```bash
useradd --system --home /opt/stickscans --shell /usr/sbin/nologin stickscans
mkdir -p /opt/stickscans/moi /opt/stickscans/cache
python3 -m venv /opt/stickscans/venv
/opt/stickscans/venv/bin/pip install -r /git/StickScans/requirements.txt   # versions figées et testées
```

**3. Script de déploiement** (copie le code du dépôt vers chaque instance, sans toucher à `data/`)
```bash
cat > /opt/stickscans/deploy.sh <<'EOF'
#!/bin/sh
for i in moi; do          # ajoute ici le nom de chaque instance
  rm -rf /opt/stickscans/$i/app /opt/stickscans/$i/static
  cp -r /git/StickScans/app /git/StickScans/static /opt/stickscans/$i/
done
chown -R stickscans: /opt/stickscans
EOF
chmod +x /opt/stickscans/deploy.sh
/opt/stickscans/deploy.sh
```

**4. Réglages de l'instance** : copie `.env.example` vers `/etc/stickscans-moi.env`, adapte-le, puis
```bash
chmod 600 /etc/stickscans-moi.env
```

**5. Service systemd**
```bash
cat > /etc/systemd/system/stickscans@.service <<'EOF'
[Unit]
Description=StickScans (%i)
After=network-online.target
Wants=network-online.target

[Service]
User=stickscans
WorkingDirectory=/opt/stickscans/%i
EnvironmentFile=/etc/stickscans-%i.env
ExecStart=/opt/stickscans/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now stickscans@moi
```

Ouvre ensuite `http://IP-DU-SERVEUR:<PORT>`.

## Gestion au quotidien

```bash
systemctl status stickscans@moi                    # état
systemctl restart stickscans@moi                   # redémarrer (aussi stop / start)
journalctl -u stickscans@moi -n 50 --no-pager      # erreurs de l'appli
tail -30 /opt/stickscans/moi/data/logs/scrape.log  # journal des vérifications
```

## Mise à jour

```bash
cd /git/StickScans && git pull
/opt/stickscans/venv/bin/pip install -r requirements-dev.txt   # seulement si requirements*.txt a changé
/opt/stickscans/venv/bin/python -m pytest -q                    # facultatif : tests
/opt/stickscans/deploy.sh
systemctl restart stickscans@moi
```

## Tests

Facultatif, à lancer depuis le dépôt avant un déploiement (aucune requête vers le site ni vers AniList) :
```bash
/opt/stickscans/venv/bin/pip install -r /git/StickScans/requirements-dev.txt   # une seule fois
cd /git/StickScans && /opt/stickscans/venv/bin/python -m pytest -q
```

## Plusieurs instances

Chaque personne a son instance (sa base, son compte, son port). Pour en ajouter une : crée
`/opt/stickscans/<nom>`, ajoute `<nom>` dans la boucle de `deploy.sh`, écris `/etc/stickscans-<nom>.env` avec un
autre `PORT`, puis `systemctl enable --now stickscans@<nom>`. Donne à toutes le même `SCRAPE_CACHE_DIR` : elles se
partagent alors les pages récupérées, l'espacement des requêtes, le plafond quotidien et la pause après un refus.

## Réglages (fichier `/etc/stickscans-<instance>.env`)

| Variable | Rôle | Défaut |
|---|---|---|
| `PORT` | port d'écoute de l'instance | (obligatoire) |
| `AUTH_USERNAME` / `AUTH_PASSWORD` | identifiants (sans mot de passe, l'appli est ouverte à tous) | `admin` / vide |
| `AUTH_REQUIRED` | `true` : refuse de démarrer sans mot de passe | `false` |
| `AUTH_COOKIE_SECURE` | `true` derrière un reverse proxy HTTPS | `false` |
| `FETCH_MIN_GAP_SECONDS` / `FETCH_MAX_GAP_SECONDS` | écart aléatoire entre deux requêtes vers le site, toutes instances confondues (jamais moins de 20 s) | 45 / 90 |
| `FETCH_DAILY_LIMIT` | requêtes vers le site par jour (UTC), toutes instances confondues | 300 |
| `FETCH_CONTACT` | adresse ajoutée au User-Agent (facultatif) | vide |
| `SCRAPE_CACHE_DIR` | dossier partagé entre instances : pages récupérées et état des requêtes | désactivé |
| `SCRAPE_CACHE_MAX_AGE_MINUTES` | âge maximal d'une copie réutilisable | 90 |
| `SCRAPE_CACHE_MODE` | `both` (lit et écrit), `read`, `write` ou `off` ; seulement si `SCRAPE_CACHE_DIR` est défini | `both` |
| `TRUST_CF_CONNECTING_IP` | `true` derrière un tunnel Cloudflare | `false` |
| `AUTH_SESSION_DAYS` | durée d'une session de connexion, en jours | 30 |
| `AUTH_SECRET` | clé de signature des sessions (sinon générée dans `data/auth_secret`) | générée |
| `AUTH_COOKIE_NAME` | nom du cookie de session (déjà différent pour chaque instance) | automatique |
| `ANILIST_SYNC_MINUTES` | fréquence de la copie de l'état AniList dans l'appli (0 = désactivée) | 15 |
| `READING_MINUTES_PER_CHAPTER` | durée estimée d'un chapitre, pour l'aperçu de lecture | 5 |

Ne sont plus utilisés (la fréquence est calculée pour chaque série) : `CHECK_INTERVAL_HOURS`, `CHECK_OFFSET_MINUTES`,
`CHECK_MIN_DELAY_SECONDS`, `CHECK_MAX_DELAY_SECONDS`, `FETCH_BLOCK_COOLDOWN_MINUTES`, `FETCH_BACKEND`. L'appli le
signale dans `journalctl` s'ils sont encore dans le fichier `.env`.

## Sauvegardes

La base est sauvegardée chaque nuit à 3 h (et au démarrage) dans `data/backups/`. Tout se règle depuis
**Réglages > Sauvegarde et restauration** : sauvegarde automatique activée ou non, nombre de copies gardées (7 par défaut),
sauvegarde manuelle, téléchargement, **restauration** d'une copie (l'état d'avant est gardé dans une copie
« avant restauration »), export et import de la base.

Ces copies sont sur le même disque : fais en plus une copie de `/opt/stickscans/*/data/` ailleurs de temps en temps.

## Réglages dans l'appli

- **Affichage** : grille ou liste, couvertures par ligne, informations affichées (propre à chaque appareil).
- **Catégories** : créer, renommer, supprimer.
- **Mises à jour** : couper les vérifications automatiques, voir l'état du site (pause, requêtes du jour) et lever
  une pause, ignorer les séries terminées, avec des chapitres non lus, ou jamais lues.
- **Stockage** : espace utilisé, vider le cache des pages, effacer les journaux, optimiser la base.
- **Sauvegarde et restauration**, **AniList**, **Aperçu de lecture** et **Vérifications**.
