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


def origine(chemin):
    """L'Espace d'où vient ce fichier, ou None.

    On revalide la forme à la LECTURE : l'attribut est inscriptible par
    n'importe quel programme du poste, et sa valeur finit dans une interface et
    dans des chemins. Ce qui vient du disque n'est pas plus digne de confiance
    que ce qui vient du réseau.
    """
    try:
        brut = os.getxattr(chemin, ATTRIBUT)
    except (OSError, AttributeError):
        return None
    try:
        valeur = brut.decode("utf-8").strip()
    except UnicodeError:
        return None
    return valeur if identifiant_valide(valeur) else None


def heriter(source, destination):
    """Reporte l'origine d'un fichier sur sa copie.

    Sans cela, la marque disparaîtrait au premier « Envoyer vers l'Espace… » —
    c'est-à-dire exactement au moment qu'elle sert à tracer.
    """
    marque = origine(source)
    return marquer(destination, marque) if marque else False
