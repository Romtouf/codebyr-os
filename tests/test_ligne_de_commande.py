# -*- coding: utf-8 -*-
"""La ligne de commande de codebyr-space.

C'est l'unique porte d'entrée : l'extension GNOME (menu du Sceau), l'ouverture
en Jetable et la configuration passent toutes par elle. Une action mal câblée
ne se voit qu'au clic de l'utilisateur — d'où ces tests sur la table d'actions
et sur l'analyse des arguments.
"""
import io
import sys
import unittest

from outils import charger

espace = charger("codebyr-space")


class TableDActions(unittest.TestCase):

    def test_chaque_usage_commence_par_son_action(self):
        # Garantit que le message d'aide ne peut pas désigner une autre action
        # que celle qu'on vient de taper.
        for nom, (_minimum, usage, _f) in espace.ACTIONS.items():
            self.assertTrue(usage.split()[0] == nom,
                            "usage de « %s » : %r" % (nom, usage))

    def test_le_nombre_d_arguments_est_coherent_avec_l_usage(self):
        # Nombre de paramètres OBLIGATOIRES : les « <…> » qui précèdent le
        # premier « [… ] » (tout ce qui suit un crochet est facultatif).
        for nom, (minimum, usage, _f) in espace.ACTIONS.items():
            obligatoires = 0
            for mot in usage.split()[1:]:
                if mot.startswith("["):
                    break
                if mot.startswith("<"):
                    obligatoires += 1
            self.assertEqual(minimum, obligatoires,
                             "« %s » exige %d argument(s) mais son usage en "
                             "annonce %d" % (nom, minimum, obligatoires))

    def test_l_aide_liste_toutes_les_actions(self):
        # L'aide est produite depuis la table : elle ne peut plus documenter
        # trois actions sur treize, comme c'était le cas.
        aide = espace._aide()
        for nom in espace.ACTIONS:
            self.assertIn("codebyr-space " + nom, aide,
                          "« %s » n'apparaît pas dans --help" % nom)


class AnalyseDesArguments(unittest.TestCase):

    def setUp(self):
        self.erreurs = io.StringIO()
        self._stderr, sys.stderr = sys.stderr, self.erreurs
        self.appels = []
        self._launch = espace.cmd_launch
        espace.cmd_launch = lambda espaces, esp_id, extra, fichier: self.appels.append(
            (esp_id, extra, fichier)) or 0

    def tearDown(self):
        sys.stderr = self._stderr
        espace.cmd_launch = self._launch

    def test_aide(self):
        self.assertEqual(espace.main(["codebyr-space"]), 0)
        self.assertEqual(espace.main(["codebyr-space", "--help"]), 0)

    def test_action_inconnue(self):
        self.assertEqual(espace.main(["codebyr-space", "nawak"]), 2)
        self.assertIn("Action inconnue", self.erreurs.getvalue())

    def test_arguments_manquants(self):
        for nom, (minimum, _u, _f) in espace.ACTIONS.items():
            if minimum == 0:
                continue
            argv = ["codebyr-space", nom] + ["x"] * (minimum - 1)
            self.assertEqual(espace.main(argv), 2,
                             "« %s » accepte trop peu d'arguments" % nom)

    def test_launch_simple(self):
        self.assertEqual(espace.main(["codebyr-space", "launch", "travail"]), 0)
        self.assertEqual(self.appels, [("travail", [], None)])

    def test_launch_avec_commande(self):
        espace.main(["codebyr-space", "launch", "banque", "--", "firefox-esr",
                     "https://exemple.test"])
        self.assertEqual(self.appels,
                         [("banque", ["firefox-esr", "https://exemple.test"], None)])

    def test_launch_piece_jointe(self):
        espace.main(["codebyr-space", "launch", "jetable", "--fichier", "/tmp/f.pdf"])
        self.assertEqual(self.appels, [("jetable", [], "/tmp/f.pdf")])

    def test_launch_fichier_et_commande(self):
        espace.main(["codebyr-space", "launch", "jetable", "--fichier", "/tmp/f.pdf",
                     "--", "evince", "/tmp/f.pdf"])
        self.assertEqual(self.appels,
                         [("jetable", ["evince", "/tmp/f.pdf"], "/tmp/f.pdf")])


if __name__ == "__main__":
    unittest.main()
