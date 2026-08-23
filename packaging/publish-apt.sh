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

# Sans terminal, l'agent ne peut pas demander la phrase de passe et gpg échoue
# sur « Inappropriate ioctl for device » — message qui ne dit rien à personne.
# Autant l'annoncer avant d'avoir régénéré tout le dépôt.
# On vérifie que GPG_TTY désigne un VRAI terminal : « export GPG_TTY=$(tty) »
# évalué hors terminal y laisse la chaîne « not a tty », non vide et donc
# trompeuse pour un simple test de présence.
if [ -z "${CODEBYR_PASSPHRASE_FILE:-}" ]    && { [ -z "${GPG_TTY:-}" ] || [ ! -c "${GPG_TTY}" ]; }; then
	echo "ERREUR : pas de terminal pour saisir la phrase de passe." >&2
	echo "         Lancez cette commande depuis un vrai terminal, ou" >&2
	echo "         indiquez CODEBYR_PASSPHRASE_FILE." >&2
	exit 1
fi

# ── Qui signe : transition de clé, sans rien demander aux utilisateurs ──────
#
# Une machine ne peut vérifier une signature que si sa copie de la clé publique
# contient la clé qui a signé. Or ce trousseau est gravé À L'INSTALLATION :
# ajouter une sous-clé de signature rend d'un coup le dépôt invérifiable par
# tout le parc déjà installé. Constaté le 20/08/2026 : « Missing key 49DF…,
# which is needed to verify signature ». Échec propre — apt refuse et le dit —
# mais total, et qui ne se répare qu'à la main sur chaque poste.
#
# La parade est celle des dépôts Debian : pendant la transition, on signe avec
# DEUX clés. apt valide dès qu'UNE signature correspond à son trousseau. Les
# machines anciennes valident par la maîtresse, les neuves par l'une ou
# l'autre, et personne ne tape quoi que ce soit.
#
# Concrètement : si la clé maîtresse est disponible (clé USB rebranchée et
# réimportée), on signe avec elle EN PLUS de la sous-clé. Sinon on signe avec
# la sous-clé seule — et on prévient de ce que cela implique.
SIGNATAIRES=(-u "$KEYID")
etat_maitresse="$(gpg --list-secret-keys --with-colons "$KEYID" 2>/dev/null \
	| awk -F: '/^sec:/ {print $15; exit}')"
if [ "$etat_maitresse" = "#" ] && [ "${CODEBYR_TRANSITION_TERMINEE:-0}" = "1" ]; then
	# Transition déclarée close : c'est le fonctionnement NORMAL, pas une
	# alerte. Afficher ici le pavé d'arrêt reviendrait à crier au loup à chaque
	# publication — et à apprendre au mainteneur à ne plus lire les messages,
	# donc à manquer celui qui compte.
	echo "    Transition terminée : signature par la sous-clé seule."
elif [ "$etat_maitresse" = "#" ]; then
	# On REFUSE, on n'avertit pas. Le 20/08/2026, cet avertissement a défilé
	# vingt lignes au-dessus d'un « Bonne signature » final : le dépôt à
	# signature unique a été produit sans que personne ne le remarque. Un
	# garde-fou qu'on franchit sans s'en apercevoir n'en est pas un.
	cat >&2 <<'TRANSITION'
    ARRÊT : la clé maîtresse n'est pas sur ce poste (elle est hors ligne,
    c'est voulu). Le dépôt ne serait donc signé QUE par la sous-clé.

    Ce que cela casserait, précisément : une machine installée avec une ISO
    antérieure à la sous-clé a un trousseau qui l'ignore. Pour le réparer il
    lui faut codebyr-tools ≥ 1.3, dont le postinst rafraîchit le trousseau —
    mais pour recevoir ce paquet, apt doit d'abord vérifier une signature
    qu'il ne sait pas vérifier. La machine est bloquée pour de bon, et ne se
    répare qu'à la main, sur place.

    Rebranchez le support, importez la maîtresse le temps de publier, retirez-la :
        mount -t drvfs D: /mnt/d          # WSL ne monte pas ce qu'on branche après lui
        gpg --import /mnt/d/codebyr-cles/codebyr-maitresse-SECRETE.asc
        …publier…
        rm $GNUPGHOME/private-keys-v1.d/<keygrip-maitresse>.key

    Le jour où plus aucune machine n'a de trousseau d'avant la sous-clé, cette
    transition n'a plus lieu d'être : CODEBYR_TRANSITION_TERMINEE=1.
TRANSITION
	exit 1
else
	# Le « ! » impose la clé MAÎTRESSE elle-même — sans lui, gpg choisirait
	# encore la sous-clé et l'on signerait deux fois avec la même.
	SIGNATAIRES+=(-u "${KEYID}!")
	echo "    Signature de transition : sous-clé + clé maîtresse."
fi

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
# « ${SIGNATAIRES[@]} » porte une ou deux clés selon la disponibilité de la
# maîtresse — voir le bloc « Qui signe » plus haut.
gpg --batch --yes "${GPG_PASS[@]+"${GPG_PASS[@]}"}" \
	"${SIGNATAIRES[@]}" --clearsign -o InRelease Release
gpg --batch --yes "${GPG_PASS[@]+"${GPG_PASS[@]}"}" \
	"${SIGNATAIRES[@]}" -abs -o Release.gpg Release

# On COMPTE les signatures au lieu d'en montrer un extrait. La version
# précédente tronquait la sortie à trois lignes : elle affichait donc une seule
# signature, la même, que le dépôt en porte une ou deux. Impossible de voir à
# l'œil que la double signature avait bien eu lieu — alors que c'est
# exactement ce qui décide qu'un parc entier reste joignable ou non.
attendues=$(( ${#SIGNATAIRES[@]} / 2 ))
echo "==> Dépôt signé. Vérification :"
for fichier in "Release.gpg Release" "InRelease"; do
	# shellcheck disable=SC2086  # découpage voulu : « Release.gpg Release »
	obtenues="$(gpg --verify $fichier 2>&1 | grep -c 'Good signature' || true)"
	echo "    ${fichier%% *} : $obtenues signature(s) valide(s) sur $attendues attendue(s)"
	if [ "$obtenues" -lt "$attendues" ]; then
		echo "ERREUR : signature manquante — ne déployez pas ce dépôt." >&2
		exit 1
	fi
done
gpg --verify Release.gpg Release 2>&1 | grep -E 'using|Good signature' || true
echo
# L'envoi se fait depuis GIT BASH, pas d'ici : la clé SSH vit côté Windows, et
# rsync n'existe que dans le WSL. La ligne « rsync … user@serveur » affichée
# auparavant ne pouvait donc marcher nulle part — un mode d'emploi faux coûte
# plus cher que pas de mode d'emploi.
echo
echo "Déployer, depuis GIT BASH (la clé SSH n'existe que côté Windows) :"
echo "    cd /c/Users/pcrom/codebyros/packaging/apt-repo && scp ./* vps-local:~/docker/codebyr-apt/apt-repo/"
