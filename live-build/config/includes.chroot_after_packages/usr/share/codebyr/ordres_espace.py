# -*- coding: utf-8 -*-
"""Les ordres que le bureau donne à un Espace à compte dédié.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Sorti de codebyr-space en 1.17.1 (découpage, audit point 8), sans changement de
comportement. Le bureau n'a pas accès au dossier d'un Espace à compte dédié :
ce qui doit s'y faire est demandé à son premier processus, qui l'exécute sous
le compte de l'Espace (voir codebyr-espace-init et cote_espace.py). Ici : le
protocole, le transport d'un ordre (avec un flux si besoin), le déménagement
des données vers le compte dédié et leur retour, la préparation du dossier.
"""
import json
import os
import shutil
import sys
import tarfile
import tempfile
import threading
import time

import archives
import bac_a_sable
import chemins
import compte_dedie
import fichiers_surs
import journal
import navigateur

# Le programme que l'Espace exécute pour un ordre : codebyr-space, qui s'inscrit
# ici au démarrage. Ce module ne peut pas se désigner lui-même (__file__) :
# l'Espace exécuterait le module au lieu du programme, et aucun ordre ne passerait.
PROGRAMME = "/usr/bin/codebyr-space"

# Le protocole : les ordres que l'Espace sait exécuter (voir cote_espace.py).
INTERNE_PREPARER = "interne-preparer"
INTERNE_IMPORTER = "interne-importer"
INTERNE_EXPORTER = "interne-exporter"
MIGRATION_FAITE = 3
INTERNE_RESTAURER = "interne-restaurer"
INTERNE_EFFACER = "interne-effacer"
INTERNE_CONTAGION = "interne-contagion"
INTERNE_RENDU = "interne-rendu"


def preparer_depuis_l_espace(session, espaces, app_cmd, filtre_reseau):
    """Fait préparer le dossier de l'Espace PAR l'Espace. Renvoie True si fait.

    Le bureau n'a plus accès à ce dossier : ce qui s'y écrivait à chaque
    ouverture est demandé au premier processus de l'Espace, qui l'exécute sous
    le compte de l'Espace. Hors du bac à sable — il écrit dans son propre
    dossier, rien de plus — mais sans que le bac à sable puisse l'atteindre :
    la socket d'ordres n'y est jamais montée.

    C'est aussi plus sûr qu'avant : le bureau écrivait dans un dossier que
    l'Espace contrôle, où un lien symbolique posé par l'Espace pouvait le
    faire écrire ailleurs. Un Espace qui se piège lui-même n'atteint plus que
    ses propres fichiers.
    """
    charge = {
        "firefox": "firefox" in os.path.basename(app_cmd[0]),
        "filtre_reseau": bool(filtre_reseau),
        "domaines_proteges": navigateur.domaines_proteges(espaces),
    }
    env = {"PATH": "/usr/bin:/bin", "LANG": os.environ.get("LANG", "C.UTF-8"),
           "HOME": session.home,
           "CODEBYR_LIB": os.environ.get("CODEBYR_LIB", "/usr/share/codebyr")}
    try:
        code = compte_dedie.executer(
            session.ordres,
            ["/usr/bin/python3", PROGRAMME, INTERNE_PREPARER,
             json.dumps(charge)],
            env)
    except compte_dedie.Indisponible as exc:
        sys.stderr.write("codebyr-space : préparation impossible (%s)\n" % exc)
        return False
    return code == 0


MARQUEUR_DEMENAGEMENT = "compte-dedie.json"
# Marge exigée en plus de la taille des données avant de déménager : le
# déménagement COPIE, et un disque plein au milieu laisserait l'Espace sans
# rien d'utilisable des deux côtés.
MARGE_DEMENAGEMENT = 200 * 1024 * 1024


def marqueur_demenagement(esp_id):
    """Côté bureau : « les données de cet Espace sont parties vers son compte »."""
    return os.path.join(chemins.DONNEES, esp_id, MARQUEUR_DEMENAGEMENT)


def commande_interne(action, *args):
    return ["/usr/bin/python3", PROGRAMME, action] + list(args)


def env_interne(session):
    return {"PATH": "/usr/bin:/bin", "LANG": os.environ.get("LANG", "C.UTF-8"),
            "HOME": session.home,
            "CODEBYR_LIB": os.environ.get("CODEBYR_LIB", "/usr/share/codebyr")}


def taille_sans_suivre(chemin):
    total = 0
    for dossier, _sous, fichiers in os.walk(chemin):
        for nom in fichiers:
            try:
                total += os.lstat(os.path.join(dossier, nom)).st_size
            except OSError:
                pass
    return total


def ordre_interne(session, action, produire=None, consommer=None, args=()):
    """Fait exécuter un ordre interne par l'Espace, avec un flux si besoin.

    `produire(flux)` écrit ce que l'Espace lira sur son entrée standard ;
    `consommer(flux)` lit ce qu'il écrit sur sa sortie. L'un ou l'autre, dans
    un fil à part : un tuyau plein bloquerait sinon les deux bouts.

    Renvoie (code, erreurs). Le bout transmis est TOUJOURS refermé ici, même
    si l'ordre échoue : sans cela, le fil attendait à jamais un correspondant
    disparu (vu dans le WSL le 14/09/2026).
    """
    erreurs = []
    options = {}
    a_fermer = None
    fil = None
    if produire or consommer:
        lecture, ecriture = os.pipe()
        if produire:
            options["entree"], a_fermer, mien, sens = lecture, lecture, ecriture, "wb"
        else:
            options["sortie"], a_fermer, mien, sens = ecriture, ecriture, lecture, "rb"
        travail = produire or consommer

        def dans_un_fil():
            try:
                with os.fdopen(mien, sens) as flux:
                    travail(flux)
            except BrokenPipeError:
                erreurs.append("l'Espace a cessé de lire")
            except (OSError, tarfile.TarError, ValueError) as exc:
                erreurs.append(str(exc))

        fil = threading.Thread(target=dans_un_fil, daemon=True)
        fil.start()
    try:
        code = compte_dedie.executer(session.ordres,
                                     commande_interne(action, *args),
                                     env_interne(session), **options)
    except compte_dedie.Indisponible as exc:
        code = None
        erreurs.append(str(exc))
    finally:
        if a_fermer is not None:
            os.close(a_fermer)
    if fil:
        fil.join()
    return code, erreurs


def session_pour_un_geste(esp):
    """Ouvre l'Espace le temps d'un geste sur ses données (sans son)."""
    return compte_dedie.Session(
        esp["id"], os.path.basename(os.environ.get("WAYLAND_DISPLAY") or "wayland-0"),
        False, *bac_a_sable.plafonds_de(esp), ephemere=bool(esp.get("ephemere")))


def emballer(dossier, noms):
    """Fabrique qui écrit l'archive d'un dossier dans un flux, sans suivre de lien."""
    def produire(flux):
        with tarfile.open(fileobj=flux, mode="w|") as tar:
            for nom in noms:
                tar.add(os.path.join(dossier, nom), arcname="./" + nom,
                        filter=archives.entree_archivable)
    return produire


def demenager_vers_compte_dedie(esp, session, prevenir):
    """Première ouverture sous compte dédié : les données de l'Espace le suivent.

    Sans cela, l'Espace s'ouvrirait VIDE, et l'utilisateur croirait avoir tout
    perdu — ses documents, son profil de navigateur, ses téléchargements.

    Ce que ce déménagement garantit :
    · root ne lit rien : le BUREAU emballe ce qu'il a le droit de lire, et
      l'ESPACE déballe chez lui, par un tuyau (voir codebyr-espace-init) ;
      tarfile ne suit pas les liens : un lien posé dans l'Espace part comme
      lien, jamais comme le fichier qu'il désigne ;
    · il COPIE, n'efface rien : les anciennes données restent en place, et
      retirer le réglage « compte » les fait revenir, à jour (voir
      rapatrier_depuis_compte_dedie) ;
    · il ne se fait qu'une fois, et un échec empêche l'ouverture — un Espace
      qui s'ouvrirait vide après un déménagement raté serait le pire résultat.

    Renvoie True si l'Espace peut s'ouvrir.
    """
    ancien = os.path.join(chemins.DONNEES, esp["id"], "home")
    if os.path.exists(marqueur_demenagement(esp["id"])):
        return True
    try:
        noms = sorted(os.listdir(ancien))
    except FileNotFoundError:
        return True                 # Espace jamais ouvert : rien à emporter
    if not noms:
        return True
    taille = taille_sans_suivre(ancien)
    libre = shutil.disk_usage(os.path.dirname(os.path.dirname(session.home))).free
    if libre < taille + MARGE_DEMENAGEMENT:
        sys.stderr.write("codebyr-space : place insuffisante pour déménager %s "
                         "(%d Mo à copier, %d Mo libres).\n"
                         % (esp["nom"], taille // 2**20, libre // 2**20))
        return False
    prevenir("Espace %s : déménagement de ses données" % esp["nom"],
              "Première ouverture sous son propre compte : ses fichiers le "
              "suivent. Rien n'est effacé. Cela peut prendre un moment.")
    code, erreurs = ordre_interne(session, INTERNE_IMPORTER,
                                   produire=emballer(ancien, noms))
    if code == MIGRATION_FAITE:
        erreurs = []                # l'Espace avait déjà reçu ses données
    elif code != 0 or erreurs:
        sys.stderr.write("codebyr-space : déménagement de %s interrompu (%s) — "
                         "les données sont intactes à leur ancien emplacement.\n"
                         % (esp["nom"], "; ".join(erreurs) or "code %s" % code))
        journal.noter("Espace %s : déménagement vers le compte dédié échoué" % esp["id"])
        return False
    with fichiers_surs.ouvrir(marqueur_demenagement(esp["id"]), "w", encoding="utf-8") as f:
        json.dump({"compte": session.compte, "date": time.strftime("%Y-%m-%d %H:%M:%S")}, f)
    journal.noter("Espace %s : données déménagées vers son compte dédié" % esp["id"])
    return True


def rapatrier_depuis_compte_dedie(esp):
    """Le réglage « compte » a été retiré : les données reviennent, à jour.

    Les anciennes données étaient restées en place, mais figées au jour du
    déménagement. Rouvrir l'Espace dessus ferait disparaître, sans un mot, tout
    ce qui a été fait depuis sous son compte. On rapatrie donc d'abord ce que
    l'Espace détient — c'est lui qui emballe, le bureau qui déballe, selon la
    règle des données d'Espace — et l'état figé est mis de côté, pas effacé.

    Sans le service des comptes, impossible de demander ses données à l'Espace :
    l'ouverture est refusée plutôt que de montrer l'état figé comme s'il était
    le bon. Renvoie True si l'Espace peut s'ouvrir.
    """
    if not os.path.exists(marqueur_demenagement(esp["id"])):
        return True
    try:
        session = session_pour_un_geste(esp)
    except compte_dedie.Indisponible as exc:
        sys.stderr.write("codebyr-space : les données récentes de %s sont restées "
                         "dans son compte dédié, et %s.\n" % (esp["nom"], exc))
        return False
    parent = os.path.join(chemins.DONNEES, esp["id"])
    home = os.path.join(parent, "home")
    sauvegarde = None
    try:
        with tempfile.TemporaryDirectory(prefix=".retour-", dir=parent) as stage:
            neuf = os.path.join(stage, "home")
            os.mkdir(neuf, 0o700)

            def deballer(flux):
                with tarfile.open(fileobj=flux, mode="r|") as tar:
                    archives.extraire_archive(tar, neuf, archives.filtre_dossier_d_espace)

            code, erreurs = ordre_interne(session, INTERNE_EXPORTER, consommer=deballer)
            if code != 0 or erreurs:
                raise ValueError("; ".join(erreurs) or "export refusé (code %s)" % code)
            with fichiers_surs.dossier(parent):
                if os.path.lexists(home):
                    if os.path.islink(home):
                        raise ValueError("Dossier personnel symbolique refusé")
                    sauvegarde = tempfile.mkdtemp(prefix="avant-retour-", dir=parent)
                    os.rmdir(sauvegarde)
                    os.rename(home, sauvegarde)
                try:
                    os.rename(neuf, home)
                except OSError:
                    if sauvegarde:
                        os.rename(sauvegarde, home)
                    raise
        code, erreurs = ordre_interne(session, INTERNE_RENDU)
        if code != 0:
            raise ValueError("l'Espace n'a pas pu noter le retour de ses données")
        os.unlink(marqueur_demenagement(esp["id"]))
    except (OSError, ValueError) as exc:
        sys.stderr.write("codebyr-space : retour des données de %s interrompu (%s) ; "
                         "rien n'a été effacé.\n" % (esp["nom"], exc))
        return False
    finally:
        session.rendre()
    journal.noter("Espace %s : données revenues de son compte dédié" % esp["id"])
    print("Données de %s revenues de son compte dédié%s." % (
        esp["nom"], " ; état précédent conservé : %s" % sauvegarde if sauvegarde else ""))
    return True


def geste_dans_l_espace(esp, action, produire=None, consommer=None, args=()):
    """Ouvre l'Espace, fait exécuter un ordre interne, le rend. Renvoie (code, erreurs)."""
    try:
        session = session_pour_un_geste(esp)
    except compte_dedie.Indisponible as exc:
        return None, [str(exc)]
    try:
        return ordre_interne(session, action, produire=produire,
                              consommer=consommer, args=args)
    finally:
        session.rendre()
