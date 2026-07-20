#!/usr/bin/env bash
# Codebyr OS — génère et SIGNE le dépôt APT à partir des .deb construits.
#
# Produit une arborescence de dépôt « flat » (simple, sans distributions) :
#   apt-repo/
#     Packages, Packages.gz      index des paquets
#     Release, InRelease, Release.gpg   métadonnées signées
#     *.deb
#
# Signé avec la clé de release Codebyr (le trousseau dédié du WSL de build) :
#   GNUPGHOME=/root/.gnupg-codebyr   (clé E6FB6616EC58E15F40DA876CB1E8C803CE596E68)
#
#   ./publish-apt.sh
#
# Ensuite : rsync apt-repo/ vers le conteneur qui sert apt.codebyr.dev.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DIST="$HERE/dist"
REPODIR="$HERE/apt-repo"
: "${GNUPGHOME:=/root/.gnupg-codebyr}"
export GNUPGHOME
KEYID="E6FB6616EC58E15F40DA876CB1E8C803CE596E68"

command -v dpkg-scanpackages >/dev/null || {
	echo "ERREUR : dpkg-dev requis (apt install dpkg-dev apt-utils)." >&2; exit 1; }
ls "$DIST"/*.deb >/dev/null 2>&1 || {
	echo "ERREUR : aucun .deb dans $DIST — lancez d'abord ./build-deb.sh." >&2; exit 1; }

echo "==> Génération du dépôt dans $REPODIR"
rm -rf "$REPODIR"
mkdir -p "$REPODIR"
cp "$DIST"/*.deb "$REPODIR/"

cd "$REPODIR"
dpkg-scanpackages --multiversion . > Packages
gzip -9c Packages > Packages.gz
echo "   Packages : $(grep -c '^Package:' Packages) paquet(s)"

# Release : empreintes des index, requis par apt pour la vérification.
cat > Release <<EOF
Origin: Codebyr OS
Label: Codebyr OS
Suite: stable
Codename: codebyr
Architectures: all
Components: main
Date: $(date -u '+%a, %d %b %Y %H:%M:%S UTC')
Description: Dépôt officiel des outils Codebyr OS
EOF
apt-ftparchive release . >> Release

# Signatures : InRelease (clair-signé) + Release.gpg (détachée).
gpg --batch --yes --pinentry-mode loopback --passphrase '' \
	--default-key "$KEYID" --clearsign -o InRelease Release
gpg --batch --yes --pinentry-mode loopback --passphrase '' \
	--default-key "$KEYID" -abs -o Release.gpg Release

echo "==> Dépôt signé. Vérification :"
gpg --verify Release.gpg Release 2>&1 | sed -n '1,3p'
echo
echo "Déployer : rsync -a --delete \"$REPODIR/\" user@serveur:/chemin/apt-repo/"
echo "ou copier apt-repo/ dans le volume du conteneur apt.codebyr.dev."
