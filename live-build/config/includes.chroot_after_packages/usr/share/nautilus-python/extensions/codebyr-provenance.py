# -*- coding: utf-8 -*-
"""Affiche l'Espace d'origine des fichiers dans le gestionnaire de fichiers.

Les Espaces cloisonnent les processus, pas les fichiers. Un document
téléchargé dans Navigation, envoyé dans Travail puis ouvert, s'y exécute avec
les droits de Travail : le bac à sable a tenu, c'est l'utilisateur qui a porté
la menace de l'autre côté — d'un geste que le clic droit encourage désormais.

Cette extension rend cette traversée VISIBLE. Elle ajoute une colonne
« Espace d'origine » : un document orange posé au milieu de vos dossiers
violets se remarque, exactement comme un liseré de fenêtre.

Une COLONNE, et pas une pastille colorée. La pastille serait plus jolie, mais
elle repose sur des emblèmes du thème d'icônes — et une icône qui ne se charge
pas ne laisse rien à l'écran, sans le moindre message. Le projet a déjà perdu
une soirée là-dessus le 23/08/2026. Du texte s'affiche ou ne s'affiche pas :
on le voit tout de suite.

Installé dans /usr/share/nautilus-python/extensions/ ; nécessite python3-nautilus.
"""
import os
import subprocess
import sys

import gi
gi.require_version("Nautilus", "4.0")
from gi.repository import GObject, Nautilus  # noqa: E402

# Le module partagé décide, valide et lit l'attribut. On ne réimplémente rien
# ici : ce projet a déjà payé le prix de quatre lectures divergentes du
# registre.
sys.path.insert(0, os.environ.get("CODEBYR_LIB", "/usr/share/codebyr"))
try:
    import provenance
    import registre
except ImportError:      # pragma: no cover — modules partagés absents
    provenance = None
    registre = None

SPACE = "/usr/bin/codebyr-space"
ATTRIBUT = "codebyr::origine"

# Même racine que codebyr-space. Un fichier encore dans son Espace n'a pas
# besoin d'attribut : son emplacement dit d'où il vient.
DONNEES = os.path.expanduser("~/.local/share/codebyr/espaces")


def _noms():
    """Identifiant d'Espace → nom lisible, pour ne pas afficher « navigation »."""
    if registre is None:
        return {}
    try:
        return {e["id"]: e.get("nom") or e["id"]
                for e in registre.charger()["espaces"] if e.get("id")}
    except Exception:
        return {}


class CodebyrAdopter(GObject.GObject, Nautilus.MenuProvider):
    """« Ce fichier m'appartient » — après l'avoir examiné sous cloche.

    Sans ce geste, un document légitime venu d'un autre Espace repartirait
    isolé à chaque ouverture, sans qu'on puisse jamais l'annoter ni
    l'enregistrer. C'est ainsi qu'une protection finit désactivée.

    L'entrée n'apparaît QUE sur un fichier réellement étranger, et seulement
    depuis un Espace : ailleurs elle n'aurait rien à adopter.
    """

    def _adopter(self, _element, chemins):
        for chemin in chemins:
            try:
                subprocess.Popen([SPACE, "adopter", chemin],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            except OSError:
                pass

    def _construire(self, fichiers):
        courant = os.environ.get("CODEBYR_ESPACE", "").strip()
        if provenance is None or not courant or not fichiers:
            return []
        if not os.path.exists(SPACE):
            return []
        chemins = []
        for f in fichiers:
            if f.is_directory() or f.get_uri_scheme() != "file":
                return []
            chemin = f.get_location().get_path()
            if not chemin:
                return []
            if not provenance.doit_isoler(provenance.origine(chemin, DONNEES),
                                          courant):
                return []   # rien à adopter : au moins un fichier est déjà chez lui
            chemins.append(chemin)

        element = Nautilus.MenuItem(
            name="Codebyr::Adopter",
            label=("Ce fichier m'appartient" if len(chemins) == 1
                   else "Ces %d fichiers m'appartiennent" % len(chemins)),
            tip="Après l'avoir examiné : il s'ouvrira normalement dans cet "
                "Espace, au lieu de partir sous cloche à chaque fois.")
        element.connect("activate", self._adopter, chemins)
        return [element]

    def get_file_items(self, *args):
        return self._construire(args[-1] if args else None)

    def get_background_items(self, *args):
        return []


class CodebyrProvenance(GObject.GObject,
                        Nautilus.ColumnProvider, Nautilus.InfoProvider):

    def get_columns(self):
        return [Nautilus.Column(
            name="CodebyrProvenance::origine",
            attribute=ATTRIBUT,
            label="Espace d'origine",
            description="L'Espace Codebyr d'où provient ce fichier")]

    def update_file_info(self, fichier):
        # Ni les dossiers ni les emplacements distants : l'attribut se lit sur
        # un fichier local, et interroger un montage réseau à chaque
        # rafraîchissement figerait la fenêtre.
        if provenance is None or fichier.get_uri_scheme() != "file":
            return
        if fichier.is_directory():
            return
        chemin = fichier.get_location().get_path()
        if not chemin:
            return
        venue = provenance.origine(chemin, DONNEES)
        if not venue:
            # Colonne vide plutôt qu'« inconnu » : la plupart des fichiers d'un
            # poste n'ont jamais transité par un Espace, et remplir la colonne
            # de « inconnu » la rendrait illisible là où elle doit alerter.
            fichier.add_string_attribute(ATTRIBUT, "")
            return
        fichier.add_string_attribute(ATTRIBUT, _noms().get(venue, venue))
