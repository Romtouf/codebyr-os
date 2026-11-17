# -*- coding: utf-8 -*-
"""L'application qui aurait ouvert ce document si Codebyr ne s'était pas interposé.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Pour qu'un document posé sur une clé USB parte sous cloche quand on
double-clique dessus, l'ouvreur de Codebyr est l'application par défaut DU
BUREAU pour les documents (/etc/xdg/mimeapps.list). Or l'immense majorité de
ces ouvertures ne concernent ni une clé ni un autre Espace : elles doivent
aboutir exactement là où elles aboutissaient avant, dans la visionneuse de PDF
ou le traitement de texte de l'utilisateur, y compris celui installé depuis
Flathub.

Demander à GNOME (« xdg-open », « gio open ») renverrait vers l'ouvreur
lui-même : une boucle. Et sa liste de secours place le Jetable en tête, faute
d'ordre défini entre applications de même rang. Ce module relit donc les préférences
dans l'ordre de la spécification freedesktop (mime-apps-spec 1.0), en sautant
les entrées de Codebyr.

Les préférences de l'utilisateur passent avant celles du système, comme
partout ailleurs : quelqu'un qui a choisi « toujours ouvrir les PDF avec… » a
fait un choix, et Codebyr ne le lui reprend pas — même si cela veut dire que
ses PDF de clé USB ne passent plus par la cloche.
"""
import mimetypes
import os
import shutil
import subprocess

# Toutes les entrées de Codebyr — l'ouvreur et le Jetable — sont sautées :
# l'une ferait boucler, l'autre enverrait sous cloche un fichier ordinaire.
PREFIXE_CODEBYR = "io.codebyr."


def _liste(env, nom, defaut):
    return [d for d in (env.get(nom) or defaut).split(":") if d]


def _maisons(env, home):
    home = home or env.get("HOME") or os.path.expanduser("~")
    config = env.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    donnees = env.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    return config, donnees


def dossiers_d_applications(env=None, home=None):
    """Où chercher les fichiers .desktop, du plus prioritaire au moins."""
    env = os.environ if env is None else env
    _config, donnees = _maisons(env, home)
    return ([os.path.join(donnees, "applications")]
            + [os.path.join(d, "applications")
               for d in _liste(env, "XDG_DATA_DIRS", "/usr/local/share:/usr/share")])


def fichiers_de_preferences(env=None, home=None):
    """Les mimeapps.list, dans l'ordre où ils comptent.

    Les dossiers de configuration passent avant ceux de données, et dans un
    même dossier le fichier propre au bureau (« gnome-mimeapps.list ») passe
    avant le fichier commun.
    """
    env = os.environ if env is None else env
    config, _donnees = _maisons(env, home)
    bureaux = [b.lower() for b in _liste(env, "XDG_CURRENT_DESKTOP", "")]
    dossiers = ([config] + _liste(env, "XDG_CONFIG_DIRS", "/etc/xdg")
                + dossiers_d_applications(env, home))
    fichiers = []
    for dossier in dossiers:
        fichiers += [os.path.join(dossier, "%s-mimeapps.list" % b) for b in bureaux]
        fichiers.append(os.path.join(dossier, "mimeapps.list"))
    return fichiers


def section(contenu, nom, type_mime):
    """Les identifiants d'applications listés pour ce type dans une section."""
    dedans = False
    for ligne in (contenu or "").splitlines():
        ligne = ligne.strip()
        if ligne.startswith("["):
            dedans = ligne == "[%s]" % nom
            continue
        if dedans and "=" in ligne:
            cle, valeur = ligne.split("=", 1)
            if cle.strip() == type_mime:
                return [v.strip() for v in valeur.split(";") if v.strip()]
    return []


def choisir(type_mime, lire, installee, fichiers, caches):
    """Décision pure : l'identifiant de l'application habituelle, ou None.

    lire(chemin) rend le contenu d'un fichier (« » s'il manque) ;
    installee(identifiant) dit si l'application est là.

    D'abord les applications par défaut, fichier par fichier ; puis les
    associations ajoutées ; puis tout ce qui se déclare capable du type
    (mimeinfo.cache — c'est ainsi qu'on trouve une application Flatpak).
    Une association retirée par l'utilisateur ne revient pas par ces
    deux derniers chemins.
    """
    retirees = set()
    for f in fichiers:
        retirees.update(section(lire(f), "Removed Associations", type_mime))

    def premiere(ids, sauf=()):
        for app in ids:
            if app.startswith(PREFIXE_CODEBYR) or app in sauf:
                continue
            if installee(app):
                return app
        return None

    for f in fichiers:
        trouvee = premiere(section(lire(f), "Default Applications", type_mime))
        if trouvee:
            return trouvee
    for f in fichiers:
        trouvee = premiere(section(lire(f), "Added Associations", type_mime), retirees)
        if trouvee:
            return trouvee
    for c in caches:
        trouvee = premiere(section(lire(c), "MIME Cache", type_mime), retirees)
        if trouvee:
            return trouvee
    return None


# ── Accès disque ────────────────────────────────────────────────────────────

def _lire(chemin):
    try:
        with open(chemin, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def chemin_du_desktop(app, dossiers):
    """Le fichier .desktop de cette application, ou None s'il est absent ou masqué."""
    if not app.endswith(".desktop") or "/" in app:
        return None
    for dossier in dossiers:
        chemin = os.path.join(dossier, app)
        if os.path.isfile(chemin):
            # « Hidden=true » vaut suppression (spécification des .desktop) :
            # c'est ainsi qu'on masque une application du système.
            for ligne in _lire(chemin).splitlines():
                if ligne.strip().replace(" ", "") == "Hidden=true":
                    return None
            return chemin
    return None


def type_dans_la_sortie(sortie):
    """Le type lu dans la sortie de « gio info », ou None.

    La DERNIÈRE ligne d'attribut : les chemins s'affichent avant les
    attributs, et un nom de fichier — choisi par qui a préparé la clé — peut
    contenir un retour à la ligne suivi d'une fausse ligne d'attribut.
    """
    trouve = None
    for ligne in (sortie or "").splitlines():
        ligne = ligne.strip()
        if ligne.startswith("standard::content-type: "):
            trouve = ligne.split(": ", 1)[1].strip() or None
    return trouve


def type_du_fichier(chemin):
    """Le type MIME tel que GNOME le voit (contenu compris), ou None.

    « gio info » d'abord : c'est la même base (shared-mime-info) que celle qui
    a choisi l'ouvreur, et elle lit le contenu — un PDF sans extension reste un
    PDF. À défaut, l'extension.
    """
    try:
        trouve = type_dans_la_sortie(subprocess.run(
            ["gio", "info", "--attributes=standard::content-type", "--", chemin],
            capture_output=True, text=True, timeout=10,
            env=dict(os.environ, LC_ALL="C.UTF-8")).stdout)
        if trouve:
            return trouve
    except (OSError, subprocess.SubprocessError, UnicodeError):
        pass
    return mimetypes.guess_type(chemin)[0]


def commande_habituelle(chemin, env=None, home=None):
    """La commande qui ouvre ce fichier avec l'application habituelle, ou None.

    « gio launch » reçoit le .desktop lui-même : l'application démarre comme
    depuis le menu (activation D-Bus, notification de démarrage), sans repasser
    par le choix de GNOME — donc sans revenir ici.
    """
    if not shutil.which("gio"):
        return None
    type_mime = type_du_fichier(chemin)
    if not type_mime:
        return None
    dossiers = dossiers_d_applications(env, home)
    app = choisir(type_mime, _lire,
                  lambda a: chemin_du_desktop(a, dossiers) is not None,
                  fichiers_de_preferences(env, home),
                  [os.path.join(d, "mimeinfo.cache") for d in dossiers])
    if not app:
        return None
    return ["gio", "launch", chemin_du_desktop(app, dossiers)]
