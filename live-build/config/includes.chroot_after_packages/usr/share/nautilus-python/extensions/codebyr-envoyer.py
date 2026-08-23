# -*- coding: utf-8 -*-
"""Ajoute « Envoyer vers l'Espace… » au menu contextuel du gestionnaire de fichiers.

Annoncé dans l'architecture du projet depuis le début, marqué `[visé]`, et
jamais réalisé : faire passer un document d'un Espace à l'autre demandait
d'exporter un instantané ou de passer par le presse-papiers. Autant dire que
personne ne le faisait.

À ne pas confondre avec « Ouvrir en Jetable », qui est le geste de la MÉFIANCE :
une pièce jointe douteuse, examinée blindée et sans réseau. Celui-ci est le
geste inverse — on classe un document dont on ne se méfie pas, et l'Espace de
destination reste ce qu'il est.

Le fichier est COPIÉ : l'original ne bouge pas. Franchir une frontière entre
Espaces ne doit jamais faire disparaître ce qu'on avait avant.

Installé dans /usr/share/nautilus-python/extensions/ ; nécessite python3-nautilus.
"""
import os
import subprocess
import sys

import gi
gi.require_version("Nautilus", "4.0")
from gi.repository import GObject, Nautilus  # noqa: E402

SPACE = "/usr/bin/codebyr-space"

# Le registre a UNE implémentation, partagée. Elle en a eu quatre, et c'est
# ainsi qu'elles ont divergé : le calque de l'utilisateur remplaçait les
# défauts du système au lieu de s'y superposer, si bien que plus on
# configurait son système, moins les durcissements livrés l'atteignaient.
# Corrigé en 1.2.0 — on ne rouvre pas cette porte pour un menu contextuel.
sys.path.insert(0, os.environ.get("CODEBYR_LIB", "/usr/share/codebyr"))
try:
    import registre
except ImportError:      # pragma: no cover — module partagé absent
    registre = None


def espaces_disponibles():
    """Les Espaces où l'on peut déposer quelque chose.

    Les Espaces éphémères sont écartés : leur dossier vit en mémoire et
    disparaît à la fermeture. « Classer » un document dans un Jetable
    reviendrait à le jeter, avec la mise en page d'un rangement.
    """
    if registre is None:
        return []
    try:
        liste = registre.charger()["espaces"]
    except Exception:
        return []
    return [(e["id"], e.get("nom") or e["id"]) for e in liste
            if e.get("id") and not e.get("ephemere")]


class CodebyrEnvoyer(GObject.GObject, Nautilus.MenuProvider):
    """Un sous-menu listant les Espaces de destination."""

    def _envoyer(self, _element, esp_id, chemins):
        for chemin in chemins:
            try:
                subprocess.Popen([SPACE, "envoyer", esp_id, chemin],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            except OSError:
                pass

    def _construire(self, fichiers):
        if not fichiers or not os.path.exists(SPACE):
            return []
        chemins = []
        for f in fichiers:
            # Ni dossiers ni emplacements distants : on copie un fichier
            # ordinaire, ce qui n'a pas de sens pour une arborescence ou un
            # montage réseau.
            if f.is_directory() or f.get_uri_scheme() != "file":
                return []
            chemins.append(f.get_location().get_path())
        if not all(chemins):
            return []

        espaces = espaces_disponibles()
        if not espaces:
            return []

        libelle = ("Envoyer vers l'Espace" if len(chemins) == 1
                   else "Envoyer %d fichiers vers l'Espace" % len(chemins))
        parent = Nautilus.MenuItem(
            name="Codebyr::Envoyer", label=libelle,
            tip="Y dépose une copie, dans le dossier « Partagé » de l'Espace. "
                "L'original ne bouge pas.")
        menu = Nautilus.Menu()
        parent.set_submenu(menu)
        for ident, nom in espaces:
            element = Nautilus.MenuItem(name="Codebyr::Envoyer::" + ident,
                                        label=nom)
            element.connect("activate", self._envoyer, ident, chemins)
            menu.append_item(element)
        return [parent]

    # La signature a changé selon les versions de Nautilus : (window, files)
    # autrefois, (files) depuis la 42. On accepte les deux plutôt que de
    # dépendre d'une version — l'entrée disparaîtrait en silence.
    def get_file_items(self, *args):
        return self._construire(args[-1] if args else None)

    def get_background_items(self, *args):
        return []
