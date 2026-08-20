# -*- coding: utf-8 -*-
"""Le tour de bienvenue, et surtout : quand proposer d'installer.

Le bouton « Installer Codebyr OS sur ce disque » s'affichait sur une machine
DÉJÀ installée, à chaque nouvelle session. La détection reposait sur la
présence de Calamares, en supposant que son retrait en fin d'installation
ferait foi — mais ce retrait passe par apt, l'installation de Codebyr se fait
hors ligne, et il peut échouer sans que rien ne le signale.
"""
import os
import unittest

from outils import BIN            # place le module partagé sur sys.path
import systeme                    # noqa: E402 — dépend de l'import ci-dessus


class DetectionDuSupportLive(unittest.TestCase):

    def test_le_dossier_de_live_boot_suffit(self):
        self.assertTrue(systeme.est_live("", ["/run/live"]))

    def test_le_parametre_du_noyau_suffit(self):
        self.assertTrue(systeme.est_live(
            "BOOT_IMAGE=/live/vmlinuz boot=live components quiet splash", []))

    def test_un_systeme_installe_n_est_pas_live(self):
        self.assertFalse(systeme.est_live(
            "BOOT_IMAGE=/boot/vmlinuz root=UUID=1234 ro quiet splash", []))

    def test_pas_de_confusion_avec_un_parametre_qui_ressemble(self):
        # « rebootable=live » ou « boot=liveusb » ne sont pas « boot=live ».
        self.assertFalse(systeme.est_live("root=UUID=1 boot=liveusb", []))
        self.assertFalse(systeme.est_live("root=UUID=1 rebootable=live", []))

    def test_sans_information_on_suppose_installe(self):
        # Mieux vaut ne pas proposer d'installer que le proposer à tort : la
        # première erreur se corrige d'un clic dans le menu, la seconde
        # revient à chaque session.
        self.assertFalse(systeme.est_live("", []))


class BoutonInstaller(unittest.TestCase):

    def setUp(self):
        with open(os.path.join(BIN, "codebyr-bienvenue"), encoding="utf-8") as f:
            self.code = f.read()

    def test_le_bouton_depend_du_support_live(self):
        self.assertIn("systeme.session_live()", self.code)

    def test_calamares_ne_sert_plus_de_preuve(self):
        self.assertNotIn('which("calamares")', self.code,
                         "la présence de Calamares ne prouve rien : son retrait "
                         "à l'installation peut échouer hors ligne")

    def test_le_tour_est_marque_vu_des_l_ouverture(self):
        # À la fermeture, une session coupée ou un plantage faisaient revenir
        # le tour à chaque connexion.
        self.assertIn("marquer_vu()", self.code)
        self.assertNotIn("do_shutdown", self.code)


if __name__ == "__main__":
    unittest.main()
