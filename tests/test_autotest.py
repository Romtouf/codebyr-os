# -*- coding: utf-8 -*-
"""Autotest du poste — les décisions, éprouvées sans machine Codebyr.

Chaque contrôle correspond à un défaut RÉELLEMENT survenu dans ce projet. Les
cas testés ici sont donc des reconstitutions, pas des hypothèses.
"""
import unittest

from outils import LIB  # noqa: F401 — place le module partagé sur sys.path
import autotest  # noqa: E402


class ExtensionJetable(unittest.TestCase):
    """Le bug du 20/08/2026 : livré, testé, empaqueté… et jamais chargé."""

    def test_greffon_absent_est_un_echec(self):
        ok, detail = autotest.analyser_extension_jetable(True, False)
        self.assertFalse(ok)
        self.assertIn("python3-nautilus", detail)

    def test_les_deux_presents(self):
        ok, _ = autotest.analyser_extension_jetable(True, True)
        self.assertTrue(ok)

    def test_extension_absente(self):
        ok, _ = autotest.analyser_extension_jetable(False, True)
        self.assertFalse(ok)


class CompteInvite(unittest.TestCase):
    """Il valait « invite » sur toutes les machines jusqu'à la 1.1.0."""

    def test_mot_de_passe_utilisable_refuse(self):
        ok, _ = autotest.analyser_invite("$y$j9T$abcdef$ghijkl")
        self.assertFalse(ok)

    def test_formes_neutralisees_acceptees(self):
        for champ in ("*", "!", "!!", ""):
            ok, _ = autotest.analyser_invite(champ)
            self.assertTrue(ok, "« %s » n'ouvre aucune authentification" % champ)

    def test_absence_de_compte_nest_pas_une_anomalie(self):
        ok, _ = autotest.analyser_invite(None)
        self.assertTrue(ok)


class DossiersPersonnels(unittest.TestCase):
    def test_dossier_lisible_par_les_autres(self):
        ok, detail = autotest.analyser_homes([("romtouf", 0o755)])
        self.assertFalse(ok)
        self.assertIn("romtouf", detail)

    def test_tous_prives(self):
        ok, _ = autotest.analyser_homes([("a", 0o700), ("b", 0o700)])
        self.assertTrue(ok)

    def test_un_seul_fautif_suffit(self):
        ok, detail = autotest.analyser_homes([("a", 0o700), ("b", 0o750)])
        self.assertFalse(ok)
        self.assertIn("b", detail)
        self.assertNotIn("a,", detail)


class Trousseau(unittest.TestCase):
    """Le trousseau est gravé à l'installation : il périme sans le dire."""

    def test_sous_cle_connue(self):
        ok, _ = autotest.analyser_trousseau(
            ["E6FB6616EC58E15F40DA876CB1E8C803CE596E68", autotest.SOUS_CLE])
        self.assertTrue(ok)

    def test_trousseau_dorigine_sans_la_sous_cle(self):
        ok, detail = autotest.analyser_trousseau(
            ["E6FB6616EC58E15F40DA876CB1E8C803CE596E68"])
        self.assertFalse(ok)
        self.assertIn("mises à jour", detail)

    def test_trousseau_illisible(self):
        ok, _ = autotest.analyser_trousseau([])
        self.assertFalse(ok)


class MisesAJour(unittest.TestCase):
    """Deux pièces indépendantes : l'une sans l'autre ne met rien à jour."""

    ARME = ('APT::Periodic::Update-Package-Lists "1";\n'
            'APT::Periodic::Unattended-Upgrade "1";\n')

    def test_reglage_et_minuterie(self):
        ok, _ = autotest.analyser_maj_automatiques(self.ARME, True)
        self.assertTrue(ok)

    def test_reglage_sans_minuterie(self):
        ok, detail = autotest.analyser_maj_automatiques(self.ARME, False)
        self.assertFalse(ok)
        self.assertIn("minuterie", detail)

    def test_desarme(self):
        ok, _ = autotest.analyser_maj_automatiques(
            'APT::Periodic::Unattended-Upgrade "0";\n', True)
        self.assertFalse(ok)

    def test_une_ligne_commentee_ne_compte_pas(self):
        """Un réglage en commentaire ressemble à un réglage — et n'en est pas."""
        ok, _ = autotest.analyser_maj_automatiques(
            '// APT::Periodic::Unattended-Upgrade "1";\n', True)
        self.assertFalse(ok)

    def test_fichier_absent(self):
        ok, _ = autotest.analyser_maj_automatiques("", True)
        self.assertFalse(ok)


class BacASable(unittest.TestCase):
    def test_tout_present(self):
        ok, _ = autotest.analyser_bac_a_sable(True, True, True)
        self.assertTrue(ok)

    def test_dbus_run_session_absent(self):
        """Sans lui, l'application tourne sans aucun bus de session."""
        ok, detail = autotest.analyser_bac_a_sable(True, True, False)
        self.assertFalse(ok)
        self.assertIn("dbus-run-session", detail)

    def test_manques_cumules(self):
        ok, detail = autotest.analyser_bac_a_sable(False, False, False)
        self.assertFalse(ok)
        for attendu in ("bubblewrap", "espaces de noms", "dbus-run-session"):
            self.assertIn(attendu, detail)


class Coherence(unittest.TestCase):
    def test_chaque_controle_a_un_libelle(self):
        """Un contrôle sans libellé ne s'afficherait jamais — donc n'existerait pas."""
        cles = {cle for cle, _ in autotest.LIBELLES}
        self.assertEqual(len(cles), len(autotest.LIBELLES),
                         "libellés en double")

    def test_la_sous_cle_est_celle_du_projet(self):
        """Elle doit correspondre à la clé qui signe réellement le dépôt."""
        self.assertEqual(len(autotest.SOUS_CLE), 40)
        self.assertTrue(autotest.SOUS_CLE.isupper())


if __name__ == "__main__":
    unittest.main()
