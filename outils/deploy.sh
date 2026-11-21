#!/bin/bash
# Déploie un commit du dépôt sur toutes les instances StickScans du serveur (sans redémarrer).
#
#   outils/deploy.sh            déploie le dernier commit (HEAD)
#   outils/deploy.sh abc1234    déploie ce commit-là : sert aussi à revenir à une version précédente
#
# Seul le contenu COMMITÉ est déployé (git archive) : une modification en cours, non commitée, ne part jamais en
# production par erreur. Les instances sont trouvées toutes seules : une par fichier /etc/stickscans-<nom>.env.
# Le commit déployé est noté dans /opt/stickscans/<nom>/VERSION (affiché dans Réglages).
# Les dossiers data/ (base, sauvegardes, journaux) ne sont jamais touchés.
set -euo pipefail

REPO=${STICKSCANS_REPO:-/git/StickScans}
ROOT=${STICKSCANS_ROOT:-/opt/stickscans}
ETC=${STICKSCANS_ETC:-/etc}
RUN_USER=${STICKSCANS_USER:-stickscans}
REV=${1:-HEAD}

commit=$(git -C "$REPO" rev-parse --verify --quiet "${REV}^{commit}") || { echo "Commit inconnu : $REV" >&2; exit 1; }
short=$(git -C "$REPO" rev-parse --short "$commit")
when=$(git -C "$REPO" show -s --format=%cd --date=format:'%Y-%m-%d %H:%M' "$commit")
subject=$(git -C "$REPO" show -s --format=%s "$commit" | tr '|' '/')

if [ -n "$(git -C "$REPO" status --porcelain -- app static)" ]; then
  echo "Attention : des modifications non commitées dans app/ ou static/ ne sont PAS déployées."
fi

instances=()
for env in "$ETC"/stickscans-*.env; do
  [ -e "$env" ] || continue
  name=${env#"$ETC"/stickscans-}
  instances+=("${name%.env}")
done
[ ${#instances[@]} -gt 0 ] || { echo "Aucune instance trouvée ($ETC/stickscans-*.env)" >&2; exit 1; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
git -C "$REPO" archive "$commit" app static | tar -x -C "$tmp"

for name in "${instances[@]}"; do
  dir="$ROOT/$name"
  if [ ! -d "$dir" ]; then
    echo "Instance $name : dossier $dir absent, ignorée"
    continue
  fi
  # Nouvelle version copiée à côté, puis échangée : l'instance n'a jamais de dossier à moitié copié.
  rm -rf "$dir/app.new" "$dir/static.new"
  cp -r "$tmp/app" "$dir/app.new"
  cp -r "$tmp/static" "$dir/static.new"
  rm -rf "$dir/app" "$dir/static"
  mv "$dir/app.new" "$dir/app"
  mv "$dir/static.new" "$dir/static"
  printf '%s|%s|%s\n' "$short" "$when" "$subject" > "$dir/VERSION"
  echo "Instance $name : version $short déployée"
done

if [ "$(id -u)" = 0 ]; then
  chown -R "$RUN_USER": "$ROOT"
fi
echo "Version $short ($when) : $subject"
