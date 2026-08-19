# -*- coding: utf-8 -*-
"""Le registre des Espaces est lu par TROIS programmes indépendants.

`codebyr-space` (Python), `codebyr-config` (Python/GTK), `codebyr-assistant`
(Python/GTK) et l'extension GNOME (GJS) ont chacun leur propre lecture du
registre — impossible de partager du code entre Python et GJS, et les outils
Python restent volontairement sans dépendance interne (ce sont des commandes,
pas une bibliothèque).

Cette duplication est assumée, mais elle DOIT rester cohérente : la copie
utilisateur (`~/.config/codebyr/espaces.json`) prime toujours sur la copie
système (`/etc/codebyr/espaces.json`). Un oubli de cette règle est un bug
silencieux — il s'est produit dans `codebyr-assistant`, qui affichait « aucune
banque enregistrée » à un utilisateur qui venait d'enregistrer la sienne.
"""
import json
import os
import tempfile
import unittest

from outils import BIN, RACINE, charger

EXTENSION = os.path.join(
    RACINE, "live-build", "config", "includes.chroot_after_packages", "usr",
    "share", "gnome-shell", "extensions", "codebyr@codebyr.io", "extension.js")

PYTHON_LECTEURS = ("codebyr-space", "codebyr-config", "codebyr-assistant")


class PrecedenceDeclaree(unittest.TestCase):
    """Chaque lecteur déclare-t-il bien les deux chemins, dans le bon ordre ?"""

    def _source(self, chemin):
        with open(chemin, encoding="utf-8") as f:
            return f.read()

    def test_les_lecteurs_python_connaissent_les_deux_copies(self):
        for nom in PYTHON_LECTEURS:
            code = self._source(os.path.join(BIN, nom))
            self.assertIn("/etc/codebyr/espaces.json", code, nom)
            self.assertIn("~/.config/codebyr/espaces.json", code, nom)
            # La copie utilisateur est testée EN PREMIER (« if os.path.exists »).
            self.assertRegex(
                code, r"USER(_REGISTRY)?\s+if\s+os\.path\.exists\(USER(_REGISTRY)?\)",
                "%s : la copie utilisateur doit primer sur la copie système" % nom)

    def test_l_extension_gnome_applique_la_meme_regle(self):
        code = self._source(EXTENSION)
        self.assertIn("/etc/codebyr/espaces.json", code)
        self.assertIn("/.config/codebyr/espaces.json", code)
        self.assertIn("GLib.file_test(u, GLib.FileTest.EXISTS) ? u : REGISTRY", code)


class PrecedenceEffective(unittest.TestCase):
    """Et le lecteur principal se comporte-t-il vraiment ainsi ?"""

    def test_la_copie_utilisateur_prime(self):
        espace = charger("codebyr-space")
        with tempfile.TemporaryDirectory() as d:
            systeme = os.path.join(d, "systeme.json")
            utilisateur = os.path.join(d, "utilisateur.json")
            with open(systeme, "w", encoding="utf-8") as f:
                json.dump({"espaces": [{"id": "banque", "nom": "Banque",
                                        "couleur": "#2FA36B"}]}, f)
            with open(utilisateur, "w", encoding="utf-8") as f:
                json.dump({"espaces": [{"id": "banque", "nom": "Ma banque à moi",
                                        "couleur": "#2FA36B"},
                                       {"id": "perso", "nom": "Perso",
                                        "couleur": "#4E8FEF"}]}, f)
            espace.REGISTRY = systeme
            espace.USER_REGISTRY = utilisateur
            charges = espace.load_espaces()
            self.assertEqual(charges["banque"]["nom"], "Ma banque à moi")
            self.assertIn("perso", charges)

            # Sans copie utilisateur, on retombe sur la copie système.
            espace.USER_REGISTRY = os.path.join(d, "absent.json")
            self.assertEqual(espace.load_espaces()["banque"]["nom"], "Banque")

    def test_un_registre_illisible_ne_fait_pas_planter(self):
        espace = charger("codebyr-space")
        with tempfile.TemporaryDirectory() as d:
            casse = os.path.join(d, "casse.json")
            with open(casse, "w", encoding="utf-8") as f:
                f.write("{ ceci n'est pas du JSON")
            espace.REGISTRY = casse
            espace.USER_REGISTRY = os.path.join(d, "absent.json")
            self.assertEqual(espace.load_espaces(), {})


if __name__ == "__main__":
    unittest.main()
