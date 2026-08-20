# -*- coding: utf-8 -*-
"""Le bac à sable des Espaces — construction, capacités, vérification.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Sorti de `codebyr-space`, qui approchait les 1 200 lignes. C'est le bloc le
plus cohérent du programme — et le plus sensible : c'est lui qui décide de ce
qu'un Espace peut atteindre. Le sortir le rend lisible d'un seul tenant, et
laisse dans la commande ce qui relève du cycle de vie des Espaces.
"""
import os
import shutil
import subprocess
import sys
import tempfile


def wrap_bwrap(home, cmd, env, renforce=False, hors_ligne=False, audio=True):
    """Enveloppe avec bubblewrap : dossier personnel isolé, /tmp isolé,
    affichage (et éventuellement son) partagés. Repli géré par l'appelant si
    bwrap échoue.

    renforce   : Blindage — isolation utilisateur, abandon des privilèges,
                 nouvelle session (anti-injection terminal).
    hors_ligne : coupe tout accès réseau (namespace réseau isolé). Idéal pour
                 examiner une pièce jointe douteuse : le piège explose sans
                 jamais pouvoir téléphoner dehors.
    audio      : donne accès au serveur de son PipeWire. À couper pour les
                 Espaces sensibles : ce socket, c'est aussi le MICRO.

    RÈGLE ABSOLUE — le bus de session de l'hôte n'entre JAMAIS ici.
    Un « --ro-bind » ne protège pas un socket : le noyau ne refuse l'écriture
    sur un montage en lecture seule que pour les fichiers, répertoires et liens
    (sb_permission()), jamais pour les sockets. Exposer $XDG_RUNTIME_DIR/bus
    revenait donc à offrir le bus de session complet à l'Espace — et avec lui
    systemd --user, dont StartTransientUnit exécute n'importe quoi HORS du bac
    à sable, sous l'identité de l'utilisateur. L'Espace lisait alors les
    données de tous les autres. C'est pour cette même raison que Flatpak
    n'expose jamais le bus en direct (il passe par xdg-dbus-proxy).

    Les applications ne perdent rien : dbus-run-session (voir cmd_launch) leur
    donne déjà un bus de session PRIVÉ, et c'est celui-là qu'elles utilisent.
    """
    # « or » et non env.get(défaut) : le défaut ne doit être calculé que s'il
    # sert (os.getuid n'existe pas partout où l'on teste ce code).
    runtime = env.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid()
    bwrap = [
        "bwrap",
        "--ro-bind", "/usr", "/usr",
        "--ro-bind", "/etc", "/etc",
        "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/lib64", "/lib64",
        "--symlink", "usr/bin", "/bin",
        "--symlink", "usr/sbin", "/sbin",
        "--proc", "/proc",
        "--dev", "/dev",
        "--dev-bind-try", "/dev/dri", "/dev/dri",
        "--tmpfs", "/tmp",
        "--bind", home, os.path.expanduser("~"),
        "--ro-bind-try", runtime + "/wayland-0", runtime + "/wayland-0",
        "--ro-bind-try", "/sys/dev/char", "/sys/dev/char",
        "--ro-bind-try", "/sys/devices", "/sys/devices",
        "--unshare-pid", "--unshare-uts", "--unshare-ipc",
        "--die-with-parent",
        "--setenv", "HOME", os.path.expanduser("~"),
        # Le chemin du bus de l'hôte hérité de l'environnement ne mène plus à
        # rien dans le bac à sable : on le retire pour éviter toute confusion
        # (dbus-run-session posera la bonne valeur juste après).
        "--unsetenv", "DBUS_SESSION_BUS_ADDRESS",
    ]
    if audio and not hors_ligne:
        bwrap += ["--ro-bind-try", runtime + "/pipewire-0", runtime + "/pipewire-0"]
    if hors_ligne:
        # Aucune interface réseau : exfiltration impossible.
        bwrap += ["--unshare-net"]
    if renforce:
        # Blindage : bac à sable utilisateur, zéro privilège, session neuve.
        bwrap += ["--unshare-user-try", "--unshare-cgroup-try",
                  "--new-session", "--cap-drop", "ALL"]
    return bwrap + ["--"] + cmd


_SCOPE_DISPO = None


def systemd_scope_dispo():
    """systemd-run --scope utilisable ? (plafonds mémoire/processus par Espace).
    Testé une seule fois puis mis en cache."""
    global _SCOPE_DISPO
    if _SCOPE_DISPO is None:
        _SCOPE_DISPO = False
        if shutil.which("systemd-run"):
            try:
                r = subprocess.run(
                    ["systemd-run", "--user", "--scope", "--quiet", "--", "true"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=6)
                _SCOPE_DISPO = (r.returncode == 0)
            except Exception:
                _SCOPE_DISPO = False
    return _SCOPE_DISPO


def plafonner_ressources(run):
    """Enveloppe la commande dans un cgroup borné : un Espace compromis ne peut
    pas épuiser la mémoire de la machine ni la saturer de processus (fork-bomb)."""
    if systemd_scope_dispo():
        return ["systemd-run", "--user", "--scope", "--quiet",
                "-p", "MemoryMax=2G", "-p", "MemorySwapMax=0",
                "-p", "TasksMax=800", "--"] + run
    return run


def user_ns_dispo():
    """Espaces de noms utilisateur non privilégiés autorisés par le noyau ?"""
    try:
        with open("/proc/sys/kernel/unprivileged_userns_clone") as f:
            return f.read().strip() == "1"
    except OSError:
        # Fichier absent = souvent activé par défaut (Debian récent).
        return True



def cmd_isolation():
    """Rapporte, en clair, le niveau d'isolation réellement disponible ici."""
    def oui_non(v):
        return "\033[32moui\033[0m" if v else "\033[31mnon\033[0m"

    bwrap = bool(shutil.which("bwrap"))
    print("Capacités d'isolation de cette machine :")
    print("  Bac à sable bubblewrap ....... %s" % oui_non(bwrap))
    print("  Isolation utilisateur (user-ns) %s" % oui_non(user_ns_dispo()))
    print("  Coupure réseau par Espace .... %s" % oui_non(bwrap))
    print("  Plafonds mémoire / processus . %s" % oui_non(systemd_scope_dispo()))
    print("  Bus de session privé ......... %s" % oui_non(bool(shutil.which("dbus-run-session"))))
    print()
    if bwrap:
        print("Niveau : Blindage disponible (bac à sable + coupure réseau).")
    else:
        print("Niveau : réduit (dossiers séparés seulement).")
    return 0


# ── Vérification de l'isolation, sur pièces ────────────────────────────────
# « codebyr-space isolation » dit ce que la MACHINE sait faire. La commande
# ci-dessous dit ce qu'un Espace peut réellement ATTEINDRE : elle lance une
# sonde à l'intérieur d'un vrai bac à sable et rapporte ce qu'elle y trouve.
# C'est la version reproductible des vérifications qu'il fallait sinon faire à
# la main dans une machine virtuelle, et que personne ne refait jamais.

SONDE = r"""
import os, socket, sys

def joignable(chemin):
    # Un socket peut exister sans être joignable : on tente la connexion.
    if not chemin or not os.path.exists(chemin):
        return False
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(chemin)
        return True
    except OSError:
        return False
    finally:
        s.close()

runtime = os.environ.get("XDG_RUNTIME_DIR", "")
mesures = {
    "bus_hote": joignable(os.path.join(runtime, "bus")) if runtime else False,
    "systemd_user": joignable(os.path.join(runtime, "systemd", "private")) if runtime else False,
    "bus_systeme": joignable("/run/dbus/system_bus_socket"),
    "x11": os.path.isdir("/tmp/.X11-unix"),
    "son": os.path.exists(os.path.join(runtime, "pipewire-0")) if runtime else False,
}
try:
    with open("/proc/net/dev", encoding="utf-8") as f:
        interfaces = [l.split(":")[0].strip() for l in f if ":" in l]
    mesures["reseau"] = any(i and i != "lo" for i in interfaces)
except OSError:
    mesures["reseau"] = False
try:
    with open(os.path.expanduser("~/.codebyr-sonde"), encoding="utf-8") as f:
        mesures["home_isole"] = f.read().strip() == sys.argv[1]
except OSError:
    mesures["home_isole"] = False
for cle, valeur in mesures.items():
    print("%s=%s" % (cle, "oui" if valeur else "non"))
"""

CONTROLES = (
    ("bus_hote", "Bus de session de l'hôte joignable"),
    ("systemd_user", "systemd --user joignable"),
    ("bus_systeme", "Bus système joignable"),
    ("x11", "Socket X11 de l'hôte visible"),
    ("son", "Son et micro (PipeWire)"),
    ("reseau", "Accès au réseau"),
    ("home_isole", "Dossier personnel bien isolé"),
)

# Ce qu'on attend selon la situation. Les trois premières lignes doivent être
# fausses PARTOUT : ce sont les portes de sortie du bac à sable.
SITUATIONS = (
    ("Espace ordinaire", {},
     {"bus_hote": False, "systemd_user": False, "bus_systeme": False, "x11": False,
      "son": True, "reseau": True, "home_isole": True}),
    ("Espace blindé, sans micro (Banque)", {"renforce": True, "audio": False},
     {"bus_hote": False, "systemd_user": False, "bus_systeme": False, "x11": False,
      "son": False, "reseau": True, "home_isole": True}),
    ("Pièce jointe en Jetable", {"renforce": True, "hors_ligne": True},
     {"bus_hote": False, "systemd_user": False, "bus_systeme": False, "x11": False,
      "son": False, "reseau": False, "home_isole": True}),
)


def analyser_sonde(sortie):
    """Transforme la sortie brute de la sonde en mesures booléennes."""
    mesures = {}
    for ligne in (sortie or "").splitlines():
        if "=" in ligne:
            cle, valeur = ligne.split("=", 1)
            mesures[cle.strip()] = valeur.strip() == "oui"
    return mesures


def evaluer(mesures, attendu):
    """Confronte les mesures aux attentes. Renvoie [(libellé, mesure, ok)]."""
    resultat = []
    for cle, libelle in CONTROLES:
        if cle not in mesures:
            resultat.append((libelle, None, False))
            continue
        resultat.append((libelle, mesures[cle], mesures[cle] == attendu[cle]))
    return resultat


def sonder(options):
    """Lance la sonde dans un vrai bac à sable et renvoie ses mesures."""
    home = tempfile.mkdtemp(prefix="codebyr-sonde-")
    jeton = os.urandom(8).hex()
    try:
        with open(os.path.join(home, ".codebyr-sonde"), "w", encoding="utf-8") as f:
            f.write(jeton)
        env = dict(os.environ)
        cmd = [sys.executable or "python3", "-c", SONDE, jeton]
        try:
            r = subprocess.run(wrap_bwrap(home, cmd, env, **options),
                               capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            sys.stderr.write("codebyr-space : sonde impossible (%s)\n" % exc)
            return {}
        return analyser_sonde(r.stdout)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def cmd_verifier_isolation():
    """Vérifie sur pièces ce qu'un Espace peut réellement atteindre."""
    if not shutil.which("bwrap"):
        sys.stderr.write("bubblewrap absent : aucun bac à sable à vérifier.\n")
        return 2
    print("Vérification de l'isolation — une sonde est lancée dans un vrai "
          "bac à sable.\n")
    tout_va_bien = True
    for titre, options, attendu in SITUATIONS:
        mesures = sonder(options)
        print("\033[1m%s\033[0m" % titre)
        if not mesures:
            print("  \033[31mLa sonde n'a rien renvoyé.\033[0m\n")
            tout_va_bien = False
            continue
        for libelle, mesure, ok in evaluer(mesures, attendu):
            etat = "\033[32m✔\033[0m" if ok else "\033[31m✘\033[0m"
            valeur = "?" if mesure is None else ("oui" if mesure else "non")
            print("  %s %-36s %s" % (etat, libelle, valeur))
            tout_va_bien = tout_va_bien and ok
        print()
    if tout_va_bien:
        print("\033[32mTout est conforme.\033[0m Aucune sortie de bac à sable "
              "détectée.")
        return 0
    print("\033[31mAu moins un contrôle a échoué.\033[0m Ne publiez pas cette "
          "version : signalez-le (voir SECURITY.md).")
    return 1
