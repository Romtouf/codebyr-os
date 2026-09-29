# -*- coding: utf-8 -*-
"""Les listes du filtre d'appels système : ce qu'elles promettent, vérifié.

Le passage à une liste d'autorisation (chantier ouvert le 29/09/2026) repose
sur une liste FIGÉE des appels connus. Figée, elle refusera les appels de
demain ; calculée à l'exécution, elle les accueillerait sans bruit. C'est ce
que le premier test garde.
"""
import ast
import os
import unittest

from outils import LIB
import filtre_syscalls  # noqa: E402

SOURCE = os.path.join(LIB, "filtre_syscalls.py")


class LesListes(unittest.TestCase):

    def test_les_appels_connus_sont_ecrits_en_toutes_lettres(self):
        with open(SOURCE, encoding="utf-8") as f:
            arbre = ast.parse(f.read())
        valeurs = [n.value for n in arbre.body if isinstance(n, ast.Assign)
                   and any(getattr(c, "id", None) == "CONNUS" for c in n.targets)]
        self.assertEqual(len(valeurs), 1)
        self.assertIsInstance(valeurs[0], ast.Tuple)
        self.assertTrue(all(isinstance(e, ast.Constant) and isinstance(e.value, str)
                            for e in valeurs[0].elts),
                        "CONNUS doit être une liste de noms écrite, pas calculée")

    def test_les_appels_connus_sont_ceux_de_libseccomp_2_6_0(self):
        self.assertEqual(len(filtre_syscalls.CONNUS), 379)
        self.assertEqual(len(set(filtre_syscalls.CONNUS)), 379, "doublon dans CONNUS")

    def test_chaque_refus_et_chaque_candidat_est_un_appel_connu(self):
        # Un nom mal orthographié n'est jamais résolu : le filtre passerait
        # pour actif sans rien refuser, ou mesurerait un appel qui n'existe pas.
        connus = set(filtre_syscalls.CONNUS)
        self.assertEqual(sorted(set(filtre_syscalls.REFUSES) - connus), [])
        self.assertEqual(sorted(set(filtre_syscalls.A_MESURER) - connus), [])

    def test_un_candidat_n_est_ni_un_refus_ni_en_double(self):
        candidats = filtre_syscalls.A_MESURER
        self.assertEqual(len(candidats), len(set(candidats)))
        self.assertEqual(sorted(set(candidats) & set(filtre_syscalls.REFUSES)), [])

    def test_ce_qui_protege_les_applications_n_est_jamais_candidat(self):
        # Firefox construit son propre bac à sable (unshare, chroot, seccomp),
        # une application peut se restreindre elle-même (landlock), la glibc se
        # rabat de clone3 sur clone, et uretprobe n'est appelé que par le
        # trampoline du noyau. Les refuser retirerait une défense, ou casserait
        # sans rien protéger.
        for garde in ("unshare", "chroot", "seccomp", "clone3", "uretprobe",
                      "landlock_create_ruleset", "landlock_add_rule",
                      "landlock_restrict_self", "prctl", "membarrier", "rseq"):
            self.assertNotIn(garde, filtre_syscalls.A_MESURER, garde)

    def test_le_mode_mesure_ne_s_active_que_depuis_etc(self):
        # /etc est en lecture seule dans le bac à sable : un Espace ne peut pas
        # le poser lui-même. Il ne desserre d'ailleurs rien (voir les tests
        # d'intégration), mais il remplirait le journal.
        self.assertTrue(filtre_syscalls.MESURE.startswith("/etc/codebyr/"))


if __name__ == "__main__":
    unittest.main()
