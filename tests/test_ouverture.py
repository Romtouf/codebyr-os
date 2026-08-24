# -*- coding: utf-8 -*-
"""Ouverture sous cloche d'un fichier venu d'un autre Espace.

C'est le moment où la provenance cesse d'informer et se met à protéger. Un
document téléchargé dans Navigation, ouvert depuis Travail, s'ouvre isolé et
sans réseau au lieu de s'exécuter au milieu des documents professionnels.

Deux principes gardés ici, et ils tirent en sens inverse :
- le doute profite à l'OUVERTURE : refuser d'ouvrir des documents ordinaires
  ferait désactiver la fonction en une semaine, et une protection désactivée
  ne protège personne ;
- les préférences de l'utilisateur ne sont jamais reprises : qui a choisi sa
  visionneuse de PDF a fait un choix.
"""
import os
import unittest

from outils import BIN, LIB  # noqa: F401 — place le module partagé sur sys.path
import outils

space = outils.charger("codebyr-space")


class Decision(unittest.TestCase):
    def test_fichier_venu_d_ailleurs(self):
        self.assertEqual(space.decider_ouverture("navigation", "travail"), "jetable")

    def test_fichier_de_l_espace_courant(self):
        self.assertEqual(space.decider_ouverture("travail", "travail"), "normale")

    def test_origine_inconnue(self):
        """Le doute profite à l'ouverture — sinon la fonction se fait couper."""
        self.assertEqual(space.decider_ouverture(None, "travail"), "normale")

    def test_hors_de_tout_espace(self):
        """Sur le bureau il n'y a pas d'« ici », donc rien à franchir."""
        self.assertEqual(space.decider_ouverture("navigation", None), "normale")


class Associations(unittest.TestCase):
    """Le mimeapps.list appartient à l'utilisateur."""

    TYPES = ["application/pdf", "text/html"]

    def test_fichier_vide(self):
        obtenu = space.associer_ouvreur("", self.TYPES)
        self.assertIn("[Default Applications]", obtenu)
        self.assertIn("application/pdf=" + space.OUVREUR, obtenu)
        self.assertIn("text/html=" + space.OUVREUR, obtenu)

    def test_un_choix_existant_est_respecte(self):
        depart = "[Default Applications]\napplication/pdf=evince.desktop\n"
        obtenu = space.associer_ouvreur(depart, self.TYPES)
        self.assertIn("application/pdf=evince.desktop", obtenu)
        self.assertNotIn("application/pdf=" + space.OUVREUR, obtenu)
        self.assertIn("text/html=" + space.OUVREUR, obtenu)

    def test_rien_a_faire_ne_reecrit_pas(self):
        """Réécrire à l'identique à chaque lancement userait le fichier pour rien."""
        depart = ("[Default Applications]\napplication/pdf=%s\ntext/html=%s\n"
                  % (space.OUVREUR, space.OUVREUR))
        self.assertEqual(space.associer_ouvreur(depart, self.TYPES), depart)

    def test_les_autres_sections_sont_preservees(self):
        depart = ("[Added Associations]\nimage/png=eog.desktop;\n\n"
                  "[Default Applications]\napplication/pdf=evince.desktop\n")
        obtenu = space.associer_ouvreur(depart, self.TYPES)
        self.assertIn("[Added Associations]", obtenu)
        self.assertIn("image/png=eog.desktop;", obtenu)

    def test_insertion_dans_la_bonne_section(self):
        """Une association placée hors de sa section ne serait jamais lue."""
        depart = ("[Default Applications]\napplication/pdf=evince.desktop\n"
                  "\n[Added Associations]\nimage/png=eog.desktop;\n")
        obtenu = space.associer_ouvreur(depart, self.TYPES).splitlines()
        defaut = obtenu.index("[Default Applications]")
        ajoutes = obtenu.index("[Added Associations]")
        html = obtenu.index("text/html=" + space.OUVREUR)
        self.assertTrue(defaut < html < ajoutes,
                        "l'association doit rester dans [Default Applications]")


class Coherence(unittest.TestCase):
    def test_les_types_viennent_du_desktop(self):
        """La liste des types n'existe qu'à un seul endroit.

        Recopiée dans le code, elle divergerait du .desktop — ce projet a déjà
        payé ce prix avec quatre lectures du registre.
        """
        desktop = os.path.join(
            os.path.dirname(BIN), "share", "applications", space.OUVREUR)
        types = space.types_ouvreur(desktop)
        self.assertIn("application/pdf", types)
        self.assertGreater(len(types), 5)

    def test_desktop_absent_ne_casse_rien(self):
        self.assertEqual(space.types_ouvreur("/inexistant/x.desktop"), [])

    def test_le_desktop_entre_dans_le_paquet(self):
        """Sans lui, la fonction ne fait RIEN, et ne le dit pas.

        Constaté le 24/08/2026 : le .desktop n'était pas dans la liste des
        chemins empaquetés. Sur une machine mise à jour par apt, aucun type
        n'aurait été trouvé, aucune association écrite, et l'ouverture sous
        cloche ne se serait jamais déclenchée — sans message ni trace.
        """
        chemin = os.path.join(outils.RACINE, "packaging", "build-deb.sh")
        with open(chemin, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("usr/share/applications/" + space.OUVREUR, source,
                      "l'ouvreur doit être empaqueté, sinon la fonction est "
                      "livrée inerte")

    def test_l_action_est_declaree(self):
        self.assertIn("ouvrir", space.ACTIONS)
        self.assertEqual(space.ACTIONS["ouvrir"][0], 1)


if __name__ == "__main__":
    unittest.main()
