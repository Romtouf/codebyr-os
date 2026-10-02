# -*- coding: utf-8 -*-
"""Banc d'essai du service root codebyr-uid : son COMPORTEMENT, pas son texte.

Lancé par tests/test_uid_comportement.py, en root, dans un espace de montage
privé (« unshare --mount ») :

    python3 uid_harnais.py <scénario> <dossier temporaire>

Le vrai service est chargé, et il fait pour de vrai ce qu'il fait sur une
machine : useradd, mount, umount, setfacl, setpriv. Ce qu'il touche est
tenu hors de la machine qui fait le test : une copie de /etc montée
par-dessus l'originale, et des tmpfs sur /run, /var/lib et /var/log. Seule
la portée systemd est simulée (« systemd-run --scope » et « systemctl stop »),
parce qu'un conteneur n'a pas de systemd : la commande qu'elle enveloppe est
exécutée telle quelle, et ses plafonds sont notés.

Le premier processus de l'Espace est remplacé par un témoin, qui dit
« j'écoute » comme le vrai — ou meurt avant, ou lance une « application »,
selon le scénario.

Sortie : un objet JSON sur la dernière ligne.
"""
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import pwd
import signal
import socket
import subprocess
import sys
import time
import types

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVRE = os.path.join(RACINE, "live-build", "config", "includes.chroot_after_packages")
# Une autre version du service peut être éprouvée (« CODEBYR_BANC_SERVICE ») :
# c'est ainsi qu'on vérifie que le banc voit un défaut qu'on a corrigé.
SERVICE = os.environ.get("CODEBYR_BANC_SERVICE") or os.path.join(
    LIVRE, "usr", "lib", "codebyr", "codebyr-uid")
LIB = os.path.join(LIVRE, "usr", "share", "codebyr")
BANC = "/run/codebyr-banc"
INIT = BANC + "/init"
SECRET = "/etc/codebyr-banc-secret"
BUREAU = "codebyr-banc-bureau"
ESPACE = "banc"

TEMOIN = """#!/usr/bin/python3
import os, subprocess, sys, threading, time
ecriture = int(sys.argv[3])
if os.path.exists("%(banc)s/init-muet"):
    sys.exit(3)                     # meurt avant d'écouter
if os.path.exists("%(banc)s/avec-application"):
    # Comme le vrai premier processus : il attend ses applications, et ne
    # laisse donc pas de zombie derrière une application fermée.
    enfant = subprocess.Popen(["/usr/bin/sleep", "600"])
    threading.Thread(target=enfant.wait, daemon=True).start()
os.write(ecriture, b"1")
os.close(ecriture)
while True:
    time.sleep(60)
""" % {"banc": BANC}


def sh(*argv):
    subprocess.run(argv, check=True, capture_output=True)


# ── Le monde : une machine à part, dans l'espace de montage du banc ─────────
def preparer_le_monde(temporaire):
    sh("mount", "--make-rprivate", "/")
    sh("cp", "-a", "/etc", os.path.join(temporaire, "etc"))
    sh("mount", "--bind", os.path.join(temporaire, "etc"), "/etc")
    for dossier in ("/run", "/var/lib", "/var/log"):
        sh("mount", "-t", "tmpfs", "-o", "mode=0755", "tmpfs", dossier)
    os.makedirs("/run/user", mode=0o755)
    os.makedirs(BANC, mode=0o755)
    with open(INIT, "w", encoding="utf-8") as f:
        f.write(TEMOIN)
    os.chmod(INIT, 0o755)

    sh("/usr/sbin/useradd", "--user-group", "--no-create-home",
       "--shell", "/usr/sbin/nologin", BUREAU)
    bureau = pwd.getpwnam(BUREAU)
    runtime = "/run/user/%d" % bureau.pw_uid
    os.makedirs(runtime, mode=0o700)
    if os.environ.get("CODEBYR_BANC_RUN") != "un-seul":
        # Comme logind : le dossier d'exécution d'un utilisateur est un tmpfs
        # à lui. Variante « un-seul » : tout /run d'un tenant, où un montage
        # lié ne change pas de périphérique (voir codebyr-uid, monte()).
        sh("mount", "-t", "tmpfs", "-o", "mode=0700", "tmpfs", runtime)
    os.chown(runtime, bureau.pw_uid, bureau.pw_gid)
    # Le fichier que les liens piégés visent : rien ne doit l'atteindre.
    with open(SECRET, "w") as f:
        f.write("secret de root\n")
    os.chmod(SECRET, 0o600)
    sockets = []
    for nom in ("wayland-0", "pipewire-0"):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(os.path.join(runtime, nom))
        s.listen(1)
        os.chown(os.path.join(runtime, nom), bureau.pw_uid, bureau.pw_gid)
        sockets.append(s)
    return bureau, sockets


# ── Le service, chargé tel qu'il est livré ──────────────────────────────────
def charger_le_service():
    os.environ["CODEBYR_LIB"] = LIB
    os.environ["CODEBYR_INIT"] = INIT
    sys.argv = [SERVICE, "--essai", "/run/codebyr-uid-banc.sock"]
    chargeur = importlib.machinery.SourceFileLoader("codebyr_uid", SERVICE)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(chargeur.name, chargeur))
    chargeur.exec_module(module)

    vrai = subprocess
    faux = types.SimpleNamespace(**{k: getattr(vrai, k) for k in dir(vrai) if not k.startswith("__")})
    faux.portees = []

    def run(argv, *a, **kw):
        if argv and argv[0] == "/usr/bin/systemctl":
            # « systemctl stop codebyr-espace-<compte>.scope » : systemd
            # arrête tous les processus de la portée, c'est-à-dire de l'Espace.
            unite = argv[-1]
            if "stop" in argv and unite.startswith("codebyr-espace-") and unite.endswith(".scope"):
                try:
                    arreter_tout(pwd.getpwnam(unite[len("codebyr-espace-"):-len(".scope")]).pw_uid)
                except KeyError:
                    pass
            return vrai.CompletedProcess(argv, 0, b"", b"")
        return vrai.run(argv, *a, **kw)

    def Popen(argv, *a, **kw):
        if argv and argv[0] == "/usr/bin/systemd-run":
            faux.portees.append(argv[:argv.index("--")])
            argv = argv[argv.index("--") + 1:]
        return vrai.Popen(argv, *a, **kw)

    faux.run, faux.Popen = run, Popen
    module.subprocess = faux
    module.journaux = []
    module.journal = module.journaux.append
    module.racines()
    return module


# ── Ce qu'on observe ─────────────────────────────────────────────────────────
def montages_sous(*prefixes):
    vus = []
    with open("/proc/self/mountinfo", encoding="utf-8") as f:
        for ligne in f:
            point = ligne.split()[4].replace("\\040", " ")
            if any(point == p or point.startswith(p + "/") for p in prefixes):
                vus.append(point)
    return sorted(vus)


def acl_nominatives(chemin):
    """Les UID qui ont un droit nominatif sur ce fichier (sans suivre de lien)."""
    r = subprocess.run(["getfacl", "--numeric", "--omit-header", "--physical", chemin],
                       capture_output=True, text=True)
    uids = []
    for ligne in r.stdout.splitlines():
        parts = ligne.split(":")
        if len(parts) >= 3 and parts[0] == "user" and parts[1]:
            uids.append(int(parts[1]))
    return sorted(uids)


def processus_de(uid):
    pids = []
    for entree in os.listdir("/proc"):
        if entree.isdigit():
            try:
                if os.stat("/proc/" + entree).st_uid == uid:
                    pids.append(int(entree))
            except OSError:
                pass
    return pids


def empreinte(chemin):
    with open(chemin, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def etat(uid_mod, bureau):
    """Tout ce qu'une ouverture pose, et qu'une fermeture doit retirer."""
    comptes = uid_mod.comptes
    nom = comptes.nom_compte(bureau.pw_uid, ESPACE)
    try:
        espace = pwd.getpwnam(nom)
    except KeyError:
        return {"compte": False}
    runtime = comptes.chemin_runtime(espace.pw_uid)
    depot = comptes.chemin_depot(nom)
    home = comptes.chemin_home(bureau.pw_uid, ESPACE)
    socket_bureau = "/run/user/%d/" % bureau.pw_uid
    st = os.lstat(home) if os.path.lexists(home) else None
    return {
        "compte": True,
        "uid_espace": espace.pw_uid,
        "systeme": espace.pw_uid < 1000,
        "home": {"mode": oct(st.st_mode & 0o7777), "a_l_espace": st.st_uid == espace.pw_uid,
                 "monte": os.path.ismount(home)} if st else None,
        "runtime": os.path.isdir(runtime),
        # « /etc » lui-même est la copie du banc ; ce qui serait monté
        # DESSOUS viendrait d'un lien suivi.
        "montages": montages_sous(runtime, comptes.RACINE_DEPOTS, home)
                    + [m for m in montages_sous("/etc") if m != "/etc"],
        "droits_wayland": acl_nominatives(socket_bureau + "wayland-0"),
        "droits_pipewire": acl_nominatives(socket_bureau + "pipewire-0"),
        "depot": os.path.isdir(depot),
        "ordres": os.path.exists(os.path.join(depot, comptes.SOCKET_EXEC)),
        "processus": len(processus_de(espace.pw_uid)),
        "ouverts": sorted(uid_mod.OUVERTS),
    }


def arreter_tout(uid):
    for pid in processus_de(uid):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def essayer(fonction, *args, **kw):
    try:
        return {"reponse": fonction(*args, **kw)}
    except Exception as exc:
        return {"exception": type(exc).__name__, "message": str(exc)}


# ── Les scénarios ────────────────────────────────────────────────────────────
def cycle(u, bureau):
    """Ouvrir puis fermer : tout ce qui est posé doit repartir."""
    ouvert = essayer(u.preparer, bureau.pw_uid, ESPACE, "wayland-0", True)
    pendant = etat(u, bureau)
    ferme = essayer(u.fermer, bureau.pw_uid, ESPACE)
    time.sleep(0.3)
    return {"ouvert": ouvert, "pendant": pendant, "ferme": ferme, "apres": etat(u, bureau),
            "portees": [[str(x) for x in p] for p in u.subprocess.portees]}


def jetable(u, bureau):
    """Un Espace jetable : son dossier en mémoire, et son contenu qui disparaît."""
    ouvert = essayer(u.preparer, bureau.pw_uid, ESPACE, "wayland-0", False, ephemere=True)
    home = u.comptes.chemin_home(bureau.pw_uid, ESPACE)
    with open(os.path.join(home, "secret"), "w") as f:
        f.write("x")
    pendant = etat(u, bureau)
    essayer(u.fermer, bureau.pw_uid, ESPACE)
    return {"ouvert": ouvert, "pendant": pendant, "apres": etat(u, bureau),
            "secret_reste": os.path.exists(os.path.join(home, "secret"))}


def echec(u, bureau):
    """Le premier processus meurt avant d'écouter, sockets et droits déjà posés."""
    open(BANC + "/init-muet", "w").close()
    return {"ouvert": essayer(u.preparer, bureau.pw_uid, ESPACE, "wayland-0", True),
            "apres": etat(u, bureau)}


def liens(u, bureau):
    """Trois liens piégés vers un secret de root ou /etc : aucun n'est suivi."""
    ombre = SECRET
    avant = {"shadow": empreinte(ombre), "droits_shadow": acl_nominatives(ombre),
             "etc": oct(os.stat("/etc").st_mode), "droits_etc": acl_nominatives("/etc")}
    sortie = {"avant": avant}

    # a) Dans le dossier d'exécution du BUREAU : « wayland-9 » → le secret,
    #    puis une demande avec cet affichage (l'élévation fermée en 1.16.2).
    os.symlink(ombre, "/run/user/%d/wayland-9" % bureau.pw_uid)
    sortie["bureau"] = {"ouvert": essayer(u.preparer, bureau.pw_uid, ESPACE, "wayland-9", False),
                        "apres": etat(u, bureau)}

    # b) Dans le dossier d'exécution de l'ESPACE, pendant qu'il est ouvert :
    #    « pipewire-0 » → le secret, puis une demande qui y présenterait le son.
    premiere = essayer(u.preparer, bureau.pw_uid, ESPACE, "wayland-0", False)
    espace = pwd.getpwnam(u.comptes.nom_compte(bureau.pw_uid, ESPACE))
    piege = os.path.join(u.comptes.chemin_runtime(espace.pw_uid), "pipewire-0")
    os.symlink(ombre, piege)
    os.lchown(piege, espace.pw_uid, espace.pw_gid)
    seconde = essayer(u.preparer, bureau.pw_uid, ESPACE, "wayland-0", True)
    pendant = etat(u, bureau)
    ferme = essayer(u.fermer, bureau.pw_uid, ESPACE)
    sortie["espace"] = {"premiere": premiere, "seconde": seconde, "pendant": pendant,
                        "ferme": ferme, "apres": etat(u, bureau)}

    # c) Le dépôt remplacé par un lien vers /etc.
    depot = u.comptes.chemin_depot(u.comptes.nom_compte(bureau.pw_uid, ESPACE))
    os.symlink("/etc", depot)
    sortie["depot"] = {"ouvert": essayer(u.preparer, bureau.pw_uid, ESPACE, "wayland-0", False),
                       "lien_intact": os.path.islink(depot) and os.readlink(depot) == "/etc"}
    os.unlink(depot)

    sortie["apres"] = {"shadow": empreinte(ombre), "shadow_monte": os.path.ismount(ombre),
                       "droits_shadow": acl_nominatives(ombre),
                       "etc": oct(os.stat("/etc").st_mode), "droits_etc": acl_nominatives("/etc")}
    return sortie


def abandon(u, bureau):
    """Le service redémarre pendant qu'un Espace est ouvert, puis range."""
    sortie = {}
    # a) Plus aucune application : l'Espace abandonné est refermé.
    essayer(u.preparer, bureau.pw_uid, ESPACE, "wayland-0", True)
    uid_espace = etat(u, bureau)["uid_espace"]
    u.OUVERTS.clear()               # le service a tout oublié
    sortie["sans_application"] = {"avant": etat(u, bureau),
                                  "rangement": essayer(u.fermer_les_espaces_abandonnes),
                                  "apres": etat(u, bureau)}
    arreter_tout(uid_espace)
    time.sleep(0.3)

    # b) Une application vit encore : on ne ferme pas sous les yeux de
    #    l'utilisateur ; dès qu'elle se ferme, le rangement se fait.
    open(BANC + "/avec-application", "w").close()
    essayer(u.preparer, bureau.pw_uid, ESPACE, "wayland-0", True)
    time.sleep(0.5)
    u.OUVERTS.clear()
    essayer(u.fermer_les_espaces_abandonnes)
    garde = etat(u, bureau)
    applications = u._applications_de(uid_espace)
    for pid in applications:
        os.kill(pid, signal.SIGKILL)
    time.sleep(0.5)
    essayer(u.fermer_les_espaces_abandonnes)
    sortie["avec_application"] = {"applications": len(applications), "garde": garde,
                                  "apres": etat(u, bureau)}
    return sortie


SCENARIOS = {"cycle": cycle, "jetable": jetable, "echec": echec, "liens": liens,
             "abandon": abandon}


def main():
    scenario, temporaire = sys.argv[1], sys.argv[2]
    bureau, _sockets = preparer_le_monde(temporaire)
    u = charger_le_service()
    try:
        resultat = SCENARIOS[scenario](u, bureau)
        resultat["journal"] = u.journaux
    finally:
        try:
            nom = u.comptes.nom_compte(bureau.pw_uid, ESPACE)
            arreter_tout(pwd.getpwnam(nom).pw_uid)
        except (KeyError, ValueError):
            pass
    print(json.dumps(resultat))


if __name__ == "__main__":
    main()
