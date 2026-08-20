# -*- coding: utf-8 -*-
"""La détection des applications installées, via les fichiers `.desktop`.

Elle décide de ce que l'utilisateur voit dans le menu du Sceau. Une entrée mal
analysée, et l'application est simplement absente — sans message, sans trace.
Cette logique vivait dans `codebyr-config`, qui importe GTK : impossible à
charger dans un test. Elle est maintenant dans le module partagé.
"""
import os
import tempfile
import unittest

from outils import LIB  # noqa: F401 — place le module partagé sur sys.path
import applications     # noqa: E402


def ecrire(dossier, nom, contenu):
    chemin = os.path.join(dossier, nom)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(contenu)
    return chemin


class Detection(unittest.TestCase):

    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.dossier = self._d.name

    def tearDown(self):
        self._d.cleanup()

    def test_entree_ordinaire(self):
        ecrire(self.dossier, "org.gnome.Calculator.desktop",
               "[Desktop Entry]\nType=Application\nName=Calculator\nExec=gnome-calculator\n")
        self.assertEqual(applications.installees([self.dossier]),
                         [("Calculator", "gnome-calculator")])

    def test_le_nom_francais_est_prefere(self):
        ecrire(self.dossier, "a.desktop",
               "[Desktop Entry]\nType=Application\nName=Files\nName[fr]=Fichiers\n"
               "Exec=nautilus\n")
        self.assertEqual(applications.installees([self.dossier])[0][0], "Fichiers")

    def test_les_codes_de_champ_sont_retires(self):
        ecrire(self.dossier, "a.desktop",
               "[Desktop Entry]\nType=Application\nName=Éditeur\n"
               "Exec=gnome-text-editor %U --new-window %i\n")
        self.assertEqual(applications.installees([self.dossier])[0][1],
                         "gnome-text-editor --new-window")

    def test_les_entrees_cachees_restent_cachees(self):
        # Leur auteur a décidé qu'elles ne devaient pas s'afficher : ce n'est
        # pas à nous de les faire réapparaître.
        for i, cle in enumerate(("NoDisplay=true", "Hidden=true", "Type=Link")):
            ecrire(self.dossier, "cachee%d.desktop" % i,
                   "[Desktop Entry]\nType=Application\nName=Cachee%d\n"
                   "Exec=x\n%s\n" % (i, cle))
        self.assertEqual(applications.installees([self.dossier]), [])

    def test_nos_propres_lanceurs_sont_exclus(self):
        for nom in ("io.codebyr.Config.desktop", "codebyr-bienvenue.desktop"):
            ecrire(self.dossier, nom,
                   "[Desktop Entry]\nType=Application\nName=Interne\nExec=x\n")
        self.assertEqual(applications.installees([self.dossier]), [])

    def test_fichier_illisible_ignore_sans_planter(self):
        ecrire(self.dossier, "casse.desktop", "ceci n'est pas un fichier desktop")
        ecrire(self.dossier, "bon.desktop",
               "[Desktop Entry]\nType=Application\nName=Bon\nExec=bon\n")
        self.assertEqual(applications.installees([self.dossier]), [("Bon", "bon")])

    def test_sans_nom_ou_sans_commande(self):
        ecrire(self.dossier, "a.desktop", "[Desktop Entry]\nType=Application\nExec=x\n")
        ecrire(self.dossier, "b.desktop", "[Desktop Entry]\nType=Application\nName=B\n")
        self.assertEqual(applications.installees([self.dossier]), [])

    def test_tri_insensible_a_la_casse(self):
        for nom in ("zèbre", "Abeille", "moineau"):
            ecrire(self.dossier, nom + ".desktop",
                   "[Desktop Entry]\nType=Application\nName=%s\nExec=%s\n" % (nom, nom))
        noms = [n for n, _c in applications.installees([self.dossier])]
        self.assertEqual(noms, ["Abeille", "moineau", "zèbre"])

    def test_doublon_le_premier_dossier_gagne(self):
        autre = tempfile.mkdtemp()
        try:
            ecrire(self.dossier, "a.desktop",
                   "[Desktop Entry]\nType=Application\nName=Deux fois\nExec=premier\n")
            ecrire(autre, "b.desktop",
                   "[Desktop Entry]\nType=Application\nName=Deux fois\nExec=second\n")
            self.assertEqual(applications.installees([self.dossier, autre]),
                             [("Deux fois", "premier")])
        finally:
            import shutil
            shutil.rmtree(autre, ignore_errors=True)


class Flatpak(unittest.TestCase):
    """Pour un Flatpak, la ligne Exec contient des jetons propres au lanceur.
    L'identifiant du fichier donne une commande stable et lisible."""

    def test_la_commande_vient_de_l_identifiant(self):
        d = tempfile.mkdtemp()
        flat = os.path.join(d, "flatpak")
        os.makedirs(flat)
        try:
            ecrire(flat, "org.kde.konsole.desktop",
                   "[Desktop Entry]\nType=Application\nName=Konsole\n"
                   "Exec=/usr/bin/flatpak run --branch=stable @@u %U @@\n")
            self.assertEqual(applications.installees([flat]),
                             [("Konsole", "flatpak run org.kde.konsole")])
        finally:
            import shutil
            shutil.rmtree(d, ignore_errors=True)


class Resolution(unittest.TestCase):
    """`resoudre()` : d'un identifiant `.desktop` à une commande exécutable."""

    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.dossier = self._d.name

    def tearDown(self):
        self._d.cleanup()

    def test_commande_simple(self):
        ecrire(self.dossier, "org.gnome.Nautilus.desktop",
               "[Desktop Entry]\nType=Application\nName=Fichiers\nExec=nautilus %U\n")
        self.assertEqual(
            applications.resoudre("org.gnome.Nautilus.desktop", [self.dossier]),
            ["nautilus"])

    def test_les_actions_ne_sont_pas_confondues_avec_l_application(self):
        # Un .desktop peut contenir plusieurs Exec : ceux des « [Desktop Action] ».
        # Lire la première ligne venue lançait potentiellement autre chose.
        ecrire(self.dossier, "firefox-esr.desktop",
               "[Desktop Entry]\nType=Application\nName=Firefox\n"
               "Exec=/usr/lib/firefox-esr/firefox-esr %u\n"
               "Actions=new-private-window;\n\n"
               "[Desktop Action new-private-window]\n"
               "Name=Fenêtre privée\n"
               "Exec=/usr/lib/firefox-esr/firefox-esr --private-window %u\n")
        self.assertEqual(
            applications.resoudre("firefox-esr.desktop", [self.dossier]),
            ["/usr/lib/firefox-esr/firefox-esr"])

    def test_chemin_avec_espaces_entre_guillemets(self):
        # « Exec="/opt/Mon App/bin" %U » est UNE commande, pas deux.
        ecrire(self.dossier, "app.desktop",
               '[Desktop Entry]\nType=Application\nName=App\n'
               'Exec="/opt/Mon App/bin" --flag %U\n')
        self.assertEqual(applications.resoudre("app.desktop", [self.dossier]),
                         ["/opt/Mon App/bin", "--flag"])

    def test_identifiant_inconnu_traite_comme_une_commande(self):
        self.assertEqual(applications.resoudre("firefox-esr", [self.dossier]),
                         ["firefox-esr"])
        self.assertEqual(applications.resoudre("absent.desktop", [self.dossier]),
                         ["absent"])


class UtiliseeParLaConfiguration(unittest.TestCase):

    def test_codebyr_config_passe_par_le_module(self):
        from outils import BIN
        with open(os.path.join(BIN, "codebyr-config"), encoding="utf-8") as f:
            code = f.read()
        self.assertIn("applications.installees()", code)
        self.assertNotIn("def apps_installees", code,
                         "la détection ne doit plus être dupliquée dans l'interface")


if __name__ == "__main__":
    unittest.main()
