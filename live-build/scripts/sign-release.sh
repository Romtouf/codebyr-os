#!/bin/sh
# sign-release.sh — signe l'ISO d'une version Codebyr OS avec la clé GPG du projet.
#
# Produit dans dist/ :
#   SHA256SUMS       (empreinte de l'ISO)
#   SHA256SUMS.asc   (signature GPG détachée de SHA256SUMS)
#
# La clé privée du projet vit dans GNUPGHOME (par défaut la clé « Codebyr OS »).
# La clé PUBLIQUE est publiée dans le dépôt (codebyr-signing-key.asc) : les
# utilisateurs vérifient l'intégrité ET l'authenticité de leur téléchargement.
set -e

REPO="${CODEBYR_REPO:-$(cd "$(dirname "$0")/../.." && pwd)}"
DIST="$REPO/dist"
: "${GNUPGHOME:=$HOME/.gnupg-codebyr}"
export GNUPGHOME
SIGNER="${CODEBYR_SIGNER:-Codebyr OS}"

ISO="$(ls -1t "$DIST"/codebyr-os-*.iso 2>/dev/null | head -n1)"
[ -n "$ISO" ] || { echo "Aucune ISO dans $DIST." >&2; exit 1; }

cd "$DIST"
echo "==> Empreinte de $(basename "$ISO")"
sha256sum "$(basename "$ISO")" > SHA256SUMS

echo "==> Signature GPG (clé : $SIGNER)"
gpg --armor --detach-sign --local-user "$SIGNER" --output SHA256SUMS.asc --yes SHA256SUMS

echo "==> Clé publique → dépôt"
gpg --armor --export "$SIGNER" > "$REPO/codebyr-signing-key.asc"

echo "==> Vérification"
gpg --verify SHA256SUMS.asc SHA256SUMS
echo "OK. Publier : SHA256SUMS, SHA256SUMS.asc (et codebyr-signing-key.asc dans le dépôt)."
