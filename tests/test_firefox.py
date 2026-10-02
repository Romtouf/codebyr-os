# -*- coding: utf-8 -*-
"""Firefox sans contenu sponsorisé ni articles recommandés (1.21.0).

Vu sur la VM le 02/10/2026 : le nouvel onglet proposait des raccourcis
sponsorisés (Amazon, Temu…). Une politique d'entreprise les coupe, dans le
fichier que Codebyr livre déjà pour le bouclier ; elle vaut pour tous les
profils, ceux des Espaces compris.

Noms vérifiés le 02/10/2026 dans la documentation des politiques de Mozilla.
Stories et SponsoredStories n'existent qu'à partir de Firefox 141 : Firefox
140 ESR, celui de Debian 13, valide les politiques avec
allowAdditionalProperties et ignore ces clés sans rejeter les autres ; elles
serviront au passage à Firefox 153 ESR. Vu sur la VM : about:policies les
affiche, sans erreur.
"""
import json
import os
import unittest

from outils import RACINE

POLITIQUE = os.path.join(RACINE, "live-build", "config", "includes.chroot_after_packages",
                         "usr", "lib", "firefox-esr", "distribution", "policies.json")


def _politiques():
    with open(POLITIQUE, encoding="utf-8") as f:
        return json.load(f)["policies"]


class SansSponsorises(unittest.TestCase):

    def test_nouvel_onglet(self):
        # Les articles recommandés aussi, à la demande de l'utilisateur après
        # l'essai sur la VM : Pocket jusqu'à Firefox 140, Stories ensuite.
        self.assertEqual(_politiques()["FirefoxHome"],
                         {"SponsoredTopSites": False, "Pocket": False, "SponsoredPocket": False,
                          "Stories": False, "SponsoredStories": False})

    def test_barre_d_adresse(self):
        self.assertEqual(_politiques()["FirefoxSuggest"],
                         {"SponsoredSuggestions": False, "ImproveSuggest": False})

    def test_le_reste_de_firefox_reste_tel_quel(self):
        # Seul le sponsorisé part : raccourcis, recherche et suggestions
        # ordinaires restent, et l'utilisateur garde la main (rien de verrouillé).
        for regle in ("FirefoxHome", "FirefoxSuggest"):
            self.assertNotIn("Locked", _politiques()[regle])
        self.assertEqual(set(_politiques()),
                         {"ExtensionSettings", "FirefoxHome", "FirefoxSuggest"})


if __name__ == "__main__":
    unittest.main()
