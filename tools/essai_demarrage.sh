#!/bin/bash
# Démarre une ISO de Codebyr OS dans QEMU et lit son essai de démarrage.
#
#     bash tools/essai_demarrage.sh dist/codebyr-os-*.iso
#
# L'image porte un service inerte (codebyr-essai-demarrage.service) que
# « codebyr.essai=1 » sur la ligne du noyau réveille : il observe la session
# live — GNOME, extensions, isolation, un Espace sous son compte — et écrit
# sur le second port série (ttyS1) une ligne « CODEBYR-ESSAI OK|ECHEC … » par
# contrôle. Ce script démarre l'image avec ce paramètre, garde les deux ports
# série (ttyS0 : la console du noyau et de systemd), et échoue si un contrôle
# échoue ou si l'essai ne va pas au bout.
#
# Avec KVM (la CI de GitHub), une dizaine de minutes ; sans (un WSL sans
# virtualisation imbriquée), l'émulation est bien plus lente :
# CODEBYR_DELAI_ESSAI règle le délai, en secondes.
set -euo pipefail

iso=${1:?usage : essai_demarrage.sh <iso>}
journal=${CODEBYR_JOURNAL_SERIE:-$PWD/essai-demarrage.log}
console=${CODEBYR_JOURNAL_CONSOLE:-$PWD/essai-console.log}
delai=${CODEBYR_DELAI_ESSAI:-2400}
travail=$(mktemp -d)
trap 'rm -rf "$travail"' EXIT

xorriso -osirrox on -indev "$iso" \
	-extract /live/vmlinuz "$travail/vmlinuz" \
	-extract /live/initrd.img "$travail/initrd.img" >/dev/null 2>&1

if [ -w /dev/kvm ]; then
	acceleration=(-enable-kvm -cpu host)
else
	echo "Sans KVM : émulation lente (délai ${delai} s)."
	acceleration=(-accel tcg)
fi

# La ligne du noyau de l'entrée « Live » de l'image, sans l'écran de
# démarrage, avec la console série — et le paramètre qui réveille l'essai.
noyau="boot=live components locales=fr_FR.UTF-8 keyboard-layouts=fr"
noyau="$noyau live-config.hostname=codebyr console=tty0 console=ttyS0,115200 codebyr.essai=1"

: >"$journal"
: >"$console"
# Premier port série (ttyS0) : la console ; second (ttyS1) : l'essai seul.
timeout "$delai" qemu-system-x86_64 "${acceleration[@]}" -m 4096 -smp 2 \
	-kernel "$travail/vmlinuz" -initrd "$travail/initrd.img" -append "$noyau" \
	-drive file="$iso",media=cdrom,readonly=on \
	-display none -vga std -serial file:"$console" -serial file:"$journal" \
	-nic user,model=virtio-net-pci -no-reboot &
qemu=$!

while kill -0 "$qemu" 2>/dev/null; do
	grep -q "CODEBYR-ESSAI FIN" "$journal" && break
	sleep 10
done
sleep 5
kill "$qemu" 2>/dev/null || true
wait "$qemu" 2>/dev/null || true

grep -a "CODEBYR-ESSAI" "$journal" || true
if ! grep -aq "CODEBYR-ESSAI FIN" "$journal"; then
	echo "L'essai n'est pas allé au bout : voir $journal et $console" >&2
	exit 1
fi
if grep -aq "CODEBYR-ESSAI ECHEC" "$journal"; then
	echo "Au moins un contrôle a échoué." >&2
	exit 1
fi
echo "L'image démarre, et tout ce qui a été observé est conforme."
