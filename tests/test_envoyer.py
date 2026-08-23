# -*- coding: utf-8 -*-
"""« Envoyer vers l'Espace… » — le geste inverse du Jetable.

Le Jetable est le geste de la méfiance : une pièce jointe douteuse, examinée
blindée et sans réseau. Envoyer est celui de la confiance : on classe un
document, et l'Espace de destination doit rester ce qu'il est.

Confondre les deux serait une régression discrète et coûteuse — un document de
travail envoyé dans un Espace soudain privé de réseau, sans explication.
"""
import os
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
