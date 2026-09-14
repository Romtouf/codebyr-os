#!/usr/bin/env python3
"""Éprouve le LANCEUR sous compte dédié, de bout en bout, sur une machine d'essai.

NON INSTALLÉ. À lancer en administrateur, depuis le terminal de la session
graphique :

    sudo -E python3 tools/essai_lanceur_uid.py

L'essai du service (essai_service_uid.py) prouve que root sait préparer un
Espace. Celui-ci prouve que `codebyr-space`, lancé par l'utilisateur comme
depuis un menu, s'en sert correctement :

  1. une application s'ouvre sous le compte de l'Espace, son dossier est
     préparé PAR l'Espace, sa notification arrive sur le bureau, et l'Espace
     se referme quand elle se ferme ;
  2. deux applications du même Espace : fermer la première ne ferme pas la
     seconde ;
  3. « Fermer l'Espace » d'un geste arrête vraiment ce qui tourne ;
  4. un geste pas encore prêt sous compte dédié est refusé, et ne touche à rien ;
  5. service absent : l'Espace NE S'OUVRE PAS — surtout pas sous le compte du
     bureau « en attendant ».

Pendant l'étape 1, une petite fenêtre « Essai compte dédié » reste ouverte six
secondes : regardez son liseré (violet) et la notification « Essai UID ».

Rien de ce qui est installé sur la machine n'est modifié : une copie du lanceur
est posée sous /usr/local/lib/codebyr-essai, un Espace « Essai UID » est ajouté
au registre de l'utilisateur, et tout est retiré à la fin.
"""
import json
import os
import pwd
import shutil
import subprocess
import sys
import time

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVRE = os.path.join(RACINE, "live-build", "config", "includes.chroot_after_packages")

COPIE = "/usr/local/lib/codebyr-essai"
COPIE_BIN = os.path.join(COPIE, "bin", "codebyr-space")
COPIE_LIB = os.path.join(COPIE, "lib")
COPIE_INIT = os.path.join(COPIE, "codebyr-espace-init")
COPIE_SERVICE = os.path.join(COPIE, "codebyr-uid")
FENETRE = os.path.join(COPIE, "fenetre.py")
SOCKET = "/run/codebyr-uid-essai-lanceur.sock"

ESPACE = "essai-uid"
ENTREE = {"id": ESPACE, "nom": "Essai UID", "couleur": "#8E44AD",
          "compte": "dedie", "app": "org.gnome.Nautilus.desktop"}
PERSONNE = 65534

sys.path.insert(0, os.path.join(LIVRE, "usr", "share", "codebyr"))
import comptes  # noqa: E402

# Exécuté DANS l'Espace. Ses preuves vont dans le dossier de l'Espace : sa
# sortie standard, elle, part au journal du premier processus.
SCRIPT_FENETRE = r'''
import json, os, sys
preuves = {"uid": os.getuid(), "home": os.environ.get("HOME"),
           "runtime": os.environ.get("XDG_RUNTIME_DIR")}
try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gio, GLib, Gtk
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    r = bus.call_sync("org.freedesktop.Notifications", "/org/freedesktop/Notifications",
                      "org.freedesktop.Notifications", "Notify",
                      GLib.Variant("(susssasa{sv}i)", ("essai", 0, "",
                                   "Notification depuis un compte dédié",
                                   "Si vous lisez ceci, le dépôt fonctionne.", [], {}, 6000)),
                      GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, 8000, None)
    preuves["notification"] = "envoyée"
except Exception as exc:
    preuves["notification"] = "échec : %s" % exc
def ecrire():
    with open(os.path.join(os.environ["HOME"], "preuves.json"), "w") as f:
        json.dump(preuves, f)
ecrire()
def demarrer(app):
    f = Gtk.ApplicationWindow(application=app, title="Essai compte dédié")
    f.set_default_size(420, 160)
    f.set_child(Gtk.Label(label="Regardez le liseré de cette fenêtre."))
    f.present()
    preuves["fenetre"] = "affichée"
    ecrire()
    GLib.timeout_add_seconds(6, lambda: (app.quit(), False)[1])
a = Gtk.Application(application_id="io.codebyr.EssaiLanceur")
a.connect("activate", demarrer)
sys.exit(a.run([]))
'''


def dire(quoi, bon, detail=""):
    print("%s %-56s %s" % ("  OUI " if bon else "  NON ", quoi, detail))
    return bool(bon)


def titre(texte):
    print("\n── %s %s" % (texte, "─" * max(0, 62 - len(texte))))


def installer_copie():
    """Pose une copie du lanceur, du service et du premier processus.

    Sous /usr/local : un compte d'Espace ne traverse pas un dossier personnel,
    et /run est monté « noexec » sur la machine d'essai (voir
    essai_service_uid.py). La copie est vérifiée exécutable par un AUTRE
    compte avant de bâtir quoi que ce soit dessus.
    """
    shutil.rmtree(COPIE, ignore_errors=True)
    os.makedirs(os.path.dirname(COPIE_BIN), mode=0o755)
    shutil.copytree(os.path.join(LIVRE, "usr", "share", "codebyr"), COPIE_LIB,
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(os.path.join(LIVRE, "usr", "bin", "codebyr-space"), COPIE_BIN)
    shutil.copyfile(os.path.join(LIVRE, "usr", "lib", "codebyr", "codebyr-espace-init"),
                    COPIE_INIT)
    shutil.copyfile(os.path.join(LIVRE, "usr", "lib", "codebyr", "codebyr-uid"),
                    COPIE_SERVICE)
    with open(FENETRE, "w", encoding="utf-8") as f:
        f.write(SCRIPT_FENETRE)
    for dossier, sous_dossiers, fichiers in os.walk(COPIE):
        os.chmod(dossier, 0o755)
        for nom in fichiers:
            os.chmod(os.path.join(dossier, nom), 0o644)
    for executable in (COPIE_BIN, COPIE_INIT, COPIE_SERVICE):
        os.chmod(executable, 0o755)
    r = subprocess.run(["/usr/bin/setpriv", "--reuid", str(PERSONNE), "--regid",
                        str(PERSONNE), "--clear-groups", "--no-new-privs", COPIE_INIT],
                       capture_output=True, text=True, timeout=20)
    return r.returncode == 2


def env_du_bureau(bureau):
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": bureau.pw_dir,
           "USER": bureau.pw_name, "LOGNAME": bureau.pw_name,
           "LANG": os.environ.get("LANG", "fr_FR.UTF-8"),
           "CODEBYR_LIB": COPIE_LIB, "CODEBYR_UID_SOCKET": SOCKET}
    for cle in ("WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS",
                "XDG_DATA_DIRS", "XDG_CURRENT_DESKTOP", "XDG_SESSION_TYPE"):
        if os.environ.get(cle):
            env[cle] = os.environ[cle]
    return env


def comme_le_bureau(bureau, args, attendre=True, delai=120):
    """Lance une commande sous le compte du bureau, comme le ferait un clic."""
    cmd = ["/usr/bin/setpriv", "--reuid", str(bureau.pw_uid), "--regid",
           str(bureau.pw_gid), "--init-groups", "/usr/bin/env", "-i"]
    cmd += ["%s=%s" % kv for kv in env_du_bureau(bureau).items()] + args
    if not attendre:
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=delai)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "aucune fin après %ds" % delai)


def lanceur(bureau, *args, attendre=True):
    return comme_le_bureau(bureau, ["/usr/bin/python3", COPIE_BIN] + list(args),
                           attendre=attendre)


def registre(bureau, geste):
    code = ("import sys; sys.path.insert(0, %r); import registre, json; "
            % COPIE_LIB)
    if geste == "ajouter":
        code += "registre.supprimer_espace(%r); registre.ajouter_espace(json.loads(%r))" % (
            ESPACE, json.dumps(ENTREE))
    else:
        code += "registre.supprimer_espace(%r)" % ESPACE
    return comme_le_bureau(bureau, ["/usr/bin/python3", "-c", code]).returncode == 0


def marqueurs(uid_bureau):
    """PID notés par le lanceur pour l'extension GNOME, pour l'Espace d'essai."""
    rundir = "/run/user/%d/codebyr" % uid_bureau
    trouves = []
    try:
        noms = os.listdir(rundir)
    except OSError:
        return trouves
    for nom in noms:
        if not nom.startswith("pid-"):
            continue
        try:
            with open(os.path.join(rundir, nom), encoding="utf-8") as f:
                if f.read().strip() == ESPACE:
                    trouves.append(int(nom[4:]))
        except (OSError, ValueError):
            continue
    return trouves


def proprietaire(pid):
    try:
        with open("/proc/%d/status" % pid, encoding="utf-8") as f:
            for ligne in f:
                if ligne.startswith("Uid:"):
                    return int(ligne.split()[1])
    except OSError:
        return None
    return None


def attendre_que(condition, delai):
    fin = time.time() + delai
    while time.time() < fin:
        if condition():
            return True
        time.sleep(0.2)
    return condition()


def espace_ouvert(nom):
    return os.path.exists(comptes.chemin_passerelle(nom))


def lancer_service():
    if os.path.exists(SOCKET):
        os.unlink(SOCKET)
    service = subprocess.Popen(
        [sys.executable, COPIE_SERVICE, "--essai", SOCKET],
        env=dict(os.environ, CODEBYR_LIB=COPIE_LIB, CODEBYR_INIT=COPIE_INIT))
    attendre_que(lambda: os.path.exists(SOCKET), 10)
    return service


def main():
    if os.geteuid() != 0:
        print("À lancer en administrateur : sudo -E python3 %s" % sys.argv[0],
              file=sys.stderr)
        return 2
    uid = int(os.environ.get("SUDO_UID") or 0)
    if uid < comptes.UID_MINIMAL or not os.environ.get("WAYLAND_DISPLAY"):
        print("Lancez avec « sudo -E » depuis le terminal de votre session graphique.",
              file=sys.stderr)
        return 2
    bureau = pwd.getpwuid(uid)
    nom = comptes.nom_compte(uid, ESPACE)
    home = comptes.chemin_home(uid, ESPACE)
    reussi = True

    print("Essai du lanceur sous compte dédié\n")
    dire("session du bureau", True, "%s (UID %d)" % (bureau.pw_name, uid))
    if not dire("copie d'essai exécutable par un autre compte", installer_copie(), COPIE):
        shutil.rmtree(COPIE, ignore_errors=True)
        return 1
    service = lancer_service()
    if not dire("Espace « Essai UID » ajouté au registre", registre(bureau, "ajouter")):
        reussi = False
    enfants = []
    try:
        titre("1. Une application, sous le compte de l'Espace")
        debut = time.time()
        app = lanceur(bureau, "launch", ESPACE, "--", "/usr/bin/python3", FENETRE,
                      attendre=False)
        enfants.append(app)
        vus = attendre_que(lambda: marqueurs(uid), 20) and marqueurs(uid)
        reussi &= dire("marqueur posé pour l'extension GNOME", bool(vus),
                       "PID %s" % (vus[0] if vus else "aucun"))
        espace = None
        try:
            espace = pwd.getpwnam(nom)
        except KeyError:
            pass
        if vus and espace:
            reussi &= dire("processus lancé sous le compte de l'Espace",
                           proprietaire(vus[0]) == espace.pw_uid,
                           "UID %s (Espace : %d)" % (proprietaire(vus[0]), espace.pw_uid))
        sortie, erreurs = app.communicate(timeout=90)
        reussi &= dire("fin de l'application rapportée au lanceur", app.returncode == 0,
                       "code %s en %.0f s" % (app.returncode, time.time() - debut))
        if app.returncode != 0:
            for ligne in (erreurs or "").strip().splitlines()[-4:]:
                print("       │ %s" % ligne)
        preuves = {}
        try:
            with open(os.path.join(home, "preuves.json"), encoding="utf-8") as f:
                preuves = json.load(f)
        except (OSError, ValueError):
            pass
        if espace:
            reussi &= dire("l'application s'est vue sous le compte de l'Espace",
                           preuves.get("uid") == espace.pw_uid, "UID %s" % preuves.get("uid"))
        reussi &= dire("fenêtre affichée", preuves.get("fenetre") == "affichée",
                       preuves.get("fenetre", "aucune preuve"))
        reussi &= dire("notification transmise au bureau",
                       preuves.get("notification") == "envoyée",
                       preuves.get("notification", "aucune preuve"))
        mimeapps = os.path.join(home, ".config", "mimeapps.list")
        prepare = os.path.exists(mimeapps) and espace and \
            os.stat(mimeapps).st_uid == espace.pw_uid
        reussi &= dire("dossier préparé PAR l'Espace (associations)", prepare,
                       mimeapps if prepare else "absent ou à un autre compte")
        reussi &= dire("Espace refermé après sa dernière application",
                       attendre_que(lambda: not espace_ouvert(nom), 15),
                       comptes.chemin_passerelle(nom))

        titre("2. Deux applications : fermer l'une ne ferme pas l'autre")
        courte = lanceur(bureau, "launch", ESPACE, "--", "/usr/bin/python3", "-c",
                         "import time; time.sleep(4)", attendre=False)
        longue = lanceur(bureau, "launch", ESPACE, "--", "/usr/bin/python3", "-c",
                         "import time; time.sleep(12)", attendre=False)
        enfants += [courte, longue]
        courte.communicate(timeout=60)
        time.sleep(1)
        reussi &= dire("après la première, l'Espace reste ouvert",
                       espace_ouvert(nom) and longue.poll() is None)
        longue.communicate(timeout=60)
        reussi &= dire("après la seconde, il se referme",
                       attendre_que(lambda: not espace_ouvert(nom), 15))

        titre("3. « Fermer l'Espace » d'un geste")
        tenace = lanceur(bureau, "launch", ESPACE, "--", "/usr/bin/python3", "-c",
                         "import time; time.sleep(120)", attendre=False)
        enfants.append(tenace)
        attendre_que(lambda: marqueurs(uid), 20)
        fermeture = lanceur(bureau, "close", ESPACE)
        reussi &= dire("commande de fermeture acceptée", fermeture.returncode == 0,
                       (fermeture.stdout or fermeture.stderr).strip()[:60])
        try:
            tenace.communicate(timeout=20)
            arretee = True
        except subprocess.TimeoutExpired:
            arretee = False
        reussi &= dire("l'application a vraiment été arrêtée", arretee)
        reussi &= dire("l'Espace est refermé",
                       attendre_que(lambda: not espace_ouvert(nom), 15))

        titre("4. Un geste pas encore prêt est refusé")
        purge = lanceur(bureau, "purge", ESPACE)
        reussi &= dire("effacement des données refusé", purge.returncode == 1,
                       (purge.stderr or "").strip()[:60])
        reussi &= dire("données de l'Espace intactes", os.path.isdir(home))

        titre("5. Service absent : l'Espace ne s'ouvre pas")
        service.terminate()
        service.wait(timeout=10)
        avant = set(marqueurs(uid))
        refus = lanceur(bureau, "launch", ESPACE, "--", "/usr/bin/python3", "-c",
                        "import time; time.sleep(30)")
        reussi &= dire("ouverture refusée", refus.returncode == 1,
                       (refus.stderr or "").strip().splitlines()[-1][:70]
                       if refus.stderr.strip() else "")
        reussi &= dire("rien lancé sous le compte du bureau à la place",
                       set(marqueurs(uid)) == avant)
    finally:
        for enfant in enfants:
            if enfant.poll() is None:
                enfant.kill()
        if service.poll() is None:
            service.terminate()
            service.wait(timeout=10)
        # Un service arrêté ne range plus rien : on reprend ce qu'il a posé.
        service = lancer_service()
        comme_le_bureau(bureau, ["/usr/bin/python3", "-c",
                                 "import sys; sys.path.insert(0, %r); import compte_dedie; "
                                 "compte_dedie.fermer(%r, %r)" % (COPIE_LIB, ESPACE, SOCKET)])
        service.terminate()
        service.wait(timeout=10)
        subprocess.run(["/usr/bin/systemctl", "stop", "--quiet",
                        comptes.unite_de_l_espace(nom)], capture_output=True)
        registre(bureau, "retirer")
        subprocess.run(["/usr/sbin/userdel", nom], capture_output=True)
        shutil.rmtree(home, ignore_errors=True)
        shutil.rmtree(COPIE, ignore_errors=True)
        if os.path.exists(SOCKET):
            os.unlink(SOCKET)
        print("\nNettoyage : Espace d'essai retiré du registre, compte, dossier "
              "et copie d'essai supprimés.")

    print("\n%s" % ("Tout est conforme." if reussi
                    else "AU MOINS UN CONTRÔLE A ÉCHOUÉ — voir les lignes « NON »."))
    print("À vérifier de vos yeux pendant l'étape 1 : le liseré violet de la "
          "fenêtre, et la notification « Essai UID ».")
    return 0 if reussi else 1


if __name__ == "__main__":
    sys.exit(main())
