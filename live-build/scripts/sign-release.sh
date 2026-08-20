#!/bin/sh
# sign-release.sh — signe l'ISO d'une version Codebyr OS avec la clé du projet.
#
# Produit dans dist/ :
#   SHA256SUMS       (empreinte de l'ISO)
#   SHA256SUMS.asc   (signature GPG détachée de SHA256SUMS)
#
# La clé PUBLIQUE est publiée dans le dépôt (codebyr-signing-key.asc) : c'est
# l'ancre de confiance de tout le projet — celle que les utilisateurs importent
# et comparent à l'empreinte publiée. On ne la remplace donc JAMAIS par
# accident : le script refuse de la réécrire si l'empreinte change, sauf
# rotation explicitement demandée (CODEBYR_ROTATION=1).
#
# Voir docs/chaine-de-signature.md pour la hiérarchie de clés et la procédure
# en cas de compromission.
set -e

REPO="${CODEBYR_REPO:-$(cd "$(dirname "$0")/../.." && pwd)}"
DIST="$REPO/dist"
: "${GNUPGHOME:=$HOME/.gnupg-codebyr}"
export GNUPGHOME

# On signe par EMPREINTE, jamais par nom : « Codebyr OS » peut désigner
# plusieurs clés dans un trousseau (l'ancienne et la nouvelle, par exemple).
SIGNER="${CODEBYR_SIGNER:-E6FB6616EC58E15F40DA876CB1E8C803CE596E68}"
CLE_PUB="$REPO/codebyr-signing-key.asc"

gpg --list-secret-keys "$SIGNER" >/dev/null 2>&1 || {
	echo "ERREUR : clé privée $SIGNER introuvable dans $GNUPGHOME." >&2; exit 1; }

ISO="$(ls -1t "$DIST"/codebyr-os-*.iso 2>/dev/null | head -n1)"
[ -n "$ISO" ] || { echo "Aucune ISO dans $DIST." >&2; exit 1; }

cd "$DIST"
echo "==> Empreinte de $(basename "$ISO")"
sha256sum "$(basename "$ISO")" > SHA256SUMS

echo "==> Signature GPG (clé : $SIGNER)"
# On ne refuse pas d'emblée faute de terminal : gpg-agent garde la phrase de
# passe en cache un moment, et une signature qui vient de suivre une
# publication n'a rien à demander. En revanche, si gpg échoue, on traduit son
# message — « Inappropriate ioctl for device » ne dit rien à personne, alors
# que la cause est presque toujours l'absence de terminal.
if ! gpg --armor --detach-sign --local-user "$SIGNER" \
         --output SHA256SUMS.asc --yes SHA256SUMS; then
	if [ -z "${GPG_TTY:-}" ] || [ ! -c "${GPG_TTY}" ]; then
		echo >&2
		echo "ERREUR : pas de terminal pour saisir la phrase de passe." >&2
		echo "         Relancez depuis un vrai terminal WSL, après :" >&2
		echo "             export GPG_TTY=\$(tty)" >&2
	fi
	rm -f SHA256SUMS.asc
	exit 1
fi

# — Ancre de confiance : on ne la change pas sans le dire —
NOUVELLE="$(mktemp)"
trap 'rm -f "$NOUVELLE"' EXIT
gpg --armor --export "$SIGNER" > "$NOUVELLE"
if [ -f "$CLE_PUB" ] && ! cmp -s "$NOUVELLE" "$CLE_PUB"; then
	if [ "${CODEBYR_ROTATION:-0}" = "1" ]; then
		cp "$NOUVELLE" "$CLE_PUB"
		echo "==> Clé publique du dépôt REMPLACÉE (rotation demandée)."
		echo "    Pensez à publier la nouvelle empreinte partout : README, SECURITY.md,"
		echo "    codebyr-verifier, site, et à annoncer la rotation aux utilisateurs."
	else
		echo "AVERTISSEMENT : la clé publique exportée diffère de $CLE_PUB." >&2
		echo "                Le dépôt n'a PAS été modifié. S'il s'agit bien d'une" >&2
		echo "                rotation de clé, relancez avec CODEBYR_ROTATION=1." >&2
	fi
else
	cp "$NOUVELLE" "$CLE_PUB"
fi

echo "==> Vérification"
gpg --verify SHA256SUMS.asc SHA256SUMS
sha256sum -c SHA256SUMS
echo "OK. Publier : SHA256SUMS, SHA256SUMS.asc (et codebyr-signing-key.asc dans le dépôt)."
