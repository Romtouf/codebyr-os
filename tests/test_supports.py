# -*- coding: utf-8 -*-
"""Clés USB et disques externes : leurs documents s'ouvrent sous cloche.

Trois choses gardées ici :
- un document posé sur une clé est reconnu, et une clé reconnue par son
  identifiant, même quand son nom contient une espace ;
- VOTRE clé peut cesser de payer pour les autres, et redevenir inconnue ;
- ce qu'un inconnu a pu écrire (un nom de clé, un fichier de préférences
  trafiqué) ne devient jamais une confiance.
"""
import importlib.machinery
import importlib.util
import os
import shutil
import sys
import tempfile
import types
import unittest

from outils import LIB  # noqa: F401 — place le module partagé sur sys.path
import outils
import supports


class Emplacement(unittest.TestCase):
    def test_un_fichier_sur_une_cle(self):
        self.assertTrue(supports.est_amovible("/media/rom/CLE/facture.pdf"))
        self.assertTrue(supports.est_amovible("/run/media/rom/CLE/facture.pdf"))

    def test_les_dossiers_du_poste_ne_sont_pas_une_cle(self):
        for chemin in ("/media", "/media/", "/run/media", "/home/rom/facture.pdf",
                       "/mediatheque/facture.pdf", "/run/mediacenter/x"):
            self.assertFalse(supports.est_amovible(chemin), chemin)


class Montages(unittest.TestCase):
    TEXTE = (
        "22 1 8:2 / / rw,relatime shared:1 - ext4 /dev/sda2 rw\n"
        "36 22 8:17 / /media/rom/MA\\040CLE rw,nosuid shared:7 master:2 - vfat /dev/sdb1 rw\n"
        "ligne illisible\n"
        "40 22 0:5 / /run/user/1000 rw - tmpfs tmpfs rw\n")

    def test_lecture(self):
        montages = supports.lire_montages(self.TEXTE)
        self.assertIn(("/media/rom/MA CLE", "/dev/sdb1"), montages,
                      "l'espace d'un nom de clé est écrite en octal par le noyau")
        self.assertIn(("/", "/dev/sda2"), montages)
        self.assertEqual(len(montages), 3, "une ligne illisible est ignorée")

    def test_le_montage_le_plus_profond(self):
        montages = supports.lire_montages(self.TEXTE)
        self.assertEqual(supports.montage_de("/media/rom/MA CLE/a/b.pdf", montages),
                         ("/media/rom/MA CLE", "/dev/sdb1"))
        self.assertEqual(supports.montage_de("/home/rom/b.pdf", montages),
                         ("/", "/dev/sda2"))

    def test_un_nom_qui_commence_pareil_n_est_pas_dedans(self):
        montages = [("/", "/dev/sda2"), ("/media/rom/CLE", "/dev/sdb1")]
        self.assertEqual(supports.montage_de("/media/rom/CLE2/x.pdf", montages),
                         ("/", "/dev/sda2"))

    def test_deux_montages_empiles(self):
        """Le dernier monté est celui qu'on voit."""
        montages = [("/media/rom/CLE", "/dev/sdb1"), ("/media/rom/CLE", "/dev/sdc1")]
        self.assertEqual(supports.montage_de("/media/rom/CLE/x", montages)[1], "/dev/sdc1")


class Etat(unittest.TestCase):
    def test_hors_d_une_cle(self):
        self.assertIsNone(supports.etat(False, "1234-ABCD", {"1234-ABCD"}))

    def test_cle_inconnue(self):
        self.assertEqual(supports.etat(True, "1234-ABCD", set()), supports.INCONNU)

    def test_cle_de_confiance(self):
        self.assertEqual(supports.etat(True, "1234-ABCD", {"1234-ABCD"}), supports.CONFIANT)

    def test_cle_sans_identifiant(self):
        """On ne peut pas se souvenir d'elle, donc pas lui faire confiance."""
        self.assertEqual(supports.etat(True, None, {"1234-ABCD"}), supports.INCONNU)


@unittest.skipUnless(os.name == "posix" and os.path.exists("/dev/null"),
                     "liens symboliques et /dev : Linux")
class SurDisque(unittest.TestCase):
    def setUp(self):
        self.racine = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.media = os.path.join(self.racine, "media")
        self.cle = os.path.join(self.media, "rom", "MA CLE")
        os.makedirs(self.cle)
        self.fichier = os.path.join(self.cle, "facture.pdf")
        with open(self.fichier, "w") as f:
            f.write("%PDF-1.4")
        self.uuid = os.path.join(self.racine, "by-uuid")
        os.makedirs(self.uuid)
        # /dev/null tient lieu de périphérique : uuid_de ne compare que des
        # chemins résolus.
        os.symlink("/dev/null", os.path.join(self.uuid, "1234-ABCD"))
        self.montages = [("/", "/dev/sda2"), (self.cle, "/dev/null")]
        self.confiance = os.path.join(self.racine, "config", "codebyr",
                                      "supports-de-confiance")

    def decrire(self, chemin):
        return supports.decrire(chemin, self.montages, self.uuid, (self.media,))

    def test_la_cle_est_reconnue(self):
        self.assertEqual(self.decrire(self.fichier),
                         {"point": self.cle, "uuid": "1234-ABCD"})

    def test_un_fichier_du_poste(self):
        ailleurs = os.path.join(self.racine, "ailleurs.pdf")
        open(ailleurs, "w").close()
        self.assertIsNone(self.decrire(ailleurs))

    def test_un_lien_vers_la_cle_compte_comme_la_cle(self):
        """Ce qui compte est l'endroit où le fichier VIT, pas le chemin suivi."""
        lien = os.path.join(self.racine, "raccourci.pdf")
        os.symlink(self.fichier, lien)
        self.assertEqual(self.decrire(lien)["uuid"], "1234-ABCD")

    def test_un_identifiant_bizarre_est_refuse(self):
        os.symlink("/dev/zero", os.path.join(self.uuid, "..\\x2fetc"))
        self.assertIsNone(supports.uuid_de("/dev/zero", self.uuid))

    def test_une_source_qui_n_est_pas_un_peripherique(self):
        self.assertIsNone(supports.uuid_de("tmpfs", self.uuid))
        self.assertIsNone(supports.uuid_de("", self.uuid))

    def test_sous_media_sans_montage_externe(self):
        """Externe quand même, mais sans identifiant : il reste inconnu."""
        self.montages = [("/", "/dev/sda2")]
        self.assertEqual(self.decrire(self.fichier), {"point": None, "uuid": None})

    def test_confiance_donnee_puis_retiree(self):
        def etat():
            return supports.etat_de(self.fichier, self.confiance, self.montages,
                                    self.uuid, (self.media,))
        self.assertEqual(etat(), supports.INCONNU)
        self.assertTrue(supports.faire_confiance("1234-ABCD", self.confiance))
        self.assertEqual(etat(), supports.CONFIANT)
        self.assertEqual(os.stat(os.path.dirname(self.confiance)).st_mode & 0o777, 0o700)
        self.assertTrue(supports.retirer_confiance("1234-ABCD", self.confiance))
        self.assertEqual(etat(), supports.INCONNU)
        self.assertFalse(supports.retirer_confiance("1234-ABCD", self.confiance))

    def test_confiance_donnee_deux_fois(self):
        supports.faire_confiance("1234-ABCD", self.confiance)
        supports.faire_confiance("1234-ABCD", self.confiance)
        with open(self.confiance) as f:
            self.assertEqual(f.read(), "1234-ABCD\n")

    def test_un_identifiant_douteux_ne_devient_pas_une_confiance(self):
        for douteux in ("", "../../etc", "1234-ABCD\nAUTRE", "-x", "a" * 80):
            self.assertFalse(supports.faire_confiance(douteux, self.confiance), douteux)
        self.assertFalse(os.path.exists(self.confiance))

    def test_un_fichier_trafique_est_relu_avec_mefiance(self):
        os.makedirs(os.path.dirname(self.confiance))
        with open(self.confiance, "w") as f:
            f.write("1234-ABCD\n../../etc\n\n  5678-EF01  \n" + "é" * 3 + "\n")
        self.assertEqual(supports.lire_confiance(self.confiance),
                         {"1234-ABCD", "5678-EF01"})

    def test_fichier_absent(self):
        self.assertEqual(supports.lire_confiance(self.confiance), set())


def _charger_extension():
    """L'extension de Fichiers, avec un faux Nautilus : la logique du menu se
    teste sans session graphique."""
    faux_gi = types.ModuleType("gi")
    faux_gi.require_version = lambda *a: None
    depot = types.ModuleType("gi.repository")

    class Base:
        pass

    class MenuItem:
        def __init__(self, **champs):
            self.champs = champs
            self.rappel = None

        def connect(self, _signal, rappel, *args):
            self.rappel = (rappel, args)

    depot.GObject = types.SimpleNamespace(GObject=Base)
    depot.Nautilus = types.SimpleNamespace(
        MenuProvider=type("MenuProvider", (), {}),
        ColumnProvider=type("ColumnProvider", (), {}),
        InfoProvider=type("InfoProvider", (), {}),
        MenuItem=MenuItem, Column=lambda **c: c)
    faux_gi.repository = depot
    anciens = {n: sys.modules.get(n) for n in ("gi", "gi.repository")}
    sys.modules["gi"], sys.modules["gi.repository"] = faux_gi, depot
    try:
        chemin = os.path.join(outils.RACINE, "live-build", "config",
                              "includes.chroot_after_packages", "usr", "share",
                              "nautilus-python", "extensions", "codebyr-provenance.py")
        loader = importlib.machinery.SourceFileLoader("codebyr_provenance_ext", chemin)
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module
    finally:
        for nom, ancien in anciens.items():
            if ancien is None:
                sys.modules.pop(nom, None)
            else:
                sys.modules[nom] = ancien


class FauxFichier:
    def __init__(self, chemin, schema="file"):
        self.chemin, self.schema = chemin, schema

    def get_uri_scheme(self):
        return self.schema

    def get_location(self):
        return types.SimpleNamespace(get_path=lambda: self.chemin)


class MenuDeFichiers(unittest.TestCase):
    """Le clic droit « Faire confiance à cette clé »."""

    def setUp(self):
        self.ext = _charger_extension()
        programme = tempfile.NamedTemporaryFile(delete=False)
        programme.close()
        self.addCleanup(os.unlink, programme.name)
        self.ext.SPACE = programme.name
        self.uuids = {"/media/rom/A/x.pdf": "1234-ABCD", "/media/rom/A/y.pdf": "1234-ABCD",
                      "/media/rom/B/z.pdf": "5678-EF01", "/media/rom/S/n.pdf": None}
        self.confiance = set()
        faux = types.SimpleNamespace(
            CONFIANT=supports.CONFIANT, INCONNU=supports.INCONNU, etat=supports.etat,
            lire_confiance=lambda: set(self.confiance),
            montages_du_systeme=lambda: [],
            decrire=lambda chemin, montages=None: (
                {"point": None, "uuid": self.uuids[chemin]} if chemin in self.uuids else None))
        self.ext.supports = faux
        os.environ.pop("CODEBYR_ESPACE", None)
        self.menu = self.ext.CodebyrConfianceCle()

    def entrees(self, *chemins):
        return self.menu.get_file_items([FauxFichier(c) for c in chemins])

    def test_cle_inconnue(self):
        (entree,) = self.entrees("/media/rom/A/x.pdf", "/media/rom/A/y.pdf")
        self.assertEqual(entree.champs["name"], "Codebyr::FaireConfianceCle")
        self.assertEqual(entree.rappel[1][0], "faire-confiance")

    def test_cle_de_confiance(self):
        self.confiance.add("1234-ABCD")
        (entree,) = self.entrees("/media/rom/A/x.pdf")
        self.assertEqual(entree.rappel[1][0], "retirer-confiance")

    def test_rien_hors_d_une_cle(self):
        self.assertEqual(self.entrees("/home/rom/x.pdf"), [])

    def test_rien_pour_deux_cles_a_la_fois(self):
        self.assertEqual(self.entrees("/media/rom/A/x.pdf", "/media/rom/B/z.pdf"), [])

    def test_rien_pour_une_cle_sans_identifiant(self):
        self.assertEqual(self.entrees("/media/rom/S/n.pdf"), [])

    def test_rien_depuis_un_espace(self):
        os.environ["CODEBYR_ESPACE"] = "travail"
        self.addCleanup(os.environ.pop, "CODEBYR_ESPACE", None)
        self.assertEqual(self.entrees("/media/rom/A/x.pdf"), [])

    def test_clic_dans_le_vide_d_un_dossier_de_la_cle(self):
        (entree,) = self.menu.get_background_items(FauxFichier("/media/rom/A/x.pdf"))
        self.assertEqual(entree.champs["name"], "Codebyr::FaireConfianceCle")

    def test_emplacement_distant(self):
        self.assertEqual(self.menu.get_file_items(
            [FauxFichier("/media/rom/A/x.pdf", "sftp")]), [])


if __name__ == "__main__":
    unittest.main()
