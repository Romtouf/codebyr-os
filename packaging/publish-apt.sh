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
# D'où ces règles, appliquées par le script :
#   1. On signe avec une SOUS-CLÉ dédiée au dépôt (CODEBYR_APT_KEY), pas avec la
#      clé maîtresse — celle-ci reste hors ligne. Voir docs/chaine-de-signature.md.
#   2. Aucune phrase de passe n'est écrite dans ce fichier. gpg-agent la demande,
#      ou on la lui fournit par CODEBYR_PASSPHRASE_FILE (fichier hors dépôt).
#   3. Une clé sans phrase de passe fait échouer le script, sauf autorisation
#      explicite (CODEBYR_AUTORISER_CLE_NUE=1) — un poste de développement volé
#      ne doit pas suffire à pousser du code root chez les utilisateurs.
#   4. On ne publie que du code commité, poussé, et validé par la CI — sauf
#      autorisation explicite (CODEBYR_PUBLIER_SANS_CI=1).
#   5. Un paquet d'essai (version en « ~ ») ne part jamais : unattended-upgrades
#      l'installerait sur tout le parc.
#   6. Le dépôt signé a une date de péremption (Valid-Until) : voir « Durée de
#      validité » plus bas, et ce qu'elle engage.
#
#   ./publish-apt.sh               publier la version de ../VERSION
#   ./publish-apt.sh --resigner    re-signer le dépôt déjà généré, sans rien
#                                  y changer, pour repousser sa péremption
#   ./publish-apt.sh --essai       publier sur le CANAL D'ESSAI le dernier
#                                  paquet <VERSION>~essaiN (voir plus bas)
#   ./publish-apt.sh --essai --resigner
#
# Ensuite : envoyer le dépôt vers le conteneur qui sert apt.codebyr.dev (la
# commande exacte est affichée à la fin).
#
# ── DEUX CANAUX, DEPUIS LA 1.20.1 ────────────────────────────────────────────
# Le parc suit le canal STABLE (apt.codebyr.dev) : une version par semaine au
# plus, sauf correctif de sécurité — chaque publication s'installe en root, sans
# personne devant l'écran, sur toutes les machines. Les testeurs ajoutent le
# canal d'ESSAI (apt.codebyr.dev/essai) : les mêmes versions stables, plus le
# dernier paquet d'essai, construit depuis un commit poussé et validé par la CI
# comme le reste. Une version d'essai « 1.20.1~essai2 » est plus ancienne que
# « 1.20.1 » pour apt : à la publication stable, les testeurs la reçoivent
# comme tout le monde. Analyse externe du 01/10/2026, point 3.2.
set -euo pipefail

MODE=publier
CANAL=stable
for argument in "$@"; do
	case "$argument" in
		--resigner) MODE=resigner ;;
		--essai) CANAL=essai ;;
		*) echo "Usage : $0 [--essai] [--resigner]" >&2; exit 2 ;;
	esac
done

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${CODEBYR_REPO:-$(cd "$HERE/.." && pwd)}"
DIST="$REPO/packaging/dist"
if [ "$CANAL" = essai ]; then
	REPODIR="$REPO/packaging/apt-repo-essai"
	# shellcheck disable=SC2088  # le dossier personnel DU SERVEUR, pas d'ici
	DISTANT="~/docker/codebyr-apt/apt-repo/essai"
	SUITE=essai
	CODENAME=codebyr-essai
	DESCRIPTION="Canal d'essai des outils Codebyr OS (testeurs)"
else
	REPODIR="$REPO/packaging/apt-repo"
	# shellcheck disable=SC2088  # le dossier personnel DU SERVEUR, pas d'ici
	DISTANT="~/docker/codebyr-apt/apt-repo"
	SUITE=stable
	CODENAME=codebyr
	DESCRIPTION="Dépôt officiel des outils Codebyr OS"
fi
: "${GNUPGHOME:=/root/.gnupg-codebyr}"
export GNUPGHOME

# Empreinte de la clé de signature du dépôt APT. Par défaut la clé de release
# historique ; à remplacer par la sous-clé dédiée dès qu'elle existe (suffixe
# « ! » pour imposer CETTE sous-clé et non la clé maîtresse).
KEYID="${CODEBYR_APT_KEY:-E6FB6616EC58E15F40DA876CB1E8C803CE596E68}"

command -v dpkg-scanpackages >/dev/null || {
	echo "ERREUR : dpkg-dev requis (apt install dpkg-dev apt-utils)." >&2; exit 1; }
command -v apt-ftparchive >/dev/null || {
	echo "ERREUR : apt-utils requis (apt install apt-utils)." >&2; exit 1; }
if [ "$MODE" = publier ]; then
	ls "$DIST"/*.deb >/dev/null 2>&1 || {
		echo "ERREUR : aucun .deb dans $DIST — lancez d'abord ./build-deb.sh." >&2; exit 1; }
	for outil in git curl python3; do
		command -v "$outil" >/dev/null || {
			echo "ERREUR : $outil requis pour vérifier la CI avant de publier." >&2; exit 1; }
	done
else
	[ -f "$REPODIR/Packages" ] || {
		echo "ERREUR : aucun dépôt à re-signer dans $REPODIR — publiez d'abord." >&2; exit 1; }
fi

# ── Durée de validité ────────────────────────────────────────────────────────
#
# Sans date de péremption, un Release signé reste valable pour toujours. Qui
# tient le serveur — ou une copie en cache — peut alors servir indéfiniment un
# ANCIEN dépôt, parfaitement signé : le parc ne reçoit plus aucun correctif,
# et rien ne le signale (l'« attaque par gel »). Avec Valid-Until, apt refuse
# un dépôt périmé, et le dit.
#
# CE QUE CELA ENGAGE : republier, ou re-signer (--resigner), AVANT l'échéance.
# Faute de quoi « apt update » affiche une erreur pour ce dépôt sur toutes les
# machines, et les outils Codebyr cessent de se mettre à jour — celles de
# Debian continuent. 0 désactive la péremption (et la protection avec elle).
VALIDITE_JOURS="${CODEBYR_VALIDITE_JOURS:-90}"
case "$VALIDITE_JOURS" in
	''|*[!0-9]*) echo "ERREUR : CODEBYR_VALIDITE_JOURS doit être un nombre de jours." >&2; exit 1 ;;
esac

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
#
# Le script lit lui-même le terminal sur lequel il tourne, comme
# sign-release.sh : exiger un « export GPG_TTY=$(tty) » préalable faisait
# échouer la publication à chaque nouvelle fenêtre WSL (13/09/2026).
if [ -z "${GPG_TTY:-}" ] && [ -t 0 ]; then
	GPG_TTY="$(tty 2>/dev/null)" && export GPG_TTY
fi
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

# ── Le paquet publié est-il celui du code actuel ? ──────────────────────────
#
# publish-apt.sh publie ce qui traîne dans dist/. Rien ne garantissait que ce
# .deb ait été construit APRÈS la dernière modification du code. Le 23/08/2026,
# la 1.5.0 a été publiée avec la version précédente de l'icône du panneau : le
# paquet datait d'avant le correctif, et personne ne pouvait le voir — le
# numéro de version, lui, était le bon.
#
# C'est le même piège que l'ISO périmée dans build.sh : un artefact daté que
# l'on republie en croyant publier le code. On compare donc les dates, et on
# refuse plutôt que d'avertir.
VERSION_COURANTE="$(tr -d ' \t\r\n' < "$REPO/VERSION")"

# ── Le code publié est-il celui que la CI a validé ? ────────────────────────
#
# La CI dit d'elle-même : « rien ne doit partir sans passer ici ». Rien ne
# l'imposait. Du 13 au 15 septembre 2026, quatre versions sont parties avec
# une CI rouge — dont un test qui contredisait le correctif de sécurité de la
# 1.12.0 — sans que personne ne la lise. Un garde-fou qu'on peut franchir sans
# s'en apercevoir n'en est pas un : on vérifie, et l'on refuse.
#
# Trois conditions : le code du paquet est commité (sinon la CI n'a pas vu ce
# qu'on publie), ce commit est sur GitHub, et le workflow « CI » y a réussi.
verifier_la_ci() {
	# safe.directory : le dépôt vit sur un disque Windows, et git refuse, en
	# root, un dépôt qui ne lui appartient pas. core.fileMode : ce disque ne
	# conserve pas les droits, qui paraîtraient tous modifiés.
	local git=(git -c safe.directory='*' -c core.fileMode=false -C "$REPO")
	local sha modifies reponse verdict
	sha="$("${git[@]}" rev-parse HEAD 2>/dev/null)" || {
		echo "ERREUR : $REPO n'est pas un dépôt git lisible." >&2; return 1; }
	modifies="$("${git[@]}" status --porcelain -- VERSION packaging live-build po 2>/dev/null)"
	if [ -n "$modifies" ]; then
		echo "ERREUR : du code du paquet n'est pas commité — la CI ne l'a jamais vu :" >&2
		echo "$modifies" | sed 's/^/         /' >&2
		return 1
	fi
	reponse="$(curl -fsS --max-time 20 \
		"https://api.github.com/repos/Romtouf/codebyr-os/actions/runs?head_sha=$sha&per_page=50")" || {
		echo "ERREUR : GitHub injoignable — l'état de la CI est inconnu." >&2; return 1; }
	# Le plus récent passage du workflow « CI » sur CE commit fait foi.
	verdict="$(printf '%s' "$reponse" | python3 -c '
import json, sys
passages = [p for p in json.load(sys.stdin).get("workflow_runs", [])
            if p.get("path", "").endswith("/ci.yml")]
if not passages:
    print("absente")
elif passages[0].get("status") != "completed":
    print("en cours")
else:
    print("verte" if passages[0].get("conclusion") == "success" else "rouge")
')"
	case "$verdict" in
		verte) echo "    CI verte sur ${sha:0:12} : OK." ;;
		absente)
			echo "ERREUR : aucune CI pour ${sha:0:12} — ce commit est-il poussé ?" >&2
			return 1 ;;
		*)
			echo "ERREUR : CI $verdict sur ${sha:0:12} :" >&2
			echo "         https://github.com/Romtouf/codebyr-os/commit/$sha" >&2
			return 1 ;;
	esac
}

if [ "$MODE" = publier ]; then
	# ── Le paquet publié est-il celui du code actuel ? ──────────────────────
	#
	# publish-apt.sh publie ce qui traîne dans dist/. Rien ne garantissait que
	# ce .deb ait été construit APRÈS la dernière modification du code. Le
	# 23/08/2026, la 1.5.0 a été publiée avec la version précédente de l'icône
	# du panneau : le paquet datait d'avant le correctif, et personne ne pouvait
	# le voir — le numéro de version, lui, était le bon.
	#
	# C'est le même piège que l'ISO périmée dans build.sh : un artefact daté
	# que l'on republie en croyant publier le code. On compare donc les dates,
	# et on refuse plutôt que d'avertir.
	if [ "$CANAL" = essai ]; then
		# Le plus récent des paquets d'essai de CETTE version.
		DEB_COURANT=""
		for deb in "$DIST"/codebyr-tools_"${VERSION_COURANTE}"~essai*_all.deb; do
			[ -f "$deb" ] || continue
			if [ -z "$DEB_COURANT" ] || dpkg --compare-versions \
					"$(dpkg-deb -f "$deb" Version)" gt "$(dpkg-deb -f "$DEB_COURANT" Version)"; then
				DEB_COURANT="$deb"
			fi
		done
		if [ -z "$DEB_COURANT" ]; then
			echo "ERREUR : aucun paquet d'essai pour la version $VERSION_COURANTE." >&2
			echo "         Lancez d'abord ./build-deb.sh ${VERSION_COURANTE}~essai1" >&2
			exit 1
		fi
		VERSION_PUBLIEE="$(dpkg-deb -f "$DEB_COURANT" Version)"
	else
		DEB_COURANT="$DIST/codebyr-tools_${VERSION_COURANTE}_all.deb"
		VERSION_PUBLIEE="$VERSION_COURANTE"
	fi
	if [ ! -f "$DEB_COURANT" ]; then
		echo "ERREUR : aucun paquet pour la version $VERSION_COURANTE." >&2
		echo "         Lancez d'abord ./build-deb.sh" >&2
		exit 1
	fi
	RECENT="$(find "$REPO/live-build/config/includes.chroot_after_packages" \
		"$REPO/packaging/build-deb.sh" "$REPO/packaging/codebyr-tools.postinst" \
		"$REPO/packaging/codebyr-tools.preinst" "$REPO/packaging/codebyr-tools.postrm" \
		-newer "$DEB_COURANT" -print -quit 2>/dev/null || true)"
	if [ -n "$RECENT" ]; then
		echo "ERREUR : le paquet $VERSION_PUBLIEE est plus ancien que le code." >&2
		echo "         Modifié depuis sa construction : $RECENT" >&2
		echo "         Vous publieriez une version périmée sous un numéro juste." >&2
		echo "         Lancez ./build-deb.sh puis recommencez." >&2
		exit 1
	fi
	echo "    Paquet $VERSION_PUBLIEE postérieur au code : OK (canal $SUITE)."

	if ! verifier_la_ci; then
		# Échappatoire explicite, comme pour la clé nue : GitHub en panne, par
		# exemple. Jamais par défaut, et toujours dit en toutes lettres.
		[ "${CODEBYR_PUBLIER_SANS_CI:-0}" = "1" ] || exit 1
		echo "         → publié SANS validation de la CI (CODEBYR_PUBLIER_SANS_CI=1)." >&2
	fi

	echo "==> Génération du dépôt dans $REPODIR"
	rm -rf "$REPODIR"
	mkdir -p "$REPODIR"
	# Pas de « cp dist/*.deb » : dist/ reçoit aussi les paquets d'ESSAI. Une
	# version en « ~ » (1.17.0~essai1) est plus récente que la version publiée
	# précédente : unattended-upgrades l'installerait sur tout le parc. Et un
	# paquet plus récent que VERSION n'a rien à faire dans cette publication.
	# Le canal d'essai, lui, prend en plus SON paquet d'essai — un seul.
	vus=" "
	for deb in "$DIST"/*.deb; do
		nom="$(dpkg-deb -f "$deb" Package)"
		v="$(dpkg-deb -f "$deb" Version)"
		case "$v" in
			*"~"*)
				if [ "$deb" != "$DEB_COURANT" ]; then
					echo "    écarté (paquet d'essai) : $(basename "$deb") — $v"
					continue
				fi ;;
		esac
		if [ "$nom" != codebyr-tools ]; then
			echo "ERREUR : paquet inattendu dans $DIST : $(basename "$deb") ($nom)." >&2; exit 1
		fi
		if dpkg --compare-versions "$v" gt "$VERSION_COURANTE"; then
			echo "ERREUR : $(basename "$deb") ($v) est plus récent que VERSION ($VERSION_COURANTE)." >&2
			exit 1
		fi
		case "$vus" in
			*" $v "*) echo "ERREUR : deux paquets portent la version $v dans $DIST." >&2; exit 1 ;;
		esac
		vus="$vus$v "
		cp "$deb" "$REPODIR/"
	done

	cd "$REPODIR"
	dpkg-scanpackages --multiversion . > Packages
	gzip -9c Packages > Packages.gz
	echo "   Packages : $(grep -c '^Package:' Packages) paquet(s)"
else
	echo "==> Re-signature du dépôt existant (aucun paquet n'y change)"
	cd "$REPODIR"
fi

# Release : empreintes des index, requis par apt pour la vérification.
#
# Tout passe par apt-ftparchive, qui date lui-même le fichier. Auparavant un
# en-tête écrit à la main portait déjà un « Date: », et apt-ftparchive en
# ajoutait un second ; il hachait même ce Release à moitié écrit, qui se
# retrouvait listé dans ses propres empreintes. Écrit hors du dossier, puis
# déplacé.
validite=()
if [ "$VALIDITE_JOURS" -gt 0 ]; then
	validite=(-o "APT::FTPArchive::Release::ValidTime=$(( VALIDITE_JOURS * 86400 ))")
fi
rm -f Release InRelease Release.gpg
release_neuf="$(mktemp)"
apt-ftparchive \
	-o APT::FTPArchive::Release::Origin="Codebyr OS" \
	-o APT::FTPArchive::Release::Label="Codebyr OS" \
	-o APT::FTPArchive::Release::Suite="$SUITE" \
	-o APT::FTPArchive::Release::Codename="$CODENAME" \
	-o APT::FTPArchive::Release::Architectures=all \
	-o APT::FTPArchive::Release::Components=main \
	-o APT::FTPArchive::Release::Description="$DESCRIPTION" \
	"${validite[@]+"${validite[@]}"}" \
	release . > "$release_neuf"
mv "$release_neuf" Release
chmod 0644 Release
if grep -q '^Valid-Until:' Release; then
	echo "   Valable jusqu'au : $(sed -n 's/^Valid-Until: //p' Release)"
else
	echo "   AVERTISSEMENT : aucune date de péremption (CODEBYR_VALIDITE_JOURS=0)." >&2
fi

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
# Le dossier local et le dossier distant, nommés une fois (voir CANAL).
if [ "$CANAL" = essai ]; then
	echo "    ssh vps-local 'mkdir -p $DISTANT' && cd /c/Users/pcrom/codebyros/packaging/$(basename "$REPODIR") && scp ./* vps-local:$DISTANT/"
	OPTION_RESIGNER="--essai --resigner"
else
	echo "    cd /c/Users/pcrom/codebyros/packaging/$(basename "$REPODIR") && scp ./* vps-local:$DISTANT/"
	OPTION_RESIGNER="--resigner"
fi
if grep -q '^Valid-Until:' Release; then
	echo
	echo "À RETENIR : ce dépôt ($SUITE) se périme le $(sed -n 's/^Valid-Until: //p' Release)."
	echo "Avant cette date, republiez, ou re-signez sans rien changer :"
	echo "    ./publish-apt.sh $OPTION_RESIGNER   (puis le même envoi)"
fi
