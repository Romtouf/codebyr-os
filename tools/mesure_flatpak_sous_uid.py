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
import signal
import subprocess
import sys
import time

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


def dire(quoi, bon, detail="", aussi_si_oui=False):
    """Une ligne de mesure.

    « detail » est presque toujours un message d'ERREUR : l'afficher derrière
    un OUI a fait lire l'inverse de ce qui s'était passé. Constaté le
    15/09/2026 : l'installation réussissait, et la ligne OUI portait un
    « Permission denied » de bubblewrap — un avertissement sans conséquence,
    qui donnait l'air d'un demi-échec. Un détail ne suit un OUI que si on le
    demande.
    """
    if bon and not aussi_si_oui:
        detail = ""
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
    """Le compte d'essai, fait exactement comme le service le fait.

    Le dossier personnel est posé DANS TOUS LES CAS, compte neuf ou non.
    Constaté le 15/09/2026 : au second passage, le compte survivait à un
    « userdel » mais son dossier avait bien été effacé ; la fonction rendait
    la main aussitôt, et Flatpak butait sur un « mkdir : Permission denied »
    parfaitement exact — le compte n'a évidemment pas le droit d'écrire dans
    /var/lib/codebyr/espaces/<uid>, qui appartient à root.
    """
    nom = comptes.nom_compte(uid_bureau, ESPACE)
    home = comptes.chemin_home(uid_bureau, ESPACE)
    try:
        compte = pwd.getpwnam(nom)
        neuf = False
    except KeyError:
        os.makedirs(os.path.dirname(home), exist_ok=True)
        os.chmod(os.path.dirname(os.path.dirname(home)), 0o711)
        os.chmod(os.path.dirname(home), 0o711)
        subprocess.run(["/usr/sbin/useradd", "--system", "--no-create-home",
                        "--home-dir", home, "--shell", "/usr/sbin/nologin", nom],
                       check=True, capture_output=True)
        compte = pwd.getpwnam(nom)
        neuf = True
    os.makedirs(os.path.dirname(home), exist_ok=True)
    os.chmod(os.path.dirname(os.path.dirname(home)), 0o711)
    os.chmod(os.path.dirname(home), 0o711)
    os.makedirs(home, exist_ok=True)
    os.chown(home, compte.pw_uid, compte.pw_gid)
    os.chmod(home, 0o700)
    return compte, home, neuf


def tuer_les_processus(uid):
    """Ce que le compte a laissé tourner, avant de le supprimer.

    Constaté le 15/09/2026 : « userdel : l'utilisateur est actuellement
    utilisé par le processus 4533 ». Le portail et le bus laissent des enfants
    (backends, helpers) que terminer le père ne suffit pas à emporter. Sans ce
    ménage, le compte survit et l'essai suivant repart d'un état bâtard.
    """
    restes = []
    for entree in os.listdir("/proc"):
        if not entree.isdigit():
            continue
        try:
            if os.stat("/proc/" + entree).st_uid == uid:
                restes.append(int(entree))
        except OSError:
            continue        # le processus est parti entre-temps : très bien
    for sig in (signal.SIGTERM, signal.SIGKILL):
        vivants = []
        for pid in restes:
            try:
                os.kill(pid, sig)
                vivants.append(pid)
            except OSError:
                pass
        if not vivants:
            break
        time.sleep(1.0)
        restes = vivants
    return restes


def supprimer_compte(compte, home):
    """Nettoie, et DIT si le nettoyage n'a pas abouti.

    Un userdel qui échoue en silence laisse un compte sans dossier : l'essai
    suivant repart d'un état bâtard, et c'est lui qu'on croit mesurer.
    """
    tuer_les_processus(compte.pw_uid)
    if os.path.isdir(home) and shutil.rmtree.avoids_symlink_attacks:
        shutil.rmtree(home, ignore_errors=True)
    r = subprocess.run(["/usr/sbin/userdel", compte.pw_name],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("  Compte %s NON supprimé : %s"
              % (compte.pw_name, (r.stderr or "").strip()[:96]))
        print("  (l'essai suivant le réutilisera ; « userdel -f %s » pour forcer)"
              % compte.pw_name)
        return False
    return True


# Exécuté SOUS le compte de l'Espace : demande au portail une vraie fenêtre
# « Ouvrir un fichier », et attend la réponse de l'utilisateur. Le code de
# réponse dit tout : 1 = annulé par l'utilisateur, donc la fenêtre s'est bien
# affichée et répondait ; 0 = un fichier choisi, même conclusion ; 2 = le
# portail a abandonné sans rien montrer.
DEMANDE_OUVRIR = r'''
import sys
import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
expediteur = bus.get_unique_name()[1:].replace(".", "_")
jeton = "codebyr_essai"
requete = "/org/freedesktop/portal/desktop/request/%s/%s" % (expediteur, jeton)
boucle = GLib.MainLoop()
resultat = {}
def reponse(_c, _e, _p, _i, _s, parametres):
    resultat["code"] = parametres.unpack()[0]
    boucle.quit()
bus.signal_subscribe("org.freedesktop.portal.Desktop",
                     "org.freedesktop.portal.Request", "Response", requete,
                     None, Gio.DBusSignalFlags.NONE, reponse)
try:
    bus.call_sync("org.freedesktop.portal.Desktop",
                  "/org/freedesktop/portal/desktop",
                  "org.freedesktop.portal.FileChooser", "OpenFile",
                  GLib.Variant("(ssa{sv})", ("", "Codebyr, essai : cliquez sur Annuler",
                               {"handle_token": GLib.Variant("s", jeton)})),
                  None, Gio.DBusCallFlags.NONE, 60000, None)
except GLib.Error as exc:
    print("APPEL-REFUSE " + exc.message)
    sys.exit(0)
def trop_long():
    resultat.setdefault("code", "delai")
    boucle.quit()
GLib.timeout_add_seconds(120, trop_long)
boucle.run()
print("REPONSE %s" % resultat.get("code"))
'''


def processus_du_compte(uid):
    """Les noms des programmes qui tournent sous ce compte : qui a répondu."""
    noms = set()
    for entree in os.listdir("/proc"):
        if not entree.isdigit():
            continue
        try:
            if os.stat("/proc/" + entree).st_uid != uid:
                continue
            with open("/proc/%s/comm" % entree, encoding="utf-8") as f:
                noms.add(f.read().strip())
        except OSError:
            continue
    return noms


def mesurer_portails(compte, home, affichage, runtime_bureau):
    """Le portail sait-il faire son travail sur le bus privé d'un Espace ?

    Le premier passage a montré qu'il RÉPOND. Reste à savoir s'il affiche une
    vraie fenêtre « Ouvrir un fichier ». Sur GNOME, elle est dessinée par un
    composant qui s'appuie d'habitude sur GNOME Shell — absent d'un bus privé.
    C'est ce que la tranche 2 doit savoir avant d'être bâtie.

    Contrairement à l'essai manuel du premier passage, le portail n'est PAS
    lancé à la main : c'est le bus qui le démarre à la première demande,
    comme il le fera dans un vrai Espace.
    """
    titre("7. Le portail fait-il son travail sur ce bus ?")
    canonique = "/run/user/%d" % compte.pw_uid
    deja = os.path.isdir(canonique)
    socket_bureau = os.path.join(runtime_bureau, affichage)
    socket_espace = os.path.join(canonique, affichage)
    monte = False
    bus = None
    code = 0
    try:
        os.makedirs(canonique, exist_ok=True)
        os.chown(canonique, compte.pw_uid, compte.pw_gid)
        os.chmod(canonique, 0o700)
        if os.path.exists(socket_bureau):
            open(socket_espace, "a").close()
            m = subprocess.run(["/usr/bin/mount", "--bind", socket_bureau,
                                socket_espace], capture_output=True, text=True)
            monte = m.returncode == 0
            if monte:
                subprocess.run(["/usr/bin/setfacl", "-m", "u:%d:rw" % compte.pw_uid,
                                socket_bureau], capture_output=True)
        if not dire("affichage présenté à l'Espace", monte, socket_bureau):
            return 1

        # L'environnement du BUS est celui que recevront les services qu'il
        # démarre : sans l'affichage et le bureau, le portail ne saurait ni où
        # dessiner, ni quel composant choisir.
        chemin_bus = os.path.join(canonique, "bus")
        adresse = "unix:path=" + chemin_bus
        env_bus = {"HOME": home, "PATH": "/usr/bin:/bin",
                   "LANG": os.environ.get("LANG", "fr_FR.UTF-8"),
                   "XDG_RUNTIME_DIR": canonique, "WAYLAND_DISPLAY": affichage,
                   "XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "GNOME",
                   "GDK_BACKEND": "wayland"}
        bus = subprocess.Popen(
            ["/usr/bin/setpriv", "--reuid", str(compte.pw_uid), "--regid",
             str(compte.pw_gid), "--clear-groups", "--no-new-privs",
             "/usr/bin/env", "-i"] + ["%s=%s" % kv for kv in sorted(env_bus.items())] +
            ["/usr/bin/dbus-daemon", "--session", "--nofork", "--address", adresse],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        attente = 0.0
        while attente < 5.0 and not os.path.exists(chemin_bus):
            time.sleep(0.1)
            attente += 0.1
        if not dire("bus privé démarré", os.path.exists(chemin_bus), chemin_bus):
            return 1

        env_appel = dict(env_bus)
        env_appel["DBUS_SESSION_BUS_ADDRESS"] = adresse
        script = os.path.join(home, "demande-ouvrir.py")
        with open(script, "w", encoding="utf-8") as f:
            f.write(DEMANDE_OUVRIR)
        os.chown(script, compte.pw_uid, compte.pw_gid)

        print()
        print("  >>> Une fenêtre « Ouvrir un fichier » va apparaître.")
        print("  >>> Cliquez simplement sur « Annuler ».")
        print("  >>> (Si rien n'apparaît d'ici une minute, ne faites rien.)")
        print()
        r = sous(compte, ["/usr/bin/python3", "-I", script], env=env_appel, delai=150)
        sortie = (r.stdout or "").strip()
        repondants = sorted(n for n in processus_du_compte(compte.pw_uid)
                            if "portal" in n)
        dire("composants démarrés par le bus", bool(repondants),
             ", ".join(repondants) or "aucun", aussi_si_oui=True)

        if sortie.startswith("REPONSE 1") or sortie.startswith("REPONSE 0"):
            dire("la fenêtre « Ouvrir un fichier » s'est affichée", True)
            consequence("le portail fonctionne sur le bus de l'Espace : la "
                        "tranche 2 peut s'appuyer sur lui tel quel.")
        else:
            code = 1
            detail = sortie or derniere_erreur(r) or "aucune réponse"
            dire("la fenêtre « Ouvrir un fichier » s'est affichée", False, detail)
            for ligne in [l.strip() for l in (r.stderr or "").splitlines()
                          if l.strip()][-5:]:
                print("         %s" % ligne[:92])
            consequence("le composant GNOME a besoin de ce que le bus privé "
                        "n'a pas : il faudra en choisir un autre.")

        # Les documents : c'est par ce portail qu'une application Flatpak
        # reçoit un fichier choisi hors de son bac à sable.
        r = sous(compte, ["/usr/bin/gdbus", "call", "--session",
                          "--dest", "org.freedesktop.portal.Documents",
                          "--object-path", "/org/freedesktop/portal/documents",
                          "--method", "org.freedesktop.portal.Documents.GetMountPoint"],
                 env=env_appel, delai=40)
        dire("le portail des documents répond", r.returncode == 0,
             (r.stdout or "").strip()[:60] if r.returncode == 0
             else derniere_erreur(r), aussi_si_oui=True)
        if r.returncode != 0:
            consequence("sans lui, une application Flatpak ne reçoit un fichier "
                        "que si ses permissions lui ouvrent déjà le dossier.")
        return code
    finally:
        if bus:
            bus.terminate()
            try:
                bus.wait(timeout=5)
            except subprocess.TimeoutExpired:
                bus.kill()
        # Le portail et ses composants ont été démarrés par le bus : ils ne
        # meurent pas avec lui.
        tuer_les_processus(compte.pw_uid)
        if monte:
            subprocess.run(["/usr/bin/umount", socket_espace], capture_output=True)
            subprocess.run(["/usr/bin/setfacl", "-x", "u:%d" % compte.pw_uid,
                            socket_bureau], capture_output=True)
        if not deja:
            # Le portail des documents peut y avoir monté son système FUSE.
            subprocess.run(["/usr/bin/umount", "--lazy", os.path.join(canonique, "doc")],
                           capture_output=True)
            shutil.rmtree(canonique, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", default=APP_DEFAUT,
                    help="application Flatpak cobaye (défaut : %s)" % APP_DEFAUT)
    ap.add_argument("--garder", action="store_true",
                    help="ne pas supprimer le compte d'essai à la fin")
    ap.add_argument("--portails", action="store_true",
                    help="mesurer seulement les portails (rien à télécharger)")
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
         % (bureau.pw_name, uid_bureau, affichage), aussi_si_oui=True)
    if not shutil.which("flatpak"):
        dire("flatpak installé", False, "paquet « flatpak » absent")
        consequence("rien à mesurer ; installez flatpak sur cette machine.")
        return 1
    version = subprocess.run(["flatpak", "--version"], capture_output=True,
                             text=True).stdout.strip()
    dire("flatpak installé", True, version, aussi_si_oui=True)

    compte, home, cree = creer_compte(uid_bureau)
    dire("compte d'essai", True, "%s (UID %d)%s"
         % (compte.pw_name, compte.pw_uid,
            "" if cree else " — déjà présent, dossier refait"),
         aussi_si_oui=True)
    flatpak_dir = os.path.join(home, "flatpak")
    runtime_espace = "/run/codebyr/essai-runtime-%d" % compte.pw_uid
    code = 0

    try:
        # ── 1. Ce dont le bac à sable de Flatpak a besoin ──────────────────
        if args.portails:
            code = mesurer_portails(compte, home, affichage, runtime_bureau)
            titre("Ce qu'il faut retenir")
            print("  Les sections 1 à 6 sont acquises (voir les passages précédents) ;")
            print("  seule la 7 a été rejouée.")
            return code

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

            # c) Ce qui manque : le bus de session, donc les portails.
            # Le test doit chercher SANS-BUS d'abord : « BUS in "SANS-BUS" »
            # est vrai, et la première version de cet outil a donc affiché OUI
            # sur une mesure qui disait exactement l'inverse.
            r = sous(compte, ["/usr/bin/flatpak", "run", "--die-with-parent",
                              "--command=/bin/sh", args.app, "-c",
                              "test -S $XDG_RUNTIME_DIR/bus && echo AVEC-BUS || echo SANS-BUS"],
                     env=env_run, delai=60)
            sortie = (r.stdout or "").strip()
            dire("l'application voit un bus de session",
                 "AVEC-BUS" in sortie, sortie or derniere_erreur(r))
            consequence("sans bus : pas de portails — ouvrir/enregistrer un "
                        "fichier, imprimer, ouvrir un lien.")

            # ── 5. La pièce à construire : un bus privé pour l'Espace ──────
            titre("5. Un bus de session PRIVÉ, sous le compte de l'Espace")
            print("  Le bus du bureau n'entrera jamais dans un Espace (règle")
            print("  absolue du bac à sable). Reste à savoir si un bus à lui")
            print("  suffit à Flatpak, et si les portails savent y vivre.")

            bus = None
            adresse = ""
            if not shutil.which("dbus-daemon"):
                dire("dbus-daemon disponible", False, "paquet « dbus-bin » absent")
            else:
                chemin_bus = os.path.join(runtime_espace, "bus")
                adresse = "unix:path=" + chemin_bus
                bus = subprocess.Popen(
                    ["/usr/bin/setpriv", "--reuid", str(compte.pw_uid),
                     "--regid", str(compte.pw_gid), "--clear-groups",
                     "--no-new-privs", "/usr/bin/dbus-daemon", "--session",
                     "--nofork", "--address", adresse],
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                attente = 0.0
                while attente < 5.0 and not os.path.exists(chemin_bus):
                    time.sleep(0.1)
                    attente += 0.1
                dire("un bus privé démarre sous ce compte",
                     os.path.exists(chemin_bus), chemin_bus)

            if bus and os.path.exists(os.path.join(runtime_espace, "bus")):
                env_bus = dict(env_run)
                env_bus["DBUS_SESSION_BUS_ADDRESS"] = adresse

                r = sous(compte, ["/usr/bin/dbus-send", "--session",
                                  "--print-reply", "--dest=org.freedesktop.DBus",
                                  "/org/freedesktop/DBus",
                                  "org.freedesktop.DBus.ListNames"],
                         env=env_bus, delai=30)
                dire("le compte parle à son bus", r.returncode == 0,
                     derniere_erreur(r))

                r = sous(compte, ["/usr/bin/flatpak", "run", "--die-with-parent",
                                  "--command=/bin/sh", args.app, "-c",
                                  "test -S $XDG_RUNTIME_DIR/bus && echo AVEC-BUS || echo SANS-BUS"],
                         env=env_bus, delai=60)
                sortie = (r.stdout or "").strip()
                vu = dire("l'application le voit à son tour",
                          "AVEC-BUS" in sortie, sortie or derniere_erreur(r))
                if vu:
                    consequence("un bus par Espace suffit à Flatpak : c'est la "
                                "pièce à poser.")
                else:
                    # « Failed to sync with dbus proxy » ne dit pas POURQUOI :
                    # Flatpak interpose xdg-dbus-proxy entre l'application et
                    # le bus, et ne rapporte que l'échec de la poignée de main.
                    # Les lignes qui précèdent, elles, nomment la cause.
                    for ligne in [l.strip() for l in (r.stderr or "").splitlines()
                                  if l.strip()][-6:]:
                        print("         %s" % ligne[:92])

                    # Le proxy, lancé à la main : s'il démarre seul, l'échec
                    # est dans la synchronisation ; s'il refuse, il le dit.
                    proxy = shutil.which("xdg-dbus-proxy")
                    if not proxy:
                        dire("xdg-dbus-proxy installé", False, "introuvable")
                    else:
                        chemin_proxy = os.path.join(runtime_espace, "proxy-essai")
                        pp = subprocess.Popen(
                            ["/usr/bin/setpriv", "--reuid", str(compte.pw_uid),
                             "--regid", str(compte.pw_gid), "--clear-groups",
                             "--no-new-privs", proxy, adresse, chemin_proxy,
                             "--filter", "--talk=org.freedesktop.portal.*"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            text=True)
                        attente = 0.0
                        while attente < 5.0 and not os.path.exists(chemin_proxy):
                            time.sleep(0.1)
                            attente += 0.1
                        debout = os.path.exists(chemin_proxy)
                        erreur = ""
                        if not debout:
                            pp.terminate()
                            try:
                                _, erreur = pp.communicate(timeout=5)
                            except subprocess.TimeoutExpired:
                                pp.kill()
                            erreur = (erreur or "").strip().splitlines()
                            erreur = erreur[-1][:92] if erreur else "aucun message"
                        dire("le proxy dbus démarre seul sous ce compte", debout,
                             erreur)
                        if debout:
                            consequence("le proxy tient : l'échec est dans la "
                                        "poignée de main avec Flatpak.")
                            pp.terminate()
                            try:
                                pp.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                pp.kill()
                        else:
                            consequence("le proxy lui-même refuse : c'est là "
                                        "qu'il faut chercher.")

                # Les portails : c'est par eux que passe « ouvrir un fichier ».
                # Debian les a déplacés de /usr/lib vers /usr/libexec ; on
                # cherche aux deux endroits plutôt que de parier.
                portail = next(
                    (c for c in ("/usr/libexec/xdg-desktop-portal",
                                 "/usr/lib/xdg-desktop-portal",
                                 "/usr/lib/x86_64-linux-gnu/xdg-desktop-portal")
                     if os.path.exists(c)), None)
                if not portail:
                    dire("xdg-desktop-portal installé", False,
                         "ni /usr/libexec ni /usr/lib")
                    consequence("sans lui, aucune application Flatpak ne sait "
                                "ouvrir un fichier — même sous votre compte.")
                else:
                    p = subprocess.Popen(
                        ["/usr/bin/setpriv", "--reuid", str(compte.pw_uid),
                         "--regid", str(compte.pw_gid), "--clear-groups",
                         "--no-new-privs", "/usr/bin/env", "-i",
                         "HOME=" + home, "PATH=/usr/bin:/bin",
                         "XDG_RUNTIME_DIR=" + runtime_espace,
                         "DBUS_SESSION_BUS_ADDRESS=" + adresse,
                         "XDG_CURRENT_DESKTOP=GNOME", portail],
                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                    time.sleep(3)
                    r = sous(compte, ["/usr/bin/dbus-send", "--session",
                                      "--print-reply",
                                      "--dest=org.freedesktop.portal.Desktop",
                                      "/org/freedesktop/portal/desktop",
                                      "org.freedesktop.DBus.Peer.Ping"],
                             env=env_bus, delai=30)
                    ok = dire("le portail répond sur ce bus", r.returncode == 0,
                              derniere_erreur(r))
                    if not ok:
                        consequence("les portails demanderont plus qu'un bus : "
                                    "lire l'erreur, c'est le prochain pas.")
                    p.terminate()
                    try:
                        p.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        p.kill()

            if bus:
                bus.terminate()
                try:
                    bus.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    bus.kill()

            # ── 6. Le dossier d'exécution à sa place canonique ─────────────
            titre("6. Et si le dossier d'exécution était à sa place ?")
            print("  bwrap a refusé de créer « .dbus-proxy » sous un chemin")
            print("  exotique. Flatpak suppose /run/user/<uid>, là où logind")
            print("  l'aurait mis. Même essai, à cette place-là.")

            canonique = "/run/user/%d" % compte.pw_uid
            deja = os.path.isdir(canonique)
            bus2 = None
            socket2 = os.path.join(canonique, affichage)
            monte2 = False
            try:
                os.makedirs(canonique, exist_ok=True)
                os.chown(canonique, compte.pw_uid, compte.pw_gid)
                os.chmod(canonique, 0o700)
                dire("préparer %s" % canonique, True,
                     "déjà présent" if deja else "créé", aussi_si_oui=True)

                if os.path.exists(socket_bureau):
                    open(socket2, "a").close()
                    m2 = subprocess.run(["/usr/bin/mount", "--bind",
                                         socket_bureau, socket2],
                                        capture_output=True, text=True)
                    monte2 = m2.returncode == 0
                    if monte2:
                        subprocess.run(["/usr/bin/setfacl", "-m",
                                        "u:%d:rw" % compte.pw_uid, socket_bureau],
                                       capture_output=True)

                chemin_bus2 = os.path.join(canonique, "bus")
                adresse2 = "unix:path=" + chemin_bus2
                bus2 = subprocess.Popen(
                    ["/usr/bin/setpriv", "--reuid", str(compte.pw_uid),
                     "--regid", str(compte.pw_gid), "--clear-groups",
                     "--no-new-privs", "/usr/bin/dbus-daemon", "--session",
                     "--nofork", "--address", adresse2],
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                attente = 0.0
                while attente < 5.0 and not os.path.exists(chemin_bus2):
                    time.sleep(0.1)
                    attente += 0.1

                env2 = {"FLATPAK_USER_DIR": flatpak_dir,
                        "XDG_RUNTIME_DIR": canonique,
                        "WAYLAND_DISPLAY": affichage,
                        "GDK_BACKEND": "wayland",
                        "XDG_SESSION_TYPE": "wayland",
                        "DBUS_SESSION_BUS_ADDRESS": adresse2}
                r = sous(compte, ["/usr/bin/flatpak", "run", "--die-with-parent",
                                  "--command=/bin/sh", args.app, "-c",
                                  "test -S $XDG_RUNTIME_DIR/bus && echo AVEC-BUS || echo SANS-BUS"],
                         env=env2, delai=60)
                sortie = (r.stdout or "").strip()
                ok2 = dire("l'application voit son bus, à cette place",
                           "AVEC-BUS" in sortie, sortie or derniere_erreur(r))
                if ok2:
                    consequence("c'était le chemin : le dossier d'exécution d'un "
                                "Espace doit être /run/user/<uid de l'Espace>.")
                else:
                    for ligne in [l.strip() for l in (r.stderr or "").splitlines()
                                  if l.strip()][-6:]:
                        print("         %s" % ligne[:92])
                    consequence("le chemin n'était pas la cause : chercher ailleurs.")
            finally:
                if bus2:
                    bus2.terminate()
                    try:
                        bus2.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        bus2.kill()
                if monte2:
                    subprocess.run(["/usr/bin/umount", socket2], capture_output=True)
                # Créé par nous : c'est à nous de le retirer. S'il était déjà
                # là, il appartient au système et on n'y touche pas.
                if not deja:
                    shutil.rmtree(canonique, ignore_errors=True)

            if monte:
                subprocess.run(["/usr/bin/umount", socket_espace], capture_output=True)
                subprocess.run(["/usr/bin/setfacl", "-x", "u:%d" % compte.pw_uid,
                                socket_bureau], capture_output=True)

        if mesurer_portails(compte, home, affichage, runtime_bureau):
            code = 1

        titre("Ce qu'il faut retenir")
        print("  Chaque NON ci-dessus est une pièce à écrire. Les OUI disent ce")
        print("  sur quoi on peut déjà s'appuyer.")
        if installee and tourne:
            print("\n  Le dossier d'exécution posé dans /run a suffi : Flatpak")
            print("  n'y exécute rien, le « noexec » de Debian ne gêne donc pas.")
    finally:
        # Un montage lié survit à l'outil et fausse l'essai suivant : on le
        # défait quoi qu'il arrive, y compris si une erreur a court-circuité
        # le nettoyage plus haut. « umount » sur ce qui n'est pas monté est
        # sans effet, et c'est ce qu'on veut.
        socket_reste = os.path.join(runtime_espace, affichage)
        if os.path.exists(socket_reste):
            subprocess.run(["/usr/bin/umount", socket_reste], capture_output=True)
        subprocess.run(["/usr/bin/setfacl", "-x", "u:%d" % compte.pw_uid,
                        os.path.join(runtime_bureau, affichage)],
                       capture_output=True)
        shutil.rmtree(runtime_espace, ignore_errors=True)
        if args.garder:
            print("\nCompte d'essai conservé : %s (%s)" % (compte.pw_name, home))
        elif supprimer_compte(compte, home):
            print("\nCompte d'essai supprimé.")
    return code


if __name__ == "__main__":
    sys.exit(main())
