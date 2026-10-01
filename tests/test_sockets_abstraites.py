# -*- coding: utf-8 -*-
"""La cloison Landlock : un Espace ne joint plus les sockets abstraites de l'hôte.

Analyse externe du 01/10/2026, point 1.3. Un Espace à réseau libre partage
l'espace de noms réseau de l'hôte, donc ses sockets abstraites — celle de
Xwayland comprise (« @/tmp/.X11-unix/X0 »). Mesuré sur la VM : GNOME exige un
cookie que le bac à sable ne monte jamais, la connexion est refusée. La
cloison est une seconde barrière, qui ne dépend pas d'un réglage de GNOME.

Le test réel crée une socket abstraite HORS du domaine, puis vérifie que la
cloison en interdit l'accès, tandis qu'une socket créée DEDANS reste
joignable (c'est le cas du bus privé de l'Espace). Il demande Linux 6.12.
"""
import os
import socket
import subprocess
import sys
import unittest
from unittest import mock

from outils import LIB  # noqa: F401 — place le module partagé sur sys.path
import bac_a_sable  # noqa: E402
import sockets_abstraites as sa  # noqa: E402

MODULE = os.path.join(LIB, "sockets_abstraites.py")
ENTETE = ["python3", "-I", "/usr/share/codebyr/sockets_abstraites.py", "--"]


def _argv(**kw):
    return bac_a_sable.wrap_bwrap("/tmp/espace-home", ["firefox"],
                                  {"XDG_RUNTIME_DIR": "/run/user/1000"}, **kw)


def _commande(argv):
    return argv[argv.index("--") + 1:]


class LaCloisonEstPosee(unittest.TestCase):

    def test_en_tete_de_chaque_espace_qui_partage_le_reseau(self):
        for options in ({}, {"renforce": True}, {"renforce": True, "audio": False, "gpu": False}):
            self.assertEqual(_commande(_argv(**options))[:4], ENTETE, options)

    def test_avant_le_filtre_d_appels_systeme(self):
        commande = _commande(_argv(renforce=True))
        self.assertLess(commande.index("/usr/share/codebyr/sockets_abstraites.py"),
                        commande.index("/usr/share/codebyr/filtre_syscalls.py"))

    def test_inutile_sans_le_reseau_de_l_hote(self):
        # Hors ligne ou derrière le filtre : espace de noms réseau à part, aucune
        # socket abstraite de l'hôte n'y est visible.
        for options in ({"hors_ligne": True}, {"filtre": "/run/x/proxy"}):
            argv = _argv(**options)
            self.assertIn("--unshare-net", argv)
            self.assertNotIn("/usr/share/codebyr/sockets_abstraites.py", argv, options)

    def test_x11_retire_de_l_environnement(self):
        argv = _argv()
        for variable in ("DISPLAY", "XAUTHORITY"):
            i = argv.index(variable)
            self.assertEqual(argv[i - 1], "--unsetenv", variable)


class FauxNoyau:
    """libc simulée : la version de Landlock, et ce que le noyau répond."""

    def __init__(self, abi, refus=None):
        self.abi, self.refus, self.appels = abi, refus, []

    def syscall(self, numero, *args):
        self.appels.append(numero)
        if numero == sa.SYS_LANDLOCK_CREATE_RULESET:
            return self.abi if args[0] is None else 7
        if numero == sa.SYS_LANDLOCK_RESTRICT_SELF:
            return -1 if self.refus == "restrict" else 0
        raise AssertionError(numero)

    def prctl(self, *args):
        self.appels.append("prctl")
        return 0


class LaDecision(unittest.TestCase):

    def test_noyau_trop_ancien_rien_n_est_pose(self):
        noyau = FauxNoyau(5)
        self.assertFalse(sa.fermer(noyau))
        self.assertNotIn(sa.SYS_LANDLOCK_RESTRICT_SELF, noyau.appels)

    def test_noyau_recent_la_cloison_est_posee(self):
        noyau = FauxNoyau(6)
        with mock.patch.object(sa.os, "close"):
            self.assertTrue(sa.fermer(noyau))
        self.assertEqual(noyau.appels[-2:], ["prctl", sa.SYS_LANDLOCK_RESTRICT_SELF])

    def test_un_refus_du_noyau_n_est_pas_tu(self):
        with mock.patch.object(sa.os, "close"):
            with self.assertRaises(OSError):
                sa.fermer(FauxNoyau(6, refus="restrict"))

    def test_refus_du_noyau_l_espace_ne_s_ouvre_pas(self):
        with mock.patch.object(sa, "fermer", side_effect=OSError(1, "refus")), \
             mock.patch.object(sa.os, "execvp") as lance, \
             mock.patch.object(sa.sys, "stderr"):
            self.assertEqual(sa.main(["x", "--", "firefox"]), 1)
        lance.assert_not_called()

    def test_noyau_trop_ancien_l_espace_s_ouvre_et_le_dit(self):
        with mock.patch.object(sa, "fermer", return_value=False), \
             mock.patch.object(sa.os, "execvp") as lance, \
             mock.patch.object(sa.sys, "stderr") as erreur:
            sa.main(["x", "--", "firefox", "--private"])
        lance.assert_called_once_with("firefox", ["firefox", "--private"])
        self.assertIn("Landlock", "".join(c.args[0] for c in erreur.write.call_args_list))

    def test_sans_commande_rien_n_est_lance(self):
        with mock.patch.object(sa.os, "execvp") as lance, mock.patch.object(sa.sys, "stderr"):
            self.assertEqual(sa.main(["x"]), 2)
            self.assertEqual(sa.main(["x", "firefox"]), 2)
        lance.assert_not_called()


def _abi():
    try:
        return sa.abi()
    except (OSError, AttributeError):
        return 0


@unittest.skipUnless(sys.platform.startswith("linux") and _abi() >= sa.ABI_MINIMALE,
                     "Linux 6.12 (Landlock 6)")
class LaCloisonPourDeVrai(unittest.TestCase):

    def setUp(self):
        self.nom = "\0codebyr-test-%d" % os.getpid()
        self.serveur = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.serveur.bind(self.nom)
        self.serveur.listen(4)
        self.addCleanup(self.serveur.close)

    def _joindre(self, cloison, programme):
        cmd = [sys.executable, "-c", programme, self.nom[1:]]
        if cloison:
            cmd = [sys.executable, "-I", MODULE, "--"] + cmd
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    JOINDRE = ("import socket, sys\n"
               "s = socket.socket(socket.AF_UNIX)\n"
               "try:\n"
               "    s.connect('\\0' + sys.argv[1]); print('joint')\n"
               "except OSError as e:\n"
               "    print('refus', e.errno)\n")

    def test_temoin_sans_cloison_on_joint(self):
        self.assertEqual(self._joindre(False, self.JOINDRE).stdout.strip(), "joint")

    def test_derriere_la_cloison_on_ne_joint_plus(self):
        resultat = self._joindre(True, self.JOINDRE)
        self.assertEqual(resultat.stdout.strip(), "refus 1", resultat.stderr)

    def test_une_socket_creee_dedans_reste_joignable(self):
        # Le bus privé de l'Espace naît dans le bac à sable, donc dans le domaine.
        dedans = ("import socket, sys\n"
                  "nom = '\\0' + sys.argv[1] + '-dedans'\n"
                  "srv = socket.socket(socket.AF_UNIX); srv.bind(nom); srv.listen(1)\n"
                  "c = socket.socket(socket.AF_UNIX); c.connect(nom); print('joint')\n")
        resultat = self._joindre(True, dedans)
        self.assertEqual(resultat.stdout.strip(), "joint", resultat.stderr)


if __name__ == "__main__":
    unittest.main()
