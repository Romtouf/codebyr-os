# -*- coding: utf-8 -*-
"""Provenance des fichiers — la couleur d'un Espace suit ce qui en sort.

Les Espaces cloisonnent les processus, pas les fichiers. Un document
téléchargé dans Navigation, envoyé dans Travail puis ouvert, s'y exécute avec
les droits de Travail : le bac à sable a tenu, c'est l'utilisateur qui a porté
la menace de l'autre côté — d'un geste que le clic droit encourage désormais.

Les décisions sont pures et testées ici. L'écriture des attributs étendus est
propre à Linux : elle est vérifiée à part, quand la plateforme le permet.
"""
import os
import tempfile
import unittest

from outils import LIB  # noqa: F401 — place le module partagé sur sys.path
import provenance  # noqa: E402


class Identifiants(unittest.TestCase):
    """Ce qui entre dans un attribut étendu doit être contraint.

    La valeur finit dans une interface et dans des chemins ; l'attribut, lui,
    est inscriptible par n'importe quel programme du poste.
    """

    def test_formes_acceptees(self):
        for bon in ("travail", "banque", "espace-2", "a"):
            self.assertTrue(provenance.identifiant_valide(bon), bon)

    def test_formes_refusees(self):
        for mauvais in ("", None, "../etc", "Travail", "esp ace", "a" * 33,
                        "-debut", "esp;rm -rf /", "espace\n"):
            self.assertFalse(provenance.identifiant_valide(mauvais), repr(mauvais))


class ParEmplacement(unittest.TestCase):
    """Un fichier encore chez lui n'a pas besoin d'être marqué.

    C'est ce qui rend la fonction utile : la marque n'était posée qu'à l'envoi,
    alors qu'un fichier entre surtout dans un Espace par TÉLÉCHARGEMENT. Ces
    fichiers-là n'étaient marqués nulle part, et leur surveillance aurait
    demandé un processus permanent — leur emplacement le dit déjà.
    """

    RACINE = "/home/moi/.local/share/codebyr/espaces"

    def test_fichier_dans_le_dossier_personnel_d_un_espace(self):
        self.assertEqual(
            provenance.origine_par_chemin(
                self.RACINE + "/navigation/home/Téléchargements/x.pdf", self.RACINE),
            "navigation")

    def test_fichier_hors_de_tout_espace(self):
        self.assertIsNone(
            provenance.origine_par_chemin("/home/moi/Documents/x.pdf", self.RACINE))

    def test_le_dossier_de_l_espace_lui_meme_ne_compte_pas(self):
        """« <id>/home » désigne le dossier, pas un fichier qui s'y trouve."""
        self.assertIsNone(
            provenance.origine_par_chemin(self.RACINE + "/travail/home", self.RACINE))

    def test_fichier_hors_du_dossier_personnel(self):
        """Les fichiers de service d'un Espace ne sont pas des documents."""
        self.assertIsNone(
            provenance.origine_par_chemin(
                self.RACINE + "/banque/domaines-refuses.txt", self.RACINE))

    def test_identifiant_impossible_refuse(self):
        self.assertIsNone(
            provenance.origine_par_chemin(self.RACINE + "/../home/x", self.RACINE))

    def test_sans_racine(self):
        self.assertIsNone(provenance.origine_par_chemin("/x/y", None))


class Decision(unittest.TestCase):
    def test_fichier_du_meme_espace(self):
        self.assertFalse(provenance.doit_isoler("travail", "travail"))

    def test_fichier_venu_d_ailleurs(self):
        self.assertTrue(provenance.doit_isoler("navigation", "travail"))

    def test_origine_inconnue_ne_declenche_rien(self):
        """La marque est un indice, pas une frontière.

        Traiter l'absence d'indice comme une accusation rendrait le système
        inutilisable dès le premier fichier venu d'une clé USB — et apprendrait
        à écarter l'avertissement, ce que le projet refuse par principe.
        """
        self.assertFalse(provenance.doit_isoler(None, "travail"))
        self.assertFalse(provenance.doit_isoler("", "travail"))

    def test_hors_de_tout_espace(self):
        """Sur le bureau, aucun fichier n'est « étranger » : il n'y a pas d'ici."""
        self.assertFalse(provenance.doit_isoler("navigation", None))


class Resume(unittest.TestCase):
    """Dire la contagion plutôt que la supposer absente."""

    def test_compte_par_origine(self):
        origines = ["navigation", "navigation", "banque", "travail", None]
        self.assertEqual(provenance.resumer(origines, "travail"),
                         {"navigation": 2, "banque": 1})

    def test_espace_sain(self):
        self.assertEqual(provenance.resumer(["travail", "travail"], "travail"), {})

    def test_sans_fichier(self):
        self.assertEqual(provenance.resumer([], "travail"), {})


@unittest.skipUnless(hasattr(os, "setxattr"), "attributs étendus (Linux seulement)")
class SurDisque(unittest.TestCase):
    """L'aller-retour réel, quand la plateforme le permet."""

    def setUp(self):
        self.dossier = tempfile.mkdtemp()

    def _fichier(self, nom="doc.pdf"):
        chemin = os.path.join(self.dossier, nom)
        with open(chemin, "w", encoding="utf-8") as f:
            f.write("contenu")
        return chemin

    def test_marquer_puis_relire(self):
        chemin = self._fichier()
        self.assertTrue(provenance.marquer(chemin, "navigation"))
        self.assertEqual(provenance.origine(chemin), "navigation")

    def test_fichier_non_marque(self):
        self.assertIsNone(provenance.origine(self._fichier()))

    def test_identifiant_invalide_refuse(self):
        chemin = self._fichier()
        self.assertFalse(provenance.marquer(chemin, "../etc/passwd"))
        self.assertIsNone(provenance.origine(chemin))

    def test_valeur_falsifiee_relue_comme_absente(self):
        """L'attribut est inscriptible par n'importe quel programme du poste.

        Ce qui vient du disque n'est pas plus digne de confiance que ce qui
        vient du réseau : on revalide à la lecture.
        """
        chemin = self._fichier()
        os.setxattr(chemin, provenance.ATTRIBUT, b"../../etc; rm -rf /")
        self.assertIsNone(provenance.origine(chemin))

    def test_heritage_a_la_copie(self):
        """Sans report, la marque disparaîtrait au premier franchissement."""
        source = self._fichier("source.pdf")
        provenance.marquer(source, "navigation")
        copie = self._fichier("copie.pdf")
        self.assertTrue(provenance.heriter(source, copie))
        self.assertEqual(provenance.origine(copie), "navigation")

    def test_heritage_depuis_un_fichier_nu(self):
        self.assertFalse(provenance.heriter(self._fichier("a"), self._fichier("b")))


if __name__ == "__main__":
    unittest.main()
