# -*- coding: utf-8 -*-
"""Détection des applications installées, par leurs fichiers `.desktop`.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Cette logique vivait dans `codebyr-config`, un fichier qui importe GTK — donc
impossible à charger dans un test sans environnement graphique. Elle décide
pourtant de ce que l'utilisateur verra dans le menu du Sceau : une entrée mal
analysée, et l'application est simplement absente, sans message.
"""
import configparser
import glob
import os
import re
import shlex

DOSSIERS = (
    "/usr/share/applications",
    "/var/lib/flatpak/exports/share/applications",
    "~/.local/share/applications",
    "~/.local/share/flatpak/exports/share/applications",
)

# %U, %f, %i… : les « codes de champ » que le lanceur doit remplacer. On lance
# sans argument, ils n'ont donc rien à faire dans la commande.
CODES_DE_CHAMP = re.compile(r"%[fFuUdDnNickvm]")


def _entree(chemin):
    """Lit la section [Desktop Entry] d'un fichier, ou None s'il est inutilisable."""
    cp = configparser.RawConfigParser(interpolation=None, strict=False)
    try:
        cp.read(chemin, encoding="utf-8")
    except (OSError, configparser.Error, UnicodeDecodeError):
        return None
    if not cp.has_section("Desktop Entry"):
        return None
    return cp["Desktop Entry"]


def _affichable(entree):
    """Une entrée cachée par son auteur ne doit pas réapparaître chez nous."""
    if entree.get("Type") != "Application":
        return False
    for cle in ("NoDisplay", "Hidden"):
        if entree.get(cle, "false").strip().lower() == "true":
            return False
    return True


def commande(entree, fichier, est_flatpak):
    """La commande à lancer pour cette entrée, ou None."""
    exe = entree.get("Exec", "")
    if not exe:
        return None
    if est_flatpak:
        # Pour un Flatpak, la ligne Exec contient des jetons « @@ » propres au
        # lanceur. L'identifiant du .desktop suffit et donne une commande stable.
        return "flatpak run " + os.path.basename(fichier)[:-len(".desktop")]
    return re.sub(r"\s+", " ", CODES_DE_CHAMP.sub("", exe)).strip() or None


def installees(dossiers=None):
    """(nom, commande) de chaque application installée, triés, sans doublon.

    Le paramètre `dossiers` n'existe que pour les tests : en usage réel, ce
    sont les emplacements standard.
    """
    if dossiers is None:
        dossiers = [os.path.expanduser(d) for d in DOSSIERS]
    vus = {}
    for dossier in dossiers:
        est_flatpak = "flatpak" in dossier
        for fichier in sorted(glob.glob(os.path.join(dossier, "*.desktop"))):
            base = os.path.basename(fichier)
            if base.lower().startswith(("io.codebyr.", "codebyr")):
                continue           # nos propres lanceurs internes
            entree = _entree(fichier)
            if entree is None or not _affichable(entree):
                continue
            nom = entree.get("Name[fr]") or entree.get("Name")
            cmd = commande(entree, fichier, est_flatpak)
            if nom and cmd and nom not in vus:
                vus[nom] = cmd
    return sorted(vus.items(), key=lambda couple: couple[0].lower())


def resoudre(desktop_id, dossiers=None):
    """Commande à lancer pour un identifiant `.desktop`, sous forme d'arguments.

    Deux pièges évités par rapport à une lecture naïve du fichier :

    · un `.desktop` peut contenir plusieurs lignes `Exec=` — celles des groupes
      « [Desktop Action …] » (« Ouvrir une fenêtre privée », par exemple). Lire
      la première venue peut donc lancer autre chose que l'application ;
    · une ligne `Exec` obéit aux règles de découpage du shell :
      `Exec="/opt/Mon App/bin" %U` est UNE commande, pas deux. Un découpage sur
      les espaces la casse en morceaux.

    Si l'identifiant ne correspond à aucun fichier, on suppose une commande
    brute (« firefox-esr ») : c'est le cas des applications lancées par nom.
    """
    if dossiers is None:
        dossiers = [os.path.expanduser(d) for d in DOSSIERS]
    for dossier in dossiers:
        chemin = os.path.join(dossier, desktop_id)
        if not os.path.exists(chemin):
            continue
        entree = _entree(chemin)          # ne lit QUE [Desktop Entry]
        if entree is None:
            continue
        cmd = commande(entree, chemin, "flatpak" in dossier)
        if not cmd:
            continue
        try:
            parts = shlex.split(cmd)
        except ValueError:
            parts = cmd.split()
        if parts:
            return parts
    return [desktop_id.replace(".desktop", "")]
