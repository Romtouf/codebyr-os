# -*- coding: utf-8 -*-
"""Le disque est chiffré par défaut — et reste ouvrable au clavier français.

Deux promesses tiennent ensemble dans la configuration de l'installateur :

1. La case « Chiffrer le système » est cochée d'avance. Proposée sans être
   cochée, la protection dépendait de l'utilisateur qui pense à la cocher.
2. La phrase de passe se tape avec le clavier de l'installation. Si c'était
   GRUB qui la demandait (/boot chiffré, réglage par défaut de Calamares), elle
   se taperait en QWERTY : un utilisateur AZERTY ne pourrait plus ouvrir son
   disque. Cocher la case par défaut aurait alors fait plus de mal que de bien.

Ces tests gardent les deux, et le détail qui les relie : /boot séparé en clair
ne doit JAMAIS s'accompagner d'un fichier de clé sur /boot.
"""
import os
import re
import unittest

from outils import ETC, RACINE

PARTITION = os.path.join(ETC, "calamares", "modules", "partition.conf")
CLAVIER = os.path.join(ETC, "initramfs-tools", "conf.d", "codebyr-clavier")
LISTES = os.path.join(RACINE, "live-build", "config", "package-lists")
AMORCE = os.path.join(RACINE, "live-build", "config", "includes.chroot_after_packages",
                      "usr", "share", "calamares", "helpers", "calamares-bootloader-config")

try:
    import yaml
except ImportError:          # pragma: no cover — PyYAML absent de l'environnement
    yaml = None


def _lire(chemin):
    with open(chemin, encoding="utf-8") as f:
        return f.read()


def _taille_en_mio(texte):
    m = re.fullmatch(r"(\d+)\s*([KMG])", str(texte))
    assert m, "taille non absolue : %r" % texte
    return int(m.group(1)) * {"K": 1 / 1024, "M": 1, "G": 1024}[m.group(2)]


@unittest.skipIf(yaml is None, "PyYAML requis pour lire la configuration Calamares")
class ConfigurationDuPartitionnement(unittest.TestCase):

    def setUp(self):
        # Une erreur de syntaxe ici ne se voit qu'au lancement de l'installateur,
        # sur la machine de l'utilisateur : le module refuse alors de se charger.
        self.conf = yaml.safe_load(_lire(PARTITION))
        self.disposition = self.conf["partitionLayout"]

    def test_le_chiffrement_est_coche_d_avance(self):
        self.assertIs(self.conf.get("enableLuksAutomatedPartitioning"), True)
        self.assertIs(self.conf.get("preCheckEncryption"), True)

    def test_luks2(self):
        # Possible parce que GRUB n'a plus à lire la partition chiffrée ; plus
        # résistant (Argon2id) que le LUKS1 imposé par un /boot chiffré.
        self.assertEqual(self.conf.get("luksGeneration"), "luks2")

    def test_boot_est_separe_et_seul_exempte(self):
        exemptees = [p for p in self.disposition if p.get("noEncrypt")]
        self.assertEqual([p.get("mountPoint") for p in exemptees], ["/boot"],
                         "seul /boot peut rester en clair : il ne contient aucune donnée")
        self.assertGreaterEqual(_taille_en_mio(exemptees[0]["size"]), 512,
                                "un /boot trop petit bloque les mises à jour du noyau")

    def test_la_racine_est_chiffree_et_prend_le_reste(self):
        racine = [p for p in self.disposition if p.get("mountPoint") == "/"]
        self.assertEqual(len(racine), 1)
        self.assertFalse(racine[0].get("noEncrypt", False))
        self.assertEqual(racine[0].get("size"), "100%")

    def test_aucun_autre_point_de_montage_n_echappe(self):
        # /home ou /data ajoutés un jour sans y penser hériteraient du
        # chiffrement ; un « noEncrypt » les en sortirait en silence.
        for p in self.disposition:
            if p.get("mountPoint") not in ("/boot",):
                self.assertFalse(p.get("noEncrypt", False), p)


class ClavierAuDeverrouillage(unittest.TestCase):

    def test_la_disposition_est_chargee_dans_l_initramfs(self):
        lignes = [l.strip() for l in _lire(CLAVIER).splitlines()
                  if l.strip() and not l.strip().startswith("#")]
        self.assertEqual(lignes, ["KEYMAP=y"])

    def test_les_outils_de_clavier_sont_embarques(self):
        # KEYMAP=y sans console-setup ne charge rien : le hook d'initramfs
        # a besoin de setupcon et de loadkeys (kbd).
        paquets = set()
        for nom in os.listdir(LISTES):
            for ligne in _lire(os.path.join(LISTES, nom)).splitlines():
                ligne = ligne.split("#", 1)[0].strip()
                if ligne:
                    paquets.add(ligne)
        for requis in ("console-setup", "kbd", "cryptsetup-initramfs"):
            self.assertIn(requis, paquets)

    def test_la_disposition_fr_est_fixee_apres_les_paquets(self):
        # keyboard-configuration peut réécrire /etc/default/keyboard à son
        # installation : le hook qui pose « fr » doit passer après.
        hook = _lire(os.path.join(RACINE, "live-build", "config", "hooks", "normal",
                                  "0500-debrand.hook.chroot"))
        self.assertIn('XKBLAYOUT="fr"', hook)


class AmorcageCompatible(unittest.TestCase):

    def test_la_racine_chiffree_est_reconnue_quel_que_soit_boot(self):
        # Le script d'amorçage de Codebyr reconnaît le chiffrement au
        # périphérique de la RACINE (/dev/mapper/luks-…), pas à /boot : il
        # reste valable avec un /boot séparé.
        script = _lire(AMORCE)
        self.assertIn('"/dev/mapper/luks"', script)
        self.assertNotIn("GRUB_ENABLE_CRYPTODISK", script)


class LanceurDeLInstallateur(unittest.TestCase):
    """Pendant l'installation, GNOME doit afficher Codebyr, pas Debian.

    Le lanceur caché « Install Debian » revendiquait la fenêtre de Calamares :
    son nom et son icône (un losange bleu) apparaissaient dans le dock, la vue
    d'ensemble et Alt+Tab — constaté sur la VM le 13/09/2026.
    """

    def test_notre_lanceur_revendique_la_fenetre_de_calamares(self):
        lanceur = _lire(os.path.join(ETC, "..", "usr", "share", "applications",
                                     "io.codebyr.Installer.desktop"))
        self.assertIn("StartupWMClass=calamares", lanceur.splitlines())

    def test_le_lanceur_debian_ne_la_revendique_plus(self):
        hook = _lire(os.path.join(RACINE, "live-build", "config", "hooks", "normal",
                                  "0800-installeur.hook.chroot"))
        self.assertIn("sed -i '/^StartupWMClass=/d' \"$d\"", hook)


if __name__ == "__main__":
    unittest.main()
