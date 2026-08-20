# -*- coding: utf-8 -*-
"""Le registre des Espaces : fusion système + utilisateur.

Il y a deux fichiers — les valeurs par défaut livrées par le paquet
(`/etc/codebyr/espaces.json`) et les personnalisations de l'utilisateur
(`~/.config/codebyr/espaces.json`). Ils se SUPERPOSENT clé par clé.

Avant, le fichier utilisateur remplaçait purement et simplement celui du
système : dès qu'on avait touché un réglage, plus aucune valeur par défaut ne
pouvait plus jamais nous atteindre. Un durcissement livré par « apt » —
couper le micro dans l'Espace Banque, par exemple — n'arrivait qu'aux
personnes n'ayant rien configuré. Plus l'utilisateur s'impliquait, moins il
était protégé. Ces tests verrouillent le comportement inverse.
"""
import json
import os
import tempfile
import unittest

from outils import BIN, RACINE   # place le module partagé sur sys.path
import registre                  # noqa: E402 — dépend de l'import ci-dessus

EXTENSION = os.path.join(
    RACINE, "live-build", "config", "includes.chroot_after_packages", "usr",
    "share", "gnome-shell", "extensions", "codebyr@codebyr.io", "extension.js")

PYTHON_LECTEURS = ("codebyr-space", "codebyr-config", "codebyr-assistant")


class Fusion(unittest.TestCase):

    def setUp(self):
        self._dossier = tempfile.TemporaryDirectory()
        d = self._dossier.name
        self._sys, self._usr = registre.SYSTEME, registre.UTILISATEUR
        registre.SYSTEME = os.path.join(d, "systeme.json")
        registre.UTILISATEUR = os.path.join(d, "utilisateur.json")

    def tearDown(self):
        registre.SYSTEME, registre.UTILISATEUR = self._sys, self._usr
        self._dossier.cleanup()

    def _ecrire(self, chemin, data):
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def _defauts(self):
        self._ecrire(registre.SYSTEME, {"espaces": [
            {"id": "banque", "nom": "Banque", "couleur": "#2FA36B",
             "blindage": "renforce", "audio": False,
             "reseau": {"mode": "liste-blanche", "domaines": []}},
            {"id": "travail", "nom": "Travail", "couleur": "#8F6CF0"},
        ], "apps": [{"nom": "Navigateur", "cmd": "firefox-esr"}]})

    def test_sans_personnalisation_on_a_les_defauts(self):
        self._defauts()
        esp = registre.espaces()
        self.assertEqual(esp["banque"]["nom"], "Banque")
        self.assertIs(esp["banque"]["audio"], False)

    def test_les_choix_de_l_utilisateur_gagnent(self):
        self._defauts()
        self._ecrire(registre.UTILISATEUR, {"espaces": [
            {"id": "banque",
             "reseau": {"mode": "liste-blanche", "domaines": ["mabanque.fr"]}},
        ]})
        banque = registre.espaces()["banque"]
        self.assertEqual(banque["reseau"]["domaines"], ["mabanque.fr"])

    def test_un_nouveau_defaut_atteint_un_utilisateur_qui_a_personnalise(self):
        """LE test de non-régression : c'est exactement ce qui ne marchait pas."""
        self._defauts()
        self._ecrire(registre.UTILISATEUR, {"espaces": [
            {"id": "banque", "nom": "Ma banque",
             "reseau": {"mode": "liste-blanche", "domaines": ["mabanque.fr"]}},
        ]})
        banque = registre.espaces()["banque"]
        self.assertEqual(banque["nom"], "Ma banque")            # son choix tient
        self.assertEqual(banque["reseau"]["domaines"], ["mabanque.fr"])
        self.assertIs(banque["audio"], False)                   # le défaut arrive
        self.assertEqual(banque["blindage"], "renforce")        # celui-là aussi

    def test_les_espaces_crees_par_l_utilisateur_sont_conserves(self):
        self._defauts()
        self._ecrire(registre.UTILISATEUR, {"espaces": [
            {"id": "assoc", "nom": "Association", "couleur": "#43C7DF"},
        ]})
        esp = registre.espaces()
        self.assertIn("assoc", esp)
        self.assertIn("banque", esp)
        self.assertFalse(esp["assoc"]["_systeme"])
        self.assertTrue(esp["banque"]["_systeme"])

    def test_un_espace_du_systeme_n_est_pas_supprimable(self):
        self._defauts()
        self.assertTrue(registre.est_systeme("banque"))
        self.assertFalse(registre.est_systeme("assoc"))

    def test_registre_illisible_ne_fait_pas_planter(self):
        with open(registre.SYSTEME, "w", encoding="utf-8") as f:
            f.write("{ ceci n'est pas du JSON")
        self.assertEqual(registre.charger()["espaces"], [])


class EcritureEnCouche(unittest.TestCase):
    """L'écriture ne doit enregistrer QUE les différences.

    Si l'on écrivait la vue fusionnée dans le fichier utilisateur, il
    redeviendrait un instantané figé des défauts du jour — et le problème
    reviendrait par la porte de derrière, silencieusement.
    """

    def setUp(self):
        self._dossier = tempfile.TemporaryDirectory()
        d = self._dossier.name
        self._sys, self._usr = registre.SYSTEME, registre.UTILISATEUR
        registre.SYSTEME = os.path.join(d, "systeme.json")
        registre.UTILISATEUR = os.path.join(d, "utilisateur.json")
        with open(registre.SYSTEME, "w", encoding="utf-8") as f:
            json.dump({"espaces": [
                {"id": "banque", "nom": "Banque", "couleur": "#2FA36B",
                 "audio": False, "blindage": "renforce"}]}, f)

    def tearDown(self):
        registre.SYSTEME, registre.UTILISATEUR = self._sys, self._usr
        self._dossier.cleanup()

    def _couche_brute(self):
        with open(registre.UTILISATEUR, encoding="utf-8") as f:
            return json.load(f)

    def test_modifier_n_ecrit_que_la_cle_touchee(self):
        registre.modifier_espace("banque", {"blindage": None})
        couche = self._couche_brute()
        entree = couche["espaces"][0]
        self.assertEqual(entree["id"], "banque")
        self.assertEqual(set(entree), {"id", "blindage"},
                         "la couche utilisateur doit rester une différence, "
                         "pas une copie complète : %r" % entree)

    def test_les_defauts_non_touches_continuent_de_s_appliquer(self):
        registre.modifier_espace("banque", {"blindage": None})
        banque = registre.espaces()["banque"]
        self.assertIsNone(banque["blindage"])     # le choix de l'utilisateur
        self.assertIs(banque["audio"], False)     # le défaut, toujours vivant
        self.assertEqual(banque["nom"], "Banque")

    def test_les_cles_calculees_ne_sont_jamais_ecrites(self):
        registre.modifier_espace("banque", {"couleur": "#123456"})
        for entree in self._couche_brute()["espaces"]:
            for cle in entree:
                self.assertFalse(cle.startswith("_"), "clé calculée écrite : %s" % cle)

    def test_creation_puis_suppression(self):
        registre.ajouter_espace({"id": "assoc", "nom": "Association",
                                 "couleur": "#43C7DF"})
        self.assertIn("assoc", registre.espaces())
        self.assertTrue(registre.supprimer_espace("assoc"))
        self.assertNotIn("assoc", registre.espaces())
        self.assertFalse(registre.supprimer_espace("assoc"))

    def test_identifiant_libre_evite_les_collisions(self):
        registre.ajouter_espace({"id": "assoc", "nom": "Association"})
        self.assertEqual(registre.identifiant_libre("assoc"), "assoc-2")
        self.assertEqual(registre.identifiant_libre("banque"), "banque-2")
        self.assertEqual(registre.identifiant_libre("neuf"), "neuf")


class LecteursCoherents(unittest.TestCase):
    """Les quatre lecteurs du registre doivent appliquer la même règle."""

    def _source(self, chemin):
        with open(chemin, encoding="utf-8") as f:
            return f.read()

    def test_les_outils_python_passent_par_le_module_partage(self):
        for nom in PYTHON_LECTEURS:
            code = self._source(os.path.join(BIN, nom))
            self.assertIn("import registre", code,
                          "%s doit lire le registre via le module partagé" % nom)
            self.assertNotIn("USER_REGISTRY if os.path.exists", code,
                             "%s applique encore l'ancienne règle « l'un OU "
                             "l'autre »" % nom)

    def test_l_extension_gnome_fusionne_aussi(self):
        code = self._source(EXTENSION)
        self.assertIn("/etc/codebyr/espaces.json", code)
        self.assertIn("/.config/codebyr/espaces.json", code)
        self.assertIn("fusionner", code,
                      "l'extension doit fusionner les deux registres, pas "
                      "choisir l'un ou l'autre")


if __name__ == "__main__":
    unittest.main()
