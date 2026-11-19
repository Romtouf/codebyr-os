# -*- coding: utf-8 -*-
"""Le menu du Sceau : ce qu'il propose de lui-même, au bon moment."""
import json
import os
import re
import shutil
import subprocess
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


@unittest.skipUnless(shutil.which("node"), "node absent : l'extension ne peut pas être exécutée")
class LEtatDuPoste(unittest.TestCase):
    """Un poste qui ne se met plus à jour se tait, comme un poste sain."""

    def _etat(self, age):
        source = _source()
        fonctions = "\n".join((
            "const _ = t => t; const n_ = (s, p, n) => n <= 1 ? s : p;",
            r"const remplir = (t, v) => t.replace(/\{(\w+)\}/g, (m, c) => v[c]);",
            re.search(r"const JOURS_SANS_MISE_A_JOUR = [^\n]*", source).group(),
            re.search(r"function etatMisesAJour\([\s\S]*?\n\}", source).group(),
            "console.log(JSON.stringify(etatMisesAJour(%s)));" % age))
        r = subprocess.run(["node", "-e", fonctions],
                           capture_output=True, text=True, encoding="utf-8", timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_a_jour(self):
        self.assertTrue(self._etat(3600)["ok"])
        etat = self._etat(2 * 86400 + 5)
        self.assertTrue(etat["ok"])
        self.assertIn("il y a 2 jours", etat["texte"])

    def test_en_retard_ou_jamais(self):
        etat = self._etat(9 * 86400)
        self.assertFalse(etat["ok"])
        self.assertIn("depuis 9 jours", etat["texte"])
        self.assertFalse(self._etat("null")["ok"])

    def test_lu_sur_le_temoin_d_apt_et_dit_dans_le_menu(self):
        source = _source()
        # Posé par apt.systemd.daily après chaque passage d'unattended-upgrades.
        self.assertIn("const TEMOIN_MISES_A_JOUR = '/var/lib/apt/periodic/upgrade-stamp';", source)
        menu = _methode(source, "_rebuild")
        self.assertIn("etatMisesAJour(ageDuTemoin())", menu)
        self.assertIn("codebyr-space verifier-poste", menu)


@unittest.skipUnless(shutil.which("node"), "node absent : l'extension ne peut pas être exécutée")
class LeMenuDefile(unittest.TestCase):
    """Un menu plus haut que l'écran défile, au lieu d'écraser à zéro pixel
    l'Espace qu'on déplie (vu sur la VM, écran de 768 pixels, en 1.22.0)."""

    def _position(self, *args):
        fonctions = "\n".join((
            re.search(r"function defilementPourMontrer\([\s\S]*?\n\}", _source()).group(),
            "console.log(JSON.stringify(defilementPourMontrer(%s)));" % ", ".join(map(str, args))))
        r = subprocess.run(["node", "-e", fonctions],
                           capture_output=True, text=True, encoding="utf-8", timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    # Arguments : haut, bas de la zone ; défilement actuel, hauteur visible,
    # bornes du défilement.
    def test_deja_visible(self):
        self.assertIsNone(self._position(100, 300, 0, 700, 0, 1000))

    def test_sous_le_bas_de_l_ecran(self):
        self.assertEqual(self._position(600, 900, 0, 700, 0, 1000), 200)

    def test_au_dessus_du_haut(self):
        self.assertEqual(self._position(50, 150, 200, 700, 0, 1000), 50)

    def test_plus_haute_que_l_ecran_on_en_montre_le_haut(self):
        """Le nom de l'Espace déplié reste visible."""
        self.assertEqual(self._position(400, 1300, 0, 700, 0, 1400), 400)

    def test_jamais_au_dela_des_bornes(self):
        self.assertEqual(self._position(900, 990, 0, 700, 0, 1000), 290)
        self.assertEqual(self._position(950, 1200, 0, 700, 0, 1000), 300)

    def test_le_menu_est_rendu_defilant(self):
        source = _source()
        self.assertIn("this._defil = rendreDefilant(this.menu);", source)
        self.assertIn("this._montrerEspace(sub)", _methode(source, "_ajouterEspace"))
        # Une source GLib laissée derrière soi après désactivation est un motif
        # de refus sur extensions.gnome.org, et une erreur dans le journal.
        self.assertIn("GLib.Source.remove(this._idDefil)", source)


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
