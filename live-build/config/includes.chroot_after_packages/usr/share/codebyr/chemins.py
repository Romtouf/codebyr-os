# -*- coding: utf-8 -*-
"""Où vivent les données des Espaces — écrit à UN seul endroit.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Jusqu'en 1.16.8, la racine des données était écrite dans codebyr-space, quatre
fois dans codebyr-config et une fois dans l'extension de Fichiers : six copies
qui devaient rester d'accord sans que rien ne le vérifie. C'est la façon
habituelle dont deux moitiés d'un même système finissent par ne plus se
parler. Le profil AppArmor du filtre réseau la porte aussi, dans sa propre
syntaxe : un test vérifie qu'elle concorde.

Toujours lire « chemins.DONNEES », jamais « from chemins import DONNEES » : la
valeur est lue au moment de l'appel, et les tests la remplacent.
"""
import os

# Les données des Espaces ordinaires (sans compte séparé) : un dossier par
# Espace, avec son dossier personnel, son installation Flatpak, ses journaux.
DONNEES = os.path.expanduser("~/.local/share/codebyr/espaces")

# Où « codebyr-space export » range les sauvegardes, et d'où il restaure.
SAUVEGARDES = os.path.expanduser("~/Espaces-Codebyr")

# Le sas d'un Espace : c'est là qu'atterrit tout fichier venu du dehors.
PARTAGE = "Partagé"

# Sous-dossier de « Partagé » où arrive une pièce jointe examinée dans un
# Espace à compte dédié (voir _lancer).
PIECE_JOINTE = "Pièce jointe du"

# Le dossier propre à Codebyr dans le dossier d'un Espace à compte dédié : ce
# qu'il contient (installation Flatpak, marqueurs) ne part ni dans une
# sauvegarde, ni au retour vers le compte du bureau.
DOSSIER_INTERNE = ".codebyr"


def dossier(esp_id):
    """Le dossier d'un Espace ordinaire."""
    return os.path.join(DONNEES, esp_id)


def home(esp_id):
    """Le dossier personnel d'un Espace ordinaire, tel que rangé sur la machine."""
    return os.path.join(DONNEES, esp_id, "home")


def flatpak(esp_id):
    """L'installation Flatpak propre à un Espace ordinaire."""
    return os.path.join(DONNEES, esp_id, "flatpak")


def refus_reseau(esp_id):
    """Le journal des sites refusés par le filtre réseau d'un Espace."""
    return os.path.join(DONNEES, esp_id, "domaines-refuses.txt")
