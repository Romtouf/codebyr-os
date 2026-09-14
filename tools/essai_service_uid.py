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
# Le premier processus d'un Espace tourne sous un compte système : il ne peut
# ni traverser un dossier personnel — lancé depuis un dépôt cloné dans « ~ »,
# il échoue avec « Permission denied » — ni s'exécuter depuis un système de
# fichiers monté « noexec », comme /run sur la machine d'essai. Deviner le bon
# emplacement a coûté deux allers-retours : l'outil en essaie plusieurs, dans
# l'ordre, et dit ce qu'il a trouvé. En production la question ne se pose
# pas : le paquet l'installe sous /usr/lib.
INIT_SOURCE = os.path.join(LIVRE, "usr", "lib", "codebyr", "codebyr-espace-init")
INITS_POSSIBLES = ("/usr/local/lib/codebyr-espace-init-essai",
                   "/usr/lib/codebyr-espace-init-essai",
                   "/opt/codebyr-espace-init-essai")
# Compte présent partout, sans rien à lui : de quoi vérifier qu'un autre que
# root peut exécuter cette copie, avant de bâtir quoi que ce soit dessus.
PERSONNE = 65534

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


def poser_le_premier_processus():
    """Pose une copie du premier processus là où un AUTRE compte peut l'exécuter.

    Ce contrôle existe parce que son absence a coûté deux allers-retours : le
    programme était bien là, bien en 0755, et refusait pourtant de démarrer —
    dans un dossier personnel une fois, sur un /run monté « noexec » l'autre.
    On essaie donc plusieurs emplacements, et l'échec se nomme lui-même au
    lieu de ressortir en « impossible ».

    Renvoie le chemin retenu, ou None.
    """
    for chemin in INITS_POSSIBLES:
        dossier = os.path.dirname(chemin)
        try:
            os.makedirs(dossier, exist_ok=True)
            shutil.copyfile(INIT_SOURCE, chemin)
            os.chmod(chemin, 0o755)
        except OSError as exc:
            dire("copie possible dans %s" % dossier, False, str(exc)[:60])
            continue
        # Sans argument, il refuse et sort avec 2 : c'est LUI qui a répondu,
        # donc il s'est bien exécuté. Tout autre code vient d'avant.
        r = sous(PERSONNE, PERSONNE, [chemin], delai=20)
        if r.returncode == 2:
            dire("premier processus exécutable par un autre compte", True, chemin)
            return chemin
        options = subprocess.run(
            ["/usr/bin/findmnt", "-no", "OPTIONS", "--target", dossier],
            capture_output=True, text=True).stdout.strip()
        dire("exécutable depuis %s" % dossier, False,
             "monté : %s" % (options or "?"))
        os.unlink(chemin)
    return None


def montages_sous(chemin):
    lignes = subprocess.run(
        ["/usr/bin/findmnt", "-rn", "-o", "TARGET"],
        capture_output=True, text=True).stdout.splitlines()
    return [l for l in lignes if l.startswith(chemin + "/")]


def signaler_restes(nom, uid_bureau, affichage):
    """Dit, AVANT de commencer, ce qu'un essai précédent a laissé derrière lui.

    Sans cela, un « NON » peut venir de l'essai d'avant et non de celui-ci —
    c'est exactement ce qui s'est produit le 14/09/2026 : une préparation
    interrompue avait laissé un montage, et le suivant s'est empilé dessus.
    """
    restes = montages_sous(comptes.chemin_passerelle(nom))
    acl = subprocess.run(["/usr/bin/getfacl", "-p",
                          "/run/user/%d/%s" % (uid_bureau, affichage)],
                         capture_output=True, text=True).stdout
    # Toute entrée nominative, pas seulement celles au nom d'un Espace : un
    # compte supprimé depuis laisse son droit sous forme de NUMÉRO.
    droits = [l for l in acl.splitlines()
              if l.startswith("user:") and not l.startswith("user::")]
    if not restes and not droits:
        dire("aucun reste d'un essai précédent", True)
        return
    dire("aucun reste d'un essai précédent", False,
         "%d montage(s), %d droit(s)" % (len(restes), len(droits)))
    for ligne in restes + droits:
        print("       → %s" % ligne)


def diagnostiquer_passerelle(passerelle, debut):
    """Dit ce qui reste d'une passerelle, et pourquoi, sans qu'on ait à le demander.

    Écrit après un « NON » dont la cause n'était pas lisible dans la sortie :
    plutôt que de deviner et de renvoyer un essai de plus, on montre ce qui
    est resté, comment c'est monté, et ce que le service en a dit.
    """
    print("       ┌ ce qui reste dans la passerelle :")
    try:
        for nom in sorted(os.listdir(passerelle)):
            chemin = os.path.join(passerelle, nom)
            print("       │   %s%s" % (nom, "  (point de montage)"
                                       if os.path.ismount(chemin) else ""))
    except OSError as exc:
        print("       │   illisible : %s" % exc)
    montages = subprocess.run(
        ["/usr/bin/findmnt", "-rn", "-o", "TARGET,SOURCE,PROPAGATION"],
        capture_output=True, text=True).stdout.splitlines()
    print("       ├ montages sous la passerelle :")
    for ligne in montages:
        if ligne.startswith(passerelle):
            print("       │   %s" % ligne)
    journal = subprocess.run(
        ["/usr/bin/journalctl", "--no-pager", "-o", "cat", "-t", "codebyr-uid",
         "--since", "@%d" % int(debut)],
        capture_output=True, text=True).stdout.splitlines()
    print("       └ ce que le service a écrit au journal :")
    for ligne in journal[-12:]:
        print("           %s" % ligne)


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

    debut = time.time()
    print("Essai du service « un UID par Espace »\n")
    dire("session du bureau", True, "%s (UID %d), affichage %s"
         % (bureau.pw_name, bureau.pw_uid, affichage))

    init_essai = poser_le_premier_processus()
    if not init_essai:
        print()
        print("Aucun emplacement exécutable trouvé pour le premier processus.")
        return 2
    service = subprocess.Popen([sys.executable, SERVICE, "--essai", SOCKET],
                               env=dict(os.environ, CODEBYR_LIB=LIB,
                                        CODEBYR_INIT=init_essai))
    time.sleep(1.5)
    perso = tempfile.mkdtemp(prefix="codebyr-essai-")
    script = os.path.join(perso, "fenetre.py")
    with open(script, "w", encoding="utf-8") as f:
        f.write(FENETRE)
    os.chmod(perso, 0o755)
    os.chmod(script, 0o644)
    nom = comptes.nom_compte(bureau.pw_uid, ESPACE)
    reussi = True
    signaler_restes(nom, uid, affichage)
    fermeture_faite = False
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
        fermeture_faite = True
        # Compté désormais : un service qui dit « fermé » sans l'avoir fait est
        # précisément ce que cet essai doit attraper.
        reussi &= dire("réponse du service", r3.get("ok"), r3.get("erreur", ""))
        if not dire("passerelle retirée", not os.path.exists(r["passerelle"]),
                    r["passerelle"]):
            reussi = False
            diagnostiquer_passerelle(r["passerelle"], debut)
        reussi &= dire("dépôt retiré", not os.path.exists(r.get("depot", "")),
                       r.get("depot", ""))
        acl = subprocess.run(["/usr/bin/getfacl", "-p",
                              "/run/user/%d/%s" % (uid, affichage)],
                             capture_output=True, text=True)
        reussi &= dire("droit retiré du socket du bureau",
                       ("user:%d" % espace.pw_uid) not in acl.stdout
                       and (":%s:" % r["compte"]) not in acl.stdout)
    finally:
        # Un essai arrêté en route fermait sans passer par le service : le
        # montage et le DROIT sur le socket du bureau lui survivaient, et
        # l'essai suivant partait d'un état faussé. On ferme donc toujours par
        # le service, qui sait ce qu'il a posé.
        if not fermeture_faite:
            demander(bureau.pw_uid, bureau.pw_gid,
                     {"action": "fermer", "espace": ESPACE})
        service.terminate()
        service.wait(timeout=5)
        # Ceinture : si l'essai s'est arrêté avant la fermeture, la portée
        # survivrait au service qui l'a ouverte, et le compte d'essai avec.
        subprocess.run(["/usr/bin/systemctl", "stop", "--quiet",
                        comptes.unite_de_l_espace(nom)], capture_output=True)
        subprocess.run(["/usr/sbin/userdel", nom], capture_output=True)
        shutil.rmtree(comptes.chemin_home(bureau.pw_uid, ESPACE), ignore_errors=True)
        shutil.rmtree(perso, ignore_errors=True)
        for reste in (SOCKET, init_essai):
            if os.path.exists(reste):
                os.unlink(reste)
        print("\nNettoyage : compte d'essai, dossier et socket de service supprimés.")

    print("\n%s" % ("Tout est conforme." if reussi
                    else "AU MOINS UN CONTRÔLE A ÉCHOUÉ — voir les lignes « NON »."))
    return 0 if reussi else 1


if __name__ == "__main__":
    sys.exit(main())
