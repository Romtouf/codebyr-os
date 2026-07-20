#!/usr/bin/env bash
# Codebyr OS — construit le paquet Debian « codebyr-tools ».
#
# Ce paquet embarque tout le userland Codebyr (les outils codebyr-*, l'extension
# GNOME, le registre des Espaces, le bouclier anti-hameçonnage). Le publier dans
# le dépôt APT permet de livrer des CORRECTIFS aux machines DÉJÀ installées —
# ce que l'ISO seule ne permet pas.
#
#   ./build-deb.sh                 # version lue dans ../VERSION
#   ./build-deb.sh 1.0.2           # version explicite
#
# Sortie : packaging/dist/codebyr-tools_<version>_all.deb
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
# CODEBYR_REPO permet de builder même si le script est copié ailleurs (ex. WSL).
REPO="${CODEBYR_REPO:-$(cd "$HERE/.." && pwd)}"
SRC="$REPO/live-build/config/includes.chroot_after_packages"
VERSION="${1:-$(tr -d ' \t\r\n' < "$REPO/VERSION")}"
OUT="$HERE/dist"

[ -d "$SRC" ] || { echo "ERREUR : arborescence source introuvable ($SRC)." >&2; exit 1; }

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "==> codebyr-tools $VERSION — assemblage"

# 1) Les fichiers du userland, exactement tels qu'ils sont livrés dans l'ISO.
#    On ne prend QUE les chemins gérés par le paquet (pas tout includes.chroot).
for chemin in \
	usr/bin/codebyr-space \
	usr/bin/codebyr-jetable \
	usr/bin/codebyr-net-proxy \
	usr/bin/codebyr-config \
	usr/bin/codebyr-assistant \
	usr/bin/codebyr-bienvenue \
	usr/bin/codebyr-verifier \
	usr/share/gnome-shell/extensions/codebyr@codebyr.io \
	usr/share/codebyr/antiphishing \
	etc/codebyr/espaces.json
do
	if [ -e "$SRC/$chemin" ]; then
		mkdir -p "$STAGE/$(dirname "$chemin")"
		cp -a "$SRC/$chemin" "$STAGE/$(dirname "$chemin")/"
	else
		echo "   (absent, ignoré) $chemin"
	fi
done

# 2) Droits corrects. IMPORTANT : « cp -a » depuis un checkout Windows (9p)
#    hérite parfois de dossiers en 777 → répertoires système inscriptibles par
#    tous = faille. On normalise : dossiers 755, scripts 755, données 644.
find "$STAGE/usr" "$STAGE/etc" -type d -exec chmod 755 {} + 2>/dev/null || true
find "$STAGE/usr/bin" -type f -exec chmod 755 {} + 2>/dev/null || true
find "$STAGE/usr/share/codebyr" -type f -exec chmod 644 {} + 2>/dev/null || true
find "$STAGE/usr/share/gnome-shell" -type f -exec chmod 644 {} + 2>/dev/null || true
[ -f "$STAGE/etc/codebyr/espaces.json" ] && chmod 644 "$STAGE/etc/codebyr/espaces.json"

# 3) Taille installée (en Ko), pour le control.
TAILLE="$(du -sk "$STAGE" | cut -f1)"

# 4) Métadonnées du paquet.
mkdir -p "$STAGE/DEBIAN"
cat > "$STAGE/DEBIAN/control" <<EOF
Package: codebyr-tools
Version: $VERSION
Architecture: all
Maintainer: Codebyr OS <romain.formationoc@gmail.com>
Installed-Size: $TAILLE
Depends: python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, bubblewrap, dbus-user-session, firefox-esr | firefox
Recommends: flatpak, gnome-shell
Section: admin
Priority: optional
Homepage: https://os.codebyr.dev
Description: Outils Codebyr OS — compartimentation en Espaces
 Le userland de Codebyr OS : moteur d'Espaces isolés (bubblewrap), ouverture
 en Jetable, filtre réseau à liste blanche, bouclier anti-hameçonnage,
 assistant de sécurité et extension GNOME (liserés colorés, menu du Sceau).
 .
 Ce paquet permet de livrer les correctifs par « apt » aux machines déjà
 installées, sans regraver l'ISO.
EOF

# /etc/codebyr/espaces.json est une conffile : dpkg préserve les modifs locales.
echo "/etc/codebyr/espaces.json" > "$STAGE/DEBIAN/conffiles"

# postinst pris dans le dépôt (pas $HERE : le script peut tourner copié ailleurs),
# et dé-CRLF-isé au cas où le dépôt serait extrait avec des fins de ligne Windows
# (un \r dans un script shell le rend inexécutable).
sed 's/\r$//' "$REPO/packaging/codebyr-tools.postinst" > "$STAGE/DEBIAN/postinst"
chmod 755 "$STAGE/DEBIAN/postinst"

# 5) Construction (root non requis : --root-owner-group fixe les propriétaires).
mkdir -p "$OUT"
DEB="$OUT/codebyr-tools_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$STAGE" "$DEB" >/dev/null
echo "==> Paquet : $DEB"
dpkg-deb --info "$DEB" | sed -n '1,3p;/Description/,$p'
echo
echo "Vérifier le contenu : dpkg-deb --contents \"$DEB\""
