# -*- coding: utf-8 -*-
"""« Envoyer vers l'Espace… » — le geste inverse du Jetable.

Le Jetable est le geste de la méfiance : une pièce jointe douteuse, examinée
blindée et sans réseau. Envoyer est celui de la confiance : on classe un
document, et l'Espace de destination doit rester ce qu'il est.

Confondre les deux serait une régression discrète et coûteuse — un document de
travail envoyé dans un Espace soudain privé de réseau, sans explication.
"""
import os
import shutil
import tempfile
import unittest

from outils import BIN, LIB  # noqa: F401 — place le module partagé sur sys.path
import outils

space = outils.charger("codebyr-space")


class NomLibre(unittest.TestCase):
    """Écraser en silence serait le pire comportement possible ici.

    L'utilisateur ne saurait même pas qu'il a perdu quelque chose : le geste,
    lui, a parfaitement l'air d'avoir réussi.
    """

    def test_dossier_vide_garde_le_nom(self):
        self.assertEqual(
            space.nom_libre("/x", "rapport.pdf", existe=lambda p: False),
            "rapport.pdf")

    def test_collision_numerote_sans_ecraser(self):
        pris = {os.path.join("/x", "rapport.pdf")}
        self.assertEqual(
            space.nom_libre("/x", "rapport.pdf", existe=lambda p: p in pris),
            "rapport (2).pdf")

    def test_collisions_successives(self):
        pris = {os.path.join("/x", n) for n in
                ("rapport.pdf", "rapport (2).pdf", "rapport (3).pdf")}
        self.assertEqual(
            space.nom_libre("/x", "rapport.pdf", existe=lambda p: p in pris),
            "rapport (4).pdf")

    def test_extension_preservee(self):
        """« rapport (2).tar.gz » serait faux, mais « .gz » doit survivre."""
        pris = {os.path.join("/x", "archive.tar.gz")}
        obtenu = space.nom_libre("/x", "archive.tar.gz",
                                 existe=lambda p: p in pris)
        self.assertTrue(obtenu.endswith(".gz"), obtenu)

    def test_fichier_sans_extension(self):
        pris = {os.path.join("/x", "NOTES")}
        self.assertEqual(
            space.nom_libre("/x", "NOTES", existe=lambda p: p in pris),
            "NOTES (2)")

    def test_abandonne_plutot_que_de_boucler(self):
        """Mille collisions : on rend la main au lieu de tourner sans fin."""
        self.assertIsNone(
            space.nom_libre("/x", "a.txt", existe=lambda p: True))


class BoiteDEnvoi(unittest.TestCase):
    """Le passage par lequel un fichier sort d'un Espace.

    Le bac à sable monte le dossier de l'Espace PAR-DESSUS « ~ ». À
    l'intérieur, la racine des données désigne donc un dossier fantôme du bac à
    sable, sans rapport avec les vrais Espaces : « envoyer » y copiait le
    fichier et annonçait « Copié dans Travail ». Il n'arrivait jamais.
    Constaté le 24/08/2026 par le mainteneur, sur sa machine.

    L'Espace dépose maintenant dans SA boîte ; l'hôte relève et distribue.
    """

    def setUp(self):
        self.hote = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.hote, True)
        self._racine = space.DATA_ROOT
        space.DATA_ROOT = self.hote
        self.addCleanup(setattr, space, "DATA_ROOT", self._racine)
        self.espaces = {"travail": {"id": "travail", "nom": "Travail"},
                        "navigation": {"id": "navigation", "nom": "Navigation"},
                        "jetable": {"id": "jetable", "nom": "Jetable",
                                    "ephemere": True}}

    def _deposer(self, source, dest, nom="doc.pdf"):
        dossier = os.path.join(space.boite_envoi(source), dest)
        os.makedirs(dossier, exist_ok=True)
        with open(os.path.join(dossier, nom), "w", encoding="utf-8") as f:
            f.write("x")
        return os.path.join(self.hote, dest, "home", space.PARTAGE, nom)

    def test_remise(self):
        attendu = self._deposer("navigation", "travail")
        self.assertEqual(space.relever_envois(self.espaces), 1)
        self.assertTrue(os.path.exists(attendu))

    def test_la_boite_est_videe(self):
        """Sans quoi le fichier serait remis à chaque ouverture d'Espace."""
        self._deposer("navigation", "travail")
        space.relever_envois(self.espaces)
        self.assertEqual(space.relever_envois(self.espaces), 0)

    def test_destination_inventee_ignoree(self):
        """Le nom du dossier vient d'une zone écrite DEPUIS un Espace.

        C'est-à-dire d'un endroit où l'on ne décide pas de ce qui s'écrit : une
        destination inconnue doit être laissée où elle est, jamais suivie.
        """
        self._deposer("navigation", "..")
        self._deposer("navigation", "inexistant")
        self.assertEqual(space.relever_envois(self.espaces), 0)

    def test_pas_de_remise_vers_un_jetable(self):
        """Son dossier vit en mémoire : y déposer reviendrait à jeter."""
        self._deposer("navigation", "jetable")
        self.assertEqual(space.relever_envois(self.espaces), 0)

    def test_collision_a_la_remise(self):
        """Deux envois du même nom : le second ne doit pas écraser le premier."""
        attendu = self._deposer("navigation", "travail")
        space.relever_envois(self.espaces)
        self._deposer("navigation", "travail")
        space.relever_envois(self.espaces)
        dossier = os.path.dirname(attendu)
        self.assertEqual(len(os.listdir(dossier)), 2, os.listdir(dossier))


class SasPartage(unittest.TestCase):
    def test_le_nom_du_sas_est_ecrit_une_seule_fois(self):
        """Il l'était à deux endroits — c'est ainsi qu'un système se désaccorde."""
        with open(os.path.join(BIN, "codebyr-space"), encoding="utf-8") as f:
            source = f.read()
        self.assertEqual(source.count('"Partagé"'), 1,
                         "le dossier partagé doit venir de la constante PARTAGE")
        self.assertIn('PARTAGE = "Partagé"', source)


class DistinctionAvecLeJetable(unittest.TestCase):
    """La séparation des deux gestes, gardée à la source.

    « launch --fichier » impose le blindage ET la coupure réseau : c'est
    l'examen d'une pièce jointe. « envoyer » ne doit rien imposer du tout.
    """

    def test_envoyer_ne_touche_ni_au_blindage_ni_au_reseau(self):
        with open(os.path.join(BIN, "codebyr-space"), encoding="utf-8") as f:
            source = f.read()
        debut = source.index("def cmd_envoyer")
        fin = source.index("\n# Table des actions", debut)
        corps = source[debut:fin]
        self.assertNotIn("renforce", corps,
                         "envoyer ne doit pas imposer le blindage")
        self.assertNotIn("hors_ligne", corps,
                         "envoyer ne doit pas couper le réseau")

    def test_envoyer_refuse_un_espace_ephemere(self):
        """Y « classer » un document reviendrait à le jeter."""
        with open(os.path.join(BIN, "codebyr-space"), encoding="utf-8") as f:
            source = f.read()
        debut = source.index("def cmd_envoyer")
        fin = source.index("\n# Table des actions", debut)
        self.assertIn("ephemere", source[debut:fin])

    def test_action_declaree_avec_deux_arguments(self):
        self.assertIn("envoyer", space.ACTIONS)
        self.assertEqual(space.ACTIONS["envoyer"][0], 2)


class Confidentialite(unittest.TestCase):
    """Le journal note l'Espace et l'action, jamais le nom du fichier.

    Consigner le nom reviendrait à écrire sur disque exactement ce que les
    Espaces servent à cloisonner.
    """

    def test_le_journal_ne_recoit_pas_le_nom_du_fichier(self):
        with open(os.path.join(BIN, "codebyr-space"), encoding="utf-8") as f:
            source = f.read()
        debut = source.index("def cmd_envoyer")
        fin = source.index("\n# Table des actions", debut)
        for ligne in source[debut:fin].splitlines():
            if "journal(" in ligne:
                self.assertNotIn("nom", ligne)
                self.assertNotIn("source", ligne)


if __name__ == "__main__":
    unittest.main()
