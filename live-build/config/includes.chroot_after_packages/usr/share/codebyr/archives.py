# -*- coding: utf-8 -*-
"""Les archives des Espaces : ce qu'on y met, ce qu'on accepte d'en sortir.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Sorti de codebyr-space en 1.17.0 (découpage, audit point 8), sans changement de
comportement. UNE règle, partagée par la restauration d'une sauvegarde, par le
déménagement vers un compte dédié et par le retour vers le compte du bureau :
deux copies de cette règle finiraient par diverger, et c'est précisément le
genre de règle qu'on ne veut voir diverger nulle part.
"""
import tarfile

from traduction import _

ARCHIVE_ENTREES_MAX = 100000
ARCHIVE_TAILLE_MAX = 20 * 1024**3


def filtre_dossier_d_espace(membre, destination):
    """Règle d'extraction pour les données d'un Espace qui changent de compte.

    La règle « data » de tarfile refuse tout lien vers un chemin absolu. Les
    applications en posent pourtant dans un dossier personnel, et un seul
    d'entre eux faisait échouer le déménagement entier : l'Espace ne se serait
    plus ouvert.

    Le lien SYMBOLIQUE est donc accepté quelle que soit sa cible : ce n'est
    qu'un nom, et tarfile refuse ensuite d'écrire À TRAVERS lui (il résout le
    chemin de chaque entrée suivante). Dans le bac à sable, une cible absolue
    se résout dans la vue de l'Espace, jamais sur le système.

    Le lien DUR, lui, reste tenu à l'intérieur : il donne accès au fichier
    lui-même. Une archive produite par un Espace compromis pourrait sinon
    poser, au retour vers le bureau, un lien dur vers la clé SSH de
    l'utilisateur — que l'Espace relirait à sa prochaine ouverture.
    """
    if membre.issym():
        return tarfile.tar_filter(membre, destination)
    return tarfile.data_filter(membre, destination)


def extraire_archive(tar, destination, filtre="data"):
    """Extrait une archive d'Espace, entrée par entrée, selon UNE règle.

    Entrée par entrée plutôt que d'un bloc : cela fonctionne aussi sur un
    FLUX, qu'on ne peut pas relire. Une archive refusée en cours de route
    laisse une extraction partielle — l'appelant extrait donc toujours dans un
    dossier de préparation qu'il jette en cas d'erreur.
    """
    entrees = 0
    taille = 0
    for membre in tar:
        entrees += 1
        taille += membre.size
        if entrees > ARCHIVE_ENTREES_MAX or taille > ARCHIVE_TAILLE_MAX:
            raise ValueError(_("Archive trop volumineuse (100 000 entrées / 20 Gio maximum)"))
        # Les liens sont ACCEPTÉS, les fichiers spéciaux refusés.
        #
        # Refuser tout lien paraissait prudent ; cela rendait la restauration
        # impossible sur un vrai Espace. Un dossier personnel avec un profil
        # Firefox contient des liens symboliques : « Revenir à un instantané »
        # échouait donc toujours, sur une archive produite par Codebyr
        # lui-même. On pouvait sauvegarder, jamais restaurer. Constaté le
        # 12/09/2026 sur une VM.
        #
        # Ce qu'il fallait refuser n'est pas le lien, c'est le lien qui SORT de
        # l'Espace. « filter="data" » s'en charge : chemins absolus, traversées
        # par « .. » et cibles hors destination sont rejetés par tarfile
        # lui-même, et lèvent une erreur que l'on attrape.
        if not (membre.isfile() or membre.isdir() or membre.issym() or membre.islnk()):
            raise ValueError(_("Archive contenant un fichier spécial"))
        tar.extract(membre, destination, filter=filtre)


def entree_archivable(info):
    """Filtre d'archivage : les fichiers spéciaux ne partent pas.

    Un tube nommé dans un dossier d'Espace ferait refuser l'archive entière à
    l'arrivée, et le déménagement avec : on ne l'emporte pas.
    """
    if info.isfile() or info.isdir() or info.issym() or info.islnk():
        return info
    return None
