# -*- coding: utf-8 -*-
"""Les applications graphiques de Codebyr : une seule allure, une seule langue."""
import ast
import os
import re
import unittest

from outils import BIN, LIB

APPLIS = ("codebyr-config", "codebyr-assistant", "codebyr-bienvenue")
# Ce qui s'écrit pareil dans toutes les langues.
INVARIANTS = {"Codebyr OS"}
AFFICHES = {"title", "subtitle", "description", "label", "text", "placeholder_text",
            "tooltip_text", "heading", "body"}


def _lire(chemin):
    with open(chemin, encoding="utf-8") as f:
        return f.read()


def _textes_hors_traduction(source):
    """Les textes affichés à l'écran qui ne passent pas par _() ou n_()."""
    arbre = ast.parse(source)
    parents = {e: n for n in ast.walk(arbre) for e in ast.iter_child_nodes(n)}

    def traduit(noeud):
        p = parents.get(noeud)
        while p is not None:
            if isinstance(p, ast.Call) and isinstance(p.func, ast.Name) and p.func.id in ("_", "n_"):
                return True
            p = parents.get(p)
        return False

    trouves = []
    for n in ast.walk(arbre):
        if not (isinstance(n, ast.Constant) and isinstance(n.value, str)):
            continue
        if " " not in n.value.strip() or n.value in INVARIANTS or traduit(n):
            continue
        p = parents.get(n)
        affiche = (isinstance(p, ast.keyword) and p.arg in AFFICHES) or (
            isinstance(p, ast.Call) and isinstance(p.func, ast.Attribute)
            and p.func.attr in ("set_text", "set_label", "set_title", "set_subtitle",
                                "set_description"))
        if affiche:
            trouves.append((n.lineno, n.value))
    return trouves


class UneSeuleLangue(unittest.TestCase):
    """Deux phrases de la configuration restaient en français dans une session
    anglaise : elles étaient ajoutées à une description, hors de _()."""

    def test_rien_d_affiche_hors_traduction(self):
        for nom in APPLIS:
            self.assertEqual(_textes_hors_traduction(_lire(os.path.join(BIN, nom))), [], nom)

    def test_le_detecteur_voit_le_defaut(self):
        source = ('row = Adw.ActionRow(title="Texte en dur ici")\n'
                  'row.set_subtitle("Autre texte en dur")\n'
                  'ok = Adw.ActionRow(title=_("Texte traduit"))\n')
        self.assertEqual(sorted(l for l, _t in _textes_hors_traduction(source)), [1, 2])


class UneSeuleAllure(unittest.TestCase):

    def test_meme_marge_partout(self):
        # Les marges allaient de 6 à 14 px selon la fenêtre.
        for nom in ("codebyr-config", "codebyr-assistant"):
            source = _lire(os.path.join(BIN, nom))
            self.assertNotRegex(source, r"set_margin_\w+\(\d+\)", nom)
            self.assertNotRegex(source, r'"set_margin_" \+ m\)\(\d+\)', nom)

    def test_meme_taille_de_fenetre_principale(self):
        for nom in ("codebyr-config", "codebyr-assistant"):
            self.assertIn("set_default_size(*interface.TAILLE_FENETRE)",
                          _lire(os.path.join(BIN, nom)), nom)

    def test_meme_en_tete(self):
        for nom in APPLIS:
            self.assertIn('subtitle="Codebyr OS"', _lire(os.path.join(BIN, nom)), nom)

    def test_l_espace_se_reconnait_a_sa_pastille_pas_a_son_code_couleur(self):
        source = _lire(os.path.join(BIN, "codebyr-config"))
        self.assertNotIn('subtitle=e.get("couleur"', source)
        self.assertGreaterEqual(source.count("row.add_prefix(interface.pastille("), 3)

    def test_la_marge_commune(self):
        interface = _lire(os.path.join(LIB, "interface.py"))
        self.assertTrue(re.search(r"^MARGE = 12$", interface, re.M))


if __name__ == "__main__":
    unittest.main()
