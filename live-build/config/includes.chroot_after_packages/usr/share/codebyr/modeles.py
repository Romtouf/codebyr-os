# -*- coding: utf-8 -*-
"""Modèles de documents — pour que « Nouveau document » existe.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

GNOME Fichiers n'affiche l'entrée « Nouveau document » que si le dossier
Modèles contient au moins un fichier. Vide, le menu disparaît entièrement : il
ne reste que « Nouveau dossier », et créer un simple fichier texte oblige à
ouvrir un terminal et taper « touch ». Sur un système qui vise des gens qui
n'ouvriront jamais de terminal, c'est une impasse.

Rien à inventer : le mécanisme existe depuis toujours, il n'était simplement
pas amorcé. On dépose donc quelques modèles vides.

Le dossier à remplir n'est pas devinable : son nom dépend de la langue —
« Modèles » en français, « Templates » en anglais — et il est déclaré dans
~/.config/user-dirs.dirs. On lit cette déclaration quand elle existe, et on
n'écrit la nôtre que dans un dossier personnel d'Espace, jamais dans celui de
l'utilisateur.
"""
import os
import shutil

SOURCE = "/usr/share/codebyr/modeles"
DECLARATION = ".config/user-dirs.dirs"
DEFAUT = "Modèles"


def dossier_declare(contenu, cle="XDG_TEMPLATES_DIR"):
    """Le dossier déclaré dans user-dirs.dirs, relatif au dossier personnel.

    Décision pure : le fichier est écrit par xdg-user-dirs, dans une syntaxe
    shell dont on ne lit qu'une ligne. Renvoie None si rien n'est déclaré.
    """
    for ligne in (contenu or "").splitlines():
        ligne = ligne.strip()
        if not ligne.startswith(cle + "="):
            continue
        valeur = ligne.split("=", 1)[1].strip().strip('"').strip("'")
        # « $HOME/Modèles » est la forme écrite par xdg-user-dirs.
        if valeur.startswith("$HOME/"):
            valeur = valeur[len("$HOME/"):]
        elif valeur.startswith("/"):
            return valeur
        return valeur or None
    return None


def a_installer(modeles, presents):
    """Ce qu'il faut déposer : ce qui manque, et rien d'autre.

    On ne remplace jamais un modèle existant. Quelqu'un qui a personnalisé le
    sien l'a fait exprès, et le lui réécrire à chaque ouverture d'Espace serait
    une façon très sûre de le fâcher.
    """
    return [m for m in modeles if m not in presents]


def installer(home, source=SOURCE):
    """Dépose les modèles manquants dans le dossier Modèles d'un HOME.

    Renvoie le nombre de fichiers déposés. Un échec n'est jamais fatal : ne pas
    avoir de modèles est un désagrément, pas une panne.
    """
    try:
        modeles = sorted(os.listdir(source))
    except OSError:
        return 0
    if not modeles:
        return 0

    fichier = os.path.join(home, DECLARATION)
    declare = None
    try:
        with open(fichier, encoding="utf-8") as f:
            declare = dossier_declare(f.read())
    except OSError:
        pass

    if not declare:
        # Sans DÉCLARATION, GNOME ne sait pas où chercher : ce chemin n'a aucune
        # valeur par défaut, il est écrit par xdg-user-dirs à la première
        # connexion — un programme qui ne tourne jamais dans un bac à sable.
        # Le dossier existait donc dans les Espaces, et personne ne le
        # regardait : « Nouveau document » n'apparaissait que sur le bureau.
        declare = DEFAUT
        try:
            os.makedirs(os.path.dirname(fichier), exist_ok=True)
            with open(fichier, "a", encoding="utf-8") as f:
                f.write('XDG_TEMPLATES_DIR="$HOME/%s"\n' % DEFAUT)
        except OSError:
            pass

    cible = declare if os.path.isabs(declare) else os.path.join(home, declare)

    try:
        os.makedirs(cible, exist_ok=True)
        presents = set(os.listdir(cible))
    except OSError:
        return 0

    poses = 0
    for nom in a_installer(modeles, presents):
        try:
            shutil.copy2(os.path.join(source, nom), os.path.join(cible, nom))
            poses += 1
        except OSError:
            continue
    return poses
