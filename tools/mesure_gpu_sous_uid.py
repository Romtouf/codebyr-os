#!/usr/bin/env python3
"""Mesure : la carte graphique est-elle atteignable depuis le compte d'un Espace ?

NON INSTALLÉ. À lancer en administrateur, depuis une session graphique :

    sudo -E python3 tools/mesure_gpu_sous_uid.py

C'est la dernière des deux limites annoncées en 1.15.0, et la dernière avant
que le compte séparé puisse devenir le défaut. Sous compte séparé, l'affichage
d'un Espace se fait en rendu logiciel : le processeur dessine ce que la carte
graphique dessinerait, plus lentement.

POURQUOI : sur un bureau ordinaire, ce n'est pas l'appartenance à un groupe qui
donne accès à /dev/dri, c'est logind — il pose un DROIT NOMINATIF (ACL) sur ces
fichiers pour l'utilisateur de la session ouverte, et le retire à la
déconnexion. Le compte d'un Espace n'a pas de session : il n'a donc aucun droit.

L'HYPOTHÈSE À MESURER : root peut poser le même droit nominatif pour le compte
de l'Espace, le temps qu'il est ouvert — exactement ce que le service fait déjà
pour le socket Wayland. Si cela suffit, le chantier est court.

Cet outil MESURE, il ne juge pas. Il crée son propre compte d'essai, retire ce
qu'il a posé, et ne touche à aucun Espace.

ATTENTION : dans une machine virtuelle, il se peut qu'il n'y ait AUCUNE
accélération matérielle à obtenir. L'outil le dit d'abord, en regardant ce que
votre propre session utilise : sans cela, on croirait mesurer un échec alors
qu'il n'y a rien à mesurer.
"""
import argparse
import os
import pwd
import re
import shutil
import signal
import subprocess
import sys
import time

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARBRE = os.path.join(RACINE, "live-build", "config",
                     "includes.chroot_after_packages", "usr", "share", "codebyr")
LIB = ARBRE if os.path.isdir(ARBRE) else "/usr/share/codebyr"

# Importer depuis l'arbre livré y écrirait un « __pycache__ », qui partirait
# tel quel dans l'image (test_packaging le refuse, à juste titre).
sys.dont_write_bytecode = True
sys.path.insert(0, LIB)
try:
    import comptes
except ImportError:
    sys.exit("Codebyr introuvable : ni %s, ni /usr/share/codebyr." % ARBRE)

ESPACE = "mesuregpu"

# Une fenêtre GTK4 qui dit QUI la dessine. GSK nomme son moteur de rendu quand
# on le lui demande : « ngl » ou « vulkan » = la carte graphique ; « cairo » =
# le processeur. C'est la seule réponse qui compte ici.
FENETRE = r'''
import os, sys
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk
def demarrer(app):
    f = Gtk.ApplicationWindow(application=app, title="Mesure carte graphique")
    f.set_default_size(320, 120)
    f.present()
    GLib.timeout_add_seconds(3, lambda: (app.quit(), False)[1])
a = Gtk.Application(application_id="io.codebyr.MesureGpu")
a.connect("activate", demarrer)
sys.exit(a.run([]))
'''


def titre(texte):
    print("\n── %s %s" % (texte, "─" * max(0, 62 - len(texte))))


def dire(quoi, bon, detail="", aussi_si_oui=False):
    if bon and not aussi_si_oui:
        detail = ""
    print("%s %-46s %s" % ("  OUI " if bon else "  NON ", quoi, detail))
    return bon


def consequence(texte):
    print("       → %s" % texte)


def moteur_de_rendu(sortie):
    """Le moteur que GSK a retenu, lu dans ce qu'il a écrit."""
    for ligne in (sortie or "").splitlines():
        m = re.search(r"[Uu]sing (?:renderer )?['\"]?(\w+)", ligne)
        if m:
            return m.group(1).lower()
    return ""


def accelere(moteur):
    return moteur in ("ngl", "gl", "vulkan")


def sous(compte, args, env=None, delai=90):
    base = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": compte.pw_dir,
            "USER": compte.pw_name, "LOGNAME": compte.pw_name}
    base.update(env or {})
    try:
        return subprocess.run(
            ["/usr/bin/setpriv", "--reuid", str(compte.pw_uid),
             "--regid", str(compte.pw_gid), "--clear-groups", "--no-new-privs",
             "/usr/bin/env", "-i"] +
            ["%s=%s" % kv for kv in sorted(base.items())] + list(args),
            capture_output=True, text=True, timeout=delai)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", "aucune réponse")


def noeuds_de_rendu():
    """Les cartes graphiques vues par le système, et leurs droits."""
    trouves = []
    for nom in sorted(os.listdir("/dev/dri")) if os.path.isdir("/dev/dri") else []:
        chemin = os.path.join("/dev/dri", nom)
        try:
            st = os.stat(chemin)
        except OSError:
            continue
        trouves.append((chemin, nom.startswith("renderD"), st))
    return trouves


def droits_nominatifs(chemin):
    sortie = subprocess.run(["/usr/bin/getfacl", "-p", chemin],
                            capture_output=True, text=True).stdout
    return [l for l in sortie.splitlines()
            if l.startswith("user:") and not l.startswith("user::")]


def creer_compte(uid_bureau):
    nom = comptes.nom_compte(uid_bureau, ESPACE)
    home = comptes.chemin_home(uid_bureau, ESPACE)
    try:
        compte = pwd.getpwnam(nom)
    except KeyError:
        os.makedirs(os.path.dirname(home), exist_ok=True)
        subprocess.run(["/usr/sbin/useradd", "--system", "--no-create-home",
                        "--home-dir", home, "--shell", "/usr/sbin/nologin", nom],
                       check=True, capture_output=True)
        compte = pwd.getpwnam(nom)
    os.chmod(os.path.dirname(os.path.dirname(home)), 0o711)
    os.chmod(os.path.dirname(home), 0o711)
    os.makedirs(home, exist_ok=True)
    os.chown(home, compte.pw_uid, compte.pw_gid)
    os.chmod(home, 0o700)
    return compte, home


def tuer_les_processus(uid):
    for entree in os.listdir("/proc"):
        if not entree.isdigit():
            continue
        try:
            if os.stat("/proc/" + entree).st_uid == uid:
                os.kill(int(entree), signal.SIGKILL)
        except OSError:
            continue


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
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

    print("Mesure : la carte graphique depuis le compte d'un Espace\n")
    dire("session du bureau", True, "%s (UID %d), affichage %s"
         % (bureau.pw_name, uid_bureau, affichage), aussi_si_oui=True)

    # ── 1. Y a-t-il quelque chose à obtenir ? ──────────────────────────────
    titre("1. Votre session utilise-t-elle vraiment la carte graphique ?")
    noeuds = noeuds_de_rendu()
    if not noeuds:
        dire("une carte graphique est visible", False, "/dev/dri absent")
        consequence("rien à mesurer sur cette machine.")
        return 1
    for chemin, rendu, st in noeuds:
        dire(chemin, True, "%s, mode %o, %s" % (
            "rendu" if rendu else "affichage", st.st_mode & 0o777,
            "; ".join(droits_nominatifs(chemin)) or "aucun droit nominatif"),
            aussi_si_oui=True)

    sonde = "/tmp/codebyr-mesure-gpu.py"
    with open(sonde, "w", encoding="utf-8") as f:
        f.write(FENETRE)
    os.chmod(sonde, 0o644)
    env_bureau = dict(os.environ)
    env_bureau["GSK_DEBUG"] = "renderer"
    chez_le_bureau = subprocess.run(
        ["/usr/bin/setpriv", "--reuid", str(uid_bureau), "--regid", str(bureau.pw_gid),
         "--init-groups", "/usr/bin/python3", sonde],
        capture_output=True, text=True, timeout=90, env=env_bureau)
    moteur_bureau = moteur_de_rendu(chez_le_bureau.stderr + chez_le_bureau.stdout)
    if not dire("votre session dessine avec la carte graphique",
                accelere(moteur_bureau), moteur_bureau or "moteur inconnu",
                aussi_si_oui=True):
        consequence("si votre propre session est déjà en rendu logiciel — c'est "
                    "fréquent en machine virtuelle — il n'y a rien à gagner pour "
                    "un Espace, et cette mesure ne conclura rien.")

    compte, home = creer_compte(uid_bureau)
    dire("compte d'essai", True, "%s (UID %d)" % (compte.pw_name, compte.pw_uid),
         aussi_si_oui=True)
    runtime = "/run/user/%d" % compte.pw_uid
    deja = os.path.isdir(runtime)
    socket_bureau = os.path.join(runtime_bureau, affichage)
    socket_espace = os.path.join(runtime, affichage)
    monte = False
    accordes = []
    try:
        os.makedirs(runtime, exist_ok=True)
        os.chown(runtime, compte.pw_uid, compte.pw_gid)
        os.chmod(runtime, 0o700)
        if os.path.exists(socket_bureau):
            open(socket_espace, "a").close()
            monte = subprocess.run(["/usr/bin/mount", "--bind", socket_bureau,
                                    socket_espace], capture_output=True).returncode == 0
            if monte:
                subprocess.run(["/usr/bin/setfacl", "-m", "u:%d:rw" % compte.pw_uid,
                                socket_bureau], capture_output=True)
        env_espace = {"XDG_RUNTIME_DIR": runtime, "WAYLAND_DISPLAY": affichage,
                      "GDK_BACKEND": "wayland", "XDG_SESSION_TYPE": "wayland",
                      "GSK_DEBUG": "renderer"}

        # ── 2. Sans rien : l'état d'aujourd'hui ────────────────────────────
        titre("2. Aujourd'hui : ce que le compte d'un Espace peut atteindre")
        for chemin, rendu, _st in noeuds:
            r = sous(compte, ["/usr/bin/test", "-r", chemin, "-a", "-w", chemin], delai=20)
            dire("ouvrir %s" % chemin, r.returncode == 0)
        avant = sous(compte, ["/usr/bin/python3", sonde], env=env_espace, delai=90)
        moteur_avant = moteur_de_rendu(avant.stderr + avant.stdout)
        dire("sa fenêtre est dessinée par la carte graphique",
             accelere(moteur_avant), moteur_avant or "aucune fenêtre", aussi_si_oui=True)
        consequence("c'est la limite annoncée en 1.15.0 : rendu logiciel.")

        # ── 3. Avec un droit nominatif, comme pour le socket Wayland ───────
        titre("3. Avec le droit que root peut accorder, le temps d'un Espace")
        for chemin, rendu, _st in noeuds:
            if not rendu:
                # Les nœuds « carte » servent à PILOTER l'écran (modes, sorties).
                # Une application ne fait que dessiner : elle n'en a pas besoin,
                # et les donner ouvrirait bien plus que nécessaire.
                continue
            r = subprocess.run(["/usr/bin/setfacl", "-m", "u:%d:rw" % compte.pw_uid,
                                chemin], capture_output=True, text=True)
            if dire("accorder %s au compte de l'Espace" % chemin,
                    r.returncode == 0, (r.stderr or "").strip()[:60]):
                accordes.append(chemin)
        for chemin in accordes:
            r = sous(compte, ["/usr/bin/test", "-r", chemin, "-a", "-w", chemin], delai=20)
            dire("il peut maintenant ouvrir %s" % chemin, r.returncode == 0)
        apres = sous(compte, ["/usr/bin/python3", sonde], env=env_espace, delai=90)
        moteur_apres = moteur_de_rendu(apres.stderr + apres.stdout)
        gagne = dire("sa fenêtre est dessinée par la carte graphique",
                     accelere(moteur_apres), moteur_apres or "aucune fenêtre",
                     aussi_si_oui=True)
        if not gagne:
            for ligne in [l.strip() for l in (apres.stderr or "").splitlines()
                          if l.strip()][-6:]:
                print("         %s" % ligne[:92])

        titre("Ce qu'il faut retenir")
        if accelere(moteur_bureau) and gagne:
            print("  Un droit nominatif suffit : le chantier se résume à le poser")
            print("  à l'ouverture et à le retirer à la fermeture, comme pour")
            print("  l'affichage.")
        elif not accelere(moteur_bureau):
            print("  Votre session elle-même n'utilise pas la carte graphique :")
            print("  cette machine ne peut pas répondre à la question. À rejouer")
            print("  sur une machine où le rendu matériel fonctionne.")
        else:
            print("  Le droit ne suffit pas : lire les lignes ci-dessus. Il manque")
            print("  autre chose que l'accès au fichier.")
        return 0 if gagne else 1
    finally:
        for chemin in accordes:
            subprocess.run(["/usr/bin/setfacl", "-x", "u:%d" % compte.pw_uid, chemin],
                           capture_output=True)
        if monte:
            subprocess.run(["/usr/bin/umount", socket_espace], capture_output=True)
            subprocess.run(["/usr/bin/setfacl", "-x", "u:%d" % compte.pw_uid,
                            socket_bureau], capture_output=True)
        tuer_les_processus(compte.pw_uid)
        if not deja:
            shutil.rmtree(runtime, ignore_errors=True)
        try:
            os.unlink(sonde)
        except OSError:
            pass
        if args.garder:
            print("\nCompte d'essai conservé : %s" % compte.pw_name)
        else:
            time.sleep(1)
            shutil.rmtree(home, ignore_errors=True)
            subprocess.run(["/usr/sbin/userdel", compte.pw_name], capture_output=True)
            print("\nCompte d'essai supprimé.")


if __name__ == "__main__":
    sys.exit(main())
