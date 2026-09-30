# -*- coding: utf-8 -*-
"""Les applications Flatpak d'un Espace : où elles vivent, avec quel environnement.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Sorti de codebyr-space en 1.17.0 (découpage, audit point 8), sans changement de
comportement. Deux cas :
  · un Espace ordinaire garde son installation à côté de son dossier personnel
    (chemins.flatpak) ;
  · un Espace à compte dédié la garde dans son dossier interne, sous son
    propre compte : c'est lui qui installe, lance et désinstalle.
Ce qui fait sortir une application de son Espace est décidé dans
permissions_flatpak.py.
"""
import os
import re
import subprocess

import chemins
import permissions_flatpak

FLATHUB_REPO = "/etc/flatpak/remotes.d/flathub.flatpakrepo"

# Un identifiant d'application Flatpak : org.gnome.Calculator. Vérifié avant
# d'entrer dans une commande ET avant d'entrer dans un chemin — c'est le seul
# morceau de ces ordres qui vienne de l'extérieur.
FORME_APPID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*(\.[A-Za-z0-9][A-Za-z0-9_-]*){1,8}\Z")


def dossier_dedie(home):
    """Installation Flatpak d'un Espace à compte dédié, dans son dossier interne.

    Sous « .codebyr » et non sous ~/.local/share : ce dossier est le seul que
    la sauvegarde et le retour au compte du bureau laissent de côté. Des
    centaines de mégaoctets de binaires, retéléchargeables d'un geste, n'ont
    rien à faire dans une archive — c'est déjà le choix fait pour les Espaces
    ordinaires, où l'installation vit à côté du dossier personnel.
    """
    return os.path.join(home, chemins.DOSSIER_INTERNE, "flatpak")


def env_dedie(esp, session, env):
    """L'environnement d'une application Flatpak sous compte dédié.

    Construit, jamais hérité : celui du bureau désigne SON dossier d'exécution
    et SON bus de session, auxquels le compte de l'Espace n'a aucun droit.
    L'application les chercherait, ne les trouverait pas, et échouerait sans
    dire pourquoi.

    Le bus est celui de l'Espace (voir codebyr-espace-init) : c'est par lui que
    l'application joint ses portails — « Ouvrir un fichier », l'impression.
    """
    runtime = session.runtime
    return {
        "PATH": "/usr/bin:/bin",
        "LANG": env.get("LANG") or "C.UTF-8",
        "HOME": session.home,
        "XDG_RUNTIME_DIR": runtime,
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + os.path.join(runtime, "bus"),
        "WAYLAND_DISPLAY": os.path.basename(env.get("WAYLAND_DISPLAY") or "wayland-0"),
        "XDG_SESSION_TYPE": "wayland",
        "XDG_CURRENT_DESKTOP": "GNOME",
        "GDK_BACKEND": "wayland",
        "FLATPAK_USER_DIR": dossier_dedie(session.home),
        "CODEBYR_ESPACE": esp["id"],
        "CODEBYR_ESPACE_COULEUR": esp.get("couleur", "#888888"),
    }


def env_ordinaire(esp_id):
    """Environnement pointant l'installation Flatpak propre à un Espace ordinaire."""
    d = chemins.flatpak(esp_id)
    os.makedirs(d, exist_ok=True)
    env = dict(os.environ)
    env["FLATPAK_USER_DIR"] = d
    return env, d


def app_dans_espace(esp_id, appid):
    """L'application est-elle installée DANS l'Espace (et non au niveau système) ?"""
    return os.path.isdir(os.path.join(chemins.flatpak(esp_id), "app", appid))


def sorties(esp, app_cmd, appid):
    """Pourquoi cette application Flatpak sortirait de cet Espace ordinaire.

    Liste vide : rien de connu. Dans le doute — identifiant illisible,
    permissions introuvables —, on refuse, comme partout ailleurs ici.
    Voir permissions_flatpak.py pour ce qui fait sortir, et pourquoi.
    """
    raisons = permissions_flatpak.options_accordees(app_cmd)
    if not appid or not FORME_APPID.match(appid):
        return raisons + ["échapper à tout contrôle : son identifiant est illisible"]
    env = dict(os.environ)
    dans_l_espace = app_dans_espace(esp["id"], appid)
    if dans_l_espace:
        env["FLATPAK_USER_DIR"] = chemins.flatpak(esp["id"])
    permissions = permissions_flatpak.lire_permissions(appid, env)
    if permissions is None:
        return raisons + ["échapper à tout contrôle : ses permissions n'ont pas pu être lues"]
    return raisons + permissions_flatpak.sorties(permissions, dans_l_espace)


def assurer_flathub(env):
    """Ajoute le dépôt Flathub à l'installation de l'Espace (fichier local → hors-ligne OK)."""
    src = FLATHUB_REPO if os.path.exists(FLATHUB_REPO) else \
        "https://flathub.org/repo/flathub.flatpakrepo"
    subprocess.run(["flatpak", "--user", "remote-add", "--if-not-exists", "flathub", src],
                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def nom_lisible(env, appid):
    """Le nom d'une application installée, tel que Flatpak l'affiche, ou None."""
    try:
        out = subprocess.check_output(
            ["flatpak", "--user", "list", "--app", "--columns=application,name"],
            env=env, text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, OSError):
        return None
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0] == appid:
            return parts[1].strip()
    return None
