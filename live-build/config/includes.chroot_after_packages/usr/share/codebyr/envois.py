# -*- coding: utf-8 -*-
"""Les boîtes d'envoi : le seul passage par lequel un fichier sort d'un Espace.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Sorti de codebyr-space en 1.17.0 (découpage, audit point 8), sans changement de
comportement.

Le bac à sable monte le dossier de l'Espace PAR-DESSUS « ~ ». À l'intérieur,
chemins.DONNEES désigne donc un dossier fantôme du bac à sable, sans rapport
avec les vrais Espaces. « envoyer » y copiait le fichier et annonçait
« Copié » : il n'arrivait jamais. Constaté le 24/08/2026.

L'Espace dépose donc dans SA boîte, montée à un chemin fixe ; l'hôte relève et
distribue. Un Espace n'écrit jamais chez un autre.
"""
import os
import shutil
import stat
import tempfile

import chemins
import compte_dedie
import comptes
import fichiers_surs
import journal

# La boîte, vue de l'INTÉRIEUR d'un Espace : c'est là que le bac à sable la monte.
ENVOI_INTERNE = os.path.expanduser("~/.codebyr-envoi")


def boite_envoi(esp_id):
    """Boîte d'envoi d'un Espace ordinaire, vue depuis l'HÔTE."""
    return os.path.join(chemins.DONNEES, esp_id, "envoi")


def boite_de_depart(esp, esp_id):
    """La boîte d'où partent les fichiers d'un Espace, selon son compte.

    Sous compte dédié, elle est hors du dossier du bureau, tenue par root, et
    le bureau peut la relever SANS ouvrir l'Espace (voir comptes.py).
    """
    if compte_dedie.demande(esp):
        return comptes.chemin_envois(os.getuid(), esp_id)
    return boite_envoi(esp_id)


def relever_envois(espaces):
    """Distribue ce que les Espaces ont déposé. Renvoie le nombre remis.

    Appelé depuis l'hôte, au lancement de n'importe quel Espace : c'est le
    moment où l'on va justement chercher ses fichiers, et cela évite un
    service qui tournerait en permanence pour un geste occasionnel.
    """
    remis = 0
    for source in list(espaces):
        try:
            racine = boite_de_depart(espaces[source], source)
        except ValueError:
            continue            # identifiant qu'un compte dédié ne peut pas porter
        try:
            with fichiers_surs.dossier(racine) as racine_fd:
                destinations = os.listdir(racine_fd)
            for dest in destinations:
                if dest not in espaces or espaces[dest].get("ephemere"):
                    continue
                # Vers un Espace dédié : sa boîte d'arrivée, qu'il recueillera
                # à sa prochaine ouverture. Lisible par lui — le mode est posé
                # sur la copie avant qu'elle ne prenne son nom.
                mode = None
                if compte_dedie.demande(espaces[dest]):
                    try:
                        cible = comptes.chemin_arrivees(os.getuid(), dest)
                    except ValueError:
                        continue
                    if not os.path.isdir(cible):
                        continue    # jamais ouvert sous son compte : ça attend
                    mode = 0o644
                dossier = os.path.join(racine, dest)
                try:
                    with fichiers_surs.dossier(dossier) as source_fd:
                        noms = os.listdir(source_fd)
                        if mode is None:
                            cible = os.path.join(chemins.DONNEES, dest, "home", chemins.PARTAGE)
                            fichiers_surs.mkdir(cible)
                        for nom in noms:
                            if nom.startswith(".codebyr-"):
                                continue
                            try:
                                # Le descripteur conserve le dossier même si son
                                # nom est remplacé pendant la remise.
                                # ouvrir() refuse /proc/self/fd (liens), donc
                                # copier depuis un fd ouvert relativement ici.
                                entree = os.open(nom, os.O_RDONLY | os.O_NOFOLLOW |
                                                os.O_NONBLOCK, dir_fd=source_fd)
                                try:
                                    st = os.fstat(entree)
                                    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                                        continue
                                    # Copie privée : jamais de déplacement d'un
                                    # chemin fourni par l'Espace vers l'hôte.
                                    with tempfile.TemporaryDirectory(prefix="codebyr-envoi-") as t:
                                        copie = os.path.join(t, "document")
                                        with os.fdopen(os.dup(entree), "rb") as src, open(copie, "wb") as dst:
                                            shutil.copyfileobj(src, dst)
                                        fichiers_surs.copier_unique(copie, cible, nom, source, mode=mode)
                                    actuel = os.stat(nom, dir_fd=source_fd, follow_symlinks=False)
                                    if (actuel.st_dev, actuel.st_ino) == (st.st_dev, st.st_ino):
                                        os.unlink(nom, dir_fd=source_fd)
                                    remis += 1
                                finally:
                                    os.close(entree)
                            except OSError:
                                continue
                except OSError as exc:
                    # Une destination listée mais illisible n'est pas normale :
                    # les fichiers y attendent, et quelqu'un doit pouvoir le
                    # savoir. Ce silence a caché qu'aucun envoi ne partait d'un
                    # Espace à compte dédié (14/09/2026).
                    journal.noter("relève impossible de %s vers %s : %s" % (source, dest, exc))
                    continue
        except OSError:
            continue
    if remis:
        journal.noter("remise de %d fichier(s) entre Espaces" % remis)
    return remis
