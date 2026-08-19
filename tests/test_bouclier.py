# -*- coding: utf-8 -*-
"""Le bouclier anti-hameçonnage (extension Firefox).

Point d'attention particulier : le `.xpi` **signé par Mozilla** est un fichier
scellé. Modifier `content.js` dans le dépôt ne change RIEN sur les machines
tant que l'extension n'a pas été re-signée : `codebyr-space` installe le .xpi
signé en priorité. Ce test compare donc les deux, pour qu'un correctif du
bouclier ne puisse pas rester lettre morte sans qu'on le voie.
"""
import glob
import json
import os
import re
import unittest
import zipfile

from outils import RACINE

SRC = os.path.join(RACINE, "live-build", "config",
                   "includes.chroot_after_packages", "usr", "share",
                   "codebyr", "antiphishing")
SIGNES = os.path.join(SRC, "signed")


class Manifeste(unittest.TestCase):

    def setUp(self):
        with open(os.path.join(SRC, "manifest.json"), encoding="utf-8") as f:
            self.manifeste = json.load(f)

    def test_identifiant_stable(self):
        # Cet identifiant est celui du manifeste de stockage managé écrit par
        # codebyr-space : les deux doivent coïncider, sinon l'extension ne
        # reçoit jamais la liste des domaines protégés.
        self.assertEqual(
            self.manifeste["browser_specific_settings"]["gecko"]["id"],
            "antiphishing@codebyr.io")
        with open(os.path.join(RACINE, "live-build", "config",
                               "includes.chroot_after_packages", "usr", "bin",
                               "codebyr-space"), encoding="utf-8") as f:
            self.assertIn('BOUCLIER_ID = "antiphishing@codebyr.io"', f.read())

    def test_permissions_minimales(self):
        self.assertEqual(self.manifeste["permissions"], ["storage"])


class CodeStatique(unittest.TestCase):
    """L'extension doit rester signable : aucune donnée injectée dans le code."""

    def setUp(self):
        with open(os.path.join(SRC, "content.js"), encoding="utf-8") as f:
            self.code = f.read()

    def test_les_domaines_viennent_du_stockage_manage(self):
        self.assertIn("storage.managed", self.code)

    def test_pas_de_domaine_en_dur(self):
        # Un domaine écrit dans le code signifierait qu'on le réécrit avant
        # installation — donc une extension non signable.
        suspects = re.findall(r'"[a-z0-9-]+\.(?:fr|com|net|org|be|ch)"', self.code)
        self.assertEqual(suspects, [], "domaines en dur : %s" % suspects)

    def test_pas_d_innerhtml_avec_des_donnees_du_site(self):
        # On construit l'avertissement avec textContent : le nom d'hôte affiché
        # vient du site visité, il n'a rien à faire dans du HTML interprété.
        self.assertEqual(re.findall(r"\.innerHTML\s*=", self.code), [])


class XpiSigne(unittest.TestCase):

    def _xpi(self):
        trouves = sorted(glob.glob(os.path.join(SIGNES, "*.xpi")))
        if not trouves:
            self.skipTest("aucun .xpi signé livré")
        return trouves[0]

    RAPPEL = ("\nLe bouclier réellement installé sur les machines est celui du "
              ".xpi signé : tant qu'il n'est pas régénéré, un correctif du "
              "bouclier n'a AUCUN effet.\n"
              "  → AMO_KEY=... AMO_SECRET=... bash live-build/scripts/sign-extension.sh\n"
              "  puis remplacer le .xpi dans %s" % SIGNES)

    def test_le_code_du_xpi_signe_correspond_a_la_source(self):
        xpi = self._xpi()
        with zipfile.ZipFile(xpi) as z:
            self.assertIn("content.js", z.namelist())
            embarque = z.read("content.js").replace(b"\r\n", b"\n")
        with open(os.path.join(SRC, "content.js"), "rb") as f:
            source = f.read().replace(b"\r\n", b"\n")
        self.assertEqual(embarque, source,
                         "content.js diffère du .xpi signé." + self.RAPPEL)

    def test_la_version_du_xpi_signe_correspond_au_manifeste(self):
        # AMO ré-encode le JSON (échappements \\uXXXX) : on compare le SENS,
        # pas les octets.
        xpi = self._xpi()
        with zipfile.ZipFile(xpi) as z:
            embarque = json.loads(z.read("manifest.json").decode("utf-8"))
        with open(os.path.join(SRC, "manifest.json"), encoding="utf-8") as f:
            source = json.load(f)
        self.assertEqual(embarque.get("version"), source.get("version"),
                         "version du manifeste ≠ version signée." + self.RAPPEL)
        self.assertEqual(embarque.get("permissions"), source.get("permissions"),
                         "permissions ≠ celles du .xpi signé." + self.RAPPEL)


if __name__ == "__main__":
    unittest.main()
