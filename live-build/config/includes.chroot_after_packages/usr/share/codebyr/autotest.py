# -*- coding: utf-8 -*-
"""Autotest du poste — vérifier que ce qui est livré fonctionne vraiment.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Pourquoi cet outil existe, très concrètement. Le 20/08/2026, le clic droit
« Ouvrir en Jetable » a été livré, testé par 124 tests automatiques, empaqueté,
et son contenu vérifié dans l'image. Il ne fonctionnait pas : le greffon qui
charge l'extension n'était qu'une *recommandation*, donc absent, et Fichiers
n'affichait rien — sans le moindre message d'erreur. Le menu contextuel avait
l'air parfaitement normal.

Aucun test du dépôt ne pouvait le voir : ils s'exécutent sur une machine de
développement, pas sur un poste installé. Il a fallu qu'une personne fasse le
geste sur une vraie machine.

C'est le mode d'échec caractéristique de ce projet : **pas « le code est faux »,
mais « tout a l'air correct »**. Un poste dont le compte invité a repris un mot
de passe, dont le trousseau ignore la clé qui signe les mises à jour, ou dont
les dossiers personnels sont redevenus lisibles, ne s'en plaint jamais. Il se
tait, exactement comme un poste sain.

D'où ce module : il MESURE, sur la machine, ce que l'on croit livré. Chaque
contrôle correspond à un défaut qui est réellement survenu ici — aucun n'est
hypothétique.

Même principe que `verifier-isolation` : on ne demande pas au système s'il va
bien, on l'observe. La partie qui décide est pure et testable ; seule la
collecte touche au disque.
"""
import os
import shutil
import subprocess

# — Ce que l'on contrôle, et l'incident qui l'a rendu nécessaire —
TROUSSEAU = "/usr/share/keyrings/codebyr-archive-keyring.gpg"
EXTENSION_JETABLE = "/usr/share/nautilus-python/extensions/codebyr-jetable.py"
PERIODIQUE = "/etc/apt/apt.conf.d/20auto-upgrades"
SHADOW = "/etc/shadow"
INVITE = "invite"

# Empreinte de la sous-clé qui signe le dépôt APT. Un trousseau qui l'ignore
# fait échouer « apt update » sur une signature pourtant légitime.
SOUS_CLE = "49DF7B8855830CCD347663345884F50B88581C19"

# Un mot de passe « utilisable » commence par un caractère de hachage. Les
# formes qui n'ouvrent AUCUNE authentification par mot de passe sont « * », « ! »
# et « !! » — le compte invité doit être dans ce cas : sa session graphique
# s'ouvre d'un clic, mais ni SSH ni « su » ne doivent y donner accès.
SANS_MOT_DE_PASSE = ("*", "!", "!!", "")


# ── Décisions pures — testables sans machine Codebyr ────────────────────────

def analyser_extension_jetable(fichier_present, greffon_present):
    """Le clic droit « Ouvrir en Jetable » est-il réellement chargeable ?

    Les deux conditions sont nécessaires et aucune n'est visible à l'usage :
    sans le greffon python3-nautilus, le fichier est là et n'est jamais lu.
    """
    if not fichier_present:
        return False, "l'extension n'est pas installée"
    if not greffon_present:
        return False, "python3-nautilus absent — l'extension n'est jamais chargée"
    return True, "extension présente et greffon installé"


def analyser_invite(champ_shadow):
    """Le compte invité doit refuser toute authentification par mot de passe.

    Il valait « invite » sur toutes les machines Codebyr jusqu'à la 1.1.0 :
    un mot de passe public donnait SSH, « su » et « sudo ».

    champ_shadow : le 2e champ de la ligne /etc/shadow, ou None si le compte
                   n'existe pas (ce qui n'est pas une anomalie).
    """
    if champ_shadow is None:
        return True, "pas de compte invité sur ce poste"
    if champ_shadow in SANS_MOT_DE_PASSE:
        return True, "aucun mot de passe ne fonctionne (session locale seule)"
    return False, "le compte invité a un mot de passe utilisable"


def analyser_homes(dossiers):
    """Les dossiers personnels doivent être privés (0700).

    La protection n'existait que sur le support live jusqu'à la 1.1.0 : sur une
    machine installée, le compte invité lisait les fichiers du propriétaire.

    dossiers : suite de (nom, mode_octal_bas_9_bits)
    """
    ouverts = [nom for nom, mode in dossiers if mode & 0o077]
    if ouverts:
        return False, "lisible(s) par d'autres comptes : " + ", ".join(sorted(ouverts))
    if not dossiers:
        return True, "aucun dossier personnel à vérifier"
    return True, "%d dossier(s) personnel(s), tous privés" % len(dossiers)


def analyser_trousseau(empreintes):
    """Le trousseau apt doit connaître la clé qui signe aujourd'hui.

    Il est gravé à l'installation. L'ajout d'une sous-clé de signature l'a rendu
    obsolète d'un coup sur tout le parc, le 20/08/2026 : apt refusait une
    signature parfaitement valide, faute de connaître la clé.
    """
    if not empreintes:
        return False, "trousseau illisible ou vide"
    if SOUS_CLE in empreintes:
        return True, "connaît la sous-clé de signature en cours"
    return False, ("ignore la sous-clé %s… — les mises à jour vont cesser"
                   % SOUS_CLE[:16])


def analyser_maj_automatiques(contenu, minuterie_active):
    """Les mises à jour doivent arriver sans que personne ne tape de commande.

    C'est une promesse du projet, pas un confort. Deux pièces indépendantes :
    le réglage périodique d'apt, et la minuterie systemd qui le déclenche. L'une
    sans l'autre ne met rien à jour, et ne le dit pas.
    """
    texte = contenu or ""
    arme = '"1"' in "".join(
        ligne for ligne in texte.splitlines()
        if "Unattended-Upgrade" in ligne and not ligne.strip().startswith("//"))
    if not arme:
        return False, "APT::Periodic::Unattended-Upgrade n'est pas à \"1\""
    if not minuterie_active:
        return False, "réglage présent mais la minuterie apt-daily est inactive"
    return True, "réglage et minuterie en place"


def analyser_bac_a_sable(bwrap, userns, dbus_run_session):
    """Sans ces trois briques, un Espace n'isole rien — ou ne démarre pas.

    dbus-run-session est le moins évident : c'est lui qui fournit le bus privé
    qui REMPLACE le bus de session de l'hôte depuis la 1.1.0. Absent,
    l'application tourne sans aucun bus.
    """
    manques = []
    if not bwrap:
        manques.append("bubblewrap")
    if not userns:
        manques.append("espaces de noms utilisateur")
    if not dbus_run_session:
        manques.append("dbus-run-session")
    if manques:
        return False, "manque : " + ", ".join(manques)
    return True, "bubblewrap, espaces de noms et bus privé disponibles"


# ── Collecte — la seule partie qui touche à la machine ──────────────────────

def _paquet_installe(nom):
    try:
        sortie = subprocess.run(["dpkg-query", "-W", "-f=${Status}", nom],
                                capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return "install ok installed" in sortie.stdout


def _champ_shadow(utilisateur):
    """2e champ de la ligne shadow, ou None si le compte n'existe pas."""
    try:
        with open(SHADOW, encoding="utf-8", errors="replace") as f:
            for ligne in f:
                parts = ligne.rstrip("\n").split(":")
                if parts and parts[0] == utilisateur:
                    return parts[1] if len(parts) > 1 else ""
    except OSError:
        # Sans droits root on ne peut pas lire /etc/shadow : on ne prétend
        # surtout pas que tout va bien.
        return "?illisible"
    return None


def _dossiers_personnels():
    trouves = []
    try:
        entrees = os.listdir("/home")
    except OSError:
        return trouves
    for nom in entrees:
        chemin = os.path.join("/home", nom)
        try:
            st = os.stat(chemin)
        except OSError:
            continue
        if os.path.isdir(chemin) and st.st_uid >= 1000:
            trouves.append((nom, st.st_mode & 0o777))
    return trouves


def _empreintes_trousseau():
    if not os.path.exists(TROUSSEAU):
        return []
    try:
        sortie = subprocess.run(
            ["gpg", "--no-default-keyring", "--keyring", TROUSSEAU,
             "--list-keys", "--with-colons"],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    return [ligne.split(":")[9] for ligne in sortie.stdout.splitlines()
            if ligne.startswith("fpr:") and len(ligne.split(":")) > 9]


def _minuterie_active():
    try:
        sortie = subprocess.run(["systemctl", "is-enabled", "apt-daily-upgrade.timer"],
                                capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return sortie.stdout.strip() in ("enabled", "enabled-runtime", "static")


def _lire(chemin):
    try:
        with open(chemin, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def _userns_dispo():
    """Repris de bac_a_sable si présent, sinon lecture directe du réglage."""
    try:
        import bac_a_sable
        return bac_a_sable.user_ns_dispo()
    except Exception:
        contenu = _lire("/proc/sys/kernel/unprivileged_userns_clone").strip()
        return contenu != "0"


def relever():
    """Toutes les mesures de la machine, en une passe."""
    champ = _champ_shadow(INVITE)
    return {
        "extension_jetable": analyser_extension_jetable(
            os.path.exists(EXTENSION_JETABLE), _paquet_installe("python3-nautilus")),
        "invite": (analyser_invite(champ) if champ != "?illisible"
                   else (None, "/etc/shadow illisible — relancez avec sudo")),
        "homes": analyser_homes(_dossiers_personnels()),
        "trousseau": analyser_trousseau(_empreintes_trousseau()),
        "maj": analyser_maj_automatiques(_lire(PERIODIQUE), _minuterie_active()),
        "bac_a_sable": analyser_bac_a_sable(
            bool(shutil.which("bwrap")), _userns_dispo(),
            bool(shutil.which("dbus-run-session"))),
    }


LIBELLES = (
    ("extension_jetable", "Clic droit « Ouvrir en Jetable »"),
    ("invite", "Compte invité sans mot de passe"),
    ("homes", "Dossiers personnels privés"),
    ("trousseau", "Trousseau à jour pour les mises à jour"),
    ("maj", "Mises à jour automatiques armées"),
    ("bac_a_sable", "Bac à sable opérationnel"),
)


def cmd_verifier_poste():
    """Affiche l'état réel du poste. Code de sortie non nul si un contrôle échoue."""
    resultats = relever()
    print("Autotest du poste — ce qui est mesuré sur cette machine, "
          "pas ce qui est promis.\n")
    echecs = 0
    indecis = 0
    for cle, libelle in LIBELLES:
        ok, detail = resultats[cle]
        if ok is None:
            etat, indecis = "\033[33m?\033[0m", indecis + 1
        elif ok:
            etat = "\033[32m✔\033[0m"
        else:
            etat, echecs = "\033[31m✘\033[0m", echecs + 1
        print("  %s %-38s %s" % (etat, libelle, detail))
    print()
    if echecs:
        print("\033[31m%d contrôle(s) en échec.\033[0m Ce sont des défauts qui ne "
              "se voient pas" % echecs)
        print("à l'usage : un poste concerné se comporte exactement comme "
              "un poste sain.")
    elif indecis:
        print("\033[32mTout ce qui a pu être mesuré est conforme.\033[0m "
              "Relancez avec sudo")
        print("pour les contrôles qui demandent les droits d'administration.")
    else:
        print("\033[32mTout est conforme.\033[0m")
    return 1 if echecs else 0
