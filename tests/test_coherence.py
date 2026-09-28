# -*- coding: utf-8 -*-
"""Ce que le projet dit de lui-même, confronté à ce qu'il est.

Deux dérives constatées le 27 septembre 2026, que rien ne détectait :

· le système installé désignait « codebyr.io » — un domaine qui n'existe pas,
  que n'importe qui pouvait acheter — comme adresse d'aide, de signalement et
  de dons, dans /etc/os-release et dans l'installeur ;
· le README et la carte du projet annonçaient la 1.16.1 « publiée » alors
  qu'aucun dépôt ne la servait.

L'état du projet est réécrit à la main en plusieurs endroits. Ces tests ne les
empêchent pas de vieillir ; ils les empêchent de se contredire.
"""
import os
import re
import unittest

from outils import RACINE

# Dossiers qui ne sont pas des sources : artefacts, caches, copies de travail.
IGNORES = {".git", "dist", "archives", "essais-retires", "apt-repo", ".kilo",
           ".ruff_cache", "__pycache__", "node_modules", "captures_ecran", "captures",
           "fonts"}

URL = re.compile(r"https?://([A-Za-z0-9.-]+)")
DOMAINE_CODEBYR = re.compile(r"(^|\.)codebyr\.[a-z]+$")
ENTETE = re.compile(r"^## (\d+\.\d+\.\d+) — (.+)$", re.MULTILINE)
NON_PUBLIEE = "non publiée"


def _sources():
    for racine, dossiers, fichiers in os.walk(RACINE):
        dossiers[:] = [d for d in dossiers if d not in IGNORES]
        for nom in fichiers:
            chemin = os.path.join(racine, nom)
            try:
                with open(chemin, encoding="utf-8") as f:
                    yield chemin, f.read()
            except (UnicodeDecodeError, OSError):
                continue        # binaire (image, police, paquet)


def _lire(*morceaux):
    with open(os.path.join(RACINE, *morceaux), encoding="utf-8") as f:
        return f.read()


class LesAdresses(unittest.TestCase):

    def test_aucune_adresse_codebyr_hors_de_codebyr_dev(self):
        fautives = []
        for chemin, texte in _sources():
            for hote in URL.findall(texte):
                hote = hote.lower().rstrip(".")
                if DOMAINE_CODEBYR.search(hote) and not (
                        hote == "codebyr.dev" or hote.endswith(".codebyr.dev")):
                    fautives.append("%s : %s" % (os.path.relpath(chemin, RACINE), hote))
        self.assertEqual(fautives, [])

    def test_l_identite_du_systeme_designe_le_projet(self):
        construction = _lire("packaging", "build-deb.sh")
        for cle in ("HOME_URL", "SUPPORT_URL", "BUG_REPORT_URL"):
            ligne = re.search(r'^%s="([^"]+)"$' % cle, construction, re.MULTILINE)
            self.assertIsNotNone(ligne, cle)
            self.assertTrue(ligne.group(1).startswith(("https://os.codebyr.dev/",
                                                       "https://github.com/Romtouf/codebyr-os/")),
                            ligne.group(1))


class LaVersionAnnoncee(unittest.TestCase):

    def setUp(self):
        self.version = _lire("VERSION").strip()
        self.entrees = ENTETE.findall(_lire("CHANGELOG.md"))
        publiees = [v for v, date in self.entrees if NON_PUBLIEE not in date]
        self.publiee = publiees[0] if publiees else None

    def test_version_est_la_derniere_entree_du_journal(self):
        self.assertTrue(self.entrees, "aucune entrée « ## x.y.z — … » dans CHANGELOG.md")
        self.assertEqual(self.entrees[0][0], self.version)

    def test_le_readme_annonce_la_derniere_version_publiee(self):
        annonce = re.search(r"Version publiée : \*\*(\d+\.\d+\.\d+)\*\*", _lire("README.md"))
        self.assertIsNotNone(annonce, "le README n'annonce plus de version publiée")
        self.assertEqual(annonce.group(1), self.publiee)

    def test_la_carte_du_projet_annonce_la_meme(self):
        annonce = re.search(r"version publiée \*\*(\d+\.\d+\.\d+)\*\*",
                            _lire("docs", "chantiers.md"))
        self.assertIsNotNone(annonce)
        self.assertEqual(annonce.group(1), self.publiee)

    def test_une_seule_version_en_preparation(self):
        # Une seule entrée « non publiée », et c'est la plus récente : une
        # version en attente sous une version publiée n'a pas de sens.
        en_attente = [v for v, date in self.entrees if NON_PUBLIEE in date]
        self.assertLessEqual(len(en_attente), 1, en_attente)
        if en_attente:
            self.assertEqual(en_attente[0], self.entrees[0][0])


if __name__ == "__main__":
    unittest.main()
