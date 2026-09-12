#!/usr/bin/env python3
"""Prototype administrateur, NON installé : UID distincts dans une VM/WSL de test.

Pas de service root, de règle sudo/polkit ni de migration automatique. Les
comptes créés ont leur mot de passe verrouillé et aucun shell de connexion.
Lancer via root : prototype_uid.py creer travail ; prototype_uid.py lancer
travail -- /usr/bin/id. Aucun accès réseau, audio ou graphique dans ce prototype.
"""
import argparse
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys

RACINE = Path("/var/lib/codebyr-prototype-uid")


def identifiant(valeur):
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,19}", valeur):
        raise ValueError("Identifiant invalide")
    return "cbyr-test-" + valeur


def dossier_root(path):
    if path.is_symlink():
        raise ValueError("Lien symbolique refusé")
    path.mkdir(mode=0o711, exist_ok=True)
    st = path.stat()
    if st.st_uid != 0 or st.st_mode & 0o022:
        raise ValueError("Le dossier de gestion doit appartenir à root et être non inscriptible")


def compte(espace, creer=False):
    nom = identifiant(espace)
    dossier_root(RACINE)
    home = RACINE / nom
    try:
        utilisateur = pwd.getpwnam(nom)
    except KeyError:
        if not creer:
            raise ValueError("Créez d'abord cet Espace de test") from None
        if home.exists() or home.is_symlink():
            raise ValueError("Le dossier existe déjà sans compte : intervention manuelle requise")
        subprocess.run(["/usr/sbin/useradd", "--system", "--user-group", "--create-home",
                        "--home-dir", str(home), "--shell", "/usr/sbin/nologin",
                        "--password", "!", nom], check=True)
        utilisateur = pwd.getpwnam(nom)
        os.chmod(home, 0o700)
    if utilisateur.pw_uid == 0 or utilisateur.pw_dir != str(home):
        raise ValueError("Compte existant incompatible")
    if home.is_symlink() or home.stat().st_uid != utilisateur.pw_uid or home.stat().st_mode & 0o077:
        raise ValueError("Le dossier doit être privé (0700) et appartenir à son UID")
    return utilisateur


def commande(utilisateur, arguments):
    if not arguments or not arguments[0].startswith("/"):
        raise ValueError("La commande doit commencer par un chemin absolu")
    return ["/usr/bin/setpriv", "--reuid", str(utilisateur.pw_uid),
            "--regid", str(utilisateur.pw_gid), "--clear-groups", "--no-new-privs",
            "/usr/bin/bwrap", "--unshare-user", "--unshare-pid", "--unshare-net",
            "--unshare-ipc", "--unshare-uts", "--new-session", "--cap-drop", "ALL",
            "--die-with-parent", "--ro-bind", "/usr", "/usr", "--ro-bind", "/etc", "/etc",
            "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib",
            "--symlink", "usr/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev",
            "--tmpfs", "/tmp", "--bind", utilisateur.pw_dir, "/home/espace",
            "--chdir", "/home/espace", "--clearenv", "--setenv", "HOME", "/home/espace",
            "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "LANG", "C.UTF-8",
            "--"] + arguments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("creer", "lancer"))
    parser.add_argument("espace")
    parser.add_argument("commande", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("Prototype réservé à l'administrateur d'une machine de test")
    try:
        utilisateur = compte(args.espace, creer=args.action == "creer")
        if args.action == "creer":
            print("%s : UID %d, dossier privé %s" % (
                utilisateur.pw_name, utilisateur.pw_uid, utilisateur.pw_dir))
            return 0
        arguments = args.commande
        if arguments and arguments[0] == "--":
            arguments = arguments[1:]
        return subprocess.call(commande(utilisateur, arguments),
                               env={"PATH": "/usr/sbin:/usr/bin:/bin", "LANG": "C.UTF-8"},
                               cwd="/")
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print("Prototype : %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
