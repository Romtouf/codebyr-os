#!/usr/bin/env python3
"""Compare un .deb aux sources locales sans l'installer (Debian/WSL)."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile


def verifier_arbre(stage, racine):
    source = racine / "live-build/config/includes.chroot_after_packages"
    attendus = list((source / "usr/share/codebyr").rglob("*"))
    for arbre in ("usr/share/gnome-shell/extensions/codebyr@codebyr.io",
                  "usr/share/nautilus-python", "etc/skel"):
        attendus += list((source / arbre).rglob("*"))
    attendus += [source / "etc/codebyr/espaces.json",
                 source / "usr/share/applications/io.codebyr.Ouvrir.desktop"]
    attendus += [source / "usr/bin" / n for n in (
        "codebyr-space", "codebyr-net-proxy", "codebyr-jetable", "codebyr-config",
        "codebyr-assistant", "codebyr-bienvenue", "codebyr-verifier", "codebyr-durcir-poste")]
    controles = 0
    for original in attendus:
        if not original.is_file():
            continue
        relatif = original.relative_to(source)
        copie = stage / relatif
        attendu = original.read_bytes()
        if original.suffix in (".py", ".sh") or original.name.startswith("codebyr-"):
            attendu = attendu.replace(b"\r\n", b"\n")
        if not copie.is_file() or copie.read_bytes() != attendu:
            raise ValueError("Absent ou différent des sources : %s" % relatif)
        if copie.stat().st_mode & 0o022:
            raise ValueError("Inscriptible par groupe/autres : %s" % relatif)
        if relatif.parts[:2] == ("usr", "bin") and not copie.stat().st_mode & 0o111:
            raise ValueError("Commande non exécutable : %s" % relatif)
        controles += 1
    for nom in ("fichiers_surs.py", "filtre_syscalls.py", "relais_reseau.py"):
        if not (stage / "usr/share/codebyr" / nom).is_file():
            raise ValueError("Module de sécurité absent : " + nom)
    print("%d fichiers conformes aux sources ; permissions vérifiées." % controles)


def verifier(paquet, racine):
    with tempfile.TemporaryDirectory(prefix="codebyr-paquet-") as temporaire:
        subprocess.run(["dpkg-deb", "--extract", str(paquet), temporaire], check=True)
        verifier_arbre(Path(temporaire), racine)
    with paquet.open("rb") as fichier:
        print("SHA256 " + hashlib.file_digest(fichier, "sha256").hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paquet", type=Path)
    parser.add_argument("--arbre", action="store_true", help="Vérifier un arbre extrait au lieu d’un .deb")
    parser.add_argument("--sources", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    fonction = verifier_arbre if args.arbre else verifier
    fonction(args.paquet.resolve(), args.sources.resolve())
