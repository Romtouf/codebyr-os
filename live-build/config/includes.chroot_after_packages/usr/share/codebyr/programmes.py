# -*- coding: utf-8 -*-
"""Les programmes qu'on ajoute au menu d'un Espace : les reconnaître, les lancer.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Sorti de codebyr-space en 1.17.0 (découpage, audit point 8), sans changement de
comportement. Sous compte séparé, lister et préparer se font DANS l'Espace, sous
son compte (voir cmd_interne_programmes) : le bureau ne voit pas son dossier, et
ne reçoit qu'une réponse qu'il revérifie (programme_valide).
"""
import os
import posixpath
import shlex
import stat

MAX_PROGRAMMES = 100
NATURES_PROGRAMME = ("appimage", "elf", "script")


class Refus(Exception):
    """Un programme que l'Espace refuse de préparer : le message dit pourquoi."""

    def __init__(self, message, code=2):
        super().__init__(message)
        self.code = code


def nature_programme(tete):
    """Ce que disent les premiers octets d'un fichier : un programme, ou None.

    Décision pure. Une AppImage est un exécutable ELF marqué « AI » suivi de
    l'octet 2 à la position 8 (AppImage de type 2) ; un script commence par
    « #! ». Le nom du fichier n'entre pas en compte : il ne prouve rien.
    """
    if tete[:4] == b"\x7fELF":
        return "appimage" if tete[8:11] == b"AI\x02" else "elf"
    if tete[:2] == b"#!":
        return "script"
    return None


def commande_programme(chemin, nature, extra=()):
    """La commande inscrite au menu pour un programme ajouté.

    Une AppImage se monte d'ordinaire par FUSE, à travers un outil à
    privilèges — ce que le Blindage interdit (aucun nouveau privilège). Elle
    prévoit elle-même l'autre voie : se décompresser et se lancer sans FUSE.
    """
    cmd = shlex.quote(chemin)
    if nature == "appimage":
        cmd += " --appimage-extract-and-run"
    if extra:
        cmd += " " + " ".join(shlex.quote(a) for a in extra)
    return cmd


def lire_tete(chemin):
    """Les premiers octets d'un fichier ORDINAIRE, sans suivre de lien ni attendre."""
    fd = os.open(chemin, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        return os.read(fd, 16) if stat.S_ISREG(os.fstat(fd).st_mode) else b""
    finally:
        os.close(fd)


def lister_programmes(home, lieux):
    """Les programmes rangés dans les `lieux` du dossier `home` d'un Espace.

    À deux niveaux au plus, sans suivre de lien, sans les dossiers cachés, au
    plus MAX_PROGRAMMES. Les chemins sont RELATIFS au dossier de l'Espace :
    c'est sous un autre chemin que ce dossier apparaît dans le bac à sable
    (voir « chez », wrap_bwrap).
    """
    trouves = []
    for lieu in lieux:
        racine = os.path.join(home, lieu)
        for dossier, sous, fichiers in os.walk(racine):
            if dossier[len(racine):].count(os.sep) >= 2:
                sous[:] = []
            sous[:] = sorted(s for s in sous if not s.startswith("."))
            for nom in sorted(fichiers):
                chemin = os.path.join(dossier, nom)
                try:
                    nature = nature_programme(lire_tete(chemin))
                except OSError:
                    continue
                if nature and len(trouves) < MAX_PROGRAMMES:
                    trouves.append({"chemin": os.path.relpath(chemin, home),
                                    "nature": nature})
    return trouves


def preparer_programme(home, chemin):
    """Vérifie UN programme du dossier `home` et le rend exécutable.

    `chemin` vient du bureau, relatif au dossier de l'Espace. Il doit désigner
    un fichier ordinaire de ce dossier, et un programme ; l'Espace, qui en est
    le propriétaire, le rend exécutable. Renvoie le chemin, relatif lui aussi,
    et la nature ; lève Refus sinon.
    """
    if not chemin or os.path.isabs(chemin) or any(c in chemin for c in "\n\r\x00"):
        raise Refus("chemin de programme mal formé.")
    home = os.path.realpath(home)
    dossier = os.path.realpath(os.path.dirname(os.path.join(home, chemin)))
    if os.path.commonpath([dossier, home]) != home:
        raise Refus("ce programme n'est pas dans l'Espace.")
    chemin = os.path.join(dossier, os.path.basename(chemin))
    try:
        nature = nature_programme(lire_tete(chemin))
        if not nature:
            raise Refus("ce fichier n'est pas un programme.")
        os.chmod(chemin, stat.S_IMODE(os.lstat(chemin).st_mode) | 0o700)
    except OSError as exc:
        raise Refus("programme illisible (%s)." % exc, code=1)
    return {"chemin": os.path.relpath(chemin, home), "nature": nature}


def programme_valide(entree):
    """Une entrée venue de l'Espace est-elle un programme bien formé ?

    Un chemin RELATIF au dossier de l'Espace, qui ne remonte pas au-dessus.
    Chemin de l'Espace, donc Linux : posixpath, quel que soit le système où
    tourne ce code (les tests passent aussi sous Windows).
    """
    if not (isinstance(entree, dict) and isinstance(entree.get("chemin"), str)
            and entree.get("nature") in NATURES_PROGRAMME):
        return False
    chemin = entree["chemin"]
    return (bool(chemin) and not posixpath.isabs(chemin)
            and ".." not in chemin.split("/")
            and not any(c in chemin for c in "\n\r\x00"))


def chemin_dans_le_bac_a_sable(relatif):
    """Où un fichier du dossier de l'Espace apparaît pour ses applications.

    Le dossier d'un Espace à compte séparé est monté au chemin du dossier du
    bureau (« chez », voir wrap_bwrap) : c'est ce chemin qu'il faut inscrire
    au menu, pas celui où le dossier est rangé sur la machine.
    """
    return os.path.join(os.path.expanduser("~"), relatif)
