#!/bin/bash
# Mise à jour complète de StickScans, en une commande (en root, depuis n'importe quel dossier) :
#
#   /git/StickScans/outils/maj.sh ~/lot.zip     applique un zip de modifications, puis tout le reste
#   /git/StickScans/outils/maj.sh               sans zip : modifications déjà faites dans /git/StickScans
#   /git/StickScans/outils/maj.sh ~/lot.zip "Message de commit"
#
# Étapes : zip appliqué (fichiers listés dans SUPPRIMER.txt supprimés, message repris de MESSAGE.txt) ->
# dépendances -> tests -> commit + push -> déploiement du commit -> redémarrage -> vérification que chaque
# instance répond. Si les tests échouent, rien n'est commité ni déployé. Si une instance ne répond pas après le
# redémarrage, la commande pour revenir à la version précédente est affichée.
set -euo pipefail

REPO=${STICKSCANS_REPO:-/git/StickScans}
ROOT=${STICKSCANS_ROOT:-/opt/stickscans}
ETC=${STICKSCANS_ETC:-/etc}
VENV=${STICKSCANS_VENV:-$ROOT/venv}
SYSTEMCTL=${STICKSCANS_SYSTEMCTL:-systemctl}

ZIP=""
if [ $# -gt 0 ] && [[ "$1" == *.zip ]]; then
  ZIP=$1
  shift
fi
MSG=${1:-}

die() { echo "ÉCHEC : $*" >&2; exit 1; }
step() { echo; echo "== $*"; }

cd "$REPO"

if [ -n "$ZIP" ]; then
  step "Application de $ZIP"
  [ -f "$ZIP" ] || die "fichier introuvable : $ZIP"
  case "$(realpath "$ZIP")" in
    "$(realpath "$REPO")"/*) die "le zip est dans le dépôt : déplace-le ailleurs (ex. /root), sinon il serait commité" ;;
  esac
  unzip -o -q "$ZIP" -d "$REPO"
  if [ -f SUPPRIMER.txt ]; then
    while IFS= read -r path || [ -n "$path" ]; do
      case "$path" in ""|\#*) continue ;; esac
      git rm -r -q --ignore-unmatch -- "$path"
      rm -rf -- "$path"
      echo "supprimé : $path"
    done < SUPPRIMER.txt
    rm -f SUPPRIMER.txt
  fi
  if [ -z "$MSG" ] && [ -f MESSAGE.txt ]; then
    MSG=$(head -n 1 MESSAGE.txt)
  fi
  rm -f MESSAGE.txt
fi

step "Dépendances"
"$VENV/bin/pip" install -q -r requirements-dev.txt

step "Tests"
if ! "$VENV/bin/python" -m pytest -q; then
  die "tests en échec : rien n'a été commité ni déployé.
Pour annuler les changements du zip : cd $REPO && git checkout -- . && git clean -fd"
fi

step "Commit et envoi sur GitHub"
git add -A
if git diff --cached --name-only | grep -qi '\.zip$'; then
  git reset -q
  die "un fichier .zip allait être commité : retire-le du dépôt"
fi
if git diff --cached --quiet; then
  echo "Rien de nouveau à commiter."
else
  git diff --cached --stat | tail -n 1
  git commit -q -m "${MSG:-Mise à jour}"
  if ! git push -q; then
    echo "Attention : git push a échoué (le déploiement continue ; pense à relancer git push)."
  fi
fi

previous=$(cut -d'|' -f1 "$(ls "$ROOT"/*/VERSION 2>/dev/null | head -n 1)" 2>/dev/null || true)

step "Déploiement"
bash "$REPO/outils/deploy.sh" HEAD

step "Redémarrage"
instances=()
for env in "$ETC"/stickscans-*.env; do
  [ -e "$env" ] || continue
  name=${env#"$ETC"/stickscans-}
  instances+=("${name%.env}")
done
units=()
for name in "${instances[@]}"; do units+=("stickscans@$name"); done
"$SYSTEMCTL" restart "${units[@]}"

step "Vérification"
failed=0
for name in "${instances[@]}"; do
  port=$(sed -n 's/^PORT=//p' "$ETC/stickscans-$name.env" | tr -d '"'"'"' \r' | head -n 1)
  ok=0
  for _ in $(seq 1 30); do
    if curl -fsS -o /dev/null "http://127.0.0.1:$port/api/auth/status" 2>/dev/null; then ok=1; break; fi
    sleep 1
  done
  if [ $ok = 1 ]; then
    echo "stickscans@$name (port $port) : OK"
  else
    echo "stickscans@$name (port $port) : NE RÉPOND PAS — journalctl -u stickscans@$name -n 50 --no-pager"
    failed=1
  fi
done

if [ $failed = 1 ]; then
  [ -n "$previous" ] && echo "Pour revenir à la version précédente : bash $REPO/outils/deploy.sh $previous && systemctl restart ${units[*]}"
  exit 1
fi
echo
echo "Mise à jour terminée : $(git log -1 --format='%h %s')"
