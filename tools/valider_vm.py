#!/usr/bin/env python3
"""VM QEMU jetable, sans disque physique ni fenêtre sur le poste utilisateur.

Usage : demarrer image.iso ; capture /var/tmp/codebyr-vm-* ;
touche /var/tmp/codebyr-vm-* ret ; arreter /var/tmp/codebyr-vm-*.
Les images restent des preuves à inspecter : démarrer QEMU ne valide pas GNOME.
"""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import tempfile


def qmp(dossier, commande, arguments=None):
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(10)
        sock.connect(str(dossier / "qmp"))
        with sock.makefile("rwb") as flux:
            json.loads(flux.readline())
            for requete in ({"execute": "qmp_capabilities"},
                            {"execute": commande, "arguments": arguments or {}}):
                flux.write(json.dumps(requete).encode() + b"\n")
                flux.flush()
                while True:
                    ligne = flux.readline()
                    if not ligne:
                        return {}
                    resultat = json.loads(ligne)
                    if "error" in resultat:
                        raise RuntimeError(resultat["error"])
                    if "return" in resultat:
                        break
            return resultat


def demarrer(iso):
    if not iso.is_file():
        raise ValueError("ISO absente")
    dossier = Path(tempfile.mkdtemp(prefix="codebyr-vm-", dir="/var/tmp"))
    disque = dossier / "disque.qcow2"
    subprocess.run(["qemu-img", "create", "-f", "qcow2", str(disque), "32G"], check=True)
    subprocess.run([
        "qemu-system-x86_64", "-accel", "tcg,thread=multi", "-cpu", "max",
        "-m", "4096", "-smp", "2", "-device", "virtio-vga",
        "-display", "none", "-monitor", "none", "-serial", "file:" + str(dossier / "serial.log"),
        "-qmp", "unix:" + str(dossier / "qmp") + ",server=on,wait=off",
        "-drive", "file=" + str(disque) + ",if=virtio,format=qcow2",
        "-cdrom", str(iso), "-boot", "d", "-nic", "user,model=virtio-net-pci",
        "-daemonize", "-pidfile", str(dossier / "pid"),
    ], check=True)
    print(dossier)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("demarrer", "capture", "touche", "arreter"))
    parser.add_argument("chemin", type=Path)
    parser.add_argument("touche", nargs="?")
    args = parser.parse_args()
    chemin = args.chemin.resolve()
    if args.action == "demarrer":
        demarrer(chemin)
    elif args.action == "capture":
        image = chemin / "ecran.png"
        qmp(chemin, "screendump", {"filename": str(image), "format": "png"})
        print(image)
    elif args.action == "touche":
        qmp(chemin, "send-key", {"keys": [{"type": "qcode", "data": args.touche}], "hold-time": 100})
    else:
        qmp(chemin, "quit")
