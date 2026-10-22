# StickScans

Tracker auto-hébergé de manhwas/mangas. Tu ajoutes des séries de [scan-manga.com](https://www.scan-manga.com), l'appli vérifie régulièrement les nouveaux chapitres et garde ta progression de lecture. Synchronisation AniList possible, installable comme application (PWA).

## Installation (Docker)

Crée un fichier `compose.yaml` (ou colle-le dans une stack Portainer) :

```yaml
services:
  stickscans:
    image: ghcr.io/stickd-hd/stickscans:latest
    container_name: stickscans
    restart: unless-stopped
    depends_on:
      byparr-stickscans:
        condition: service_healthy
    ports:
      - 8420:8000
    environment:
      - AUTH_USERNAME=username
      - AUTH_PASSWORD=password
    volumes:
      - /chemin/a/changer:/app/data

  byparr-stickscans:
    image: ghcr.io/thephaseless/byparr:latest
    container_name: byparr-stickscans
    restart: unless-stopped
    shm_size: 2gb
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8191/"]
      interval: 15s
      timeout: 5s
      retries: 5
```

Puis `docker compose up -d` et ouvre `http://IP-DU-SERVEUR:8420`.

| Réglage | Rôle |
|---|---|
| `AUTH_USERNAME` / `AUTH_PASSWORD` | Identifiants de connexion. Sans mot de passe, l'appli est accessible à tous. |
| `/app/data` | Base de données, sauvegardes et journaux. À monter sur un dossier de ton serveur. |
| `byparr-stickscans` | Service qui contourne la protection Cloudflare du site. Obligatoire. |

## Plusieurs instances (une par personne)

Pour que deux personnes aient chacune leur compte sans doubler les requêtes vers le site, ajoute une seconde instance. Elles partagent le même Byparr et un cache de pages (détecté automatiquement grâce au volume `cache`).

```yaml
services:
  stickscans:
    image: ghcr.io/stickd-hd/stickscans:latest
    container_name: stickscans
    restart: unless-stopped
    depends_on:
      byparr-stickscans:
        condition: service_healthy
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
    depends_on:
      byparr-stickscans:
        condition: service_healthy
    ports:
      - 8421:8000
    environment:
      - AUTH_USERNAME=username
      - AUTH_PASSWORD=password
      - CHECK_OFFSET_MINUTES=30
    volumes:
      - /autre/chemin/a/changer:/app/data
      - cache:/app/cache

  byparr-stickscans:
    image: ghcr.io/thephaseless/byparr:latest
    container_name: byparr-stickscans
    restart: unless-stopped
    shm_size: 2gb
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8191/"]
      interval: 15s
      timeout: 5s
      retries: 5

volumes:
  cache:
```

Chaque instance garde sa propre base et sa propre progression. `CHECK_OFFSET_MINUTES` décale les vérifications (0 et 30) pour que la seconde instance réutilise les pages déjà récupérées par la première.

## Mise à jour

```bash
docker compose pull && docker compose up -d
```

Avec Portainer : *Update the stack* en cochant *Re-pull image*.

## Réglages optionnels

Variables d'environnement facultatives, à ajouter sous `environment` :

| Variable | Défaut | Rôle |
|---|---|---|
| `CHECK_INTERVAL_HOURS` | `1` | Fréquence des vérifications |
| `CHECK_OFFSET_MINUTES` | _(vide)_ | Minute de l'heure où la vérification a lieu |
| `CHECK_MIN_DELAY_SECONDS` / `CHECK_MAX_DELAY_SECONDS` | `3` / `8` | Délai aléatoire entre deux séries |
| `AUTH_SESSION_DAYS` | `30` | Durée d'une session |
| `SCRAPE_CACHE_MAX_AGE_MINUTES` | `40` | Âge maximal d'une page réutilisable depuis le cache |
