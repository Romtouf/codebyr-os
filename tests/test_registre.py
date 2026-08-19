# -*- coding: utf-8 -*-
"""Le registre des Espaces livré dans l'image (/etc/codebyr/espaces.json).

Un registre invalide casse TOUT : l'extension GNOME, le lanceur, la
configuration. Il est lu par trois programmes différents (Python ×2, GJS ×1) —
raison de plus pour le valider en CI plutôt qu'au premier démarrage.
"""
import json
import os
import re
import unittest

from outils import ETC

CHEMIN = os.path.join(ETC, "codebyr", "espaces.json")
COULEUR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class Registre(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(CHEMIN, encoding="utf-8") as f:
            cls.data = json.load(f)
        cls.espaces = cls.data["espaces"]

    def test_champs_obligatoires(self):
        for e in self.espaces:
            for champ in ("id", "nom", "couleur"):
                self.assertIn(champ, e, "Espace sans « %s » : %r" % (champ, e))
            self.assertRegex(e["couleur"], COULEUR)

    def test_identifiants_uniques(self):
        ids = [e["id"] for e in self.espaces]
        self.assertEqual(len(ids), len(set(ids)), "identifiants dupliqués : %s" % ids)

    def test_espaces_integres_presents(self):
        # Ces identifiants sont codés en dur dans l'extension GNOME (BUILTIN)
        # et dans codebyr-space : ils ne peuvent pas disparaître du registre.
        ids = {e["id"] for e in self.espaces}
        for attendu in ("personnel", "travail", "banque", "navigation", "jetable"):
            self.assertIn(attendu, ids)

    def test_un_seul_espace_ephemere(self):
        ephemeres = [e["id"] for e in self.espaces if e.get("ephemere")]
        self.assertEqual(ephemeres, ["jetable"])

    def test_banque_est_verrouillee_par_defaut(self):
        banque = next(e for e in self.espaces if e["id"] == "banque")
        self.assertEqual(banque.get("blindage"), "renforce")
        self.assertEqual(banque.get("audio"), False,
                         "Banque doit être sans micro (socket PipeWire coupé)")
        self.assertEqual(banque.get("reseau", {}).get("mode"), "liste-blanche")
        # Aucun domaine d'exemple livré : un « example.com » par défaut ferait
        # crier le bouclier anti-hameçonnage sur tout site contenant « example ».
        self.assertEqual(banque["reseau"].get("domaines"), [])

    def test_les_applications_par_defaut_sont_utilisables(self):
        for app in self.data.get("apps", []):
            self.assertTrue(app.get("nom"))
            self.assertTrue(app.get("cmd"))


if __name__ == "__main__":
    unittest.main()
