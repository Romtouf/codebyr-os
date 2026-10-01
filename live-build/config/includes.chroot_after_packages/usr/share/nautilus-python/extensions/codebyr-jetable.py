# -*- coding: utf-8 -*-
"""Ajoute « Ouvrir en Jetable » au menu contextuel du gestionnaire de fichiers.

C'est le geste naturel — clic droit sur une pièce jointe douteuse — et il était
promis dans la documentation du projet depuis le début sans jamais exister. Il
fallait passer par le menu du Sceau ou la ligne de commande, c'est-à-dire ne
jamais s'en servir au moment où l'on en a besoin.

Un fichier ouvert ainsi part dans un Espace éphémère, BLINDÉ ET SANS RÉSEAU :
le piège s'exécute dans le vide, ne peut rien envoyer dehors, et disparaît
avec l'Espace à la fermeture.

Installé dans /usr/share/nautilus-python/extensions/ ; nécessite python3-nautilus.
"""
import os
import subprocess
import sys

import gi
gi.require_version("Nautilus", "4.0")
from gi.repository import GObject, Nautilus  # noqa: E402

sys.path.insert(0, os.environ.get("CODEBYR_LIB", "/usr/share/codebyr"))
# Les textes dans la langue de la session. Si le module manquait, le menu
# resterait en français plutôt que de disparaître : Fichiers ne charge pas
# une extension dont l'import échoue.
try:
    from traduction import _, n_  # noqa: E402
except ImportError:
    def _(texte):
        return texte

    def n_(singulier, pluriel, nombre):
        return singulier if nombre <= 1 else pluriel

JETABLE = "/usr/bin/codebyr-jetable"


class CodebyrJetable(GObject.GObject, Nautilus.MenuProvider):
    """Un seul élément de menu, sur les fichiers ordinaires."""

    def _ouvrir(self, _element, chemins):
        for chemin in chemins:
            try:
                subprocess.Popen([JETABLE, chemin],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            except OSError:
                pass

    def _construire(self, fichiers):
        if not fichiers or not os.path.exists(JETABLE):
            return []
        chemins = []
        for f in fichiers:
            # Ni les dossiers, ni ce qui n'est pas sur le disque local : un
            # Espace jetable reçoit une COPIE du fichier, ce qui n'a pas de
            # sens pour une arborescence ou un montage distant.
            if f.is_directory() or f.get_uri_scheme() != "file":
                return []
            chemins.append(f.get_location().get_path())
        if not all(chemins):
            return []

        # « Ouvrir en Jetable » est aussi un texte du menu du Sceau : un même
        # texte ne peut pas être à la fois simple et singulier d'un pluriel.
        libelle = (_("Ouvrir en Jetable") if len(chemins) == 1
                   else n_("Ouvrir {n} fichier en Jetable", "Ouvrir {n} fichiers en Jetable",
                           len(chemins)).format(n=len(chemins)))
        element = Nautilus.MenuItem(
            name="Codebyr::Jetable",
            label=libelle,
            tip=_("S'ouvre dans un Espace éphémère, sans réseau, détruit à la "
                  "fermeture — un piège ne peut rien envoyer ni rien laisser."))
        element.connect("activate", self._ouvrir, chemins)
        return [element]

    # La signature a changé selon les versions de Nautilus : (window, files)
    # autrefois, (files) depuis la 42. On accepte les deux plutôt que de
    # dépendre d'une version — l'entrée de menu disparaîtrait en silence.
    def get_file_items(self, *args):
        return self._construire(args[-1] if args else None)

    def get_background_items(self, *args):
        return []
