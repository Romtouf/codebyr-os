# -*- coding: utf-8 -*-
"""Modèles de documents — pour que « Nouveau document » existe.

GNOME Fichiers n'affiche cette entrée que si le dossier Modèles contient au
moins un fichier. Vide, le menu disparaît : il ne reste que « Nouveau
dossier », et créer un fichier texte oblige à ouvrir un terminal pour taper
« touch ». Sur un système qui vise des gens qui n'ouvriront jamais de
terminal, c'est une impasse — signalée par le mainteneur le 24/08/2026.
"""
import os
import shutil
import tempfile
import unittest

from outils import LIB, RACINE  # noqa: F401 — place le module partagé sur sys.path
import modeles  # noqa: E402

SOURCE = os.path.join(
    RACINE, "live-build", "config", "includes.chroot_after_packages",
    "usr", "share", "codebyr", "modeles")


class DossierDeclare(unittest.TestCase):
    """Le nom du dossier dépend de la langue : « Modèles », « Templates »…

    Il est déclaré par xdg-user-dirs dans une syntaxe shell dont on ne lit
    qu'une ligne. Le deviner mènerait à remplir un dossier que Fichiers ne
    regarde pas — et le menu resterait absent sans que rien ne l'explique.
    """

    def test_forme_habituelle(self):
        self.assertEqual(
            modeles.dossier_declare('XDG_TEMPLATES_DIR="$HOME/Modèles"'),
            "Modèles")

    def test_anglais(self):
        self.assertEqual(
            modeles.dossier_declare('XDG_TEMPLATES_DIR="$HOME/Templates"'),
            "Templates")

    def test_chemin_absolu(self):
        self.assertEqual(
            modeles.dossier_declare('XDG_TEMPLATES_DIR="/srv/modeles"'),
            "/srv/modeles")

    def test_parmi_les_autres_lignes(self):
        contenu = ('XDG_DESKTOP_DIR="$HOME/Bureau"\n'
                   'XDG_TEMPLATES_DIR="$HOME/Modèles"\n'
                   'XDG_DOWNLOAD_DIR="$HOME/Téléchargements"\n')
        self.assertEqual(modeles.dossier_declare(contenu), "Modèles")

    def test_absent(self):
        self.assertIsNone(modeles.dossier_declare('XDG_DESKTOP_DIR="$HOME/Bureau"'))

    def test_fichier_vide(self):
        self.assertIsNone(modeles.dossier_declare(""))
        self.assertIsNone(modeles.dossier_declare(None))


class ChoixDesFichiers(unittest.TestCase):
    def test_rien_de_present(self):
        self.assertEqual(modeles.a_installer(["a.txt", "b.csv"], set()),
                         ["a.txt", "b.csv"])

    def test_un_modele_personnalise_est_respecte(self):
        """Celui qui a modifié le sien l'a fait exprès."""
        self.assertEqual(modeles.a_installer(["a.txt", "b.csv"], {"a.txt"}),
                         ["b.csv"])

    def test_deja_complet(self):
        self.assertEqual(
            modeles.a_installer(["a.txt"], {"a.txt", "autre.odt"}), [])


class Installation(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, True)

    def test_depot_dans_le_dossier_par_defaut(self):
        poses = modeles.installer(self.home, SOURCE)
        self.assertGreater(poses, 0)
        self.assertTrue(os.listdir(os.path.join(self.home, modeles.DEFAUT)))

    def test_le_dossier_declare_est_suivi(self):
        config = os.path.join(self.home, ".config")
        os.makedirs(config)
        with open(os.path.join(config, "user-dirs.dirs"), "w",
                  encoding="utf-8") as f:
            f.write('XDG_TEMPLATES_DIR="$HOME/Templates"\n')
        modeles.installer(self.home, SOURCE)
        self.assertTrue(os.path.isdir(os.path.join(self.home, "Templates")))
        self.assertFalse(os.path.isdir(os.path.join(self.home, modeles.DEFAUT)))

    def test_la_declaration_est_ecrite_si_elle_manque(self):
        """Sans elle, GNOME ne sait pas où chercher — et le menu reste absent.

        Ce chemin n'a AUCUNE valeur par défaut : il est écrit par xdg-user-dirs
        à la première connexion, un programme qui ne tourne jamais dans un bac
        à sable. Le dossier existait donc dans les Espaces et personne ne le
        regardait : « Nouveau document » n'apparaissait que sur le bureau.
        Constaté le 24/08/2026.
        """
        modeles.installer(self.home, SOURCE)
        with open(os.path.join(self.home, modeles.DECLARATION),
                  encoding="utf-8") as f:
            self.assertEqual(modeles.dossier_declare(f.read()), modeles.DEFAUT)

    def test_une_declaration_existante_n_est_pas_doublee(self):
        config = os.path.join(self.home, ".config")
        os.makedirs(config)
        with open(os.path.join(config, "user-dirs.dirs"), "w",
                  encoding="utf-8") as f:
            f.write('XDG_TEMPLATES_DIR="$HOME/Templates"\n')
        modeles.installer(self.home, SOURCE)
        modeles.installer(self.home, SOURCE)
        with open(os.path.join(config, "user-dirs.dirs"), encoding="utf-8") as f:
            self.assertEqual(f.read().count("XDG_TEMPLATES_DIR"), 1)

    def test_second_passage_ne_repose_rien(self):
        """Appelé à CHAQUE ouverture d'Espace : il doit être sans effet ensuite."""
        modeles.installer(self.home, SOURCE)
        self.assertEqual(modeles.installer(self.home, SOURCE), 0)

    def test_source_absente_ne_casse_rien(self):
        self.assertEqual(modeles.installer(self.home, "/inexistant"), 0)


class Livraison(unittest.TestCase):
    def test_des_modeles_sont_livres(self):
        """Sans fichier, le menu reste absent : c'est tout l'objet."""
        self.assertTrue(os.path.isdir(SOURCE))
        self.assertTrue(os.listdir(SOURCE))

    def test_ils_sont_aussi_dans_etc_skel(self):
        """Pour les comptes créés APRÈS l'installation."""
        skel = os.path.join(
            RACINE, "live-build", "config", "includes.chroot_after_packages",
            "etc", "skel", "Modèles")
        self.assertTrue(os.path.isdir(skel))
        self.assertEqual(sorted(os.listdir(skel)), sorted(os.listdir(SOURCE)))


if __name__ == "__main__":
    unittest.main()
