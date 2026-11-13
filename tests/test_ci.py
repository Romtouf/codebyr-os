# -*- coding: utf-8 -*-
"""La CI elle-même : ce qu'elle exécute, et ce qu'elle surveille."""
from datetime import datetime, timezone
import glob
import importlib.util
import os
import re
import unittest

from outils import RACINE

FLUX = sorted(glob.glob(os.path.join(RACINE, ".github", "workflows", "*.yml")))


def _lire(chemin):
    with open(chemin, encoding="utf-8") as f:
        return f.read()


def _module_echeances():
    chemin = os.path.join(RACINE, "tools", "surveiller_echeances.py")
    spec = importlib.util.spec_from_file_location("surveiller_echeances", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LesActions(unittest.TestCase):
    """Une étiquette (« @v7 ») se déplace : qui la contrôle change ce que la
    CI exécute — et la CI construit le paquet qu'installent, en root, toutes
    les machines. Une empreinte de commit, elle, ne bouge pas. Dependabot
    met à jour l'empreinte et le commentaire de version."""

    def test_epinglees_par_empreinte(self):
        self.assertTrue(FLUX)
        for flux in FLUX:
            for ligne in _lire(flux).splitlines():
                if "uses:" not in ligne:
                    continue
                self.assertRegex(ligne, r"uses: [\w./-]+@[0-9a-f]{40} # v\d",
                                 "%s : %s" % (os.path.basename(flux), ligne.strip()))

    def test_droits_minimaux_declares(self):
        # Sans « permissions: », un jeton aux droits d'écriture par défaut.
        # Seule la signature du bouclier écrit : elle commite le .xpi signé.
        for flux in FLUX:
            droit = re.search(r"(?m)^permissions:\n  contents: (\w+)$", _lire(flux))
            self.assertIsNotNone(droit, os.path.basename(flux))
            attendu = "write" if os.path.basename(flux) == "signer-bouclier.yml" else "read"
            self.assertEqual(droit.group(1), attendu, os.path.basename(flux))


class LesEcheances(unittest.TestCase):
    """Un dépôt périmé ou une sous-clé expirée arrête les mises à jour de tout
    le parc, sans rien afficher."""

    def setUp(self):
        self.m = _module_echeances()

    def test_surveillees_chaque_semaine(self):
        flux = _lire(os.path.join(RACINE, ".github", "workflows", "surveiller-echeances.yml"))
        self.assertIn("cron:", flux)
        self.assertIn("python3 tools/surveiller_echeances.py", flux)
        self.assertIn("gh issue create", flux)
        self.assertEqual(set(self.m.DEPOTS.values()),
                         {"https://apt.codebyr.dev/Release",
                          "https://apt.codebyr.dev/essai/Release"})

    def test_lit_le_valid_until(self):
        release = "Origin: Codebyr OS\nValid-Until: Thu, 14 Jan 2027 06:45:32 +0000\nSuite: stable\n"
        self.assertEqual(self.m.valide_jusqu_a(release),
                         datetime(2027, 1, 14, 6, 45, 32, tzinfo=timezone.utc))
        self.assertIsNone(self.m.valide_jusqu_a("Origin: Codebyr OS\n"))

    def test_lit_les_echeances_de_la_cle(self):
        colonnes = ("pub:-:255:22:B1E8C803CE596E68:1783527007:1846599007::-:::scSC:::::ed25519:::0:\n"
                    "fpr:::::::::E6FB6616EC58E15F40DA876CB1E8C803CE596E68:\n"
                    "sub:-:255:22:5884F50B88581C19:1787228167:1818764167:::::s:::::ed25519::\n"
                    "sub:e:255:22:0000000000000001:1700000000:1710000000:::::s:::::ed25519::\n"
                    "sub:-:255:18:0000000000000002:1787228167:1818764167:::::e:::::cv25519::\n")
        roles = [(e, r) for e, r, _ in self.m.echeances_de_la_cle(colonnes)]
        # La sous-clé déjà expirée et celle de chiffrement ne comptent pas.
        self.assertEqual(roles, [("B1E8C803CE596E68", "clé maîtresse"),
                                 ("5884F50B88581C19", "sous-clé de signature")])

    def test_alerte_sous_la_marge_seulement(self):
        maintenant = datetime(2026, 12, 1, tzinfo=timezone.utc)
        echeances = [("loin", datetime(2027, 3, 1, tzinfo=timezone.utc), 30, "r"),
                     ("proche", datetime(2026, 12, 20, tzinfo=timezone.utc), 30, "r"),
                     ("passé", datetime(2026, 11, 1, tzinfo=timezone.utc), 30, "r")]
        self.assertEqual([a[0] for a in self.m.alertes(echeances, maintenant)],
                         ["proche", "passé"])

    def test_la_cle_lue_est_celle_du_depot(self):
        self.assertTrue(os.path.samefile(self.m.CLE, os.path.join(RACINE, "codebyr-signing-key.asc")))


if __name__ == "__main__":
    unittest.main()
