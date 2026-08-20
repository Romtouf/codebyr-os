# -*- coding: utf-8 -*-
"""La saisie d'un domaine bancaire — la seule porte d'entrée de la liste blanche.

Ce qui sort de `normaliser_domaine()` devient une adresse que l'Espace Banque
aura le droit de joindre. Une analyse trop permissive y ferait entrer autre
chose que ce que la personne croit avoir tapé — et cette fonction n'avait
aucun test, alors qu'elle porte déjà la cicatrice d'un bug (`lstrip("www.")`
transformait « wise.com » en « ise.com », parce que lstrip retire tous les
caractères de l'ensemble {w, .} et pas le préfixe).
"""
import unittest

from outils import LIB  # noqa: F401 — place le module partagé sur sys.path
import registre         # noqa: E402


class SaisiesOrdinaires(unittest.TestCase):

    def test_un_domaine_simple(self):
        self.assertEqual(registre.normaliser_domaine("mabanque.fr"), "mabanque.fr")

    def test_espaces_et_majuscules(self):
        self.assertEqual(registre.normaliser_domaine("  MaBanque.FR  "), "mabanque.fr")

    def test_adresse_complete_collee_du_navigateur(self):
        self.assertEqual(
            registre.normaliser_domaine("https://www.labanquepostale.fr/accueil.html"),
            "labanquepostale.fr")

    def test_le_www_est_retire_sans_manger_de_lettres(self):
        # La cicatrice : lstrip("www.") rendait « ise.com ».
        self.assertEqual(registre.normaliser_domaine("wise.com"), "wise.com")
        self.assertEqual(registre.normaliser_domaine("www.wise.com"), "wise.com")

    def test_port_chemin_ancre_et_parametres(self):
        for saisi in ("mabanque.fr:443", "mabanque.fr/espace/client",
                      "mabanque.fr?x=1", "mabanque.fr#ancre",
                      "https://mabanque.fr:8443/a/b?c=d#e"):
            self.assertEqual(registre.normaliser_domaine(saisi), "mabanque.fr", saisi)

    def test_sous_domaine_conserve(self):
        self.assertEqual(registre.normaliser_domaine("particuliers.mabanque.fr"),
                         "particuliers.mabanque.fr")


class SaisiesRefusees(unittest.TestCase):
    """Refuser franchement vaut mieux qu'autoriser « à peu près »."""

    def test_vide_ou_sans_point(self):
        for saisi in ("", "   ", None, "mabanque", "localhost"):
            self.assertIsNone(registre.normaliser_domaine(saisi), repr(saisi))

    def test_identifiants_dans_l_adresse(self):
        # « https://mabanque.fr@piege.fr/ » : le vrai hôte est piege.fr. Le
        # navigateur ira sur piege.fr — la liste blanche doit voir la même chose
        # que lui, jamais ce que l'œil croit lire.
        self.assertEqual(registre.normaliser_domaine("https://mabanque.fr@piege.fr/"),
                         "piege.fr")

    def test_caracteres_interdits(self):
        for saisi in ("ma banque.fr", "mabanque..fr", "ma_banque.fr",
                      "mabanque.fr,piege.fr", "mabanque.fr;rm -rf",
                      "-mabanque.fr", "mabanque-.fr", "mabanque.f"):
            self.assertIsNone(registre.normaliser_domaine(saisi), saisi)

    def test_adresses_ip_refusees(self):
        # Une banque a un nom. Une IP dans une liste blanche ne protège de rien :
        # elle peut être réattribuée, et elle ne dit rien de qui répond.
        for saisi in ("192.168.1.1", "8.8.8.8", "https://10.0.0.1/"):
            self.assertIsNone(registre.normaliser_domaine(saisi), saisi)

    def test_unicode_refuse(self):
        # Un domaine internationalisé doit être saisi en punycode (xn--…) :
        # accepter « mabanquè.fr » tel quel laisserait passer un homographe.
        self.assertIsNone(registre.normaliser_domaine("mabanquè.fr"))
        self.assertEqual(registre.normaliser_domaine("xn--mabanqu-fya.fr"),
                         "xn--mabanqu-fya.fr")


class UtiliseeParLaConfiguration(unittest.TestCase):

    def test_codebyr_config_passe_par_le_module(self):
        from outils import BIN
        import os
        with open(os.path.join(BIN, "codebyr-config"), encoding="utf-8") as f:
            code = f.read()
        self.assertIn("registre.normaliser_domaine", code)
        self.assertNotIn('removeprefix("www.")', code,
                         "l'analyse ne doit plus être dupliquée dans l'interface")


if __name__ == "__main__":
    unittest.main()
