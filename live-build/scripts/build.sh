#!/usr/bin/env bash
# Codebyr OS — construction de l'ISO (Phase 1).
#
#   ./build.sh          construit l'ISO
#   ./build.sh clean    purge l'arbre de build
#
# IMPORTANT : live-build exige root ET un système de fichiers Linux natif.
# On ne construit JAMAIS directement sur /mnt/c (9p) : on recopie la config
# dans un répertoire ext4 de WSL, puis on rapatrie l'ISO dans dist/.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
# Racine du dépôt : priorité à CODEBYR_REPO (fiable même si ce script est copié
# ailleurs, ex. /tmp), sinon déduction depuis l'emplacement du script.
REPO="${CODEBYR_REPO:-$(cd "$HERE/../.." 2>/dev/null && pwd)}"
SRC="$REPO/live-build"
WORK="${CODEBYR_WORK:-/var/tmp/codebyr-build}"
DIST="$REPO/dist"

# GARDE-FOU : sans config live-build valide, on n'exécute AUCUN rsync.
# (empêche une source erronée comme "/" de déclencher une copie catastrophique)
if [ ! -f "$SRC/auto/config" ] || [ ! -d "$SRC/config/package-lists" ]; then
	echo "ERREUR : config live-build introuvable sous '$SRC'." >&2
	echo "Définissez CODEBYR_REPO vers la racine du dépôt," >&2
	echo "ex: CODEBYR_REPO=/mnt/c/Users/pcrom/codebyros" >&2
	exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
	echo "ERREUR : live-build doit s'exécuter en root (sudo ou -u root)." >&2
	exit 1
fi

# — Construction REPRODUCTIBLE : l'image d'un commit, pas d'un poste —
#
# Deux constructions du même commit doivent donner la même ISO, octet pour
# octet : c'est ce qui permet à quiconque de vérifier que l'image publiée sort
# bien du code publié. Trois choses variaient d'une construction à l'autre :
#
#   · les SOURCES. Le dossier de travail peut contenir des modifications non
#     commitées, et, lu depuis le disque Windows (9p), chaque fichier y apparaît
#     en 777 avec la date de son dernier passage sur ce poste. On construit donc
#     depuis le COMMIT, extrait par « git archive » : mêmes octets, mêmes droits
#     (ceux que git enregistre), même date — celle du commit — partout ;
#   · l'HEURE. live-build sait estampiller toute l'image d'une date unique,
#     SOURCE_DATE_EPOCH : on lui donne celle du commit ;
#   · l'état du MIROIR Debian, qui change chaque jour. On l'installe depuis
#     snapshot.debian.org, tel qu'il était la veille du commit. L'image, elle,
#     garde les miroirs ordinaires pour ses mises à jour.
#
# CODEBYR_NON_COMMITE=1 construit le dossier de travail tel quel, pour essayer
# une modification avant de la commiter. Cette image-là n'est PAS reproductible
# et ne doit jamais être publiée.
GIT="git -C $REPO -c safe.directory=*"
if [ "${CODEBYR_NON_COMMITE:-0}" = "1" ]; then
	SOURCE="$REPO"
	SNAPSHOT=""
	echo "==> Dossier de travail, commité ou non : image NON reproductible (essai seulement)." >&2
else
	COMMIT="$($GIT rev-parse HEAD)"
	if [ -n "$($GIT status --porcelain -- VERSION live-build branding packaging po)" ]; then
		echo "==> ATTENTION : des modifications non commitées ne seront PAS dans l'image" >&2
		echo "    (CODEBYR_NON_COMMITE=1 pour les essayer)." >&2
	fi
	SOURCE="$(mktemp -d /var/tmp/codebyr-source.XXXXXX)"
	trap 'rm -rf "$SOURCE"' EXIT
	# tar.umask : les droits de l'archive sont ceux de git (644, ou 755 pour un
	# programme), pas ceux que le masque du poste ferait sortir.
	$GIT -c tar.umask=0022 archive --format=tar "$COMMIT" \
		VERSION live-build branding packaging po | tar -x -C "$SOURCE"
	SOURCE_DATE_EPOCH="$($GIT log -1 --format=%ct "$COMMIT")"
	export SOURCE_DATE_EPOCH
	# Debian tel qu'il était 24 heures AVANT le commit. snapshot.debian.org
	# publie par lots, toutes les quelques heures : un lot en cours d'import à
	# l'heure du commit apparaît plus tard, daté d'avant. Construit aussitôt,
	# le commit aurait eu un Debian ; reconstruit le lendemain, un autre. Un
	# jour de marge ne laisse que des lots terminés.
	SNAPSHOT="$(date -u -d "@$((SOURCE_DATE_EPOCH - 86400))" +%Y%m%dT%H%M%SZ)"
	echo "==> Commit  : $COMMIT"
	echo "==> Date    : $(date -u -d "@$SOURCE_DATE_EPOCH" +%Y%m%dT%H%M%SZ) (SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH)"
	echo "==> Debian  : tel qu'au $SNAPSHOT (snapshot.debian.org)"
fi
SRC="$SOURCE/live-build"

echo "==> Source  : $SRC"
echo "==> Travail : $WORK   (FS natif — obligatoire)"
echo "==> Sortie  : $DIST"

# — Recopie de la config vers un FS natif —
mkdir -p "$WORK"
rsync -a --delete \
	--exclude 'cache/' --exclude '.build/' --exclude 'chroot/' \
	--exclude 'binary/' --exclude 'dist/' \
	"$SRC"/ "$WORK"/

# — Fonds d'écran : injectés depuis branding/ (source unique de vérité) —
# includes.chroot_after_packages = copié après l'install, juste avant les hooks.
BGDIR="$WORK/config/includes.chroot_after_packages/usr/share/backgrounds/codebyr"
mkdir -p "$BGDIR"
cp -f "$SOURCE/branding/wallpapers/codebyr-clair.svg"  "$BGDIR/"
cp -f "$SOURCE/branding/wallpapers/codebyr-sombre.svg" "$BGDIR/"

# — Fond de menu de démarrage : rasterisé depuis branding/boot-splash.svg —
if command -v rsvg-convert >/dev/null 2>&1 && [ -f "$SOURCE/branding/boot-splash.svg" ]; then
	for d in "$WORK/config/bootloaders/syslinux_common" "$WORK/config/bootloaders/grub-pc"; do
		mkdir -p "$d"
		rsvg-convert -w 800 -h 600 "$SOURCE/branding/boot-splash.svg" -o "$d/splash.png"
	done
	echo "==> Fond de démarrage Codebyr généré (splash.png)"
fi

# — Paquet codebyr-tools embarqué : le hook 1000 l'installera via dpkg pour que
#   codebyr-tools soit un VRAI paquet (donc suivi par apt/unattended-upgrades).
#   Construit ici pour être toujours cohérent avec la version courante du dépôt.
# Version relevée UNE FOIS, avant toute construction : c'est elle qui sera
# embarquée dans l'image, et c'est donc elle qui doit la nommer à la fin.
VER_EMBARQUEE="$(tr -d ' \t\r\n' < "$SOURCE/VERSION")"

# Cette version doit aussi NOMMER le système à l'intérieur de l'image, et pas
# seulement le fichier ISO. Les hooks de branding la figeaient en dur : l'ISO
# 1.15.0 s'annonçait « Codebyr OS 1.0 » dans /etc/os-release, dans lsb_release
# et sur la bannière de console. On la dépose donc dans le chroot, et les hooks
# la lisent — ce qui reste vrai aux versions suivantes sans rien y retoucher.
mkdir -p "$WORK/config/includes.chroot_after_packages/etc/codebyr"
printf '%s\n' "$VER_EMBARQUEE" \
	> "$WORK/config/includes.chroot_after_packages/etc/codebyr/version"

if [ -f "$SOURCE/packaging/build-deb.sh" ]; then
	echo "==> Construction du paquet codebyr-tools $VER_EMBARQUEE (embarqué pour les MAJ)"
	CODEBYR_REPO="$SOURCE" bash "$SOURCE/packaging/build-deb.sh" >/dev/null
	DEBSRC="$SOURCE/packaging/dist/codebyr-tools_${VER_EMBARQUEE}_all.deb"
	if [ -f "$DEBSRC" ]; then
		mkdir -p "$WORK/config/includes.chroot_after_packages/opt/codebyr"
		cp -f "$DEBSRC" "$WORK/config/includes.chroot_after_packages/opt/codebyr/"
	else
		echo "AVERTISSEMENT : paquet codebyr-tools introuvable, canal MAJ non embarqué." >&2
	fi
fi

# — Bits exécutables (perdus/incertains via 9p) —
chmod +x "$WORK/auto/config"
chmod +x "$WORK"/config/hooks/normal/*.hook.chroot 2>/dev/null || true

cd "$WORK"

if [ "${1:-build}" = "clean" ]; then
	lb clean --purge || true
	echo "==> Nettoyage terminé."
	exit 0
fi

# — Jalons d'une construction précédente : le piège à ISO périmée —
#
# live-build note chaque étape terminée dans .build/, et « rsync --delete »
# n'y touche pas (le dossier est exclu). Relancer une construction sur un arbre
# déjà bâti fait donc SAUTER toutes les étapes : lb annonce fièrement « Build
# completed successfully »… sans avoir rien reconstruit, et sans produire la
# moindre ISO. Pire, s'il en produisait une, elle contiendrait l'ancien chroot.
#
# Constaté en vrai : une reconstruction de la 1.2.0 a « réussi » en 90 secondes
# sur un arbre du 2 août, contenant encore le userland de la 1.0.7.
#
# On nettoie donc systématiquement dès qu'un jalon traîne. « lb clean » garde le
# cache des paquets téléchargés : on perd le chroot, pas le téléchargement.
if [ -d "$WORK/.build" ] && [ -n "$(ls -A "$WORK/.build" 2>/dev/null)" ]; then
	if [ "${CODEBYR_INCREMENTAL:-0}" = "1" ]; then
		echo "==> Jalons conservés (CODEBYR_INCREMENTAL=1) — l'ISO produite" >&2
		echo "    peut ne pas refléter vos modifications." >&2
	else
		echo "==> Construction précédente détectée : nettoyage (le cache est gardé)"
		lb clean
	fi
fi

# — Construction —
#
# En mode reproductible, trois réglages de plus :
#   · le miroir figé à la date du commit, pour construire (--mirror-bootstrap,
#     --mirror-chroot, --mirror-chroot-security). Les index de sécurité d'une
#     date passée portent une échéance de 7 jours : apt la dépasserait dès
#     qu'on reconstruit une version ancienne, d'où Check-Valid-Until=false —
#     la signature, elle, reste vérifiée ;
#   · --apt-indices false : en fin de construction, live-build retélécharge
#     les index apt depuis le miroir DU JOUR et les laisse dans l'image. La
#     machine installée les récupère à sa première mise à jour ;
#   · le système de base (debootstrap) refait à chaque fois : live-build le
#     garde en cache (cache/bootstrap) et le réutilise d'une construction à
#     l'autre, mis à niveau. Celui de ce poste datait du 12/09/2026 ; la CI,
#     elle, part de rien. Le cache des PAQUETS reste : chaque fichier y est
#     vérifié par son empreinte, il ne change rien au résultat.
LB_OPTIONS=()
if [ -n "$SNAPSHOT" ]; then
	SNAP="http://snapshot.debian.org/archive"
	LB_OPTIONS=(
		--mirror-bootstrap "$SNAP/debian/$SNAPSHOT/"
		--mirror-chroot "$SNAP/debian/$SNAPSHOT/"
		--mirror-chroot-security "$SNAP/debian-security/$SNAPSHOT/"
		--apt-options "--yes -o Acquire::Retries=5 -o Acquire::Check-Valid-Until=false"
		--apt-indices false
	)
	rm -rf "$WORK/cache/bootstrap"
fi
echo "==> lb config"
lb config "${LB_OPTIONS[@]}"
echo "==> lb build  (téléchargement + assemblage — peut durer 20–40 min)"
# Preuve qu'on ne signera pas un reliquat : on EFFACE toute ISO présente avant
# de construire. Ce qui se trouvera là ensuite ne peut venir que d'ici.
#
# La version précédente comparait les dates — et se trompait toujours. live-build
# fait des constructions REPRODUCTIBLES : il fixe SOURCE_DATE_EPOCH au démarrage
# de « lb build » et xorriso en estampille l'image. La date de l'ISO est donc,
# par construction, celle du début — jamais postérieure à un repère pris au même
# instant. Le test ne pouvait pas être vrai une seule fois.
#
# Le 20/08/2026, il a rejeté une ISO parfaitement valide en annonçant « rien n'a
# été reconstruit », et fait relancer une construction d'une heure pour rien. Un
# garde-fou qui crie au loup à chaque passage finit par être contourné, ce qui
# est pire que son absence : on le désactive le jour où il a raison.
rm -f "$WORK"/*.iso

# Les étapes de « lb build », une à une : juste avant la mise en image du
# système (lb binary), on efface ce qui dépend de la machine qui construit, ou
# de l'instant. Pas plus tôt : « lb installer », même sans installeur Debian,
# remonte les sources apt et relance « apt update », qui refait pkgcache.bin. Relevé le 30/09/2026 en comparant,
# pour le même commit, l'ISO construite sur ce poste à celle de la CI :
#   · la date du dossier /proc, point de montage, qui variait d'une machine
#     à l'autre (les autres points de montage suivent, par précaution) ;
#   · les caches d'apt (pkgcache.bin) et du catalogue de logiciels
#     (swcatalog), que leurs outils refont seuls au premier besoin ;
#   · debconf : quand la machine qui construit démarre en UEFI, le script
#     d'installation de shim-signed le voit (/sys/firmware/efi) et enregistre
#     ses questions une seconde fois, sous « shim-signed:amd64 ». Sans effet —
#     ce champ ne sert qu'à la purge du paquet — mais l'image en dépendait.
normaliser_le_systeme() {
	local racine="$WORK/chroot"
	[ -d "$racine/etc" ] || return 0
	if [ -n "${SOURCE_DATE_EPOCH:-}" ]; then
		touch -h -d "@$SOURCE_DATE_EPOCH" "$racine/proc" "$racine/sys" "$racine/dev" "$racine/run"
	fi
	rm -f "$racine"/var/cache/apt/*.bin
	rm -rf "$racine"/var/cache/swcatalog/cache/*
	sed -i 's/^Owners: shim-signed, shim-signed:amd64$/Owners: shim-signed/' \
		"$racine/var/cache/debconf/config.dat"
	echo "==> Système normalisé avant la mise en image"
}

# live-build renvoie parfois un code non-zéro sur une étape finale de nettoyage
# alors que l'ISO est bien produite : on ne s'y fie pas, on vérifie l'ISO.
{ lb bootstrap && lb chroot && lb installer && normaliser_le_systeme && lb binary && lb source; } \
	|| echo "==> live-build a renvoyé un code non-zéro — vérification de l'ISO…"

# — Rapatriement de l'ISO —
mkdir -p "$DIST"
ISO="$(ls -1 "$WORK"/*.iso 2>/dev/null | head -n1 || true)"
if [ -z "$ISO" ]; then
	echo "ERREUR : aucune ISO produite (voir la sortie ci-dessus)." >&2
	exit 1
fi
# Le nom porte la version EMBARQUÉE, relevée au début de la construction — pas
# celle lue maintenant. Une construction dure une heure : si VERSION change
# entre-temps (correctif publié pendant ce temps), relire le fichier ici
# baptiserait l'image d'une version qu'elle ne contient pas. Une étiquette qui
# ment sur son contenu est pire que pas d'étiquette du tout.
# La date du nom est celle de l'image (SOURCE_DATE_EPOCH, fixée par live-build
# s'il ne l'a pas reçue), pas celle du jour : reconstruire un commit plus tard
# doit redonner le même nom.
OUT="$DIST/codebyr-os-${VER_EMBARQUEE}-$(date -u -d "@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y%m%d)-amd64.iso"
cp -f "$ISO" "$OUT"
sync
echo "==> ISO prête : $OUT  ($(du -h "$OUT" | cut -f1))"
if [ -n "$SNAPSHOT" ]; then
	echo "    Commit $COMMIT, Debian au $SNAPSHOT."
	echo "    SHA256 $(sha256sum "$OUT" | cut -d' ' -f1)"
	echo "    Reconstruire ce commit ailleurs doit redonner cette empreinte."
fi
