# -*- coding: utf-8 -*-
"""Ce qu'un Espace à compte dédié fait chez lui, sous son propre compte.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Sorti de codebyr-space en 1.17.1 (découpage, audit point 8), sans changement de
comportement. Ces fonctions sont les ordres « interne-… », exécutés PAR
l'Espace à la demande du bureau (voir ordres_espace.py) : chacune refuse de
tourner ailleurs que sous le compte d'un Espace, et n'écrit que chez lui.
"""
import json
import os
import shutil
import sys
import tarfile
import tempfile
import time

import archives
import chemins
import comptes
import fichiers_surs
import ordres_espace
import provenance


def compte_courant():
    """Le compte sous lequel on tourne, s'il est celui d'un Espace ; sinon None."""
    import pwd
    import comptes
    compte = pwd.getpwuid(os.getuid())
    return compte if comptes.est_compte_d_espace(compte.pw_name) else None


def recueillir_arrivees(home, arrivees):
    """Recopie chez l'Espace ce que le bureau lui a envoyé, puis vide la boîte.

    Exécuté PAR l'Espace. Il RECOPIE plutôt que de déplacer : un fichier
    déplacé garderait le bureau pour propriétaire, et l'Espace ne pourrait pas
    le modifier. La provenance suit la copie.

    Un lot (sous-dossier, pour une pièce jointe) arrive sous le même nom dans
    « Partagé » : c'est ce qui permet au lanceur d'ouvrir le fichier à un
    chemin connu d'avance. Renvoie le nombre de fichiers recueillis.
    """
    import stat as stat_
    try:
        with fichiers_surs.dossier(arrivees) as fd:
            noms = sorted(os.listdir(fd))
    except FileNotFoundError:
        return 0
    partage = os.path.join(home, chemins.PARTAGE)
    recus = 0

    def recueillir(chemin, dossier_cible, nom):
        origine = None
        try:
            origine = os.getxattr(chemin, provenance.ATTRIBUT,
                                  follow_symlinks=False).decode("ascii")
        except (OSError, UnicodeDecodeError):
            pass
        if origine and not provenance.identifiant_valide(origine):
            origine = None
        fichiers_surs.mkdir(dossier_cible)
        fichiers_surs.copier_unique(chemin, dossier_cible, nom, origine)
        os.unlink(chemin)
        return 1

    for nom in noms:
        if nom.startswith(".codebyr-"):
            continue        # écriture du bureau encore en cours
        chemin = os.path.join(arrivees, nom)
        st = os.lstat(chemin)
        if stat_.S_ISREG(st.st_mode):
            recus += recueillir(chemin, partage, nom)
        elif stat_.S_ISDIR(st.st_mode):
            for sous in sorted(os.listdir(chemin)):
                interne = os.path.join(chemin, sous)
                if not sous.startswith(".codebyr-") and stat_.S_ISREG(os.lstat(interne).st_mode):
                    recus += recueillir(interne, os.path.join(partage, nom), sous)
            try:
                os.rmdir(chemin)
            except OSError:
                pass
    return recus


def importer():
    """Reçoit sur l'entrée standard les données d'un Espace, et les pose chez lui.

    Exécuté PAR l'Espace, sous son compte : il n'écrit que dans son propre
    dossier, et ce qu'il reçoit passe par la même règle que toute restauration
    (voir archives.extraire_archive).

    Une seule fois : un second déménagement écraserait ce que l'Espace a fait
    depuis le premier. Code ordres_espace.MIGRATION_FAITE si c'est déjà fait.
    Rien de ce qui se trouve déjà là n'est effacé — un nom déjà pris est mis
    de côté dans .codebyr/avant-migration-<date>.
    """
    compte = compte_courant()
    if not compte:
        sys.stderr.write("codebyr-space : réservé au compte d'un Espace.\n")
        return 2
    home = compte.pw_dir
    interne = os.path.join(home, chemins.DOSSIER_INTERNE)
    marqueur = os.path.join(interne, "migration.json")
    if os.path.exists(marqueur):
        sys.stderr.write("codebyr-space : données déjà déménagées dans cet Espace.\n")
        return ordres_espace.MIGRATION_FAITE
    fichiers_surs.mkdir(interne)
    stage = tempfile.mkdtemp(prefix="import-", dir=interne)
    try:
        with tarfile.open(fileobj=sys.stdin.buffer, mode="r|*") as tar:
            archives.extraire_archive(tar, stage, archives.filtre_dossier_d_espace)
        mis_de_cote = os.path.join(interne, "avant-migration-%s" % time.strftime("%Y%m%d-%H%M%S"))
        for nom in sorted(os.listdir(stage)):
            if nom == chemins.DOSSIER_INTERNE:
                continue
            cible = os.path.join(home, nom)
            if os.path.lexists(cible):
                os.makedirs(mis_de_cote, mode=0o700, exist_ok=True)
                os.rename(cible, os.path.join(mis_de_cote, nom))
            os.rename(os.path.join(stage, nom), cible)
        with fichiers_surs.ouvrir(marqueur, "w", encoding="utf-8") as f:
            json.dump({"date": time.strftime("%Y-%m-%d %H:%M:%S")}, f)
    except (OSError, tarfile.TarError, ValueError) as exc:
        sys.stderr.write("codebyr-space : déménagement refusé (%s)\n" % exc)
        return 1
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return 0


def restaurer():
    """Remplace le contenu de l'Espace par l'archive reçue sur l'entrée standard.

    Exécuté PAR l'Espace. Même garantie que la restauration d'un Espace
    ordinaire : l'archive est entièrement déballée AVANT de toucher à quoi que
    ce soit, et l'état d'avant est mis de côté, pas effacé — dans
    .codebyr/avant-restauration-<date>.
    """
    compte = compte_courant()
    if not compte:
        sys.stderr.write("codebyr-space : réservé au compte d'un Espace.\n")
        return 2
    home = compte.pw_dir
    interne = os.path.join(home, chemins.DOSSIER_INTERNE)
    fichiers_surs.mkdir(interne)
    stage = tempfile.mkdtemp(prefix="restauration-", dir=interne)
    try:
        with tarfile.open(fileobj=sys.stdin.buffer, mode="r|*") as tar:
            archives.extraire_archive(tar, stage, archives.filtre_dossier_d_espace)
        cote = os.path.join(interne, "avant-restauration-%s" % time.strftime("%Y%m%d-%H%M%S"))
        os.makedirs(cote, mode=0o700)
        mis_de_cote, poses = [], []
        try:
            for nom in sorted(os.listdir(home)):
                if nom != chemins.DOSSIER_INTERNE:
                    os.rename(os.path.join(home, nom), os.path.join(cote, nom))
                    mis_de_cote.append(nom)
            for nom in sorted(os.listdir(stage)):
                if nom != chemins.DOSSIER_INTERNE:
                    os.rename(os.path.join(stage, nom), os.path.join(home, nom))
                    poses.append(nom)
        except OSError:
            # Remettre ce qu'on a déjà bougé : un Espace à moitié restauré
            # serait pire que pas restauré du tout.
            for nom in reversed(poses):
                os.rename(os.path.join(home, nom), os.path.join(stage, nom))
            for nom in reversed(mis_de_cote):
                os.rename(os.path.join(cote, nom), os.path.join(home, nom))
            raise
    except (OSError, tarfile.TarError, ValueError) as exc:
        sys.stderr.write("codebyr-space : restauration refusée, données conservées (%s)\n" % exc)
        return 1
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    sys.stdout.write(cote + "\n")
    return 0


def effacer():
    """Efface les données de l'Espace, et ses deux boîtes. Exécuté PAR l'Espace.

    C'est l'Espace qui efface chez lui : root n'a pas à parcourir un dossier
    qu'un Espace compromis aurait pu garnir de liens. Les boîtes sont vidées
    aussi — un fichier en route est une donnée de l'Espace comme une autre.
    """
    compte = compte_courant()
    if not compte:
        sys.stderr.write("codebyr-space : réservé au compte d'un Espace.\n")
        return 2
    proprietaire, esp_id = comptes.decomposer(compte.pw_name)
    restes = []
    for dossier in (compte.pw_dir, comptes.chemin_envois(proprietaire, esp_id),
                    comptes.chemin_arrivees(proprietaire, esp_id)):
        try:
            noms = os.listdir(dossier)
        except FileNotFoundError:
            continue
        for nom in noms:
            chemin = os.path.join(dossier, nom)
            try:
                if os.path.isdir(chemin) and not os.path.islink(chemin):
                    shutil.rmtree(chemin)
                else:
                    os.unlink(chemin)
            except OSError as exc:
                restes.append("%s (%s)" % (nom, exc))
    if restes:
        sys.stderr.write("codebyr-space : non effacé : %s\n" % "; ".join(restes[:5]))
        return 1
    return 0


def contagion():
    """Écrit, en JSON, la provenance de chaque fichier de l'Espace. Exécuté PAR lui.

    Seul l'attribut étendu compte ici : c'est lui qui a suivi un fichier venu
    d'ailleurs. L'emplacement ne dit rien, puisque tout est chez l'Espace.
    """
    compte = compte_courant()
    if not compte:
        sys.stderr.write("codebyr-space : réservé au compte d'un Espace.\n")
        return 2
    origines = []
    total = 0
    for dossier, sous, fichiers in os.walk(compte.pw_dir):
        if dossier == compte.pw_dir and chemins.DOSSIER_INTERNE in sous:
            sous.remove(chemins.DOSSIER_INTERNE)
        for nom in fichiers:
            total += 1
            origines.append(provenance.origine(os.path.join(dossier, nom)))
    json.dump({"total": total, "origines": origines}, sys.stdout)
    return 0


def rendu():
    """L'Espace oublie qu'il a reçu un déménagement : ses données sont reparties.

    Sans cela, réactiver le compte dédié plus tard ferait répondre « déjà
    déménagé » à l'Espace, et tout ce que l'utilisateur aurait fait entre-temps
    sous le compte du bureau serait ignoré, sans un mot. Le marqueur est mis de
    côté, pas effacé.
    """
    compte = compte_courant()
    if not compte:
        sys.stderr.write("codebyr-space : réservé au compte d'un Espace.\n")
        return 2
    marqueur = os.path.join(compte.pw_dir, chemins.DOSSIER_INTERNE, "migration.json")
    try:
        if os.path.exists(marqueur):
            os.rename(marqueur, marqueur.replace(
                "migration.json", "migration-rendue-%s.json" % time.strftime("%Y%m%d-%H%M%S")))
    except OSError as exc:
        sys.stderr.write("codebyr-space : %s\n" % exc)
        return 1
    return 0


def exporter():
    """Écrit sur la sortie standard les données de l'Espace, en archive.

    Exécuté PAR l'Espace : il ne peut emporter que ce que son compte peut lire.
    Le dossier interne de Codebyr reste là où il est.
    """
    compte = compte_courant()
    if not compte:
        sys.stderr.write("codebyr-space : réservé au compte d'un Espace.\n")
        return 2
    home = compte.pw_dir
    try:
        with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as tar:
            for nom in sorted(os.listdir(home)):
                if nom == chemins.DOSSIER_INTERNE:
                    continue
                tar.add(os.path.join(home, nom), arcname="./" + nom,
                        filter=archives.entree_archivable)
    except (OSError, tarfile.TarError) as exc:
        sys.stderr.write("codebyr-space : export refusé (%s)\n" % exc)
        return 1
    return 0
