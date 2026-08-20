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
cp -f "$REPO/branding/wallpapers/codebyr-clair.svg"  "$BGDIR/"
cp -f "$REPO/branding/wallpapers/codebyr-sombre.svg" "$BGDIR/"

# — Fond de menu de démarrage : rasterisé depuis branding/boot-splash.svg —
if command -v rsvg-convert >/dev/null 2>&1 && [ -f "$REPO/branding/boot-splash.svg" ]; then
	for d in "$WORK/config/bootloaders/syslinux_common" "$WORK/config/bootloaders/grub-pc"; do
		mkdir -p "$d"
		rsvg-convert -w 800 -h 600 "$REPO/branding/boot-splash.svg" -o "$d/splash.png"
	done
	echo "==> Fond de démarrage Codebyr généré (splash.png)"
fi

# — Paquet codebyr-tools embarqué : le hook 1000 l'installera via dpkg pour que
#   codebyr-tools soit un VRAI paquet (donc suivi par apt/unattended-upgrades).
#   Construit ici pour être toujours cohérent avec la version courante du dépôt.
# Version relevée UNE FOIS, avant toute construction : c'est elle qui sera
# embarquée dans l'image, et c'est donc elle qui doit la nommer à la fin.
VER_EMBARQUEE="$(tr -d ' \t\r\n' < "$REPO/VERSION")"

if [ -f "$REPO/packaging/build-deb.sh" ]; then
	echo "==> Construction du paquet codebyr-tools $VER_EMBARQUEE (embarqué pour les MAJ)"
	CODEBYR_REPO="$REPO" bash "$REPO/packaging/build-deb.sh" >/dev/null
	DEBSRC="$REPO/packaging/dist/codebyr-tools_${VER_EMBARQUEE}_all.deb"
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
echo "==> lb config"
lb config
echo "==> lb build  (téléchargement + assemblage — peut durer 20–40 min)"
# Repère temporel : sert à prouver que l'ISO trouvée ensuite est bien CELLE
# de cette construction, et pas un reliquat oublié dans l'arbre.
DEBUT="$WORK/.codebyr-debut"
: > "$DEBUT"

# live-build renvoie parfois un code non-zéro sur une étape finale de nettoyage
# alors que l'ISO est bien produite : on ne s'y fie pas, on vérifie l'ISO.
lb build || echo "==> lb build a renvoyé un code non-zéro — vérification de l'ISO…"

# — Rapatriement de l'ISO —
mkdir -p "$DIST"
ISO="$(ls -1 "$WORK"/*.iso 2>/dev/null | head -n1 || true)"
if [ -n "$ISO" ] && [ ! "$ISO" -nt "$DEBUT" ]; then
	echo "ERREUR : l'ISO trouvée est ANTÉRIEURE au début de cette construction." >&2
	echo "         C'est un reliquat, pas votre version : rien n'a été reconstruit." >&2
	# Les deux dates, sans quoi le diagnostic se fait à l'aveugle : c'est ce qui
	# a coûté une demi-heure d'enquête le 20/08/2026.
	echo "         ISO   : $(date -r "$ISO" '+%F %T')  ($ISO)" >&2
	echo "         Début : $(date -r "$DEBUT" '+%F %T')" >&2
	echo "         Relancez avec « $0 clean » pour repartir d'un arbre propre." >&2
	exit 1
fi
if [ -z "$ISO" ]; then
	echo "ERREUR : aucune ISO produite (voir la sortie ci-dessus)." >&2
	exit 1
fi
# Le nom porte la version EMBARQUÉE, relevée au début de la construction — pas
# celle lue maintenant. Une construction dure une heure : si VERSION change
# entre-temps (correctif publié pendant ce temps), relire le fichier ici
# baptiserait l'image d'une version qu'elle ne contient pas. Une étiquette qui
# ment sur son contenu est pire que pas d'étiquette du tout.
OUT="$DIST/codebyr-os-${VER_EMBARQUEE}-$(date +%Y%m%d)-amd64.iso"
cp -f "$ISO" "$OUT"
sync
echo "==> ISO prête : $OUT  ($(du -h "$OUT" | cut -f1))"
