#!/usr/bin/env python3
"""Mesure : la chaîne de lancement d'un Espace survit-elle sous un compte dédié ?

NON INSTALLÉ. À lancer en administrateur, depuis une session graphique :

    sudo -E python3 tools/mesure_espace_sous_uid.py

Le service privilégié est éprouvé (tools/essai_service_uid.py). Reste la
question qui décide de l'architecture de la suite : ce que `codebyr-space`
construit aujourd'hui — bubblewrap, bus de session privé, filtre d'appels
système, plafonds mémoire, sockets de notification et d'envoi — fonctionne-t-il
encore quand l'Espace ne tourne plus sous le compte du bureau ?

Cet outil MESURE, il ne juge pas. Une ligne « NON » n'est pas un échec du
chantier : c'est une pièce de plomberie à écrire, et on préfère la connaître
avant d'avoir bâti par-dessus.

Un fait est déjà acquis, et il n'est pas mesurable : le compte du bureau ne
peut pas devenir un autre compte (il n'a pas CAP_SETUID). C'est donc le service
root qui devra lancer l'Espace — jamais le lanceur lui-même.
"""
import json
import os
import pwd
import shutil
import socket
import subprocess
import sys
import tempfile
import time

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVRE = os.path.join(RACINE, "live-build", "config", "includes.chroot_after_packages")
SERVICE = os.path.join(LIVRE, "usr", "lib", "codebyr", "codebyr-uid")
LIB = os.path.join(LIVRE, "usr", "share", "codebyr")
SOCKET = "/run/codebyr-uid-mesure.sock"
ESPACE = "mesure"

sys.path.insert(0, LIB)
import bac_a_sable  # noqa: E402
import comptes  # noqa: E402

FENETRE = """
import sys, gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
def demarrer(app):
    f = Gtk.ApplicationWindow(application=app, title="Mesure Codebyr")
    f.set_default_size(360, 140)
    f.present()
    print("FENETRE-AFFICHEE", flush=True)
    GLib.timeout_add_seconds(2, lambda: (app.quit(), False)[1])
a = Gtk.Application(application_id="io.codebyr.MesureUid")
a.connect("activate", demarrer)
sys.exit(a.run([]))
"""

# Lit le plafond mémoire que systemd a réellement posé sur le cgroup courant.
PLAFOND_LU = """
import sys
chemin = open("/proc/self/cgroup").read().strip().split(":")[-1]
try:
    print(open("/sys/fs/cgroup" + chemin + "/memory.max").read().strip())
except OSError as e:
    print("illisible: %s" % e)
"""


def titre(texte):
    print("\n── %s %s" % (texte, "─" * max(0, 62 - len(texte))))


def dire(quoi, bon, detail=""):
    print("%s %-50s %s" % ("  OUI " if bon else "  NON ", quoi, detail))
    return bon


def consequence(texte):
    print("       → %s" % texte)


def sous(uid, gid, args, entree=None, delai=90):
    """Exécute sous l'identité voulue. C'est le noyau qui tranche, pas nous."""
    return subprocess.run(
        ["/usr/bin/setpriv", "--reuid", str(uid), "--regid", str(gid),
         "--clear-groups", "--no-new-privs"] + args,
        capture_output=True, text=True, timeout=delai, input=entree)


def demander(uid, gid, demande):
    code = (
        "import json,socket,sys\n"
        "s=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(20)\n"
        "s.connect(%r)\n"
        "s.sendall(sys.stdin.read().encode())\n"
        "print(s.recv(4096).decode().strip())\n" % SOCKET)
    r = sous(uid, gid, ["/usr/bin/python3", "-c", code], entree=json.dumps(demande))
    try:
        return json.loads(r.stdout.strip() or "{}")
    except ValueError:
        return {"ok": False, "brut": (r.stdout + r.stderr)[:200]}


def derniere_erreur(r):
    lignes = [l for l in (r.stderr or "").splitlines() if l.strip()]
    return lignes[-1][:88] if lignes else ""


def dans_le_bac(espace, home, passerelle, cmd, env_sup=None, **options):
    """Construit la VRAIE ligne de commande du bac à sable, et l'exécute.

    On appelle bac_a_sable.wrap_bwrap, pas une copie : mesurer une copie
    reviendrait à mesurer autre chose que ce qui sera lancé.
    """
    run = bac_a_sable.wrap_bwrap(
        home, cmd, {"XDG_RUNTIME_DIR": "/run/user/%d" % espace.pw_uid},
        passerelle=passerelle, chez=home, **options)
    environnement = ["/usr/bin/env", "-i", "PATH=/usr/bin:/bin",
                     "LANG=C.UTF-8", "HOME=" + home,
                     "WAYLAND_DISPLAY=wayland-0", "GDK_BACKEND=wayland"]
    environnement += env_sup or []
    return sous(espace.pw_uid, espace.pw_gid, environnement + run)


def socket_de_l_hote(dossier_parent, uid_bureau, gid_bureau):
    """Reproduit une socket telle que `codebyr-space` en crée aujourd'hui.

    Dossier temporaire du compte du BUREAU, en 0700 : c'est ainsi que sont
    servies les notifications, la boîte d'envoi et le filtre réseau.
    """
    coin = tempfile.mkdtemp(prefix="codebyr-hote-", dir=dossier_parent)
    os.chown(coin, uid_bureau, gid_bureau)
    os.chmod(coin, 0o700)
    chemin = os.path.join(coin, "socket")
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(chemin)
    os.chown(chemin, uid_bureau, gid_bureau)
    srv.listen(4)
    return srv, chemin


def joignable(espace, chemin):
    code = ("import socket,sys\n"
            "s=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(5)\n"
            "s.connect(%r)\n"
            "print('JOINT')\n" % chemin)
    r = sous(espace.pw_uid, espace.pw_gid, ["/usr/bin/python3", "-c", code], delai=20)
    return "JOINT" in r.stdout, derniere_erreur(r)


def main():
    if os.geteuid() != 0:
        print("À lancer en administrateur : sudo -E python3 %s" % sys.argv[0],
              file=sys.stderr)
        return 2
    uid = int(os.environ.get("SUDO_UID") or 0)
    if uid < comptes.UID_MINIMAL:
        print("Lancez avec « sudo -E » depuis votre session (SUDO_UID manquant).",
              file=sys.stderr)
        return 2
    bureau = pwd.getpwuid(uid)
    affichage = os.path.basename(os.environ.get("WAYLAND_DISPLAY", "wayland-0"))

    print("Mesure : la chaîne de lancement sous un compte dédié\n")
    dire("session du bureau", True, "%s (UID %d), affichage %s"
         % (bureau.pw_name, bureau.pw_uid, affichage))

    service = subprocess.Popen([sys.executable, SERVICE, "--essai", SOCKET],
                               env=dict(os.environ, CODEBYR_LIB=LIB))
    time.sleep(1.5)
    nom = comptes.nom_compte(bureau.pw_uid, ESPACE)
    sockets_hote = []
    coin_hote = tempfile.mkdtemp(prefix="codebyr-mesure-")
    os.chmod(coin_hote, 0o755)
    manques = []
    try:
        r = demander(bureau.pw_uid, bureau.pw_gid,
                     {"action": "preparer", "espace": ESPACE,
                      "affichage": affichage, "son": True})
        if not r.get("ok"):
            dire("préparation de l'Espace", False, r.get("erreur") or r.get("brut", ""))
            return 1
        espace = pwd.getpwnam(r["compte"])
        home, passerelle = r["home"], r["passerelle"]
        dire("Espace préparé", True, "%s (UID %d), passerelle %s"
             % (r["compte"], espace.pw_uid, ", ".join(r["presentes"]) or "rien"))

        script = os.path.join(home, "fenetre.py")
        with open(script, "w", encoding="utf-8") as f:
            f.write(FENETRE)
        os.chown(script, espace.pw_uid, espace.pw_gid)

        titre("1. Le bac à sable démarre-t-il sous ce compte ?")
        r1 = dans_le_bac(espace, home, passerelle, ["/bin/true"], audio=False)
        if not dire("bubblewrap, isolation ordinaire", r1.returncode == 0,
                    derniere_erreur(r1)):
            manques.append("bubblewrap ne démarre pas sous un compte système")
            consequence("tout le reste en dépend : rien d'autre ne sera concluant")

        titre("2. Et avec le Blindage ?")
        r2 = dans_le_bac(espace, home, passerelle, ["/bin/true"],
                         renforce=True, audio=False)
        if not dire("espace de noms utilisateur + filtre d'appels système",
                    r2.returncode == 0, derniere_erreur(r2)):
            manques.append("le Blindage ne passe pas sous un compte dédié")
            consequence("Banque et Jetable en dépendent — à régler avant tout "
                        "déploiement")

        titre("3. L'affichage passe-t-il par la passerelle ?")
        r3 = dans_le_bac(espace, home, passerelle,
                         ["/usr/bin/python3", script], audio=False)
        if not dire("fenêtre affichée depuis le bac à sable",
                    "FENETRE-AFFICHEE" in r3.stdout, derniere_erreur(r3)):
            manques.append("l'affichage ne traverse pas le bac à sable")

        titre("4. Et avec le bus de session privé par-dessus ?")
        r4 = dans_le_bac(espace, home, passerelle,
                         ["/usr/bin/dbus-run-session", "--",
                          "/usr/bin/python3", script], audio=False)
        if not dire("dbus-run-session + fenêtre",
                    "FENETRE-AFFICHEE" in r4.stdout, derniere_erreur(r4)):
            manques.append("le bus de session privé ne démarre pas")
            consequence("c'est lui qui remplace le bus de l'hôte : sans lui, "
                        "les applications mono-instance se rejoignent entre Espaces")

        titre("5. Le dossier personnel est-il vraiment à lui ?")
        r5 = dans_le_bac(espace, home, passerelle,
                         ["/bin/sh", "-c",
                          "echo bonjour > %s/temoin && cat %s/temoin"
                          % (home, home)], audio=False)
        dire("écriture dans le dossier de l'Espace", "bonjour" in r5.stdout,
             derniere_erreur(r5))
        temoin = os.path.join(home, "temoin")
        if os.path.exists(temoin):
            dire("fichier créé appartenant à l'Espace",
                 os.stat(temoin).st_uid == espace.pw_uid,
                 "UID %d" % os.stat(temoin).st_uid)

        titre("6. Là où l'hôte pose ses sockets AUJOURD'HUI")
        # Dossier temporaire du bureau en 0700 : hors d'atteinte d'un compte
        # dédié, et c'est normal. On le mesure pour garder la trace du pourquoi
        # du dépôt — un « NON » ici est la situation d'avant, pas un manque.
        ancien = 0
        for quoi in ("notifications", "boîte d'envoi", "filtre réseau"):
            srv, chemin = socket_de_l_hote(coin_hote, bureau.pw_uid, bureau.pw_gid)
            sockets_hote.append(srv)
            ok, erreur = joignable(espace, chemin)
            ancien += 1 if ok else 0
            dire("socket « %s » dans un dossier temporaire" % quoi, ok,
                 "joignable" if ok else erreur)
        if not ancien:
            consequence("attendu : c'est précisément ce que le dépôt remplace")

        titre("7. Et déposées dans le dépôt, le sont-elles ?")
        depot = r.get("depot")
        if not depot:
            dire("dépôt préparé par le service", False,
                 "réponse sans « depot » — service trop ancien")
            manques.append("le service ne prépare pas encore de dépôt")
        else:
            dire("dépôt préparé par le service", True, depot)
            chemin = os.path.join(depot, "notif")
            # Le bureau dépose et sert la socket lui-même, sous SON compte :
            # c'est exactement ce que fera codebyr-space.
            serveur = subprocess.Popen(
                ["/usr/bin/setpriv", "--reuid", str(bureau.pw_uid),
                 "--regid", str(bureau.pw_gid), "--clear-groups",
                 "--no-new-privs", "/usr/bin/python3", "-c",
                 "import os,socket\n"
                 "s=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)\n"
                 "s.bind(%r); os.chmod(%r, 0o666); s.listen(4)\n"
                 "c,_=s.accept(); c.sendall(b'SERVI'); c.close()\n"
                 % (chemin, chemin)])
            time.sleep(1.0)
            depose = os.path.exists(chemin)
            if not dire("le bureau peut déposer une socket", depose,
                        "" if depose else "écriture refusée dans le dépôt"):
                manques.append("le bureau ne peut pas écrire dans le dépôt")
            if depose:
                # Le trajet complet d'une notification : de l'application, dans
                # le bac à sable, jusqu'au service qui écoute sur le bureau.
                dedans = dans_le_bac(
                    espace, home, passerelle,
                    ["/usr/bin/python3", "-c",
                     "import socket\n"
                     "s=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)\n"
                     "s.settimeout(5); s.connect('/run/codebyr-notif')\n"
                     "print(s.recv(16).decode())\n"],
                    audio=False, notifications=chemin)
                if not dire("socket du dépôt jointe DEPUIS le bac à sable",
                            "SERVI" in dedans.stdout, derniere_erreur(dedans)):
                    manques.append("le dépôt ne traverse pas le bac à sable")
            serveur.terminate()
            serveur.wait(timeout=5)

        titre("8. Les plafonds mémoire tiennent-ils ?")
        plafond = subprocess.run(
            ["/usr/bin/systemd-run", "--scope", "--quiet",
             "--uid=%d" % espace.pw_uid, "--gid=%d" % espace.pw_gid,
             "-p", "MemoryMax=256M", "-p", "TasksMax=64",
             "--", "/usr/bin/python3", "-c", PLAFOND_LU],
            capture_output=True, text=True, timeout=60)
        pose = plafond.stdout.strip()
        if not dire("systemd-run --scope --uid pose un plafond",
                    pose.isdigit() and int(pose) <= 256 * 1024 * 1024,
                    pose or derniere_erreur(plafond)):
            manques.append("les plafonds mémoire ne s'appliquent pas sous un autre compte")
            consequence("aujourd'hui posés par « systemd-run --user », qui ne "
                        "traverse pas le changement de compte")
    finally:
        for srv in sockets_hote:
            srv.close()
        # Par le service lui-même : c'est aussi une façon de vérifier qu'il
        # sait défaire ce qu'il a fait, montages et droits compris.
        demander(bureau.pw_uid, bureau.pw_gid,
                 {"action": "fermer", "espace": ESPACE})
        service.terminate()
        service.wait(timeout=5)
        subprocess.run(["/usr/sbin/userdel", nom], capture_output=True)
        shutil.rmtree(comptes.chemin_home(bureau.pw_uid, ESPACE), ignore_errors=True)
        shutil.rmtree(coin_hote, ignore_errors=True)
        shutil.rmtree(comptes.chemin_passerelle(nom), ignore_errors=True)
        if os.path.exists(SOCKET):
            os.unlink(SOCKET)
        acl = subprocess.run(["/usr/bin/getfacl", "-p",
                              "/run/user/%d/%s" % (uid, affichage)],
                             capture_output=True, text=True)
        reste = ":%s:" % nom in acl.stdout
        print("\nNettoyage : compte de mesure, dossiers et sockets supprimés%s."
              % (" — ATTENTION : un droit subsiste sur le socket du bureau"
                 if reste else ""))

    print()
    if manques:
        print("À écrire avant que le compte dédié soit utilisable :")
        for m in manques:
            print("  · %s" % m)
    else:
        print("La chaîne de lancement tient telle quelle sous un compte dédié.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
