# -*- coding: utf-8 -*-
"""Le menu du Sceau : ce qu'il propose de lui-même, au bon moment."""
import os
import unittest

from outils import RACINE

EXTENSION = os.path.join(RACINE, "live-build", "config", "includes.chroot_after_packages",
                         "usr", "share", "gnome-shell", "extensions", "codebyr@codebyr.io",
                         "extension.js")


def _source():
    with open(EXTENSION, encoding="utf-8") as f:
        return f.read()


def _methode(source, nom):
    return source.split("    %s(" % nom, 1)[1].split("\n    }\n", 1)[0]


class LeRedemarrage(unittest.TestCase):
    """Depuis la 1.21.0, un noyau se met à jour tout seul ; l'ancien tourne,
    avec ses failles, jusqu'au redémarrage — et rien ne le montrait."""

    def setUp(self):
        self.source = _source()

    def test_le_fichier_de_debian(self):
        # Écrit par /etc/kernel/postinst.d/unattended-upgrades à chaque noyau.
        self.assertIn("const REDEMARRAGE = '/run/reboot-required';", self.source)

    def test_suivi_pendant_la_session(self):
        classe = self.source.split("class Redemarrage {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("monitor_file(", classe)
        self.assertIn("Main.notify(", classe)
        # Une fois par session : pas un rappel à chaque événement du fichier.
        self.assertIn("if (this._prevenu || !redemarrageAttendu())", classe)
        self.assertIn("this._suivi?.cancel();", classe)

    def test_le_menu_propose_de_redemarrer(self):
        menu = _methode(self.source, "_rebuild")
        self.assertIn("if (redemarrageAttendu())", menu)
        self.assertIn("activateRestart()", menu)
        # Placé en tête, avant les Espaces.
        self.assertLess(menu.index("redemarrageAttendu()"), menu.index("for (const e of espaces)"))

    def test_active_et_retire_avec_l_extension(self):
        self.assertIn("this._redemarrage = new Redemarrage();", self.source)
        self.assertIn("this._redemarrage?.detruire();", self.source)


class LeModeInvite(unittest.TestCase):
    """L'écran de connexion ne se laisse pas présélectionner un compte : on dit
    avant d'y aller ce qu'il faudra choisir."""

    def test_on_explique_avant_de_changer_d_utilisateur(self):
        corps = _methode(_source(), "_modeInvite")
        self.assertIn("new ModalDialog.ModalDialog(", corps)
        self.assertIn("« Invité »", corps)
        # Le changement n'a lieu qu'après la confirmation.
        passer = corps.split("const passer = () => {", 1)[1].split("};", 1)[0]
        self.assertIn("activateSwitchUser()", passer)
        self.assertEqual(corps.count("activateSwitchUser()"), 1)


if __name__ == "__main__":
    unittest.main()
