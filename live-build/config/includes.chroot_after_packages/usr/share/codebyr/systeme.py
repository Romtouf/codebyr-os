# -*- coding: utf-8 -*-
"""Détection de l'environnement — sommes-nous sur le support live, ou installés ?

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

La question paraît triviale ; elle ne l'est pas. On la posait en cherchant si
Calamares était installé, en supposant que son retrait à la fin de
l'installation ferait foi. Mais ce retrait passe par apt, et l'installation de
Codebyr OS se fait **hors ligne** : il peut échouer sans que rien ne le
signale. Résultat, sur une machine pourtant installée depuis des semaines, le
tour de bienvenue continuait de proposer « Installer Codebyr OS sur ce disque ».

Le support live, lui, laisse des traces que rien ne peut effacer : le
répertoire monté par live-boot, et le paramètre passé au noyau au démarrage.
"""
import os

# live-boot monte le support ici ; l'ancien emplacement est gardé par sécurité.
DOSSIERS_LIVE = ("/run/live", "/lib/live/mount/medium")
CMDLINE = "/proc/cmdline"


def est_live(cmdline, dossiers_presents):
    """Décision pure, sans accès disque — pour pouvoir la tester.

    cmdline           : contenu de /proc/cmdline
    dossiers_presents : les chemins de DOSSIERS_LIVE réellement présents
    """
    if dossiers_presents:
        return True
    return "boot=live" in (cmdline or "").split()


def session_live():
    """Vrai si le système tourne depuis le support live (clé USB, DVD, ISO)."""
    presents = [d for d in DOSSIERS_LIVE if os.path.isdir(d)]
    cmdline = ""
    try:
        with open(CMDLINE, encoding="utf-8") as f:
            cmdline = f.read()
    except OSError:
        pass
    return est_live(cmdline, presents)
