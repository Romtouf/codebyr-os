#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde : un programme peut-il joindre le serveur X11 du bureau ?

Analyse externe du 01/10/2026, point 1.3. Un Espace qui partage l'espace de
noms réseau de l'hôte (tout Espace à réseau libre) voit aussi ses sockets
ABSTRAITES, qui ne sont pas des fichiers : aucun montage ne les cache. Or
Xwayland écoute sur « @/tmp/.X11-unix/X<n> », et GNOME l'autorise pour tout
processus du même compte que la session (« si:localuser »), sans cookie.
Un tel processus lirait le presse-papiers à tout moment, verrait les
fenêtres X11 et pourrait leur envoyer des frappes.

La sonde fait la vraie poignée de main X11, SANS identifiant : la réponse
du serveur dit s'il accepte. Elle n'envoie rien d'autre, ne lit rien.

    python3 sonde_x11.py

À lancer dans la console d'un Espace, et sur le bureau pour comparer.
"""
import ctypes
import os
import pwd
import socket
import struct

REPONSES = {0: "REFUSÉ", 1: "ACCEPTÉ", 2: "identifiant exigé"}


def abi_landlock():
    """Version de Landlock offerte par le noyau, 0 s'il n'en a pas.

    landlock_create_ruleset(NULL, 0, LANDLOCK_CREATE_RULESET_VERSION) ; la
    version 6 (Linux 6.12) sait interdire de joindre une socket abstraite
    créée hors du bac à sable."""
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(444, None, ctypes.c_size_t(0), ctypes.c_uint32(1))
    return abi if abi > 0 else 0


def poignee_de_main(adresse):
    """Résultat de la connexion X11 à cette adresse, en clair."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5)
    try:
        s.connect(adresse)
    except OSError as e:
        return "injoignable (%s)" % (e.strerror or e)
    try:
        # Ordre des octets « l », protocole 11.0, aucun identifiant.
        s.sendall(b"l\x00" + struct.pack("<HHHH", 11, 0, 0, 0) + b"\x00\x00")
        tete = s.recv(8)
        if not tete:
            return "connexion fermée sans réponse"
        etat = REPONSES.get(tete[0], "réponse inconnue %d" % tete[0])
        if tete[0] == 0 and len(tete) > 1:
            raison = s.recv(tete[1]).decode("latin-1", "replace").strip()
            etat += " — « %s »" % raison
        return etat
    except OSError as e:
        return "erreur (%s)" % (e.strerror or e)
    finally:
        s.close()


def main():
    uid = os.getuid()
    try:
        nom = pwd.getpwuid(uid).pw_name
    except KeyError:
        nom = "?"
    print("Compte : uid=%d (%s), DISPLAY=%s" % (uid, nom, os.environ.get("DISPLAY", "(vide)")))
    abi = abi_landlock()
    print("Landlock : %s" % ("ABI %d%s" % (abi, " — sait fermer les sockets abstraites"
                                            if abi >= 6 else " — trop ancien pour les sockets")
                             if abi else "absent"))
    for n in range(3):
        print("X11 :%d, socket abstraite : %s" % (n, poignee_de_main("\0/tmp/.X11-unix/X%d" % n)))
        chemin = "/tmp/.X11-unix/X%d" % n
        if os.path.exists(chemin):
            print("X11 :%d, fichier %s : %s" % (n, chemin, poignee_de_main(chemin)))


if __name__ == "__main__":
    main()
