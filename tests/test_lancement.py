# -*- coding: utf-8 -*-
"""Les brouillons de lancement ne disent rien de faux.

Analyse externe du 01/10/2026, point 3.4 : ils citaient la v1.5.5 et
affirmaient que le filtre de la Banque n'était « pas encore une règle
système » — faux depuis la 1.11.0. Un brouillon qui attend des semaines ne se
relit pas tout seul ; ces affirmations-là ne reviennent pas.
"""
import glob
import os
import re
import unittest

from outils import RACINE

POSTS = sorted(glob.glob(os.path.join(RACINE, "docs", "lancement", "posts", "*.md")))

# Ce qui a été vrai, et ne l'est plus.
PERIMES = {
    "pas encore une règle": "le réseau de la Banque est une règle système depuis la 1.11.0",
    "not yet a system-level": "le réseau de la Banque est une règle système depuis la 1.11.0",
    "150 locales": "Codebyr parle français et anglais (1.18.0) ; seul l'installeur a 150 langues",
    "~150 langues (français": "Codebyr parle français et anglais (1.18.0)",
    "aucun audit externe": "une analyse externe a eu lieu le 01/10/2026 (pas un audit professionnel)",
    "no external audit": "une analyse externe a eu lieu le 01/10/2026 (pas un audit professionnel)",
    "~3k lines": "le code propre à Codebyr dépasse 13 000 lignes",
}


class LesBrouillons(unittest.TestCase):

    def test_il_y_en_a(self):
        self.assertGreaterEqual(len(POSTS), 5)

    def test_aucune_affirmation_perimee(self):
        for chemin in POSTS:
            with open(chemin, encoding="utf-8") as f:
                texte = f.read()
            for phrase, raison in PERIMES.items():
                with self.subTest(post=os.path.basename(chemin), phrase=phrase):
                    self.assertNotIn(phrase, texte, raison)

    def test_aucune_version_annoncee_d_avant_la_1_20(self):
        # La version annoncée comme ÉTAT (« v1.20 », « Version 1.20 ») ; les
        # mentions historiques (« fermée en 1.1.0 ») sont justes.
        for chemin in POSTS:
            with open(chemin, encoding="utf-8") as f:
                versions = re.findall(r"(?:\bv|Version )1\.(\d+)", f.read())
            anciennes = [v for v in versions if int(v) < 20]
            self.assertEqual(anciennes, [], os.path.basename(chemin))


if __name__ == "__main__":
    unittest.main()
