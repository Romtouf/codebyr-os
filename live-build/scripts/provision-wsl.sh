#!/usr/bin/env bash
# Codebyr OS — provisionne la distribution WSL2 « Codebyr-Build » pour construire l'ISO.
# Idempotent : peut être relancé sans dommage. À exécuter en root dans la distro Debian.
set -euo pipefail

echo "==> Configuration des dépôts APT (trixie, toutes les zones)"
# Format deb822 (standard sur Debian 13). On écrase pour garantir les 4 zones.
cat > /etc/apt/sources.list.d/debian.sources <<'EOF'
Types: deb
URIs: http://deb.debian.org/debian
Suites: trixie trixie-updates
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg

Types: deb
URIs: http://security.debian.org/debian-security
Suites: trixie-security
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg
EOF
# Neutralise un éventuel sources.list hérité de l'image de conteneur.
[ -f /etc/apt/sources.list ] && : > /etc/apt/sources.list || true

export DEBIAN_FRONTEND=noninteractive

echo "==> Mise à jour de l'index"
apt-get update -qq

echo "==> Installation de la chaîne de build"
apt-get install -y --no-install-recommends \
	live-build \
	debootstrap \
	xorriso \
	squashfs-tools \
	mtools \
	dosfstools \
	ca-certificates \
	rsync \
	git \
	debian-archive-keyring \
	librsvg2-bin \
	imagemagick \
	file \
	xz-utils \
	zstd

echo "==> wget résilient (l'étape installateur de live-build utilise wget, pas APT)"
# Idempotent : on (re)pose notre bloc marqué.
sed -i '/# >>> codebyr wget resilient >>>/,/# <<< codebyr wget resilient <<</d' /etc/wgetrc 2>/dev/null || true
cat >> /etc/wgetrc <<'EOF'
# >>> codebyr wget resilient >>>
tries = 30
waitretry = 5
retry_connrefused = on
timeout = 60
# <<< codebyr wget resilient <<<
EOF

echo "==> Versions installées"
echo -n "live-build : "; dpkg-query -W -f='${Version}\n' live-build
echo -n "debootstrap: "; dpkg-query -W -f='${Version}\n' debootstrap
echo -n "xorriso    : "; xorriso --version 2>&1 | head -n1

echo "==> OK — environnement de build prêt."
