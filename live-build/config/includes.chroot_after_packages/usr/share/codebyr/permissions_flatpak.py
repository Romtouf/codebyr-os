# -*- coding: utf-8 -*-
"""Ce qu'une application Flatpak atteint HORS de l'Espace où on l'ouvre.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Une application Flatpak ne s'ouvre pas dans le bac à sable de Codebyr : elle a
le sien, et deux bacs à sable ne s'imbriquent pas. Dans un Espace ordinaire —
sans compte séparé —, ce sont donc SES permissions qui décident de ce qu'elle
atteint, sous VOTRE compte. Certaines la font sortir de l'Espace tout entier :

· le bus de session du bureau (« --socket=session-bus »), ou les services qui
  lancent des programmes pour qui le leur demande (org.freedesktop.Flatpak,
  c'est-à-dire « flatpak-spawn --host », et systemd) : c'est la sortie de bac à
  sable fermée pour les applications ordinaires en 1.1.0 ;
· les réglages du bureau (ca.desrt.dconf), parmi lesquels la commande qu'un
  raccourci clavier exécute ;
· le système de fichiers entier (« host »), le dossier d'exécution où vit le
  bus de session (« xdg-run »), ou — pour une application installée pour toute
  la machine — les parties décisives de votre dossier personnel : les données
  de TOUS les Espaces, les lanceurs, ce qui s'exécute à l'ouverture de session
  (voir DOSSIERS_DECISIFS).

Une telle application ouverte « dans Travail » portait pourtant le liseré de
Travail. La couleur mentait : c'est ce que ce module permet de refuser.

Sous « Compte séparé », ces mêmes permissions sont bornées par le compte de
l'Espace — qui n'a ni votre dossier personnel, ni votre bus, ni vos réglages.
Le contrôle ne vaut donc que pour les Espaces ordinaires.
"""
import configparser
import subprocess

from traduction import _

# Services de bus dont un seul appel suffit à exécuter hors de tout bac à sable,
# ou à le faire faire au bureau. « talk » et « own » y donnent accès ; « see »
# ne permet que de constater leur présence.
BUS_QUI_FONT_SORTIR = {
    "org.freedesktop.Flatpak":
        _("lancer des programmes sur le bureau, hors de tout bac à sable"),
    "org.freedesktop.systemd1":
        _("lancer des programmes sur le bureau, hors de tout bac à sable"),
    "ca.desrt.dconf":
        _("modifier les réglages du bureau — dont la commande d'un raccourci clavier"),
}

# Options de « flatpak run » qui AJOUTENT une permission à celles déclarées.
OPTIONS_QUI_ACCORDENT = (
    "--share", "--socket", "--device", "--allow", "--filesystem", "--own-name",
    "--talk-name", "--system-own-name", "--system-talk-name", "--add-policy",
)

# Ce que votre dossier personnel contient de décisif, relatif à lui. Écrire ici,
# c'est agir HORS de l'Espace : les données des autres Espaces, les lanceurs
# d'applications, ce qui s'exécute à l'ouverture de session (autostart,
# systemd, profils du shell, ~/.local/bin qui entre dans le PATH), et les
# installations Flatpak — la vôtre comme celles des Espaces.
#
# Un chemin qui CONTIENT l'un d'eux (« ~ », « ~/.config ») est refusé ; un
# chemin à côté (« ~/.local/share/Steam ») ne l'est pas.
DOSSIERS_DECISIFS = (
    ".local/share/codebyr", ".config/codebyr",
    ".config/autostart", ".config/systemd", ".config/environment.d",
    ".local/share/applications", ".local/share/flatpak", ".local/bin",
    ".bashrc", ".profile", ".bash_profile", ".bash_login", ".pam_environment",
)

# Les dossiers XDG, traduits en chemins relatifs au dossier personnel.
XDG_EN_CLAIR = {"xdg-config": ".config", "xdg-data": ".local/share"}

TOUT_VOIR = _("voir tous vos fichiers, ceux des autres Espaces compris")
LE_BUS = _("joindre le bus de session du bureau, donc y lancer des programmes")
LE_DOSSIER = (_("atteindre votre dossier personnel, où vivent les données de tous "
                "les Espaces et les programmes lancés à l'ouverture de session"))


def incompatibilite(esp, renforce, hors_ligne, sous_compte):
    """Ce qui empêche TOUTE application Flatpak de s'ouvrir dans cet Espace.

    Renvoie une raison (texte), ou None. Une application Flatpak garde son
    propre bac à sable : elle ne peut pas recevoir les promesses que Codebyr
    fait par le sien.

    · Réseau coupé ou restreint (pièce jointe, Banque) : ses permissions
      décident de son réseau, et la promesse ne serait pas tenue.
    · Espace jetable : il n'y a rien où l'installer durablement.
    · Blindage : refusé dans un Espace ordinaire — rien n'y borne
      l'application. Accepté sous compte séparé depuis la 1.16.1 : le compte
      de l'Espace la borne, et le lanceur dit qu'elle a le bac à sable de
      Flatpak, pas le Blindage. Sans cette exception, aucun Espace livré
      n'accepterait plus une application Flatpak, Personnel et Travail étant
      blindés depuis la 1.16.1.
    """
    if hors_ligne or (esp.get("reseau") or {}).get("mode") == "liste-blanche":
        return _("Son réseau dépend de ses propres permissions : le réseau restreint de cet Espace ne serait pas tenu.")
    if esp.get("ephemere"):
        return _("Un Espace jetable ne garde rien : l'application n'y a pas sa place.")
    if renforce and not sous_compte:
        return (_("Son bac à sable est celui de Flatpak, pas le Blindage de cet Espace. "
                  "Activez « Compte séparé » pour cet Espace : son compte la bornera."))
    return None


def identifiant(argv):
    """L'application que lance « flatpak run … », ou None.

    Le dernier argument ne convient pas : une commande prise dans un fichier
    .desktop se termine par les jetons de transmission de fichiers (« @@ »),
    et l'on cherchait alors une application nommée « @@ ».
    """
    try:
        debut = argv.index("run") + 1
    except ValueError:
        return None
    for argument in argv[debut:]:
        if argument.startswith("-"):
            continue
        # « app/org.x.Y/x86_64/stable » ou « org.x.Y//stable » : la référence
        # complète désigne la même application.
        if argument.startswith("app/"):
            morceaux = argument.split("/")
            argument = morceaux[1] if len(morceaux) > 1 else ""
        return argument.split("//")[0] or None
    return None


def options_accordees(argv):
    """Les raisons de refuser tenant à la ligne de commande elle-même."""
    try:
        debut = argv.index("run") + 1
    except ValueError:
        return []
    raisons = []
    for argument in argv[debut:]:
        if not argument.startswith("-"):
            break           # l'application : ce qui suit est à elle
        if argument.split("=", 1)[0] in OPTIONS_QUI_ACCORDENT:
            raisons.append(_("recevoir une permission ajoutée à sa ligne de "
                             "commande (%s)") % argument)
    return raisons


def lire(texte):
    """Le résultat de « flatpak info --show-permissions », section par section."""
    lecteur = configparser.RawConfigParser(interpolation=None, strict=False,
                                           delimiters=("=",))
    lecteur.optionxform = str          # les noms de bus sont sensibles à la casse
    lecteur.read_string(texte)
    return {section: dict(lecteur[section]) for section in lecteur.sections()}


def _liste(valeur):
    return [v.strip() for v in (valeur or "").split(";") if v.strip()]


def _couvre(politique, nom):
    """La politique « politique » (éventuellement « x.y.* ») donne-t-elle « nom » ?"""
    if politique.endswith(".*"):
        prefixe = politique[:-2]
        return nom == prefixe or nom.startswith(prefixe + ".")
    return politique == nom


def _relatif_au_dossier_personnel(chemin):
    """« ~/x », « home », « xdg-config/y »… en chemin relatif, ou None."""
    if chemin in ("home", "~"):
        return ""
    if chemin.startswith("~/"):
        return chemin[2:].strip("/")
    for xdg, clair in XDG_EN_CLAIR.items():
        if chemin == xdg:
            return clair
        if chemin.startswith(xdg + "/"):
            return clair + "/" + chemin[len(xdg) + 1:].strip("/")
    return None


def _touche_un_dossier_decisif(relatif):
    for decisif in DOSSIERS_DECISIFS:
        if (relatif == "" or relatif == decisif or decisif.startswith(relatif + "/")
                or relatif.startswith(decisif + "/")):
            return True
    return False


def _chemin(entree):
    """Une entrée « filesystems » sans son mode (« :ro », « :rw », « :create »)."""
    chemin, _, mode = entree.rpartition(":")
    if chemin and mode in ("ro", "rw", "create"):
        return chemin
    return entree


def sorties(permissions, dossier_de_l_espace):
    """Les raisons, en clair, pour lesquelles l'application sortirait de l'Espace.

    dossier_de_l_espace : vrai quand l'application est installée DANS l'Espace.
    Elle y est alors lancée avec le dossier personnel de l'Espace, et « home »,
    « ~ » ou « xdg-config » désignent ce dossier-là, pas le vôtre.

    Liste vide : rien de ce qui est connu pour faire sortir de l'Espace.
    """
    contexte = permissions.get("Context", {})
    raisons = []

    if "session-bus" in _liste(contexte.get("sockets")):
        raisons.append(LE_BUS)

    for politique, niveau in permissions.get("Session Bus Policy", {}).items():
        if niveau.strip() not in ("talk", "own"):
            continue
        for nom, raison in BUS_QUI_FONT_SORTIR.items():
            if _couvre(politique.strip(), nom):
                raisons.append(raison)

    for entree in _liste(contexte.get("filesystems")):
        if entree.startswith("!"):
            continue        # permission RETIRÉE (flatpak override --nofilesystem)
        chemin = _chemin(entree)
        if chemin in ("host", "/") or chemin.startswith(("/home", "/var/home")):
            raisons.append(TOUT_VOIR)
        elif (chemin == "xdg-run" or chemin.startswith(("xdg-run/bus", "xdg-run/systemd"))
              or chemin.startswith("/run/user")):
            # Le dossier d'exécution n'est pas celui de l'Espace, même pour une
            # application installée dans l'Espace : c'est celui du bureau.
            raisons.append(LE_BUS)
        elif not dossier_de_l_espace:
            relatif = _relatif_au_dossier_personnel(chemin)
            if relatif is not None and _touche_un_dossier_decisif(relatif):
                raisons.append(LE_DOSSIER)

    # Une raison par sorte, dans l'ordre où on les a trouvées.
    return list(dict.fromkeys(raisons))


def lire_permissions(appid, env):
    """Les permissions effectives d'une application (surcharges comprises), ou None.

    None — flatpak absent, application introuvable, sortie illisible — veut
    dire qu'on ne sait pas : l'appelant refuse, comme partout ailleurs ici.
    """
    try:
        sortie = subprocess.run(["flatpak", "info", "--show-permissions", appid],
                                env=env, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if sortie.returncode != 0:
        return None
    try:
        return lire(sortie.stdout)
    except configparser.Error:
        return None
