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
        """Aucune empreinte inconnue ne doit circuler — une coquille se voit ici.

        Deux valeurs sont légitimes, et il a fallu publier les DEUX : l'ancre,
        et la sous-clé que `gpg` affiche réellement. Ne montrer que l'ancre
        conduisait un utilisateur attentif à constater que les empreintes ne
        correspondent pas — et, suivant l'avertissement du site lui-même, à
        refuser une version parfaitement valide.

        Toute troisième valeur reste une erreur.
        """
        vues = {}
        for relatif in FICHIERS:
            chemin = os.path.join(RACINE, relatif)
            if not os.path.exists(chemin):
                continue
            for e in empreintes_de(chemin):
                vues.setdefault(e, []).append(relatif)
        self.assertTrue(vues, "l'empreinte n'est publiée nulle part")
        inconnues = {e: f for e, f in vues.items() if e not in (EMPREINTE, SOUS_CLE)}
        self.assertEqual(inconnues, {},
                         "empreintes inconnues : %r" % inconnues)
        self.assertIn(EMPREINTE, vues, "l'ancre de confiance doit être publiée")

    def test_la_sous_cle_est_expliquee_la_ou_elle_est_montree(self):
        """Montrer une empreinte sans dire ce qu'elle est fabrique du doute.

        Un utilisateur qui lit deux empreintes différentes sans explication
        conclut à une anomalie. Partout où la sous-clé apparaît devant un
        utilisateur, le texte doit dire que c'est celle que `gpg` affiche et
        que c'est normal.
        """
        for relatif in FICHIERS:
            chemin = os.path.join(RACINE, relatif)
            if not os.path.exists(chemin):
                continue
            if SOUS_CLE not in empreintes_de(chemin):
                continue
            with open(chemin, encoding="utf-8") as f:
                contenu = f.read().lower()
            self.assertIn("sous-clé", contenu,
                          "%s montre la sous-clé sans la nommer" % relatif)
            self.assertTrue(
                "hors ligne" in contenu or "hors-ligne" in contenu,
                "%s doit expliquer POURQUOI l'ancre diffère : elle est hors "
                "ligne" % relatif)

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


class CleEmbarquee(unittest.TestCase):
    """La clé publique existe en trois exemplaires dans le dépôt.

    · `codebyr-signing-key.asc` — celle que les utilisateurs importent ;
    · `…/usr/share/keyrings/codebyr.asc` — celle que l'ISO grave dans le
      trousseau apt de chaque machine installée ;
    · `…/usr/share/codebyr/codebyr-signing-key.asc` — celle que le paquet
      embarque pour rafraîchir ce trousseau.

    Elles ont divergé : l'ajout d'une sous-clé de signature n'a été répercuté
    que sur la première. Toute machine installée depuis l'ISO s'est alors
    retrouvée incapable de vérifier le dépôt — donc de recevoir la moindre
    mise à jour de sécurité. L'échec était propre (apt refuse), mais total.
    """

    EXEMPLAIRES = (
        "codebyr-signing-key.asc",
        "live-build/config/includes.chroot_after_packages/usr/share/keyrings/codebyr.asc",
        "live-build/config/includes.chroot_after_packages/usr/share/codebyr/"
        "codebyr-signing-key.asc",
    )

    def test_les_exemplaires_sont_identiques(self):
        contenus = {}
        for relatif in self.EXEMPLAIRES:
            chemin = os.path.join(RACINE, *relatif.split("/"))
            self.assertTrue(os.path.exists(chemin), "absent : %s" % relatif)
            with open(chemin, "rb") as f:
                contenus.setdefault(f.read().replace(b"\r\n", b"\n"), []).append(relatif)
        self.assertEqual(
            len(contenus), 1,
            "la clé publique diverge entre ses exemplaires — une machine "
            "installée ne pourrait plus vérifier le dépôt :\n  %s"
            % "\n  ".join(str(v) for v in contenus.values()))

    def test_la_sous_cle_de_signature_y_figure(self):
        # Sans elle, apt refuse : « Missing key …, needed to verify signature ».
        for relatif in self.EXEMPLAIRES:
            chemin = os.path.join(RACINE, *relatif.split("/"))
            with open(chemin, encoding="utf-8") as f:
                blocs = f.read().count("BEGIN PGP PUBLIC KEY BLOCK")
            self.assertEqual(blocs, 1, relatif)
        # La présence de la sous-clé se lit à la taille : une clé maîtresse
        # seule fait ~460 octets, avec une sous-clé ~870.
        taille = os.path.getsize(os.path.join(RACINE, "codebyr-signing-key.asc"))
        self.assertGreater(taille, 700,
                           "la clé publiée semble ne contenir que la maîtresse")
