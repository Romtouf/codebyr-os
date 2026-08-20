#!/bin/sh
# durcir-cle.sh — met la clé de signature Codebyr en configuration sûre.
#
# Trois choses, dans l'ordre :
#   1. crée une SOUS-CLÉ de signature (valable un an) ;
#   2. exporte une sauvegarde complète + le certificat de révocation vers un
#      support que VOUS choisissez (clé USB) ;
#   3. VÉRIFIE cette sauvegarde en la réimportant dans un trousseau jetable.
#
# Ce que ce script ne fait PAS, volontairement : supprimer la clé maîtresse du
# poste. C'est le seul geste irréversible de toute la chaîne — un défaut ici et
# la clé du projet est perdue. Le script affiche les deux commandes à taper
# vous-même, une fois la clé USB rangée ailleurs.
#
# POURQUOI UNE SOUS-CLÉ ?
# Aujourd'hui, une seule clé signe tout. Si elle fuite, il faut la révoquer et
# faire réimporter la nouvelle à TOUS les utilisateurs — l'empreinte publiée
# partout devient fausse. Avec une sous-clé, on révoque et on remplace la
# sous-clé : l'empreinte de la clé maîtresse, celle que les gens connaissent,
# ne bouge pas.
#
# Une seule sous-clé, pas deux : séparer « releases » et « apt » n'a de sens
# que si elles vivent sur des machines différentes. Ici les deux seraient sur
# ce poste — ce serait de la cérémonie, pas de la sécurité.
#
# Usage :
#   GNUPGHOME=/root/.gnupg-codebyr sh durcir-cle.sh /mnt/e/codebyr-cles
set -e

CLE="${CODEBYR_CLE:-E6FB6616EC58E15F40DA876CB1E8C803CE596E68}"
: "${GNUPGHOME:=/root/.gnupg-codebyr}"
export GNUPGHOME
SORTIE="$1"

echo "=== Durcissement de la clé de signature Codebyr ==="
echo

# ── Contrôles préalables ────────────────────────────────────────────────────
if [ -z "$SORTIE" ]; then
	cat >&2 <<'AIDE'
ERREUR : indiquez où écrire la sauvegarde.

  sh durcir-cle.sh /chemin/vers/la/cle-usb

Ce dossier recevra la clé privée du projet EN CLAIR (protégée par votre phrase
de passe, mais tout de même). Choisissez un support amovible, pas un dossier de
ce disque : l'intérêt est précisément que la sauvegarde survive à la perte de
cette machine.
AIDE
	exit 1
fi

if [ -z "${GPG_TTY:-}" ]; then
	echo "ERREUR : GPG_TTY n'est pas défini — la demande de phrase de passe" >&2
	echo "         échouerait en silence. Faites : export GPG_TTY=\$(tty)" >&2
	exit 1
fi

gpg --list-secret-keys "$CLE" >/dev/null 2>&1 || {
	echo "ERREUR : clé privée $CLE introuvable dans $GNUPGHOME." >&2; exit 1; }

protection="$(gpg-connect-agent 'keyinfo --list' /bye 2>/dev/null \
	| awk '/^S KEYINFO/ {print $8}' | sort -u | tr '\n' ' ' || true)"
case " $protection " in
	*" C "*)
		echo "ERREUR : la clé n'a pas de phrase de passe. Posez-la d'abord :" >&2
		echo "         gpg --edit-key $CLE   puis  passwd  puis  save" >&2
		exit 1 ;;
esac

case "$SORTIE" in
	*codebyros*)
		echo "ERREUR : n'écrivez pas la sauvegarde dans le dépôt du projet." >&2
		exit 1 ;;
esac

mkdir -p "$SORTIE"
chmod 700 "$SORTIE"

# ── 1) Sous-clé de signature ────────────────────────────────────────────────
echo "==> Sous-clés de signature déjà présentes :"
gpg --list-keys --with-subkey-fingerprints "$CLE" | grep -A1 "^sub" || echo "   (aucune)"
echo
printf "Créer une nouvelle sous-clé de signature (valable 1 an) ? [o/N] "
read -r reponse
case "$reponse" in
	o|O|oui|OUI)
		echo "==> Création (votre phrase de passe va être demandée)"
		gpg --quick-add-key "$CLE" ed25519 sign 1y
		echo "==> Sous-clé créée." ;;
	*)
		echo "==> Étape passée." ;;
esac

# ── 2) Sauvegardes ──────────────────────────────────────────────────────────
echo
echo "==> Export vers $SORTIE (phrase de passe demandée)"
gpg --armor --export-secret-keys "$CLE" > "$SORTIE/codebyr-maitresse-SECRETE.asc"
gpg --armor --export-secret-subkeys "$CLE" > "$SORTIE/codebyr-sous-cles-SECRETE.asc"
gpg --armor --export "$CLE" > "$SORTIE/codebyr-publique.asc"
for rev in "$GNUPGHOME"/openpgp-revocs.d/*.rev; do
	[ -e "$rev" ] || continue
	cp -f "$rev" "$SORTIE/"
done
chmod 600 "$SORTIE"/*.asc "$SORTIE"/*.rev 2>/dev/null || true
ls -1 "$SORTIE"

# ── 3) Vérification de la sauvegarde — AVANT toute suppression ─────────────
echo
echo "==> Vérification : réimport de la sauvegarde dans un trousseau jetable"
TEMOIN="$(mktemp -d)"
trap 'rm -rf "$TEMOIN"' EXIT
chmod 700 "$TEMOIN"
if GNUPGHOME="$TEMOIN" gpg --batch --quiet \
		--import "$SORTIE/codebyr-maitresse-SECRETE.asc" 2>/dev/null \
	&& GNUPGHOME="$TEMOIN" gpg --list-secret-keys --with-colons 2>/dev/null \
		| grep -q '^sec:'; then
	echo "    La sauvegarde contient bien la clé maîtresse : OK."
else
	echo "ERREUR : la sauvegarde ne se réimporte pas. NE SUPPRIMEZ RIEN." >&2
	echo "         Recommencez, ou gardez la configuration actuelle." >&2
	exit 1
fi

# ── Ce qui reste à faire à la main ─────────────────────────────────────────
# Empreinte de la sous-clé de SIGNATURE la plus récente. En format « colons »,
# une ligne « sub: » porte ses capacités en champ 12 (« s » = signature) et la
# ligne « fpr: » qui suit donne son empreinte.
SOUS="$(gpg --list-keys --with-colons --with-subkey-fingerprints "$CLE" | awk -F: '
	/^sub:/  { signature = ($12 ~ /s/) ? 1 : 0; next }
	/^fpr:/  { if (signature) { empreinte = $10; signature = 0 } }
	END      { print empreinte }')"
[ -n "$SOUS" ] || SOUS="<aucune sous-clé de signature>"

cat <<FIN

════════════════════════════════════════════════════════════════════════
  Sauvegarde faite et VÉRIFIÉE. Trois choses maintenant, dans cet ordre.
════════════════════════════════════════════════════════════════════════

1. RETIREZ LA CLÉ MAÎTRESSE DE CE POSTE — support TOUJOURS BRANCHÉ, puisque
   la seconde commande y lit le fichier des sous-clés :

     gpg --delete-secret-keys $CLE
     gpg --import "$SORTIE/codebyr-sous-cles-SECRETE.asc"

   Contrôle : « gpg -K » doit afficher « sec# » (le dièse dit que la clé
   maîtresse n'est plus là — seules les sous-clés restent, c'est le but).

2. ALORS SEULEMENT, RANGEZ LE SUPPORT.
   Débranchez la clé USB et mettez-la ailleurs que près de cet ordinateur.
   Elle contient de quoi signer au nom du projet, et de quoi le révoquer :
   c'est le double du trousseau, pas une copie de confort.

3. SIGNEZ AVEC LA SOUS-CLÉ. Le « ! » impose CETTE clé et non une autre :

     export CODEBYR_APT_KEY='$SOUS!'
     export CODEBYR_SIGNER='$SOUS!'

   À noter dans vos scripts de publication, ou dans le .bashrc du WSL.

Dans un an, la sous-clé expire : ressortez la clé maîtresse du support, faites
« gpg --edit-key $CLE » puis « expire », et réexportez les sous-clés.
Rien à republier côté utilisateur — l'empreinte publiée ne change pas.
FIN
