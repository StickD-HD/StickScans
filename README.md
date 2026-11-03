# StickScans

Tracker auto-hébergé de manhwas/mangas. Tu ajoutes des séries de [scan-manga.com](https://www.scan-manga.com), l'appli vérifie régulièrement les nouveaux chapitres et garde ta progression de lecture. Synchronisation AniList possible, installable comme application (PWA).

Pour passer la protection Cloudflare du site, StickScans embarque son propre navigateur (Google Chrome piloté par Playwright, dans un écran virtuel). Aucun service externe n'est nécessaire : un seul conteneur suffit.

## Prérequis

- Docker et Docker Compose
- Une machine **x86_64 (amd64)** : Google Chrome n'existe pas en version stable pour ARM
- Environ **3 Go de RAM** disponibles pendant les vérifications (Chrome se ferme tout seul après 3 minutes d'inactivité)
- Si tu utilises Docker dans un conteneur LXC (Proxmox) : l'option *nesting* doit être activée

## Installation (Docker)

Crée un fichier `compose.yaml` (ou colle-le dans une stack Portainer) :

```yaml
services:
  stickscans:
    image: ghcr.io/stickd-hd/stickscans:latest
    container_name: stickscans
    restart: unless-stopped
    init: true
    shm_size: 2gb
    ports:
      - 8420:8000
    environment:
      - AUTH_USERNAME=username
      - AUTH_PASSWORD=password
    volumes:
      - /chemin/a/changer:/app/data
```

Puis `docker compose up -d` et ouvre `http://IP-DU-SERVEUR:8420`.

| Réglage | Rôle |
|---|---|
| `AUTH_USERNAME` / `AUTH_PASSWORD` | Identifiants de connexion. Sans mot de passe, l'appli est accessible à tous. |
| `/app/data` | Base de données, sauvegardes, journaux et profil du navigateur. À monter sur un dossier de ton serveur. |
| `shm_size: 2gb` | Mémoire partagée nécessaire à Chrome. Sans elle, le navigateur plante sur les pages lourdes. |
| `init: true` | Évite l'accumulation de processus Chrome orphelins. |

## Plusieurs instances (une par personne)

Pour que deux personnes aient chacune leur compte sans doubler les requêtes vers le site, ajoute une seconde instance. Elles partagent un cache de pages (détecté automatiquement grâce au volume `cache`). Chaque instance a son propre navigateur et son propre dossier de données : ne partage jamais le même dossier `/app/data` entre deux instances.

```yaml
services:
  stickscans:
    image: ghcr.io/stickd-hd/stickscans:latest
    container_name: stickscans
    restart: unless-stopped
    init: true
    shm_size: 2gb
    ports:
      - 8420:8000
    environment:
      - AUTH_USERNAME=username
      - AUTH_PASSWORD=password
      - CHECK_OFFSET_MINUTES=0
    volumes:
      - /chemin/a/changer:/app/data
      - cache:/app/cache

  stickscans-2:
    image: ghcr.io/stickd-hd/stickscans:latest
    container_name: stickscans-2
    restart: unless-stopped
    init: true
    shm_size: 2gb
    ports:
      - 8421:8000
    environment:
      - AUTH_USERNAME=username
      - AUTH_PASSWORD=password
      - CHECK_OFFSET_MINUTES=30
    volumes:
      - /autre/chemin/a/changer:/app/data
      - cache:/app/cache

volumes:
  cache:
```

Chaque instance garde sa propre base et sa propre progression. `CHECK_OFFSET_MINUTES` décale les vérifications (0 et 30) pour que la seconde instance réutilise les pages déjà récupérées par la première, et pour que les deux navigateurs ne tournent pas en même temps.

## Mise à jour

```bash
docker compose pull && docker compose up -d
```

Avec Portainer : *Update the stack* en cochant *Re-pull image*.

### Migration depuis une version avec Byparr

Les anciennes versions utilisaient un service `byparr-stickscans`, qui n'est plus nécessaire. Retire-le de ton `compose.yaml` ainsi que les lignes `depends_on` qui y faisaient référence, ajoute `init: true` et `shm_size: 2gb` au service StickScans, puis :

```bash
docker compose pull && docker compose up -d --remove-orphans
```

Tes données (base, progression, réglages) sont conservées.

## Construire l'image soi-même

Si tu préfères construire l'image sur ton serveur plutôt que de la télécharger :

```bash
git clone https://github.com/StickD-HD/StickScans.git
cd StickScans
```

Dans le `compose.yaml` du dépôt, le service utilise déjà `build: .`. Après avoir modifié le fichier (identifiants, ports), lance :

```bash
docker compose up -d --build
```

Pour mettre à jour : `git pull && docker compose up -d --build`.

## Réglages optionnels

Variables d'environnement facultatives, à ajouter sous `environment` :

| Variable | Défaut | Rôle |
|---|---|---|
| `CHECK_INTERVAL_HOURS` | `1` | Fréquence des vérifications |
| `CHECK_OFFSET_MINUTES` | _(vide)_ | Minute de l'heure où la vérification a lieu |
| `CHECK_MIN_DELAY_SECONDS` / `CHECK_MAX_DELAY_SECONDS` | `3` / `8` | Délai aléatoire entre deux séries |
| `AUTH_SESSION_DAYS` | `30` | Durée d'une session |
| `SCRAPE_CACHE_MAX_AGE_MINUTES` | `40` | Âge maximal d'une page réutilisable depuis le cache |
| `BROWSER_HEADLESS` | `false` | `true` lance Chrome sans fenêtre virtuelle (plus léger, mais plus facilement détecté par Cloudflare) |
| `BROWSER_BLOCK_MEDIA` | `true` | Ne charge pas les images, médias et polices (pages plus rapides, moins de données) |
| `BROWSER_IDLE_SECONDS` | `180` | Délai d'inactivité avant la fermeture de Chrome pour libérer la mémoire |
| `BROWSER_PROFILE_DIR` | `data/browser-profile` | Dossier du profil Chrome (cookies de session conservés entre deux redémarrages) |

## Dépannage

Les journaux se trouvent dans le dossier de données :

- `data/logs/scrape.log` : détail de chaque vérification (aussi téléchargeable depuis l'appli)
- `data/debug/*.png` : capture d'écran du navigateur à chaque échec de récupération (les 10 dernières sont gardées). Elle montre exactement ce que Chrome voit : page de challenge Cloudflare, erreur du site, etc.

| Symptôme | Piste |
|---|---|
| Erreurs « Challenge Cloudflare non résolu » | Ouvre la dernière capture dans `data/debug/` pour voir la page affichée. Vérifie que `BROWSER_HEADLESS` n'est pas à `true`. |
| « Target closed » ou « browser has been closed » | Chrome a été tué faute de mémoire : augmente la RAM de la machine ou du conteneur LXC, et vérifie `shm_size`. |
| Le conteneur ne démarre pas sur un Raspberry Pi ou un serveur ARM | Google Chrome stable n'est disponible qu'en x86_64. |
| Plus d'erreurs après une coupure brutale | Chrome nettoie ses verrous au prochain démarrage ; si le problème persiste, supprime le dossier `data/browser-profile` (tu perds seulement les cookies de session). |
