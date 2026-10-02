# -*- coding: utf-8 -*-
"""Le code livré dit la règle et sa raison ; son histoire vit dans docs/decisions.md.

Analyse externe du 01/10/2026, point 2.3 : environ un tiers des lignes du code
Python étaient des commentaires, dont des dizaines de récits datés
(« Constaté le 14/09/2026 : … »). Un récit vieillit, et noie la règle qu'il
justifie. Depuis la 1.20.1, ce qui est installé sur une machine ne porte plus
de date : l'histoire est dans docs/decisions.md, les failles dans SECURITY.md.
"""
import os
import re
import unittest

from outils import RACINE

LIVRE = os.path.join(RACINE, "live-build", "config", "includes.chroot_after_packages")
DATE = re.compile(r"\b\d{2}/\d{2}/20\d{2}\b")

# Le bouclier est scellé par la signature de Mozilla : retoucher un
# commentaire demande de le faire signer de nouveau. Ses récits datés partiront
# à la prochaine modification du bouclier (voir docs/signer-le-bouclier.md).
SCELLES = {os.path.join("usr", "share", "codebyr", "antiphishing")}


def _livres():
    for dossier, _sous, fichiers in os.walk(LIVRE):
        relatif = os.path.relpath(dossier, LIVRE)
        if any(relatif == s or relatif.startswith(s + os.sep) for s in SCELLES):
            continue
        for nom in fichiers:
            yield os.path.join(dossier, nom)
    for nom in ("codebyr-tools.postinst", "codebyr-tools.preinst", "codebyr-tools.postrm"):
        yield os.path.join(RACINE, "packaging", nom)
    yield os.path.join(RACINE, "packaging", "grub", "10_linux")


class LeCodeLivre(unittest.TestCase):

    def test_aucun_recit_date(self):
        fautes = []
        for chemin in _livres():
            try:
                with open(chemin, encoding="utf-8") as f:
                    for numero, ligne in enumerate(f, 1):
                        if DATE.search(ligne):
                            fautes.append("%s:%d" % (os.path.relpath(chemin, RACINE), numero))
            except (UnicodeDecodeError, OSError):
                continue        # image, paquet signé…
        self.assertEqual(fautes, [], "l'histoire va dans docs/decisions.md")

    def test_l_histoire_a_sa_place(self):
        decisions = os.path.join(RACINE, "docs", "decisions.md")
        self.assertTrue(os.path.isfile(decisions))
        with open(os.path.join(LIVRE, "usr", "lib", "codebyr", "codebyr-uid"), encoding="utf-8") as f:
            self.assertIn("docs/decisions.md", f.read())
        with open(os.path.join(RACINE, "CONTRIBUTING.md"), encoding="utf-8") as f:
            self.assertIn("docs/decisions.md", f.read())


if __name__ == "__main__":
    unittest.main()
