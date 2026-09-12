# -*- coding: utf-8 -*-
"""Les vérifications se lancent DEPUIS LE BUREAU, jamais depuis un Espace.

Constaté le 12/09/2026 sur une VM, par le mainteneur. Lancé depuis l'Espace
Banque, `verifier-isolation` a mesuré un « Espace ordinaire » sans réseau ni
micro, puis conclu :

    Au moins un contrôle a échoué. Ne publiez pas cette version.

Rien n'était cassé. La sonde s'exécutait dans un bac à sable IMBRIQUÉ dans
Banque et héritait de ses restrictions : elle mesurait celles-là, pas celles
qu'on voulait vérifier. De même, `verifier-poste` échouait sur `sudo` — dont
l'impossibilité dans un Espace est précisément ce que le Blindage garantit.

Un outil qui accuse à tort quand on l'emploie depuis le mauvais endroit finit
ignoré, et c'est justement celui qu'il faudra croire le jour où il aura raison.
"""
import contextlib
import io
import os
import unittest

from outils import LIB  # noqa: F401 — place les modules partagés sur sys.path
import autotest  # noqa: E402
import bac_a_sable  # noqa: E402


class DepuisUnEspace(unittest.TestCase):
    """Refus explicite, avec la raison et la marche à suivre."""

    def setUp(self):
        self._avant = os.environ.get("CODEBYR_ESPACE")
        os.environ["CODEBYR_ESPACE"] = "banque"
        self.addCleanup(self._restaurer)

    def _restaurer(self):
        if self._avant is None:
            os.environ.pop("CODEBYR_ESPACE", None)
        else:
            os.environ["CODEBYR_ESPACE"] = self._avant

    def test_isolation_refuse(self):
        """Mesurer un bac à sable depuis un bac à sable ne dit rien d'utile."""
        self.assertEqual(bac_a_sable.cmd_verifier_isolation(), 2)

    def test_poste_refuse(self):
        """Les fichiers lus seraient ceux du bac à sable, pas ceux du poste."""
        self.assertEqual(autotest.cmd_verifier_poste(), 2)


class DepuisLeBureau(unittest.TestCase):
    """La garde ne doit pas gêner l'usage normal.

    Une protection qui empêche l'outil de servir là où il sert est pire que le
    défaut qu'elle corrige.
    """

    def setUp(self):
        self._avant = os.environ.pop("CODEBYR_ESPACE", None)
        self.addCleanup(self._restaurer)

    def _restaurer(self):
        if self._avant is not None:
            os.environ["CODEBYR_ESPACE"] = self._avant

    @staticmethod
    def _sans_bruit(fonction):
        """Capture la sortie : les marques ✔/✘ ne passent pas la console Windows.

        Et un test qui déverse un rapport complet rend la suite illisible.
        """
        with contextlib.redirect_stdout(io.StringIO()):
            return fonction()

    def test_le_poste_est_bien_mesure(self):
        """Sur le bureau, l'autotest doit RÉPONDRE — 0 ou 1, jamais le refus."""
        self.assertIn(self._sans_bruit(autotest.cmd_verifier_poste), (0, 1))

    def test_une_valeur_vide_ne_compte_pas(self):
        """Une variable présente mais vide n'est pas un Espace."""
        os.environ["CODEBYR_ESPACE"] = "   "
        self.assertIn(self._sans_bruit(autotest.cmd_verifier_poste), (0, 1))


if __name__ == "__main__":
    unittest.main()
