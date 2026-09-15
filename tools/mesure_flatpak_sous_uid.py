#!/usr/bin/env python3
"""Mesure : une application Flatpak peut-elle tourner sous le compte d'un Espace ?

NON INSTALLÉ. À lancer en administrateur, depuis une session graphique :

    sudo -E python3 tools/mesure_flatpak_sous_uid.py

C'est la première des deux limites qui empêchent de cocher « Compte séparé »
d'office. Aujourd'hui, Codebyr REFUSE d'ouvrir une application Flatpak dans un
Espace à compte dédié (compte_dedie.incompatibilites) — refus honnête, mais
refus.

Ce que fait Codebyr aujourd'hui, sous le compte du BUREAU :
  - « install » pose l'application dans FLATPAK_USER_DIR propre à l'Espace,
    sous le dossier personnel du bureau ;
  - « launch » lance « flatpak run » SANS notre bubblewrap et SANS bus privé :
    Flatpak a son propre bac à sable et a besoin du vrai bus pour ses portails.

Sous compte dédié, trois choses disparaissent d'un coup, et c'est ce qu'on
vient mesurer :
  1. le dossier d'installation est chez un autre compte ;
  2. le compte de l'Espace n'a pas de dossier d'exécution (XDG_RUNTIME_DIR) :
     il n'a pas de session logind, donc rien ne le crée ;
  3. il n'a pas de bus de session, donc pas de portails.

Cet outil MESURE, il ne juge pas. Une ligne « NON » n'est pas un échec : c'est
une pièce de plomberie à écrire, et mieux vaut la connaître avant d'avoir bâti
par-dessus.

Il ne touche à RIEN de ce qui existe : il crée son propre compte d'essai, le
nettoie à la fin, et ne lit aucun Espace de l'utilisateur.
"""
import argparse
import os
import pwd
import shutil
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVRE = os.path.join(RACINE, "live-build", "config", "includes.chroot_after_packages")
ARBRE = os.path.join(LIVRE, "usr", "share", "codebyr")
# Sur la machine d'essai, il n'y a pas de dépôt : seulement Codebyr installé.
# L'outil doit donc pouvoir y être déposé seul, sans rien d'autre.
LIB = ARBRE if os.path.isdir(ARBRE) else "/usr/share/codebyr"

# Importer depuis l'arbre livré y écrirait un « __pycache__ », qui partirait
# tel quel dans l'image (test_packaging le refuse, à juste titre).
sys.dont_write_bytecode = True
sys.path.insert(0, LIB)
try:
    import comptes  # noqa: E402
except ImportError:
    sys.exit("Codebyr introuvable : ni %s, ni /usr/share/codebyr." % ARBRE)

ESPACE = "mesureflat"
# Petite, sans réseau, et son runtime est celui que GNOME installe de toute
# façon : c'est le cobaye le moins coûteux à télécharger sur une machine
# d'essai. Remplaçable par --app.
APP_DEFAUT = "org.gnome.Calculator"


def titre(texte):
    print("\n── %s %s" % (texte, "─" * max(0, 62 - len(texte))))


def dire(quoi, bon, detail=""):
    print("%s %-48s %s" % ("  OUI " if bon else "  NON ", quoi, detail))
    return bon


def consequence(texte):
    print("       → %s" % texte)


def derniere_erreur(r, mots=()):
    """La ligne d'erreur qui explique, pas la dernière venue.

    Flatpak et bubblewrap parlent beaucoup ; ce qui compte est la ligne qui
    nomme la cause. On la cherche par mot-clé, et à défaut on prend la
    dernière.
    """
    lignes = [l.strip() for l in (r.stderr or "").splitlines() if l.strip()]
    for mot in mots:
        for ligne in lignes:
            if mot in ligne:
                return ligne[:96]
    return lignes[-1][:96] if lignes else ""


def sous(compte, args, env=None, delai=600, entree=None):
    """Exécute sous l'identité du compte de l'Espace. Le noyau tranche, pas nous."""
    base = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
            "HOME": compte.pw_dir, "USER": compte.pw_name,
            "LOGNAME": compte.pw_name}
    base.update(env or {})
    try:
        return subprocess.run(
            ["/usr/bin/setpriv", "--reuid", str(compte.pw_uid),
             "--regid", str(compte.pw_gid), "--clear-groups", "--no-new-privs",
             "/usr/bin/env", "-i"] +
            ["%s=%s" % (k, v) for k, v in sorted(base.items())] + list(args),
            capture_output=True, text=True, timeout=delai, input=entree)
    except subprocess.TimeoutExpired:
        # Une attente sans fin est une mesure, pas un incident.
        return subprocess.CompletedProcess(args, 124, "",
                                           "aucune réponse après %ds" % delai)


def creer_compte(uid_bureau):
    """Le compte d'essai, fait exactement comme le service le fait."""
    nom = comptes.nom_compte(uid_bureau, ESPACE)
    home = comptes.chemin_home(uid_bureau, ESPACE)
    try:
        return pwd.getpwnam(nom), home, False
    except KeyError:
        pass
    os.makedirs(os.path.dirname(home), exist_ok=True)
    os.chmod(os.path.dirname(os.path.dirname(home)), 0o711)
    os.chmod(os.path.dirname(home), 0o711)
    subprocess.run(["/usr/sbin/useradd", "--system", "--no-create-home",
                    "--home-dir", home, "--shell", "/usr/sbin/nologin", nom],
                   check=True, capture_output=True)
    compte = pwd.getpwnam(nom)
    os.makedirs(home, exist_ok=True)
    os.chown(home, compte.pw_uid, compte.pw_gid)
    os.chmod(home, 0o700)
    return compte, home, True


def supprimer_compte(compte, home):
    if os.path.isdir(home) and shutil.rmtree.avoids_symlink_attacks:
        shutil.rmtree(home, ignore_errors=True)
    subprocess.run(["/usr/sbin/userdel", compte.pw_name], capture_output=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", default=APP_DEFAUT,
                    help="application Flatpak cobaye (défaut : %s)" % APP_DEFAUT)
    ap.add_argument("--garder", action="store_true",
                    help="ne pas supprimer le compte d'essai à la fin")
    args = ap.parse_args()

    if os.geteuid() != 0:
        print("À lancer en administrateur : sudo -E python3 %s" % sys.argv[0],
              file=sys.stderr)
        return 2
    uid_bureau = int(os.environ.get("SUDO_UID") or 0)
    if uid_bureau < comptes.UID_MINIMAL:
        print("Lancez avec « sudo -E » depuis votre session (SUDO_UID manquant).",
              file=sys.stderr)
        return 2
    bureau = pwd.getpwuid(uid_bureau)
    affichage = os.path.basename(os.environ.get("WAYLAND_DISPLAY", "wayland-0"))
    runtime_bureau = os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % uid_bureau

    print("Mesure : une application Flatpak sous le compte d'un Espace\n")
    dire("session du bureau", True, "%s (UID %d), affichage %s"
         % (bureau.pw_name, uid_bureau, affichage))
    if not shutil.which("flatpak"):
        dire("flatpak installé", False, "paquet « flatpak » absent")
        consequence("rien à mesurer ; installez flatpak sur cette machine.")
        return 1
    version = subprocess.run(["flatpak", "--version"], capture_output=True,
                             text=True).stdout.strip()
    dire("flatpak installé", True, version)

    compte, home, cree = creer_compte(uid_bureau)
    dire("compte d'essai", True, "%s (UID %d)%s"
         % (compte.pw_name, compte.pw_uid, "" if cree else " — déjà présent"))
    flatpak_dir = os.path.join(home, "flatpak")
    runtime_espace = "/run/codebyr/essai-runtime-%d" % compte.pw_uid
    code = 0

    try:
        # ── 1. Ce dont le bac à sable de Flatpak a besoin ──────────────────
        titre("1. Le compte peut-il faire ce que Flatpak exige du noyau ?")

        r = sous(compte, ["/usr/bin/unshare", "--user", "--map-root-user",
                          "/bin/true"], delai=20)
        userns = dire("créer un espace de noms utilisateur", r.returncode == 0,
                      derniere_erreur(r))
        if not userns:
            consequence("bubblewrap, donc Flatpak, ne peut pas démarrer du tout.")
        else:
            consequence("le bac à sable interne de Flatpak peut se construire.")

        r = sous(compte, ["/usr/bin/test", "-r", "/var/lib/flatpak"], delai=20)
        dire("lire l'installation Flatpak du système", r.returncode == 0,
             "/var/lib/flatpak")

        # ── 2. Le dossier d'exécution ──────────────────────────────────────
        titre("2. Le dossier d'exécution (XDG_RUNTIME_DIR)")

        existe = os.path.isdir("/run/user/%d" % compte.pw_uid)
        dire("le compte en a un, fourni par le système", existe,
             "/run/user/%d" % compte.pw_uid)
        if not existe:
            consequence("attendu : pas de session logind pour un compte d'Espace. "
                        "Il faudra le créer nous-mêmes.")

        # Ce que le service devra poser : un dossier 0700 au compte de l'Espace.
        os.makedirs(runtime_espace, exist_ok=True)
        os.chown(runtime_espace, compte.pw_uid, compte.pw_gid)
        os.chmod(runtime_espace, 0o700)
        r = sous(compte, ["/usr/bin/touch", os.path.join(runtime_espace, "essai")],
                 delai=20)
        dire("un dossier fabriqué par root lui est écrivable",
             r.returncode == 0, derniere_erreur(r))

        # /run est monté « noexec » par Debian. Le dossier d'exécution d'un
        # Espace y vivrait naturellement, à côté de la passerelle — mais si
        # Flatpak a besoin d'y exécuter quoi que ce soit, il faudra le poser
        # ailleurs. Mieux vaut le savoir maintenant qu'après l'avoir bâti.
        essai_x = os.path.join(runtime_espace, "essai-x")
        with open(essai_x, "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(essai_x, 0o755)
        os.chown(essai_x, compte.pw_uid, compte.pw_gid)
        r = sous(compte, [essai_x], delai=20)
        dire("…et permet d'y exécuter un programme", r.returncode == 0,
             derniere_erreur(r) or ("sous %s" % runtime_espace))
        if r.returncode != 0:
            consequence("/run est « noexec » chez Debian : si Flatpak en a "
                        "besoin, le dossier devra vivre ailleurs.")

        # ── 3. L'installation dans l'Espace ────────────────────────────────
        titre("3. Installer l'application DANS l'Espace, comme l'Espace")

        env_fp = {"FLATPAK_USER_DIR": flatpak_dir,
                  "XDG_RUNTIME_DIR": runtime_espace}
        depot = "/etc/flatpak/remotes.d/flathub.flatpakrepo"
        source = depot if os.path.exists(depot) else \
            "https://flathub.org/repo/flathub.flatpakrepo"
        r = sous(compte, ["/usr/bin/flatpak", "--user", "remote-add",
                          "--if-not-exists", "flathub", source], env=env_fp, delai=120)
        dire("ajouter le dépôt Flathub", r.returncode == 0, derniere_erreur(r))

        print("       (téléchargement de %s — peut être long)" % args.app)
        r = sous(compte, ["/usr/bin/flatpak", "--user", "install", "-y",
                          "flathub", args.app], env=env_fp, delai=1800)
        installee = dire("installer %s" % args.app, r.returncode == 0,
                         derniere_erreur(r, ("error:", "Erreur", "Permission")))
        if not installee:
            consequence("l'installation devra peut-être passer par le service, "
                        "ou par un ordre exécuté DANS l'Espace.")

        if installee:
            r = sous(compte, ["/usr/bin/flatpak", "--user", "list", "--app",
                              "--columns=application"], env=env_fp, delai=60)
            dire("l'Espace revoit son application", args.app in (r.stdout or ""),
                 (r.stdout or "").strip().replace("\n", " ")[:60])

        # ── 4. Le lancement ────────────────────────────────────────────────
        titre("4. Lancer l'application sous le compte de l'Espace")
        if not installee:
            dire("lancement", False, "rien à lancer, l'installation a échoué")
            code = 1
        else:
            lancer = ["/usr/bin/flatpak", "run", "--die-with-parent", args.app]

            # a) Sans rien : ce qui se passerait si l'on se contentait de
            #    changer de compte.
            r = sous(compte, lancer, env={"FLATPAK_USER_DIR": flatpak_dir}, delai=45)
            dire("sans dossier d'exécution ni affichage", r.returncode == 0,
                 derniere_erreur(r, ("XDG_RUNTIME_DIR", "runtime", "error:")))
            consequence("attendu : c'est la mesure de référence, pas une cible.")

            # b) Avec le dossier d'exécution et le socket Wayland du bureau,
            #    présentés comme la passerelle le fait déjà pour bubblewrap.
            socket_bureau = os.path.join(runtime_bureau, affichage)
            socket_espace = os.path.join(runtime_espace, affichage)
            monte = False
            if os.path.exists(socket_bureau):
                open(socket_espace, "a").close()
                m = subprocess.run(["/usr/bin/mount", "--bind", socket_bureau,
                                    socket_espace], capture_output=True, text=True)
                monte = m.returncode == 0
                dire("présenter le socket Wayland dans ce dossier", monte,
                     derniere_erreur(m))
                if monte:
                    # Le montage ne donne pas le droit : l'ACL sur l'inode, si.
                    subprocess.run(["/usr/bin/setfacl", "-m",
                                    "u:%d:rw" % compte.pw_uid, socket_bureau],
                                   capture_output=True)
            else:
                dire("socket Wayland du bureau trouvé", False, socket_bureau)

            env_run = {"FLATPAK_USER_DIR": flatpak_dir,
                       "XDG_RUNTIME_DIR": runtime_espace,
                       "WAYLAND_DISPLAY": affichage,
                       "GDK_BACKEND": "wayland",
                       "XDG_SESSION_TYPE": "wayland"}
            r = sous(compte, lancer, env=env_run, delai=45)
            # Une application graphique qui s'ouvre ne rend pas la main : le
            # délai dépassé est ici le signe qu'elle TOURNE. Un code non nul
            # immédiat est un vrai refus.
            tourne = r.returncode == 124
            dire("avec dossier d'exécution + Wayland", tourne,
                 "fenêtre ouverte (l'outil l'a arrêtée)" if tourne
                 else derniere_erreur(r, ("portal", "dbus", "Wayland", "error:")))
            if not tourne:
                consequence("c'est ici que se joue le chantier : lire l'erreur ci-dessus.")
                code = 1

            # c) Ce qui manque encore : le bus de session, donc les portails.
            r = sous(compte, ["/usr/bin/flatpak", "run", "--die-with-parent",
                              "--command=/bin/sh", args.app, "-c",
                              "test -S $XDG_RUNTIME_DIR/bus && echo BUS || echo SANS-BUS"],
                     env=env_run, delai=60)
            dire("l'application voit un bus de session", "BUS" in (r.stdout or ""),
                 (r.stdout or "").strip() or derniere_erreur(r))
            consequence("sans bus : pas de portails — ouvrir/enregistrer un "
                        "fichier, imprimer, ouvrir un lien.")

            if monte:
                subprocess.run(["/usr/bin/umount", socket_espace], capture_output=True)
                subprocess.run(["/usr/bin/setfacl", "-x", "u:%d" % compte.pw_uid,
                                socket_bureau], capture_output=True)

        titre("Ce qu'il faut retenir")
        print("  Chaque NON ci-dessus est une pièce à écrire. Les OUI disent ce")
        print("  sur quoi on peut déjà s'appuyer.")
    finally:
        shutil.rmtree(runtime_espace, ignore_errors=True)
        if args.garder:
            print("\nCompte d'essai conservé : %s (%s)" % (compte.pw_name, home))
        else:
            supprimer_compte(compte, home)
            print("\nCompte d'essai supprimé.")
    return code


if __name__ == "__main__":
    sys.exit(main())
