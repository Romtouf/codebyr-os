# -*- coding: utf-8 -*-
"""Chargement des outils Codebyr comme modules Python.

Les scripts `codebyr-*` n'ont pas d'extension `.py` (ce sont des commandes,
pas des bibliothèques) : `import` ne sait donc pas les trouver. On les charge
explicitement par leur chemin. Importer un de ces fichiers n'exécute que ses
constantes et ses définitions — `main()` reste protégé par `__main__`.
"""
import importlib.machinery
import importlib.util
import os
import sys

# Charger ces scripts écrirait un __pycache__ À CÔTÉ d'eux, c'est-à-dire dans
# l'arborescence copiée telle quelle dans l'ISO. Les tests ne doivent rien
# déposer dans l'image.
sys.dont_write_bytecode = True

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(RACINE, "live-build", "config",
                   "includes.chroot_after_packages", "usr", "bin")
ETC = os.path.join(RACINE, "live-build", "config",
                   "includes.chroot_after_packages", "etc")
LIB = os.path.join(RACINE, "live-build", "config",
                   "includes.chroot_after_packages", "usr", "share", "codebyr")

# Les outils chargent leur module partagé depuis CODEBYR_LIB : on les fait
# pointer sur la copie du dépôt, pas sur celle installée sur la machine.
os.environ["CODEBYR_LIB"] = LIB
if LIB not in sys.path:
    sys.path.insert(0, LIB)


def charger(nom):
    """Charge /usr/bin/<nom> du dépôt comme module Python."""
    chemin = os.path.join(BIN, nom)
    loader = importlib.machinery.SourceFileLoader(nom.replace("-", "_"), chemin)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module
