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
OUT="$REPO/packaging/dist"

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
	usr/bin/codebyr-durcir-poste \
	usr/lib/codebyr \
	usr/lib/systemd/system/codebyr-uid.socket \
	usr/lib/systemd/system/codebyr-uid.service \
	usr/lib/firefox-esr/distribution/policies.json \
	usr/share/gnome-shell/extensions/codebyr@codebyr.io \
	usr/share/codebyr \
	usr/share/nautilus-python \
	usr/share/applications/io.codebyr.Ouvrir.desktop \
	usr/share/applications/io.codebyr.Bienvenue.desktop \
	usr/share/icons/hicolor/scalable/apps/io.codebyr.Bienvenue.svg \
	usr/share/glib-2.0/schemas/90_codebyr.gschema.override \
	usr/share/plymouth/themes/codebyr \
	etc/xdg/autostart/codebyr-bienvenue.desktop \
	etc/skel \
	etc/codebyr/espaces.json \
	etc/sysctl.d/91-codebyr-noyau.conf \
	etc/default/grub.d/90-codebyr-noyau.cfg \
	etc/default/grub.d/91-codebyr-demarrage.cfg \
	etc/grub.d/35_codebyr_menu \
	etc/apparmor.d/codebyr-net-proxy \
	etc/apparmor.d/codebyr-uid
do
	if [ -e "$SRC/$chemin" ]; then
		mkdir -p "$STAGE/$(dirname "$chemin")"
		cp -a "$SRC/$chemin" "$STAGE/$(dirname "$chemin")/"
	else
		echo "   (absent, ignoré) $chemin"
	fi
done

# 1 bis) Fins de ligne. Un « \r » à la fin du shebang rend le script
#    INEXÉCUTABLE sous Linux : env cherche un programme nommé « python3\r ».
#    Sur Codebyr, cela veut dire qu'aucun Espace ne s'ouvre. Le postinst était
#    déjà protégé ainsi ; les scripts livrés ne l'étaient pas, alors que ce sont
#    eux qui font tourner le système. Constaté le 24/08/2026.
#
#    On corrige ICI, dans le paquet, et pas seulement dans le dépôt : c'est la
#    dernière barrière avant la machine de l'utilisateur, et la seule qui ne
#    dépende ni de git ni du poste où l'on construit.
find "$STAGE" -type f \( -name 'codebyr-*' -o -name '*.py' -o -name '*.sh' \) \
	-exec sed -i 's/\r$//' {} + 2>/dev/null || true

# 1 ter) Identité du système. Ce paquet la détourne de base-files (voir
#    codebyr-tools.preinst) et la génère ici, depuis SA version : c'est ainsi
#    qu'elle suit les mises à jour. Écrite par un hook de l'image, elle restait
#    à la version de l'ISO pour toujours, désignait un domaine qui n'existe pas
#    (codebyr.io), et base-files l'aurait rendue à Debian à la première version
#    mineure de Debian.
#
#    Les adresses sont vérifiées par tests/test_coherence.py : un domaine
#    « codebyr » qui ne serait pas codebyr.dev y échoue.
mkdir -p "$STAGE/usr/lib"
cat > "$STAGE/usr/lib/os-release" <<EOF
PRETTY_NAME="Codebyr OS $VERSION"
NAME="Codebyr OS"
VERSION_ID="$VERSION"
VERSION="$VERSION"
VERSION_CODENAME=codebyr
ID=codebyr
ID_LIKE=debian
LOGO=codebyr-logo
HOME_URL="https://os.codebyr.dev/"
SUPPORT_URL="https://github.com/Romtouf/codebyr-os/issues/new/choose"
BUG_REPORT_URL="https://github.com/Romtouf/codebyr-os/issues"
EOF

# 1 quater) Avatar par défaut des nouveaux comptes : le Sceau, à la place de la
#    spirale Debian que desktop-base livre en /etc/skel/.face (détournée par le
#    preinst, comme l'identité du système).
#
#    Posé ICI, dans le paquet, et jamais par l'image : celle-ci copie ses
#    fichiers AVANT d'installer le paquet (hook 1000). Le preinst aurait alors
#    rangé le Sceau comme « copie de desktop-base » — et, ce fichier étant une
#    conffile de desktop-base, chaque mise à jour de desktop-base l'aurait cru
#    modifié et posé une question, qu'unattended-upgrades ne pose pas : il
#    aurait laissé desktop-base de côté, pour toujours.
mkdir -p "$STAGE/etc/skel"
cp "$SRC/usr/share/codebyr/avatar.svg" "$STAGE/etc/skel/.face"

# 1 quater bis) Les entrées Linux du menu de GRUB, sans « Loading Linux … » :
#    ce script remplace celui de grub-common, détourné par le preinst (voir
#    packaging/grub/10_linux). Posé ICI, jamais par l'image, pour la même
#    raison que l'avatar : le preinst aurait rangé ce script comme étant
#    celui de Debian, et il se serait appelé lui-même.
mkdir -p "$STAGE/etc/grub.d"
sed 's/\r$//' "$REPO/packaging/grub/10_linux" > "$STAGE/etc/grub.d/10_linux"

# 1 quinquies) Les langues autres que le français (po/<langue>.po), compilées
#    pour les programmes (.mo, gettext) et pour l'extension GNOME (.json). Voir
#    packaging/traductions.py. Obligatoires : sans elles, un testeur qui ne
#    lit pas le français recevrait un système entièrement en français, sans
#    que rien ne le signale à la construction.
[ -d "$REPO/po" ] || { echo "ERREUR : traductions introuvables ($REPO/po)." >&2; exit 1; }
python3 -B "$REPO/packaging/traductions.py" compiler "$REPO/po" "$STAGE"

# 2) Droits corrects. IMPORTANT : « cp -a » depuis un checkout Windows (9p)
#    hérite de fichiers et de dossiers en 777 → inscriptibles par tous = faille.
#
#    TOUT part donc de 644 (fichiers) et 755 (dossiers) ; seuls les programmes
#    reçoivent ensuite le bit d'exécution, un par un. La version précédente ne
#    normalisait que des dossiers choisis : de 1.13.0 à 1.16.6, le lanceur de
#    session /etc/xdg/autostart/codebyr-bienvenue.desktop et son icône partaient
#    en 777. N'importe quel compte de la machine — l'invité, sans mot de passe —
#    pouvait y écrire une commande, exécutée à l'ouverture de session de
#    chacun. Constaté le 30/09/2026 en préparant l'ISO reproductible.
find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE" -type f -exec chmod 644 {} +
find "$STAGE/usr/bin" -type f -exec chmod 755 {} + 2>/dev/null || true
# Le service des comptes d'Espaces et le premier processus d'un Espace : root
# exécute l'un, et l'autre est exécuté sous le compte de l'Espace. Sans le bit
# d'exécution, aucun Espace à compte dédié ne s'ouvre.
find "$STAGE/usr/lib/codebyr" -type f -exec chmod 755 {} + 2>/dev/null || true
find "$STAGE/usr/lib/systemd/system" -type f -exec chmod 644 {} + 2>/dev/null || true
find "$STAGE/usr/share/codebyr" "$STAGE/usr/share/nautilus-python" \
	-type f -exec chmod 644 {} + 2>/dev/null || true
find "$STAGE/usr/share/gnome-shell" -type f -exec chmod 644 {} + 2>/dev/null || true
find "$STAGE/usr/share/applications" -type f -exec chmod 644 {} + 2>/dev/null || true
chmod 644 "$STAGE/usr/lib/os-release"
# La politique qui fait installer le bouclier par Firefox lui-même.
chmod 644 "$STAGE/usr/lib/firefox-esr/distribution/policies.json"
# Réglages GNOME par défaut (dont Verr. Maj à la manière de Windows). Ils ne
# vivaient que dans l'image : une machine installée ne recevait jamais un
# nouveau défaut. glib les recompile seul, par son déclencheur dpkg.
if [ -f "$STAGE/usr/share/glib-2.0/schemas/90_codebyr.gschema.override" ]; then
	sed -i 's/\r$//' "$STAGE/usr/share/glib-2.0/schemas/90_codebyr.gschema.override"
	chmod 644 "$STAGE/usr/share/glib-2.0/schemas/90_codebyr.gschema.override"
fi
# /etc/skel est recopié dans le dossier personnel de chaque nouveau compte : un
# modèle en 0777 y arriverait exécutable et inscriptible par tous.
find "$STAGE/etc/skel" -type f -exec chmod 644 {} + 2>/dev/null || true
find "$STAGE/etc/skel" -type d -exec chmod 755 {} + 2>/dev/null || true
[ -f "$STAGE/etc/codebyr/espaces.json" ] && chmod 644 "$STAGE/etc/codebyr/espaces.json"
[ -d "$STAGE/etc/sysctl.d" ] && chmod 644 "$STAGE"/etc/sysctl.d/*.conf
# Même raison que pour les scripts : un réglage noyau suivi d'un « \r » serait
# rejeté par systemd-sysctl, en silence pour qui ne lit pas le journal.
[ -d "$STAGE/etc/sysctl.d" ] && sed -i 's/\r$//' "$STAGE"/etc/sysctl.d/*.conf
# Options du noyau : un « \r » collé à la dernière la rendrait invalide, et le
# noyau l'ignorerait sans rien dire.
[ -d "$STAGE/etc/default/grub.d" ] && sed -i 's/\r$//' "$STAGE"/etc/default/grub.d/*.cfg
# Scripts de GRUB : update-grub les exécute à chaque nouveau noyau. Sans le
# bit d'exécution, grub-mkconfig les saute en silence ; avec un « \r », il
# échoue, et le noyau ne s'installe pas.
if [ -d "$STAGE/etc/grub.d" ]; then
	find "$STAGE/etc/grub.d" -type f -exec sed -i 's/\r$//' {} +
	find "$STAGE/etc/grub.d" -type f -exec chmod 755 {} +
fi
# Profils AppArmor : un « \r » y est une erreur de syntaxe, et un profil qui ne
# se charge pas laisse le programme NON confiné, sans rien qui le signale.
if [ -d "$STAGE/etc/apparmor.d" ]; then
	find "$STAGE/etc/apparmor.d" -type f -exec sed -i 's/\r$//' {} +
	find "$STAGE/etc/apparmor.d" -type f -exec chmod 644 {} +
fi

# 3) Taille installée (en Ko), pour le control.
TAILLE="$(du -sk "$STAGE" | cut -f1)"

# 4) Métadonnées du paquet.
#
# python3-nautilus est une dépendance FERME, et non une simple recommandation.
# Sans lui, le clic droit « Ouvrir en Jetable » n'est pas chargé — en silence,
# sans le moindre message : le menu contextuel a l'air parfaitement normal.
# Constaté le 20/08/2026 sur un poste où le paquet avait été installé par
# « dpkg -i », qui n'installe jamais les recommandations.
#
# La leçon vaut au-delà de ce cas : une fonctionnalité qui repose sur un
# Recommends n'est pas livrée, elle est espérée. Deux autres dépendances
# passent donc de l'espoir à la règle :
#
#   · acl — le service des comptes d'Espaces appelle /usr/bin/setfacl pour
#     prêter l'affichage et la carte graphique à un Espace. Le paquet n'était
#     présent que par ricochet (colord, libsane1) : qu'ils partent, et un
#     Espace à compte séparé ne s'ouvrait plus ;
#   · libnotify-bin — c'est par notify-send que codebyr-space dit POURQUOI il
#     refuse d'ouvrir un Espace. Sans lui, le refus a lieu en silence ;
#   · systemd-cryptsetup — c'est lui qui ouvre, une fois le système démarré,
#     les volumes chiffrés de /etc/crypttab autres que le disque principal
#     (que l'image de démarrage ouvre seule). Debian 13 l'a sorti dans un
#     paquet à part, et l'image ne l'avait pas : l'espace d'échange chiffré
#     ne s'ouvrait jamais, et chaque démarrage l'attendait 90 secondes en vain.
#     Constaté le 28/09/2026 ;
#   · libgdk-pixbuf2.0-bin — gdk-pixbuf-thumbnailer, qui fabrique les vignettes
#     des images (PNG, JPEG, SVG, WebP…) dans Fichiers. Nautilus ne fait que le
#     recommander : aucune image n'avait d'aperçu, nulle part dans Codebyr.
#     Constaté le 29/09/2026.
mkdir -p "$STAGE/DEBIAN"
cat > "$STAGE/DEBIAN/control" <<EOF
Package: codebyr-tools
Version: $VERSION
Architecture: all
Maintainer: Codebyr OS <romain.formationoc@gmail.com>
Installed-Size: $TAILLE
Depends: python3 (>= 3.12), libseccomp2, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, bubblewrap, dbus-user-session, firefox-esr | firefox, python3-nautilus, acl, libnotify-bin, systemd-cryptsetup, libgdk-pixbuf2.0-bin
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
# preinst et postrm : la déviation de l'identité du système (voir 1 ter).
for script in preinst postrm; do
	sed 's/\r$//' "$REPO/packaging/codebyr-tools.$script" > "$STAGE/DEBIAN/$script"
	chmod 755 "$STAGE/DEBIAN/$script"
done

# 5) Construction (root non requis : --root-owner-group fixe les propriétaires).
mkdir -p "$OUT"
DEB="$OUT/codebyr-tools_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$STAGE" "$DEB" >/dev/null
echo "==> Paquet : $DEB"
dpkg-deb --info "$DEB" | sed -n '1,3p;/Description/,$p'
echo
echo "Vérifier le contenu : dpkg-deb --contents \"$DEB\""
