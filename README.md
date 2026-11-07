# StickScans

Suivi personnel de séries de [scan-manga.com](https://www.scan-manga.com) : l'appli vérifie régulièrement les fiches
des séries que tu suis, détecte les nouveaux chapitres, garde ton état de lecture et peut synchroniser ta progression
avec AniList. Elle s'utilise depuis un navigateur (FastAPI + SQLite).

## Comment elle récupère les pages

Par de simples requêtes HTTP, avec un User-Agent qui s'identifie honnêtement. Aucun navigateur automatisé, aucun
contournement : si le site répond 403 ou 429, ou renvoie une page de protection, la collecte s'arrête et se met en
pause (60 min par défaut). Les requêtes sont espacées de quelques secondes. Lis les conditions d'utilisation du site
avant d'utiliser l'appli.

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
/opt/stickscans/venv/bin/pip install -r /git/StickScans/requirements.txt
/opt/stickscans/venv/bin/pip install requests==2.32.3 urllib3==2.3.0   # versions testées
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
/opt/stickscans/deploy.sh
systemctl restart stickscans@moi
```

## Plusieurs instances

Chaque personne a son instance (sa base, son compte, son port). Pour en ajouter une : crée
`/opt/stickscans/<nom>`, ajoute `<nom>` dans la boucle de `deploy.sh`, écris `/etc/stickscans-<nom>.env` avec un
autre `PORT`, puis `systemctl enable --now stickscans@<nom>`. Avec le même `SCRAPE_CACHE_DIR`, les instances se
partagent les pages récupérées et sollicitent moins le site. Décale leurs vérifications avec `CHECK_OFFSET_MINUTES`.

## Réglages (fichier `/etc/stickscans-<instance>.env`)

| Variable | Rôle | Défaut |
|---|---|---|
| `PORT` | port d'écoute de l'instance | (obligatoire) |
| `AUTH_USERNAME` / `AUTH_PASSWORD` | identifiants (sans mot de passe, l'appli est ouverte à tous) | `admin` / vide |
| `AUTH_REQUIRED` | `true` : refuse de démarrer sans mot de passe | `false` |
| `AUTH_COOKIE_SECURE` | `true` derrière un reverse proxy HTTPS | `false` |
| `CHECK_INTERVAL_HOURS` | fréquence des vérifications | 1 |
| `CHECK_OFFSET_MINUTES` | minute de l'heure où lancer la vérification | aucune |
| `CHECK_MIN_DELAY_SECONDS` / `CHECK_MAX_DELAY_SECONDS` | pause aléatoire entre deux séries | 3 / 8 |
| `FETCH_CONTACT` | adresse ajoutée au User-Agent (facultatif) | vide |
| `FETCH_BLOCK_COOLDOWN_MINUTES` | pause après un 403/429 | 60 |
| `SCRAPE_CACHE_DIR` | dossier de pages partagé entre instances | désactivé |
| `SCRAPE_CACHE_MAX_AGE_MINUTES` | âge maximal d'une copie réutilisable | 40 |
| `TRUST_CF_CONNECTING_IP` | `true` derrière un tunnel Cloudflare | `false` |

## Sauvegardes

La base est sauvegardée chaque nuit à 3 h dans `data/backups/` (7 copies). Ces copies sont sur le même disque : fais en
plus une copie de `/opt/stickscans/*/data/` ailleurs de temps en temps.
