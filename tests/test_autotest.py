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


class Microcode(unittest.TestCase):
    """Les images jusqu'à la 1.21.1 n'avaient aucun microcode : firmware-linux
    ne fait que le recommander, et l'image se construit sans recommandations."""

    def test_le_paquet_du_fabricant(self):
        ok, detail = autotest.analyser_microcode("GenuineIntel", ["intel-microcode"])
        self.assertTrue(ok)
        ok, detail = autotest.analyser_microcode("AuthenticAMD", ["intel-microcode"])
        self.assertFalse(ok)
        self.assertIn("sudo apt install amd64-microcode", detail)

    def test_un_autre_fabricant_n_est_pas_une_faute(self):
        self.assertTrue(autotest.analyser_microcode("", [])[0])
        self.assertTrue(autotest.analyser_microcode("HygonGenuine", [])[0])

    def test_l_image_et_le_paquet_l_apportent(self):
        import os
        from outils import RACINE
        with open(os.path.join(RACINE, "live-build", "config", "package-lists",
                               "hardening.list.chroot"), encoding="utf-8") as f:
            liste = f.read().split()
        with open(os.path.join(RACINE, "packaging", "build-deb.sh"), encoding="utf-8") as f:
            construction = f.read()
        depend = [l for l in construction.splitlines() if l.startswith("Depends:")][0]
        # Exigé, pas seulement recommandé : la mise à jour automatique
        # n'installe pas les recommandations nouvelles (vu sur la VM, 1.21.2~essai1).
        for paquet in autotest.MICROCODE.values():
            self.assertIn(paquet, liste)
            self.assertIn(paquet, [d.strip() for d in depend[len("Depends:"):].split(",")])

    def test_la_section_qui_les_fournit_est_dans_les_sources(self):
        # Exiger un paquet de non-free-firmware n'est sûr que parce que
        # l'image écrit cette section dans les sources de toute machine.
        import os
        from outils import RACINE
        with open(os.path.join(RACINE, "live-build", "auto", "config"), encoding="utf-8") as f:
            self.assertIn("non-free-firmware", f.read().split("--archive-areas", 1)[1].splitlines()[0])


class Redemarrage(unittest.TestCase):

    def test_rien_en_attente(self):
        self.assertEqual(autotest.analyser_redemarrage(False, [])[0], True)

    def test_un_noyau_attend(self):
        ok, detail = autotest.analyser_redemarrage(
            True, ["linux-image-6.12.57+deb13-amd64", "linux-image-6.12.57+deb13-amd64"])
        self.assertFalse(ok)
        self.assertEqual(detail.count("linux-image-6.12.57+deb13-amd64"), 1)

    def test_le_fichier_de_debian(self):
        # Écrit par /etc/kernel/postinst.d/unattended-upgrades, à chaque noyau.
        self.assertEqual(autotest.REDEMARRAGE, "/run/reboot-required")


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
