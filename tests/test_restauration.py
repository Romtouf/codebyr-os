# -*- coding: utf-8 -*-
"""Restauration d'un instantané : accepter les liens, refuser les évasions.

Le lot du 12 septembre refusait TOUT lien dans une archive. L'intention était
juste — un lien peut écrire hors de l'Espace — mais le contrôle refusait aussi
les archives produites par Codebyr lui-même : un dossier personnel avec un
profil Firefox contient des liens symboliques.

« Revenir à un instantané » échouait donc toujours, sur un vrai Espace. On
pouvait sauvegarder, jamais restaurer. Constaté le 12/09/2026 sur une VM, où
l'interface annonçait « restauration impossible ».

Ce qu'il fallait refuser n'est pas le lien, c'est le lien qui SORT. Ces tests
gardent les deux moitiés : le cas réel doit passer, l'évasion doit échouer.
"""
import os
import shutil
import tarfile
import tempfile
import unittest

from outils import BIN, LIB  # noqa: F401 — place les modules partagés sur sys.path
import outils

space = outils.charger("codebyr-space")

ESPACES = {"travail": {"id": "travail", "nom": "Travail"}}


@unittest.skipUnless(hasattr(os, "O_NOFOLLOW") and os.supports_dir_fd,
                     "accès disque par descripteurs (O_NOFOLLOW, dir_fd) — Linux")
class Restauration(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.base, True)
        self._racine, self._sauvegardes = space.DATA_ROOT, space.BACKUP_DIR
        self.addCleanup(setattr, space, "DATA_ROOT", self._racine)
        self.addCleanup(setattr, space, "BACKUP_DIR", self._sauvegardes)
        space.DATA_ROOT = os.path.join(self.base, "espaces")
        space.BACKUP_DIR = os.path.join(self.base, "sauvegardes")
        os.makedirs(space.BACKUP_DIR)
        self.home = os.path.join(space.DATA_ROOT, "travail", "home")
        os.makedirs(self.home)
        with open(os.path.join(self.home, "essai.txt"), "w",
                  encoding="utf-8") as f:
            f.write("contenu")

    def _archiver(self, ajouter=None):
        chemin = os.path.join(space.BACKUP_DIR, "travail-test.tar.gz")
        with tarfile.open(chemin, "w:gz") as tar:
            tar.add(self.home, arcname=".")
            if ajouter:
                ajouter(tar)
        return chemin

    @staticmethod
    def _lien(nom, cible, genre=tarfile.SYMTYPE):
        def ajouter(tar):
            info = tarfile.TarInfo(nom)
            info.type = genre
            info.linkname = cible
            tar.addfile(info)
        return ajouter

    def test_un_lien_interne_passe(self):
        """Le cas réel : tout dossier personnel en contient.

        C'est cette exigence qui rendait la fonction inutilisable.
        """
        os.symlink("essai.txt", os.path.join(self.home, "raccourci"))
        self.assertEqual(space.cmd_import(ESPACES, "travail", self._archiver()), 0)
        self.assertIn("raccourci", os.listdir(self.home))
        self.assertIn("essai.txt", os.listdir(self.home))

    def test_un_lien_absolu_est_refuse(self):
        archive = self._archiver(self._lien("./fuite", "/etc/passwd"))
        self.assertEqual(space.cmd_import(ESPACES, "travail", archive), 1)

    def test_un_lien_traversant_est_refuse(self):
        """« .. » répétés : la façon classique d'écrire hors de la destination."""
        archive = self._archiver(self._lien("./fuite", "../../../../etc/passwd"))
        self.assertEqual(space.cmd_import(ESPACES, "travail", archive), 1)

    def test_un_fichier_special_est_refuse(self):
        """Un tube nommé bloquerait une lecture ; un périphérique ferait pire."""
        def ajouter(tar):
            info = tarfile.TarInfo("./tube")
            info.type = tarfile.FIFOTYPE
            tar.addfile(info)
        self.assertEqual(space.cmd_import(ESPACES, "travail", self._archiver(ajouter)), 1)

    def test_les_anciennes_donnees_sont_conservees(self):
        """Une restauration ne doit jamais être une perte sèche."""
        space.cmd_import(ESPACES, "travail", self._archiver())
        frères = os.listdir(os.path.join(space.DATA_ROOT, "travail"))
        self.assertTrue([n for n in frères if n.startswith("avant-restauration-")],
                        frères)


if __name__ == "__main__":
    unittest.main()
