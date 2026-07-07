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

# — Bits exécutables (perdus/incertains via 9p) —
chmod +x "$WORK/auto/config"
chmod +x "$WORK"/config/hooks/normal/*.hook.chroot 2>/dev/null || true

cd "$WORK"

if [ "${1:-build}" = "clean" ]; then
	lb clean --purge || true
	echo "==> Nettoyage terminé."
	exit 0
fi

# — Construction —
echo "==> lb config"
lb config
echo "==> lb build  (téléchargement + assemblage — peut durer 20–40 min)"
# live-build renvoie parfois un code non-zéro sur une étape finale de nettoyage
# alors que l'ISO est bien produite : on ne s'y fie pas, on vérifie l'ISO.
lb build || echo "==> lb build a renvoyé un code non-zéro — vérification de l'ISO…"

# — Rapatriement de l'ISO —
mkdir -p "$DIST"
ISO="$(ls -1 "$WORK"/*.iso 2>/dev/null | head -n1 || true)"
if [ -z "$ISO" ]; then
	echo "ERREUR : aucune ISO produite (voir la sortie ci-dessus)." >&2
	exit 1
fi
OUT="$DIST/codebyr-os-1.0-$(date +%Y%m%d)-amd64.iso"
cp -f "$ISO" "$OUT"
sync
echo "==> ISO prête : $OUT  ($(du -h "$OUT" | cut -f1))"
