# -*- coding: utf-8 -*-
"""L'empreinte de la clé de signature — l'ancre de confiance du projet.

C'est le seul repère dont dispose quelqu'un qui télécharge une ISO : il compare
ce que `gpg` lui affiche à ce que le projet publie. Elle doit donc être écrite
au même endroit… et surtout, écrite pareil partout.

Jusqu'ici elle ne figurait qu'à un seul endroit — le dépôt GitHub. Quiconque
contrôlait le dépôt contrôlait l'ancre. Elle est maintenant aussi sur le site,
servi par un autre hébergement : deux sources indépendantes qui doivent
concorder, et qui se surveillent l'une l'autre.
"""
import glob
import os
import re
import unittest

from outils import RACINE

# La MAÎTRESSE : l'ancre de confiance, celle que les utilisateurs comparent.
EMPREINTE = "E6FB6616EC58E15F40DA876CB1E8C803CE596E68"
# La sous-clé de signature : détail d'exploitation, documenté mais jamais
# présenté aux utilisateurs comme repère de confiance.
SOUS_CLE = "49DF7B8855830CCD347663345884F50B88581C19"
# 40 caractères hexadécimaux, éventuellement coupés par des espaces ou &nbsp;.
MOTIF = re.compile(r"(?:[0-9A-F]{4}(?:&nbsp;|\s)*){10}")

# Les endroits où l'empreinte est présentée à un UTILISATEUR comme repère.
# La documentation d'exploitation (chaine-de-signature.md) est traitée à part :
# elle mentionne aussi la sous-clé, ce qui y est normal.
FICHIERS = ("SECURITY.md", "README.md", "site/index.html", "packaging/README.md")


def empreintes_de(chemin):
    with open(chemin, encoding="utf-8") as f:
        contenu = f.read()
    trouvees = set()
    for brut in MOTIF.findall(contenu):
        trouvees.add(re.sub(r"&nbsp;|\s", "", brut))
    return trouvees


class UneSeuleEmpreinte(unittest.TestCase):

    def test_toutes_les_mentions_concordent(self):
        vues = {}
        for relatif in FICHIERS:
            chemin = os.path.join(RACINE, relatif)
            if not os.path.exists(chemin):
                continue
            for e in empreintes_de(chemin):
                vues.setdefault(e, []).append(relatif)
        self.assertTrue(vues, "l'empreinte n'est publiée nulle part")
        self.assertEqual(list(vues), [EMPREINTE],
                         "empreintes divergentes : %r" % vues)

    def test_publiee_sur_deux_hebergements_independants(self):
        # Le dépôt et le site ne sont pas servis par la même machine : c'est
        # tout l'intérêt. Une seule source, et sa compromission passe inaperçue.
        depot = empreintes_de(os.path.join(RACINE, "SECURITY.md"))
        site = empreintes_de(os.path.join(RACINE, "site", "index.html"))
        self.assertIn(EMPREINTE, depot, "absente de SECURITY.md")
        self.assertIn(EMPREINTE, site, "absente du site")

    def test_la_cle_publique_du_depot_est_bien_celle_annoncee(self):
        # On ne peut pas calculer l'empreinte sans gpg, mais on peut vérifier
        # que le fichier de clé publique existe et n'est pas vide : sans lui,
        # la procédure de vérification publiée ne mène nulle part.
        cle = os.path.join(RACINE, "codebyr-signing-key.asc")
        self.assertTrue(os.path.exists(cle), "clé publique absente du dépôt")
        with open(cle, encoding="utf-8") as f:
            contenu = f.read()
        self.assertIn("BEGIN PGP PUBLIC KEY BLOCK", contenu)
        self.assertGreater(len(contenu), 200)

    def test_aucune_empreinte_egaree_ailleurs(self):
        # Une empreinte différente qui traînerait dans un coin du dépôt serait
        # au mieux périmée, au pire un piège.
        for chemin in glob.glob(os.path.join(RACINE, "**", "*.md"), recursive=True):
            if os.sep + ".git" + os.sep in chemin:
                continue
            for e in empreintes_de(chemin):
                self.assertIn(e, (EMPREINTE, SOUS_CLE),
                              "empreinte inattendue dans %s : %s — au mieux "
                              "périmée, au pire un piège"
                              % (os.path.relpath(chemin, RACINE), e))


if __name__ == "__main__":
    unittest.main()
