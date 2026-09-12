#!/bin/sh
# Inspection du contenu réel de l'ISO (montage en lecture seule).
set -e
ISO=/mnt/c/Users/pcrom/codebyros/dist/codebyr-os-1.0-20260707-amd64.iso
mkdir -p /mnt/codebyr-iso /mnt/codebyr-squash
umount /mnt/codebyr-squash 2>/dev/null || true
umount /mnt/codebyr-iso 2>/dev/null || true
mount -o loop,ro "$ISO" /mnt/codebyr-iso
mount -o loop,ro /mnt/codebyr-iso/live/filesystem.squashfs /mnt/codebyr-squash
S=/mnt/codebyr-squash
echo "calamares            : $(test -f $S/usr/bin/calamares && echo PRESENT || echo ABSENT)"
echo "codebyr-installer    : $(test -f $S/usr/bin/codebyr-installer && echo PRESENT || echo ABSENT)"
echo "branding codebyr     : $(grep -l 'Codebyr OS' $S/etc/calamares/branding/debian/branding.desc >/dev/null 2>&1 && echo PRESENT || echo ABSENT)"
echo "bouton bienvenue     : $(grep -q 'Installer Codebyr OS sur ce disque' $S/usr/bin/codebyr-bienvenue 2>/dev/null && echo PRESENT || echo ABSENT)"
echo "correctif visionneuse: $(grep -q '_visionneuse_pour' $S/usr/bin/codebyr-space 2>/dev/null && echo PRESENT || echo ABSENT)"
echo "install-debian (officiel) :"
sed -n '1,40p' $S/usr/bin/install-debian 2>/dev/null || echo "  absent"
echo "--- sudoers live ---"
cat $S/etc/sudoers.d/codebyr-live 2>/dev/null || echo absent
umount /mnt/codebyr-squash
umount /mnt/codebyr-iso
