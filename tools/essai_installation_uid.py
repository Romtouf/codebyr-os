#!/usr/bin/env python3
"""Éprouve le compte dédié tel qu'il est INSTALLÉ, sur une machine réelle.

NON INSTALLÉ. À lancer en administrateur, depuis le terminal de la session
graphique, APRÈS avoir installé le paquet codebyr-tools :

    sudo -E python3 tools/essai_installation_uid.py

Les autres essais (essai_service_uid, essai_lanceur_uid) posent leur propre
copie du service et le lancent à la main. Celui-ci ne copie RIEN : il éprouve
ce qui est installé, démarré par systemd, confiné par AppArmor. C'est le seul
qui puisse voir ce qu'un essai « à la main » ne verra jamais :

  · un durcissement d'unité hérité par les applications de l'Espace — un
    filtre seccomp aurait empêché le navigateur de compiler son JavaScript ;
  · un espace de noms de montage qui cacherait ses sockets à l'Espace ;
  · un profil AppArmor trop serré, qui refuserait en silence.

À la fin, l'Espace d'essai est supprimé, compte compris.
"""
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import time

ESPACE = "essai-installe"
ENTREE = {"id": ESPACE, "nom": "Essai installé", "couleur": "#1F7A8C",
          "compte": "dedie", "blindage": "renforce",
          "app": "org.gnome.Nautilus.desktop"}
LIB = "/usr/share/codebyr"
COIN = "/usr/local/lib/codebyr-essai-installe"
SOCKET = "/run/codebyr-uid.sock"

# Importer depuis l'arbre livré y écrirait un « __pycache__ », qui partirait
# tel quel dans l'image (test_packaging le refuse, à juste titre).
sys.dont_write_bytecode = True
sys.path.insert(0, LIB)
try:
    import comptes
except ImportError:
    comptes = None

FENETRE = r'''
import json, os, sys
preuves = {"uid": os.getuid()}
# Où l'application cherche ses sockets, et si l'affichage y est bien : depuis
# 1.16.0, le dossier d'exécution de l'Espace est /run/user/<son UID>.
_runtime = os.environ.get("XDG_RUNTIME_DIR", "")
preuves["runtime"] = _runtime
preuves["wayland_present"] = bool(_runtime) and os.path.exists(
    os.path.join(_runtime, os.environ.get("WAYLAND_DISPLAY", "wayland-0")))
# Le bus de l'Espace sert aux applications Flatpak. Une application ordinaire,
# dans son bac à sable, ne doit PAS le voir : elle a le sien.
preuves["bus_visible"] = bool(_runtime) and os.path.exists(os.path.join(_runtime, "bus"))
try:
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk
    def demarrer(app):
        f = Gtk.ApplicationWindow(application=app, title="Essai de l'installation")
        f.set_default_size(400, 140)
        f.present()
        preuves["fenetre"] = "affichée"
        with open(os.path.join(os.environ["HOME"], "preuves.json"), "w") as g:
            json.dump(preuves, g)
        GLib.timeout_add_seconds(4, lambda: (app.quit(), False)[1])
    a = Gtk.Application(application_id="io.codebyr.EssaiInstalle")
    a.connect("activate", demarrer)
    a.run([])
except Exception as exc:
    preuves["erreur"] = str(exc)
with open(os.path.join(os.environ["HOME"], "preuves.json"), "w") as g:
    json.dump(preuves, g)
'''


def dire(quoi, bon, detail=""):
    print("%s %-54s %s" % ("  OUI " if bon else "  NON ", quoi, detail))
    return bool(bon)


def titre(texte):
    print("\n── %s %s" % (texte, "─" * max(0, 60 - len(texte))))


def systemctl(*args):
    return subprocess.run(["/usr/bin/systemctl"] + list(args),
                          capture_output=True, text=True, timeout=30)


def comme_le_bureau(bureau, args, attendre=True, delai=180):
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": bureau.pw_dir,
           "USER": bureau.pw_name, "LOGNAME": bureau.pw_name,
           "LANG": os.environ.get("LANG", "fr_FR.UTF-8")}
    for cle in ("WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS",
                "XDG_DATA_DIRS", "XDG_CURRENT_DESKTOP", "XDG_SESSION_TYPE"):
        if os.environ.get(cle):
            env[cle] = os.environ[cle]
    cmd = ["/usr/bin/setpriv", "--reuid", str(bureau.pw_uid), "--regid",
           str(bureau.pw_gid), "--init-groups", "/usr/bin/env", "-i"]
    cmd += ["%s=%s" % kv for kv in env.items()] + args
    if not attendre:
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=delai)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "aucune fin après %ds" % delai)


def lanceur(bureau, *args, attendre=True):
    return comme_le_bureau(bureau, ["/usr/bin/codebyr-space"] + list(args), attendre=attendre)


def registre(bureau, geste):
    code = "import sys; sys.path.insert(0, %r); import registre, json; " % LIB
    if geste == "ajouter":
        code += "registre.supprimer_espace(%r); registre.ajouter_espace(json.loads(%r))" % (
            ESPACE, json.dumps(ENTREE))
    else:
        code += "registre.supprimer_espace(%r)" % ESPACE
    return comme_le_bureau(bureau, ["/usr/bin/python3", "-c", code]).returncode == 0


def refus_apparmor(depuis):
    """Ce qu'AppArmor a refusé au service : l'opération et le CHEMIN, rien d'autre.

    La ligne brute du noyau est longue, et le chemin s'y trouve au milieu : en
    la tronquant, on perdait exactement l'information qui sert (14/09/2026).
    """
    noyau = subprocess.run(["/usr/bin/journalctl", "-k", "--no-pager", "-o", "cat",
                            "--since", "@%d" % int(depuis)],
                           capture_output=True, text=True).stdout.splitlines()
    refus = []
    for ligne in noyau:
        if "apparmor=" not in ligne or "DENIED" not in ligne or "codebyr" not in ligne:
            continue
        champs = dict(re.findall(r'(\w+)="([^"]*)"', ligne))
        # Un refus de capacité ne porte pas de « name » mais un « capname » :
        # sans lui, la ligne disait « capable ? » — un refus sans son objet.
        quoi = champs.get("name") or champs.get("capname") or "?"
        resume = "%s %s (%s)" % (champs.get("operation", "?"), quoi,
                                 champs.get("profile", "?"))
        if resume not in refus:
            refus.append(resume)
    return refus


def main():
    if os.geteuid() != 0:
        print("À lancer en administrateur : sudo -E python3 %s" % sys.argv[0],
              file=sys.stderr)
        return 2
    uid = int(os.environ.get("SUDO_UID") or 0)
    if uid < 1000 or not os.environ.get("WAYLAND_DISPLAY"):
        print("Lancez avec « sudo -E » depuis le terminal de votre session graphique.",
              file=sys.stderr)
        return 2
    bureau = pwd.getpwuid(uid)
    debut = time.time()
    reussi = True
    print("Essai du compte dédié tel qu'il est installé\n")
    dire("session du bureau", True, "%s (UID %d)" % (bureau.pw_name, uid))

    # La version D'ABORD : sans elle, un paquet non installé donne une liste de
    # « absent » sans dire ce qu'il faut faire — et le premier lecteur croit à
    # un paquet cassé plutôt qu'à un paquet pas encore installé.
    attendue = ""
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "VERSION"), encoding="utf-8") as f:
            attendue = f.read().strip()
    except OSError:
        pass
    installee = subprocess.run(["/usr/bin/dpkg-query", "-W", "-f=${Version}", "codebyr-tools"],
                               capture_output=True, text=True).stdout.strip()
    if attendue and installee != attendue:
        dire("paquet codebyr-tools à la version éprouvée", False,
             "installé : %s — attendu : %s" % (installee or "aucun", attendue))
        print("\nCet essai éprouve ce qui est INSTALLÉ. Installez d'abord le paquet :")
        print("  sudo apt install -y /tmp/codebyr.deb")
        return 2
    dire("paquet codebyr-tools à la version éprouvée", True, installee)

    titre("1. Ce que le paquet a livré")
    for chemin in ("/usr/lib/codebyr/codebyr-uid",
                   "/usr/lib/codebyr/codebyr-espace-init",
                   "/usr/lib/systemd/system/codebyr-uid.socket",
                   "/usr/lib/systemd/system/codebyr-uid.service",
                   "/etc/apparmor.d/codebyr-uid",
                   "/usr/share/codebyr/compte_dedie.py"):
        existe = os.path.exists(chemin)
        executable = os.access(chemin, os.X_OK) if "/usr/lib/codebyr/" in chemin else True
        reussi &= dire(os.path.basename(chemin), existe and executable,
                       "" if existe and executable else
                       "absent" if not existe else "pas exécutable")
    if comptes is None:
        dire("modules du compte dédié installés", False,
             "%s/comptes.py introuvable (le dossier, lui, existe)" % LIB)
        return 1

    titre("2. Le service : activé, mais rien ne tourne")
    reussi &= dire("socket activée au démarrage",
                   systemctl("is-enabled", "codebyr-uid.socket").stdout.strip() == "enabled")
    reussi &= dire("socket en écoute",
                   systemctl("is-active", "codebyr-uid.socket").stdout.strip() == "active")
    # Ce qu'un essai précédent a laissé teinte tout ce qui suit : on remet le
    # service à zéro, puis on vérifie qu'il ne revient QUE sur demande.
    etat = systemctl("is-active", "codebyr-uid.service").stdout.strip()
    if etat in ("active", "failed"):
        print("       (le service restait d'un essai précédent (%s) : arrêté)" % etat)
        systemctl("stop", "codebyr-uid.service")
        systemctl("reset-failed", "codebyr-uid.service")
        etat = systemctl("is-active", "codebyr-uid.service").stdout.strip()
    reussi &= dire("service à l'arrêt tant qu'aucun Espace ne le demande",
                   etat != "active", etat)
    charge = subprocess.run(["/usr/sbin/aa-status"], capture_output=True, text=True)
    reussi &= dire("profil AppArmor chargé", "codebyr-uid" in charge.stdout,
                   "" if "codebyr-uid" in charge.stdout else "absent de aa-status")

    titre("3. Un Espace s'ouvre, par le chemin réel")
    os.makedirs(COIN, mode=0o755, exist_ok=True)
    script = os.path.join(COIN, "fenetre.py")
    with open(script, "w", encoding="utf-8") as f:
        f.write(FENETRE)
    os.chmod(script, 0o644)
    reussi &= dire("Espace d'essai ajouté au registre", registre(bureau, "ajouter"))
    nom = comptes.nom_compte(uid, ESPACE)
    home = comptes.chemin_home(uid, ESPACE)
    app = lanceur(bureau, "launch", ESPACE, "--", "/usr/bin/python3", script)
    reussi &= dire("ouverture acceptée", app.returncode == 0,
                   (app.stderr or "").strip().splitlines()[-1][:70]
                   if app.returncode and (app.stderr or "").strip() else "")
    preuves = {}
    try:
        with open(os.path.join(home, "preuves.json"), encoding="utf-8") as f:
            preuves = json.load(f)
    except OSError:
        pass
    try:
        espace = pwd.getpwnam(nom)
    except KeyError:
        espace = None
    reussi &= dire("fenêtre affichée depuis le compte de l'Espace",
                   preuves.get("fenetre") == "affichée" and bool(espace)
                   and preuves.get("uid") == espace.pw_uid,
                   preuves.get("erreur", "") or "UID %s" % preuves.get("uid"))
    reussi &= dire("le service a démarré à la demande",
                   systemctl("is-active", "codebyr-uid.service").stdout.strip() == "active")

    # ── Ce que la 1.16.0 a changé : le dossier d'exécution de l'Espace ──
    attendu = "/run/user/%d" % espace.pw_uid if espace else "?"
    # Le détail d'un contrôle nouveau est un message d'ÉCHEC : il ne suit un
    # OUI que s'il dit autre chose qu'un échec. Constaté le 15/09/2026 —
    # « OUI plus aucune passerelle … existe encore » se lisait à l'envers.
    vu = preuves.get("runtime") == attendu
    reussi &= dire("l'Espace voit son dossier d'exécution à sa place", vu,
                   attendu if vu else "vu : %s — attendu : %s"
                   % (preuves.get("runtime") or "rien", attendu))
    reussi &= dire("l'affichage y est présenté", preuves.get("wayland_present") is True)
    # ── Tranche 2 : le bus de l'Espace ──
    espace_journal = subprocess.run(
        ["/usr/bin/journalctl", "--no-pager", "-o", "cat", "-t", "codebyr-espace",
         "--since", "@%d" % int(debut)], capture_output=True, text=True).stdout
    demarre = "bus démarré" in espace_journal
    reussi &= dire("l'Espace a démarré son bus de session", demarre,
                   "" if demarre else (espace_journal.strip().splitlines() or
                                       ["rien au journal de codebyr-espace"])[-1][:70])
    reussi &= dire("une application ordinaire ne le voit pas",
                   preuves.get("bus_visible") is False,
                   "" if preuves.get("bus_visible") is False else
                   "visible depuis le bac à sable : %s" % preuves.get("bus_visible"))
    ancienne = os.path.exists("/run/codebyr/passerelles")
    reussi &= dire("plus aucune passerelle à l'ancienne", not ancienne,
                   "/run/codebyr/passerelles existe encore" if ancienne else "")
    # Le lanceur est revenu : sa dernière application est fermée, l'Espace
    # doit l'être aussi — dossier effacé, droit sur l'affichage retiré.
    ferme = False
    for _ in range(30):
        if not os.path.exists(attendu):
            ferme = True
            break
        time.sleep(0.5)
    reussi &= dire("fermé, son dossier d'exécution est effacé", ferme,
                   "" if ferme else "%s existe encore" % attendu)
    affichage_bureau = "/run/user/%d/%s" % (uid, os.environ.get("WAYLAND_DISPLAY", "wayland-0"))
    acl = subprocess.run(["/usr/bin/getfacl", "-pn", affichage_bureau],
                         capture_output=True, text=True).stdout
    garde = bool(espace) and ("user:%d:" % espace.pw_uid) in acl
    reussi &= dire("…et son droit sur votre affichage retiré", not garde,
                   "le compte de l'Espace garde un droit sur %s" % affichage_bureau
                   if garde else "")
    for sensible in ("/run/user/%d" % uid, affichage_bureau):
        st = os.stat(sensible)
        if st.st_uid != uid:
            reussi &= dire("votre dossier d'exécution est resté à vous", False,
                           "%s appartient à l'UID %d" % (sensible, st.st_uid))

    titre("4. Le service est bien confiné")
    principal = systemctl("show", "-p", "MainPID", "--value", "codebyr-uid.service").stdout.strip()
    profil = ""
    try:
        with open("/proc/%s/attr/current" % principal, encoding="utf-8") as f:
            profil = f.read().strip("\x00\n ")
    except OSError:
        pass
    reussi &= dire("il tourne sous son profil, en mode strict",
                   profil.startswith("codebyr-uid") and "enforce" in profil,
                   profil or "profil illisible (PID %s)" % principal)
    refuses = refus_apparmor(debut)
    reussi &= dire("aucun refus d'AppArmor pendant l'ouverture", not refuses,
                   "%d refus" % len(refuses))
    for ligne in refuses[:4]:
        print("       │ %s" % ligne.strip()[:130])

    titre("5. Le navigateur, sous compte dédié et blindage")
    # C'est LE contrôle que seul l'installé peut faire : un durcissement
    # d'unité hérité (MemoryDenyWriteExecute) aurait empêché Firefox de
    # compiler son JavaScript, et aucun essai « à la main » ne l'aurait vu.
    capture = os.path.join(bureau.pw_dir, "capture-essai.png")
    navigateur = lanceur(bureau, "launch", ESPACE, "--", "firefox-esr", "--headless",
                         "--screenshot", capture, "https://example.org/")
    sur_disque = os.path.join(home, "capture-essai.png")
    taille = os.path.getsize(sur_disque) if os.path.exists(sur_disque) else 0
    reussi &= dire("le navigateur s'ouvre et rend une page", taille > 4000,
                   "capture de %d octets" % taille if taille else
                   (navigateur.stderr or "").strip().splitlines()[-1][:70]
                   if (navigateur.stderr or "").strip() else "aucune capture")

    titre("6. Suppression complète")
    suppression = lanceur(bureau, "delete", ESPACE)
    reussi &= dire("Espace supprimé", suppression.returncode == 0,
                   (suppression.stderr or "").strip()[:70])
    try:
        pwd.getpwnam(nom)
        reste = True
    except KeyError:
        reste = False
    reussi &= dire("son compte est retiré", not reste)
    reussi &= dire("son dossier aussi", not os.path.exists(home))

    registre(bureau, "retirer")
    shutil.rmtree(COIN, ignore_errors=True)
    for chemin in (capture, os.path.join(bureau.pw_dir, "preuves.json")):
        try:
            os.unlink(chemin)
        except OSError:
            pass
    print("\nNettoyage : Espace d'essai retiré du registre, compte et dossier supprimés.")
    print("\n%s" % ("Tout est conforme." if reussi
                    else "AU MOINS UN CONTRÔLE A ÉCHOUÉ — voir les lignes « NON »."))
    return 0 if reussi else 1


if __name__ == "__main__":
    sys.exit(main())
