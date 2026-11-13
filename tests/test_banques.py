# -*- coding: utf-8 -*-
"""La liste « Choisir ma banque » de la configuration.

Un domaine faux dans la liste blanche de l'Espace Banque casse l'accès à la
banque, ou apprend à tout autoriser. Chaque domaine de banques.json a été lu
sur le site officiel de la banque le 13/11/2026 — page d'accueil récupérée,
et, sauf pour Caisse d'Épargne, Banque Populaire et Crédit Mutuel, l'hôte du
lien « Espace client » lu dans la page (docs/decisions.md, « Liste de
banques »). BNP Paribas, Hello bank! et Revolut refusent la lecture
automatique de leur site (HTTP 403) : absentes, faute de vérification.
"""
import json
import os
import tempfile
import unittest

from outils import BIN, LIB

import banques
import registre


class LaListe(unittest.TestCase):

    def setUp(self):
        self.liste = banques.charger()

    def test_le_fichier_livre_se_charge_en_entier(self):
        with open(os.path.join(LIB, "banques.json"), encoding="utf-8") as f:
            brut = json.load(f)["banques"]
        self.assertEqual(len(self.liste), len(brut))
        self.assertGreaterEqual(len(self.liste), 15)

    def test_chaque_domaine_est_deja_sous_sa_forme_normale(self):
        # Ce qui est écrit est exactement ce qui sera ajouté : aucune
        # transformation silencieuse entre la liste et la liste blanche.
        with open(os.path.join(LIB, "banques.json"), encoding="utf-8") as f:
            for banque in json.load(f)["banques"]:
                for d in banque["domaines"]:
                    self.assertEqual(registre.normaliser_domaine(d), d, banque["nom"])

    def test_un_nom_une_fois(self):
        noms = [nom.casefold() for nom, _ in self.liste]
        self.assertEqual(len(noms), len(set(noms)))
        self.assertEqual(noms, sorted(noms))

    def test_aucune_banque_non_verifiee(self):
        noms = {nom for nom, _ in self.liste}
        for absente in ("BNP Paribas", "Hello bank!", "Revolut"):
            self.assertNotIn(absente, noms)


class UnFichierAbime(unittest.TestCase):

    def _charger(self, contenu):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            f.write(contenu)
        self.addCleanup(os.unlink, f.name)
        return banques.charger(f.name)

    def test_un_domaine_douteux_est_ecarte(self):
        liste = self._charger(json.dumps({"banques": [
            {"nom": "Piège", "domaines": ["192.168.1.1", "-piege.fr", "bonne.fr"]},
            {"nom": "Vide", "domaines": ["http://"]},
        ]}))
        self.assertEqual(liste, [("Piège", ["bonne.fr"])])

    def test_illisible_donne_une_liste_vide(self):
        self.assertEqual(self._charger("{pas du json"), [])
        self.assertEqual(banques.charger("/n/existe/pas.json"), [])


class LaConfiguration(unittest.TestCase):

    def test_le_choix_passe_par_l_ajout_ordinaire(self):
        # Même porte d'entrée que la saisie : normalisation et « *.domaine ».
        with open(os.path.join(BIN, "codebyr-config"), encoding="utf-8") as f:
            code = f.read()
        corps = code.split("def _ajouter_banque(self, banque):", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("self._ajouter_domaine(d)", corps)

    def test_le_choix_survit_a_l_ajout(self):
        # La page se reconstruit après chaque ajout : la liste revenait à sa
        # première banque (vu sur la VM), qu'un second clic aurait ajoutée.
        with open(os.path.join(BIN, "codebyr-config"), encoding="utf-8") as f:
            code = f.read()
        self.assertIn('choix.set_selected(min(getattr(self, "_banque_choisie", 0)', code)
        self.assertIn('setattr(self, "_banque_choisie", r.get_selected())', code)


if __name__ == "__main__":
    unittest.main()
