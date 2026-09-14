#!/usr/bin/env python3
"""Éprouve le service privilégié « un UID par Espace », sur une machine d'essai.

NON INSTALLÉ. À lancer en administrateur, depuis une session graphique :

    sudo -E python3 tools/essai_service_uid.py

Ce que cet essai vérifie, dans l'ordre où ça compte :

  1. le service prépare un Espace : compte dédié, dossier à lui seul ;
  2. le compte du BUREAU ne peut pas lire ce dossier — c'est tout l'objet du
     chantier : aujourd'hui, ce qui s'échappe d'un Espace lit les autres ;
  3. une fenêtre s'affiche depuis ce compte, par la passerelle ;
  4. ce que le BUREAU demande s'exécute sous le compte de l'ESPACE, dans le
     bac à sable, sous plafond — sans que root ait vu la commande ;
  5. depuis ce même compte, le bus de session du bureau reste hors d'atteinte ;
  6. un compte d'ESPACE qui interroge le service est refusé (sinon « jetable »
     ferait ouvrir « banque ») ;
  7. la fermeture retire tout : montages, droits, passerelle, dépôt, portée.

À la fin, le compte d'essai et ses fichiers sont supprimés.
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
SOCKET = "/run/codebyr-uid-essai.sock"
ESPACE = "essai"
# Le premier processus d'un Espace tourne sous un compte système, qui ne peut
# pas traverser un dossier personnel : lancé depuis un dépôt cloné dans « ~ »,
# il échouerait avec « Permission denied ». On en pose donc une copie dans
# /run, que tout le monde traverse.
INIT_SOURCE = os.path.join(LIVRE, "usr", "lib", "codebyr", "codebyr-espace-init")
INIT_ESSAI = "/run/codebyr-espace-init-essai"

sys.path.insert(0, LIB)
import bac_a_sable  # noqa: E402
import comptes  # noqa: E402

FENETRE = """
import sys, gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
def demarrer(app):
    f = Gtk.ApplicationWindow(application=app, title="Essai Codebyr")
    f.set_default_size(320, 120)
    f.present()
    print("FENETRE-AFFICHEE", flush=True)
    GLib.timeout_add_seconds(2, lambda: (app.quit(), False)[1])
a = Gtk.Application(application_id="io.codebyr.EssaiUid")
a.connect("activate", demarrer)
sys.exit(a.run([]))
"""


def dire(quoi, bon, detail=""):
    print("%s %-54s %s" % ("  OUI " if bon else "  NON ", quoi, detail))
    return bon


def sous(uid, gid, args, entree=None, delai=30):
    try:
        return subprocess.run(
            ["/usr/bin/setpriv", "--reuid", str(uid), "--regid", str(gid),
             "--clear-groups", "--no-new-privs"] + args,
            capture_output=True, text=True, timeout=delai, input=entree)
    except subprocess.TimeoutExpired:
        # Une attente sans fin est un résultat, pas un incident : elle doit
        # donner une ligne « NON » et laisser l'essai aller au nettoyage.
        return subprocess.CompletedProcess(args, 124, "",
                                           "aucune réponse après %ds" % delai)


def demander(uid, gid, demande):
    """Interroge le service SOUS l'identité voulue : c'est le noyau qui le dira."""
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


def ordonner(uid, gid, socket_ordres, demande):
    """Fait exécuter une commande DANS l'Espace, comme le fera le lanceur.

    La connexion reste ouverte jusqu'à la fin du processus : on récupère donc
    la réponse de lancement puis le code de sortie.
    """
    code = (
        "import json,socket,sys\n"
        "s=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.settimeout(20)\n"
        "s.connect(%r)\n"
        "s.sendall(sys.stdin.read().encode())\n"
        "d=b''\n"
        "while True:\n"
        "    m=s.recv(4096)\n"
        "    if not m:\n"
        "        break\n"
        "    d+=m\n"
        "sys.stdout.write(d.decode())\n" % socket_ordres)
    r = sous(uid, gid, ["/usr/bin/python3", "-c", code], entree=json.dumps(demande))
    reponses = []
    for ligne in r.stdout.splitlines():
        try:
            reponses.append(json.loads(ligne))
        except ValueError:
            pass
    return reponses


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

    print("Essai du service « un UID par Espace »\n")
    dire("session du bureau", True, "%s (UID %d), affichage %s"
         % (bureau.pw_name, bureau.pw_uid, affichage))

    shutil.copyfile(INIT_SOURCE, INIT_ESSAI)
    os.chmod(INIT_ESSAI, 0o755)
    service = subprocess.Popen([sys.executable, SERVICE, "--essai", SOCKET],
                               env=dict(os.environ, CODEBYR_LIB=LIB,
                                        CODEBYR_INIT=INIT_ESSAI))
    time.sleep(1.5)
    perso = tempfile.mkdtemp(prefix="codebyr-essai-")
    script = os.path.join(perso, "fenetre.py")
    with open(script, "w", encoding="utf-8") as f:
        f.write(FENETRE)
    os.chmod(perso, 0o755)
    os.chmod(script, 0o644)
    nom = comptes.nom_compte(bureau.pw_uid, ESPACE)
    reussi = True
    try:
        print("\n── 1. Le service prépare l'Espace ────────────────────────────────")
        r = demander(bureau.pw_uid, bureau.pw_gid,
                     {"action": "preparer", "espace": ESPACE,
                      "affichage": affichage, "son": False})
        reussi &= dire("réponse du service", r.get("ok"), r.get("erreur") or r.get("brut", ""))
        if not r.get("ok"):
            return 1
        espace = pwd.getpwnam(r["compte"])
        dire("compte dédié", True, "%s (UID %d)" % (r["compte"], espace.pw_uid))
        st = os.stat(r["home"])
        # Sans dépôt, les contrôles qui suivent passeraient à vide : mieux vaut
        # le dire ici que conclure « conforme » sur une absence.
        reussi &= dire("dépôt préparé", bool(r.get("depot")), r.get("depot", ""))
        reussi &= dire("dossier à lui seul (0700)",
                       st.st_uid == espace.pw_uid and not st.st_mode & 0o077,
                       "%s, mode %s" % (r["home"], oct(st.st_mode & 0o777)))

        print("\n── 2. Le bureau ne lit PAS le dossier de l'Espace ────────────────")
        lecture = sous(bureau.pw_uid, bureau.pw_gid, ["/usr/bin/test", "-r", r["home"]])
        reussi &= dire("dossier de l'Espace lisible par le bureau",
                       lecture.returncode != 0,
                       "hors d'atteinte — c'est le but" if lecture.returncode
                       else "à refuser")

        print("\n── 3. L'affichage passe par la passerelle ────────────────────────")
        lien = os.path.join(r["passerelle"], affichage)
        dire("socket présentée", os.path.ismount(lien), lien)
        fen = sous(espace.pw_uid, espace.pw_gid, [
            "/usr/bin/env", "-i", "PATH=/usr/bin:/bin", "LANG=C.UTF-8",
            "HOME=" + perso, "XDG_RUNTIME_DIR=" + perso,
            "WAYLAND_DISPLAY=" + lien, "GDK_BACKEND=wayland",
            "/usr/bin/python3", script])
        derniere = [l for l in fen.stderr.splitlines() if l.strip()]
        reussi &= dire("fenêtre affichée depuis le compte de l'Espace",
                       "FENETRE-AFFICHEE" in fen.stdout,
                       derniere[-1][:80] if derniere and "FENETRE" not in fen.stdout else "")

        print("\n── 4. Le bureau fait exécuter DANS l'Espace ──────────────────────")
        reussi &= dire("socket d'ordres ouverte", bool(r.get("ordres")),
                       r.get("ordres", ""))
        preuve = os.path.join(r["home"], "preuve")
        # La VRAIE ligne de commande du bac à sable, comme le lanceur la
        # construira : on mesure la chaîne entière, pas un raccourci.
        argv = bac_a_sable.wrap_bwrap(
            r["home"], ["/bin/sh", "-c", "id -u > %s" % preuve], {},
            passerelle=r["passerelle"], chez=r["home"], audio=False, gpu=False)
        reponses = ordonner(bureau.pw_uid, bureau.pw_gid, r.get("ordres", ""),
                            {"argv": argv,
                             "env": {"PATH": "/usr/bin:/bin", "HOME": r["home"]}})
        lance = reponses[0] if reponses else {}
        reussi &= dire("ordre accepté", bool(lance.get("ok")),
                       lance.get("erreur", "") or "PID %s" % lance.get("pid"))
        fin = reponses[1].get("fin") if len(reponses) > 1 else None
        reussi &= dire("fin du processus rapportée au bureau", fin == 0,
                       "code %s" % fin)
        vu = ""
        if os.path.exists(preuve):
            with open(preuve, encoding="ascii") as f:
                vu = f.read().strip()
        # Le cœur du chantier tient dans cette ligne : ce que le BUREAU a
        # demandé s'est exécuté sous le compte de l'ESPACE, et non le sien.
        reussi &= dire("exécuté sous le compte de l'Espace",
                       vu == str(espace.pw_uid),
                       "UID %s" % (vu or "aucune preuve écrite"))
        plafond = subprocess.run(
            ["/usr/bin/systemctl", "show", "-p", "MemoryMax", "--value",
             comptes.unite_de_l_espace(r["compte"])],
            capture_output=True, text=True).stdout.strip()
        reussi &= dire("plafond mémoire posé sur tout l'Espace",
                       plafond.isdigit() and int(plafond) > 0, plafond)

        print("\n── 5. Ce qui reste hors d'atteinte ───────────────────────────────")
        for chemin, quoi in ((os.path.join("/run/user/%d" % uid, "bus"),
                              "bus de session du bureau"),
                             (bureau.pw_dir, "dossier personnel du bureau")):
            joint = sous(espace.pw_uid, espace.pw_gid, ["/usr/bin/test", "-r", chemin])
            reussi &= dire(quoi, joint.returncode != 0,
                           "hors d'atteinte" if joint.returncode else "à refuser")
        # Le dépôt se traverse, il ne se lit pas : sinon l'Espace découvrirait
        # les sockets que le bureau y place, et pourrait en fabriquer une.
        lu = sous(espace.pw_uid, espace.pw_gid,
                  ["/usr/bin/test", "-r", r.get("depot", "/nonexistant")])
        reussi &= dire("contenu du dépôt lisible par l'Espace", lu.returncode != 0,
                       "hors d'atteinte" if lu.returncode else "à refuser")

        print("\n── 6. Un Espace ne demande rien ──────────────────────────────────")
        r2 = demander(espace.pw_uid, espace.pw_gid,
                      {"action": "preparer", "espace": "banque",
                       "affichage": affichage, "son": False})
        reussi &= dire("demande venue d'un compte d'Espace refusée",
                       not r2.get("ok"), r2.get("erreur", ""))

        print("\n── 7. La fermeture retire tout ───────────────────────────────────")
        r3 = demander(bureau.pw_uid, bureau.pw_gid, {"action": "fermer", "espace": ESPACE})
        dire("réponse du service", r3.get("ok"), r3.get("erreur", ""))
        reussi &= dire("passerelle retirée", not os.path.exists(r["passerelle"]),
                       r["passerelle"])
        reussi &= dire("dépôt retiré", not os.path.exists(r.get("depot", "")),
                       r.get("depot", ""))
        acl = subprocess.run(["/usr/bin/getfacl", "-p",
                              "/run/user/%d/%s" % (uid, affichage)],
                             capture_output=True, text=True)
        reussi &= dire("droit retiré du socket du bureau",
                       ("user:%d" % espace.pw_uid) not in acl.stdout
                       and (":%s:" % r["compte"]) not in acl.stdout)
    finally:
        service.terminate()
        service.wait(timeout=5)
        # Ceinture : si l'essai s'est arrêté avant la fermeture, la portée
        # survivrait au service qui l'a ouverte, et le compte d'essai avec.
        subprocess.run(["/usr/bin/systemctl", "stop", "--quiet",
                        comptes.unite_de_l_espace(nom)], capture_output=True)
        subprocess.run(["/usr/sbin/userdel", nom], capture_output=True)
        shutil.rmtree(comptes.chemin_home(bureau.pw_uid, ESPACE), ignore_errors=True)
        shutil.rmtree(perso, ignore_errors=True)
        for reste in (SOCKET, INIT_ESSAI):
            if os.path.exists(reste):
                os.unlink(reste)
        print("\nNettoyage : compte d'essai, dossier et socket de service supprimés.")

    print("\n%s" % ("Tout est conforme." if reussi
                    else "AU MOINS UN CONTRÔLE A ÉCHOUÉ — voir les lignes « NON »."))
    return 0 if reussi else 1


if __name__ == "__main__":
    sys.exit(main())
