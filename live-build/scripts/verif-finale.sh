#!/bin/sh
# Vérification finale de l'ISO installable.
set -e
ISO=/mnt/c/Users/pcrom/codebyros/dist/codebyr-os-1.0-20260707-amd64.iso
mkdir -p /mnt/codebyr-iso /mnt/codebyr-squash
umount /mnt/codebyr-squash 2>/dev/null || true
umount /mnt/codebyr-iso 2>/dev/null || true
mount -o loop,ro "$ISO" /mnt/codebyr-iso
mount -o loop,ro /mnt/codebyr-iso/live/filesystem.squashfs /mnt/codebyr-squash
S=/mnt/codebyr-squash
echo "branding images: OK ?  $(grep -c 'images:' $S/etc/calamares/branding/debian/branding.desc)"
echo "style: retiré ?        $(grep -c 'sidebarBackground' $S/etc/calamares/branding/debian/branding.desc || true)"
echo "journal lanceur ?      $(grep -c 'codebyr-installer.log' $S/usr/bin/codebyr-installer)"
echo "d-i dans l'ISO ?       $(test -d /mnt/codebyr-iso/install && echo ENCORE LA || echo absent) / $(test -d /mnt/codebyr-iso/d-i && echo ENCORE LA || echo absent)"
echo "entrees menu grub :"
grep -E "menuentry" /mnt/codebyr-iso/boot/grub/grub.cfg 2>/dev/null | head -6
umount /mnt/codebyr-squash
umount /mnt/codebyr-iso
