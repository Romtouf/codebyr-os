# -*- coding: utf-8 -*-
"""Provenance des fichiers — la couleur d'un Espace suit ce qui en sort.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Les Espaces cloisonnent les PROCESSUS. Ils ne cloisonnent pas les FICHIERS.
Un document téléchargé dans Navigation, déplacé dans Travail puis ouvert, s'y
exécute avec les droits de Travail, au milieu des documents professionnels. Le
bac à sable a parfaitement tenu ; c'est l'utilisateur qui a transporté la
menace de l'autre côté du mur, d'un geste que le système encourage désormais
d'un clic droit.

Windows appelle cela « Mark of the Web », macOS la quarantaine. Ce sont, de
l'avis général, leurs mitigations les plus rentables — davantage que leurs bacs
à sable.

Le principe ici : **un fichier garde l'identifiant de l'Espace d'où il vient**,
dans un attribut étendu. Rien de nouveau à apprendre pour l'utilisateur — la
couleur disait déjà « à quel Espace ceci appartient » pour les fenêtres ; elle
le dit maintenant aussi pour les fichiers.

LIMITE, à dire avant qu'on la découvre : un attribut étendu ne survit ni à une
clé USB en FAT, ni à une pièce jointe, ni à la plupart des partages réseau. La
marque se perd donc précisément là où elle servirait le plus. Windows a le même
défaut, et cela reste efficace — mais ce n'est pas une frontière, c'est un
indice.
"""
import os
import re

# Espace de noms « user. » : le seul inscriptible sans privilège particulier.
ATTRIBUT = "user.codebyr.origine"

# Même forme que les identifiants du registre : on refuse tout le reste plutôt
# que d'écrire dans un attribut une chaîne venue d'ailleurs.
#
# « \Z » et non « $ » : en Python, « $ » accepte un saut de ligne FINAL. Avec
# « $ », la valeur « travail\n » passait pour un identifiant valide — et cette
# valeur finit affichée à l'écran et concaténée à d'autres chaînes. Trouvé par
# le test, pas à la relecture.
FORME = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}\Z")


# ── Décisions pures — testables sans système de fichiers ────────────────────

def identifiant_valide(esp_id):
    return bool(esp_id) and bool(FORME.match(esp_id))


def origine_par_chemin(chemin, racine_donnees):
    """L'Espace déduit de l'EMPLACEMENT du fichier, ou None.

    Un fichier qui vit dans « <racine>/navigation/home/... » vient de
    Navigation : c'est vrai par construction, sans qu'on ait rien eu à écrire.

    Cela comble le trou qui rendait la marque presque inutile. Elle n'était
    posée qu'au moment d'un envoi, alors qu'un fichier entre surtout dans un
    Espace par TÉLÉCHARGEMENT — et ces fichiers-là n'étaient marqués nulle
    part. Les surveiller demanderait un processus permanent ; leur emplacement
    le dit déjà.

    L'attribut étendu garde tout son rôle : il est ce qui survit à la SORTIE de
    l'Espace, quand le chemin ne dit plus rien.
    """
    if not chemin or not racine_donnees:
        return None
    try:
        relatif = os.path.relpath(os.path.realpath(chemin),
                                  os.path.realpath(racine_donnees))
    except (OSError, ValueError):
        return None
    morceaux = relatif.replace("\\", "/").split("/")
    # « <id>/home/… » : au moins un fichier SOUS le dossier personnel, sinon on
    # désignerait le dossier de l'Espace lui-même.
    if len(morceaux) < 3 or morceaux[1] != "home":
        return None
    return morceaux[0] if identifiant_valide(morceaux[0]) else None


def doit_isoler(origine, espace_courant):
    """Faut-il ouvrir ce fichier sous cloche plutôt que dans l'Espace courant ?

    Vrai quand le fichier vient d'AILLEURS. Un fichier sans origine connue ne
    déclenche rien : la marque est un indice, pas une frontière, et traiter
    l'absence d'indice comme une accusation rendrait le système inutilisable
    dès le premier fichier venu d'une clé USB.
    """
    if not origine or not espace_courant:
        return False
    return origine != espace_courant


def resumer(origines, espace_courant):
    """Compte les fichiers étrangers, par Espace d'origine.

    C'est ce qui permet de DIRE la contagion au lieu de la supposer absente :
    « 14 fichiers venus de Navigation se trouvent dans votre Espace Travail ».
    """
    compte = {}
    for origine in origines:
        if doit_isoler(origine, espace_courant):
            compte[origine] = compte.get(origine, 0) + 1
    return compte


# ── Accès disque ────────────────────────────────────────────────────────────

def marquer(chemin, esp_id):
    """Pose l'origine sur un fichier. Vrai si elle a été écrite.

    Un échec n'est jamais fatal : les attributs étendus n'existent pas sur tous
    les systèmes de fichiers, et un fichier non marqué doit rester ouvrable.
    """
    if not identifiant_valide(esp_id):
        return False
    try:
        os.setxattr(chemin, ATTRIBUT, esp_id.encode("utf-8"))
        return True
    except (OSError, AttributeError, UnicodeError):
        return False


def origine(chemin, racine_donnees=None):
    """L'Espace d'où vient ce fichier, ou None.

    L'attribut étendu d'abord — c'est lui qui a suivi le fichier hors de son
    Espace. À défaut, l'emplacement : un fichier encore chez lui n'a pas besoin
    d'être marqué pour qu'on sache d'où il vient.

    On revalide la forme à la LECTURE : l'attribut est inscriptible par
    n'importe quel programme du poste, et sa valeur finit dans une interface et
    dans des chemins. Ce qui vient du disque n'est pas plus digne de confiance
    que ce qui vient du réseau.
    """
    try:
        brut = os.getxattr(chemin, ATTRIBUT)
    except (OSError, AttributeError):
        brut = None
    if brut is not None:
        try:
            valeur = brut.decode("utf-8").strip()
        except UnicodeError:
            valeur = ""
        if identifiant_valide(valeur):
            return valeur
    return origine_par_chemin(chemin, racine_donnees)


def heriter(source, destination, racine_donnees=None):
    """Reporte l'origine d'un fichier sur sa copie.

    Sans cela, la marque disparaîtrait au premier « Envoyer vers l'Espace… » —
    c'est-à-dire exactement au moment qu'elle sert à tracer.

    La racine est transmise à dessein : le cas le plus courant est un fichier
    TÉLÉCHARGÉ dans un Espace, qui n'a pas d'attribut mais dont l'emplacement
    dit tout. C'est là qu'on transforme cette information de position en marque
    durable, juste avant qu'il quitte son Espace et que le chemin cesse de
    parler.
    """
    marque = origine(source, racine_donnees)
    return marquer(destination, marque) if marque else False
