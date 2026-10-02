# -*- coding: utf-8 -*-
"""Un Espace ne joint plus les sockets abstraites de l'hôte (Landlock).

── LE PROBLÈME ─────────────────────────────────────────────────────────────
Une socket Unix « abstraite » n'est pas un fichier : son nom commence par un
octet nul, et aucun montage ne la cache. Elle appartient à l'espace de noms
RÉSEAU. Un Espace à réseau libre partage celui de l'hôte, donc voit toutes
ses sockets abstraites — dont celle de Xwayland, « @/tmp/.X11-unix/X0 ».

Ce qui protège aujourd'hui, c'est le cookie : GNOME exige un identifiant, et
le bac à sable ne monte jamais le fichier qui le contient (mesuré sur la VM :
connexion refusée, depuis un Espace comme depuis le bureau).
Mais une barrière unique, qui tient à un réglage de GNOME, ne suffit pas pour
un serveur qui donnerait le presse-papiers de tous les Espaces et les frappes
au clavier (voir SECURITY.md, « Analyse externe »).

── CE QUE FAIT CE MODULE ───────────────────────────────────────────────────
Lancé EN TÊTE de la commande, dans le bac à sable :

    python3 -I /usr/share/codebyr/sockets_abstraites.py -- <commande>

il pose sur lui-même un domaine Landlock qui interdit de joindre une socket
abstraite créée HORS de ce domaine (LANDLOCK_SCOPE_ABSTRACT_UNIX_SOCKET,
Linux 6.12, celui de Debian 13), puis cède la place à la commande (exec) :
tout ce qu'elle lance en hérite, sans pouvoir s'en défaire. Les sockets
créées DANS l'Espace — son bus de session privé — restent joignables.

Retirer DISPLAY de l'environnement ne suffirait pas : c'est une indication
pour les programmes honnêtes, un programme hostile s'en passe.

Noyau sans cette version de Landlock : la commande est lancée quand même, et
on le dit — le cookie reste la première barrière. Noyau qui l'offre mais
refuse de la poser : l'Espace ne s'ouvre pas, comme partout ailleurs quand
une protection annoncée manque.
"""
import ctypes
import os
import sys

# Numéros d'appels système (x86-64, la seule architecture de Codebyr).
SYS_LANDLOCK_CREATE_RULESET = 444
SYS_LANDLOCK_RESTRICT_SELF = 446
LANDLOCK_CREATE_RULESET_VERSION = 1 << 0
LANDLOCK_SCOPE_ABSTRACT_UNIX_SOCKET = 1 << 0
PR_SET_NO_NEW_PRIVS = 38
ABI_MINIMALE = 6


class _Regles(ctypes.Structure):
    """struct landlock_ruleset_attr : on ne gère ni fichiers ni réseau, on
    ne fait que limiter la portée des sockets abstraites."""
    _fields_ = [("handled_access_fs", ctypes.c_uint64),
                ("handled_access_net", ctypes.c_uint64),
                ("scoped", ctypes.c_uint64)]


def _libc():
    return ctypes.CDLL(None, use_errno=True)


def abi(libc=None):
    """Version de Landlock offerte par le noyau ; 0 s'il n'en a pas."""
    libc = libc or _libc()
    version = libc.syscall(SYS_LANDLOCK_CREATE_RULESET, None, ctypes.c_size_t(0),
                           ctypes.c_uint32(LANDLOCK_CREATE_RULESET_VERSION))
    return version if version > 0 else 0


def fermer(libc=None):
    """Pose la cloison sur le processus courant et ses descendants.

    Renvoie False si le noyau ne la connaît pas ; lève OSError s'il la
    connaît mais refuse de la poser."""
    libc = libc or _libc()
    if abi(libc) < ABI_MINIMALE:
        return False
    regles = _Regles(0, 0, LANDLOCK_SCOPE_ABSTRACT_UNIX_SOCKET)
    fd = libc.syscall(SYS_LANDLOCK_CREATE_RULESET, ctypes.byref(regles),
                      ctypes.c_size_t(ctypes.sizeof(regles)), ctypes.c_uint32(0))
    if fd < 0:
        raise OSError(ctypes.get_errno(), "landlock_create_ruleset")
    try:
        # Exigé pour se restreindre sans privilège ; bubblewrap le pose déjà.
        if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS")
        if libc.syscall(SYS_LANDLOCK_RESTRICT_SELF, fd, ctypes.c_uint32(0)) != 0:
            raise OSError(ctypes.get_errno(), "landlock_restrict_self")
    finally:
        os.close(fd)
    return True


def main(argv):
    if len(argv) < 3 or argv[1] != "--":
        sys.stderr.write("usage : sockets_abstraites.py -- <commande>\n")
        return 2
    try:
        if not fermer():
            sys.stderr.write("codebyr : noyau sans Landlock %d — les sockets abstraites "
                             "de l'hôte restent joignables depuis cet Espace.\n" % ABI_MINIMALE)
    except OSError as e:
        sys.stderr.write("codebyr : cloison Landlock refusée par le noyau (%s) — "
                         "Espace non ouvert.\n" % e)
        return 1
    os.execvp(argv[2], argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
