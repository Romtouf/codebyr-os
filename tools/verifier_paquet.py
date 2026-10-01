#!/usr/bin/env python3
"""Compare un .deb aux sources locales sans l'installer (Debian/WSL)."""
import argparse
import gettext
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import tarfile
import tempfile


def droits_fautifs(archive):
    """Les entrées qu'un paquet installerait modifiables par un autre que root.

    Lu dans l'archive elle-même, pas sur une copie extraite : extraire sous un
    compte ordinaire applique son masque, qui peut cacher un 777. Et TOUTES
    les entrées, pas une liste choisie : de 1.13.0 à 1.16.6, le lanceur de
    session codebyr-bienvenue.desktop partait en 777, hors de la liste.
    """
    fautes = []
    for entree in archive.getmembers():
        if entree.issym() or entree.islnk():
            continue
        nom = entree.name
        if entree.mode & 0o022:
            fautes.append("%s (%o, inscriptible par groupe/autres)" % (nom, entree.mode & 0o7777))
        elif entree.uid != 0 or entree.gid != 0:
            fautes.append("%s (propriétaire %d:%d, pas root)" % (nom, entree.uid, entree.gid))
    return fautes


def verifier_droits(paquet):
    contenu = subprocess.run(["dpkg-deb", "--fsys-tarfile", str(paquet)],
                             check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(contenu)) as archive:
        fautes = droits_fautifs(archive)
        total = len(archive.getmembers())
    if fautes:
        raise ValueError("Droits dangereux dans le paquet :\n  " + "\n  ".join(fautes))
    print("%d entrées : aucune modifiable par un autre que root." % total)


def verifier_arbre(stage, racine):
    source = racine / "live-build/config/includes.chroot_after_packages"
    attendus = list((source / "usr/share/codebyr").rglob("*"))
    for arbre in ("usr/share/gnome-shell/extensions/codebyr@codebyr.io",
                  "usr/share/nautilus-python", "etc/skel",
                  "usr/share/plymouth/themes/codebyr"):
        attendus += list((source / arbre).rglob("*"))
    attendus += [source / "etc/codebyr/espaces.json",
                 source / "usr/share/applications/io.codebyr.Ouvrir.desktop",
                 source / "usr/share/glib-2.0/schemas/90_codebyr.gschema.override",
                 source / "usr/lib/firefox-esr/distribution/policies.json"]
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
    # L'avatar des nouveaux comptes n'est pas dans /etc/skel des sources : le
    # paquet le fabrique (voir build-deb.sh, « 1 quater »).
    face = stage / "etc/skel/.face"
    if not face.is_file() or face.read_bytes() != (source / "usr/share/codebyr/avatar.svg").read_bytes():
        raise ValueError("Avatar absent ou différent des sources : etc/skel/.face")
    # Une langue par fichier po/<langue>.po, compilée pour les programmes et
    # pour l'extension GNOME (packaging/traductions.py).
    for po in sorted((racine / "po").glob("*.po")):
        langue = po.stem
        catalogue = stage / "usr/share/locale" / langue / "LC_MESSAGES/codebyr.mo"
        extension = (stage / "usr/share/gnome-shell/extensions/codebyr@codebyr.io/traductions"
                     / (langue + ".json"))
        try:
            with catalogue.open("rb") as f:
                gettext.GNUTranslations(f)
            json.loads(extension.read_text(encoding="utf-8"))
        except (OSError, ValueError, struct.error) as e:
            raise ValueError("Traduction « %s » absente ou illisible : %s" % (langue, e))
        # L'écran de démarrage traduit (« Phrase de passe du disque »).
        theme = stage / "usr/share/plymouth/themes" / ("codebyr-" + langue)
        for nom in ("codebyr-%s.plymouth" % langue, "codebyr-%s.script" % langue):
            if not (theme / nom).is_file():
                raise ValueError("Écran de démarrage « %s » absent : %s" % (langue, nom))
    for nom in ("fichiers_surs.py", "filtre_syscalls.py", "relais_reseau.py",
                "permissions_flatpak.py", "navigateur.py"):
        if not (stage / "usr/share/codebyr" / nom).is_file():
            raise ValueError("Module de sécurité absent : " + nom)
    print("%d fichiers conformes aux sources ; permissions vérifiées." % controles)


def verifier(paquet, racine):
    verifier_droits(paquet)
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
