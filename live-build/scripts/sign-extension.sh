#!/bin/sh
# sign-extension.sh — signe le bouclier anti-hameçonnage via Mozilla (AMO),
# en distribution PRIVÉE (unlisted) : produit un .xpi signé, installable sur
# Firefox/ESR SANS désactiver la vérification des signatures.
#
# PRÉREQUIS (côté toi, une seule fois) :
#   1. Un compte Firefox / addons.mozilla.org
#   2. Des identifiants API : https://addons.mozilla.org/developers/addon/api/key/
#      → un « JWT issuer » (AMO_KEY) et un « JWT secret » (AMO_SECRET)
#   3. web-ext : `npm install -g web-ext` (ou `npx web-ext`)
#
# USAGE :
#   AMO_KEY=user:xxxxx:123 AMO_SECRET=yyyy ./sign-extension.sh
#
# Le .xpi signé est déposé dans build-signature/ ; place-le ensuite dans
#   live-build/config/includes.chroot_after_packages/usr/share/codebyr/antiphishing/signed/
# et rebuild : codebyr-space l'installera tel quel (voir la note d'intégration).
set -e

REPO="${CODEBYR_REPO:-$(cd "$(dirname "$0")/../.." && pwd)}"
SRC="$REPO/live-build/config/includes.chroot_after_packages/usr/share/codebyr/antiphishing"
OUT="$REPO/build-signature"

[ -n "$AMO_KEY" ] && [ -n "$AMO_SECRET" ] || {
    echo "Définis AMO_KEY et AMO_SECRET (voir l'en-tête du script)." >&2
    exit 1
}
command -v web-ext >/dev/null 2>&1 || WEBEXT="npx web-ext"
: "${WEBEXT:=web-ext}"

mkdir -p "$OUT"
# On signe une COPIE (le manifeste et content.js réels utilisent un placeholder
# de domaines ; la version signée doit lire les domaines au runtime — voir la
# note d'architecture docs/signer-le-bouclier.md).
$WEBEXT sign --channel=unlisted \
    --source-dir "$SRC" \
    --artifacts-dir "$OUT" \
    --api-key "$AMO_KEY" \
    --api-secret "$AMO_SECRET"

echo "XPI signé dans $OUT/. Voir docs/signer-le-bouclier.md pour l'intégration."
