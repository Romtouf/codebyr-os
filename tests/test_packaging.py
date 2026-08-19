# -*- coding: utf-8 -*-
"""Le paquet codebyr-tools doit embarquer TOUT le userland Codebyr.

C'est le seul chemin de correctif vers les machines déjà installées : un outil
oublié dans la liste de `build-deb.sh` n'atteindra jamais un poste existant,
même après un « apt upgrade ». Le bug est silencieux — d'où ce test.
"""
import glob
import os
import re
import unittest

from outils import BIN, RACINE

BUILD_DEB = os.path.join(RACINE, "packaging", "build-deb.sh")

# Outils volontairement ABSENTS du paquet, parce qu'ils n'ont de sens que sur le
# support live et jamais sur une machine installée :
#   · codebyr-installer            lance Calamares, qui est désinstallé à la fin
#                                  de l'installation ;
#   · codebyr-nettoyage-installation  supprime le compte de démonstration
#                                  (« userdel -r user ») — un script à ne pas
#                                  laisser traîner sur un poste en service.
HORS_PAQUET = {
    "usr/bin/codebyr-installer",
    "usr/bin/codebyr-nettoyage-installation",
}


def chemins_du_paquet():
    """Les chemins listés dans la boucle « for chemin in ... » de build-deb.sh."""
    with open(BUILD_DEB, encoding="utf-8") as f:
        source = f.read()
    bloc = re.search(r"for chemin in \\\n(.*?)\ndo\n", source, re.S)
    assert bloc, "boucle « for chemin in » introuvable dans build-deb.sh"
    return [l.strip().rstrip("\\").strip() for l in bloc.group(1).splitlines()
            if l.strip().rstrip("\\").strip()]


class Paquet(unittest.TestCase):

    def setUp(self):
        self.chemins = chemins_du_paquet()
        self.src = os.path.join(RACINE, "live-build", "config",
                                "includes.chroot_after_packages")

    def test_les_chemins_listes_existent(self):
        for chemin in self.chemins:
            self.assertTrue(os.path.exists(os.path.join(self.src, chemin)),
                            "listé dans build-deb.sh mais absent du dépôt : %s" % chemin)

    def test_aucun_outil_codebyr_oublie(self):
        listes = set(self.chemins)
        for f in sorted(glob.glob(os.path.join(BIN, "codebyr-*"))):
            nom = "usr/bin/" + os.path.basename(f)
            if os.path.isdir(f) or nom in HORS_PAQUET:
                continue
            self.assertIn(nom, listes,
                          "%s n'est pas embarqué dans codebyr-tools : les machines "
                          "déjà installées ne le recevront jamais." % nom)

    def test_le_postinst_rattrape_les_machines_existantes(self):
        with open(os.path.join(RACINE, "packaging", "codebyr-tools.postinst"),
                  encoding="utf-8") as f:
            postinst = f.read()
        self.assertIn("codebyr-durcir-poste", postinst,
                      "sans cet appel, les correctifs de durcissement ne "
                      "toucheraient que les nouvelles installations")

    def test_pas_de_cache_python_dans_l_image(self):
        # Un __pycache__ traîné depuis un poste de développement finirait copié
        # tel quel dans l'ISO.
        parasites = glob.glob(os.path.join(self.src, "**", "__pycache__"),
                              recursive=True)
        self.assertEqual(parasites, [], "caches Python à supprimer : %s" % parasites)


if __name__ == "__main__":
    unittest.main()
