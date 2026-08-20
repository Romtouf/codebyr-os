#!/usr/bin/env bash
# Codebyr OS — génère et SIGNE le dépôt APT à partir des .deb construits.
#
# Produit une arborescence de dépôt « flat » (simple, sans distributions) :
#   apt-repo/
#     Packages, Packages.gz      index des paquets
#     Release, InRelease, Release.gpg   métadonnées signées
#     *.deb
#
# ── CE QUE CETTE SIGNATURE ENGAGE ────────────────────────────────────────────
# Ce dépôt a un accès root implicite à TOUTES les machines Codebyr installées :
# ce qui est signé ici est installé automatiquement par unattended-upgrades.
# La clé qui signe est donc l'actif le plus sensible du projet — plus que le
# serveur, plus que le compte GitHub.
#
# D'où trois règles, appliquées par le script :
#   1. On signe avec une SOUS-CLÉ dédiée au dépôt (CODEBYR_APT_KEY), pas avec la
#      clé maîtresse — celle-ci reste hors ligne. Voir docs/chaine-de-signature.md.
#   2. Aucune phrase de passe n'est écrite dans ce fichier. gpg-agent la demande,
#      ou on la lui fournit par CODEBYR_PASSPHRASE_FILE (fichier hors dépôt).
#   3. Une clé sans phrase de passe fait échouer le script, sauf autorisation
#      explicite (CODEBYR_AUTORISER_CLE_NUE=1) — un poste de développement volé
#      ne doit pas suffire à pousser du code root chez les utilisateurs.
#
#   ./publish-apt.sh
#
# Ensuite : rsync apt-repo/ vers le conteneur qui sert apt.codebyr.dev.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${CODEBYR_REPO:-$(cd "$HERE/.." && pwd)}"
DIST="$REPO/packaging/dist"
REPODIR="$REPO/packaging/apt-repo"
: "${GNUPGHOME:=/root/.gnupg-codebyr}"
export GNUPGHOME

# Empreinte de la clé de signature du dépôt APT. Par défaut la clé de release
# historique ; à remplacer par la sous-clé dédiée dès qu'elle existe (suffixe
# « ! » pour imposer CETTE sous-clé et non la clé maîtresse).
KEYID="${CODEBYR_APT_KEY:-E6FB6616EC58E15F40DA876CB1E8C803CE596E68}"

command -v dpkg-scanpackages >/dev/null || {
	echo "ERREUR : dpkg-dev requis (apt install dpkg-dev apt-utils)." >&2; exit 1; }
ls "$DIST"/*.deb >/dev/null 2>&1 || {
	echo "ERREUR : aucun .deb dans $DIST — lancez d'abord ./build-deb.sh." >&2; exit 1; }

# ── Contrôles avant signature ────────────────────────────────────────────────
echo "==> Clé de signature : $KEYID"
gpg --list-secret-keys "$KEYID" >/dev/null 2>&1 || {
	echo "ERREUR : clé privée $KEYID introuvable dans $GNUPGHOME." >&2; exit 1; }

# Expiration : une clé expirée casse « apt update » sur tout le parc, et une clé
# sans expiration ne peut jamais périmer d'elle-même en cas de fuite.
expire="$(gpg --list-keys --with-colons "$KEYID" | awk -F: '/^pub:/ {print $7; exit}')"
if [ -z "$expire" ]; then
	echo "AVERTISSEMENT : cette clé n'expire jamais. Une date d'expiration est un" >&2
	echo "                filet de sécurité en cas de compromission." >&2
else
	restant=$(( (expire - $(date +%s)) / 86400 ))
	echo "    Expire dans $restant jour(s)."
	[ "$restant" -gt 0 ] || { echo "ERREUR : clé expirée." >&2; exit 1; }
	[ "$restant" -gt 30 ] || echo "AVERTISSEMENT : expiration proche — renouvelez AVANT." >&2
fi

# Phrase de passe : on interroge gpg-agent. La ligne a cette forme —
#   S KEYINFO <keygrip> D - - <cache> <protection> <fpr> <ttl> <flags>
# soit, pour awk : $3 le keygrip, $7 le CACHE (0/1/-), $8 la PROTECTION (P/C/-).
#
# Ce contrôle lisait $7. Il cherchait donc un « C » dans une colonne qui n'en
# contient jamais : le garde-fou ne pouvait PAS se déclencher. Une sécurité
# décorative, qui rassure sans rien vérifier — le pire des deux mondes.
protection="$(gpg-connect-agent 'keyinfo --list' /bye 2>/dev/null \
	| awk '/^S KEYINFO/ {print $8}' | sort -u | tr '\n' ' ' || true)"
case " $protection " in
	*" C "*)
		echo "ERREUR : au moins une clé privée de ce trousseau est SANS phrase de passe." >&2
		echo "         Cette clé installe du code en root sur toutes les machines Codebyr." >&2
		echo "         Voir docs/chaine-de-signature.md pour la protéger, ou forcez avec" >&2
		echo "         CODEBYR_AUTORISER_CLE_NUE=1 en assumant le risque." >&2
		[ "${CODEBYR_AUTORISER_CLE_NUE:-0}" = "1" ] || exit 1
		echo "         → forcé par CODEBYR_AUTORISER_CLE_NUE=1." >&2
		;;
	*" P "*) echo "    Clé protégée par une phrase de passe : OK." ;;
	*)       echo "    (protection de la clé indéterminée — vérifiez-la vous-même.)" ;;
esac

# Comment la phrase de passe est fournie : agent (défaut) ou fichier hors dépôt.
GPG_PASS=()
if [ -n "${CODEBYR_PASSPHRASE_FILE:-}" ]; then
	[ -f "$CODEBYR_PASSPHRASE_FILE" ] || {
		echo "ERREUR : CODEBYR_PASSPHRASE_FILE introuvable." >&2; exit 1; }
	GPG_PASS=(--pinentry-mode loopback --passphrase-file "$CODEBYR_PASSPHRASE_FILE")
fi

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
gpg --batch --yes "${GPG_PASS[@]+"${GPG_PASS[@]}"}" \
	--default-key "$KEYID" --clearsign -o InRelease Release
gpg --batch --yes "${GPG_PASS[@]+"${GPG_PASS[@]}"}" \
	--default-key "$KEYID" -abs -o Release.gpg Release

echo "==> Dépôt signé. Vérification :"
gpg --verify Release.gpg Release 2>&1 | sed -n '1,3p'
echo
echo "Déployer : rsync -a --delete \"$REPODIR/\" user@serveur:/chemin/apt-repo/"
echo "ou copier apt-repo/ dans le volume du conteneur apt.codebyr.dev."
