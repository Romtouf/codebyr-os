# -*- coding: utf-8 -*-
"""Les listes du filtre d'appels système : ce qu'elles promettent, vérifié.

Depuis la 1.16.4, le Blindage est une liste d'autorisation : elle repose sur
une liste FIGÉE des appels connus. Figée, elle refuse les appels de demain ;
calculée à l'exécution, elle les accueillerait sans bruit. C'est ce que le
premier test garde.
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

    def test_chaque_refus_et_chaque_ecarte_est_un_appel_connu(self):
        # Un nom mal orthographié n'est jamais résolu : le filtre passerait
        # pour actif sans rien refuser, ou écarterait un appel qui n'existe pas.
        connus = set(filtre_syscalls.CONNUS)
        self.assertEqual(sorted(set(filtre_syscalls.REFUSES) - connus), [])
        self.assertEqual(sorted(set(filtre_syscalls.ECARTES) - connus), [])

    def test_un_ecarte_n_est_ni_un_refus_ni_en_double(self):
        ecartes = filtre_syscalls.ECARTES
        self.assertEqual(len(ecartes), len(set(ecartes)))
        self.assertEqual(sorted(set(ecartes) & set(filtre_syscalls.REFUSES)), [])

    def test_sont_autorises_les_connus_moins_refus_et_ecartes(self):
        autorises = filtre_syscalls.autorises()
        self.assertEqual(len(autorises), len(filtre_syscalls.CONNUS)
                         - len(filtre_syscalls.REFUSES) - len(filtre_syscalls.ECARTES))
        self.assertEqual(sorted(set(autorises) & set(filtre_syscalls.REFUSES)), [])
        self.assertEqual(sorted(set(autorises) & set(filtre_syscalls.ECARTES)), [])

    def test_ce_qui_protege_les_applications_n_est_jamais_ecarte(self):
        # Firefox construit son propre bac à sable (unshare, chroot, seccomp),
        # une application peut se restreindre elle-même (landlock), la glibc se
        # rabat de clone3 sur clone, et uretprobe n'est appelé que par le
        # trampoline du noyau. Les refuser retirerait une défense, ou casserait
        # sans rien protéger.
        for garde in ("unshare", "chroot", "seccomp", "clone3", "uretprobe",
                      "landlock_create_ruleset", "landlock_add_rule",
                      "landlock_restrict_self", "prctl", "membarrier", "rseq"):
            self.assertIn(garde, filtre_syscalls.autorises(), garde)

    def test_ce_que_la_mesure_a_vu_servir_reste_autorise(self):
        # Relevés sur la VM le 29/09/2026 : Firefox (quotactl), un bwrap
        # imbriqué — Flatpak, vignettes de Fichiers — (mount, pivot_root, et
        # toute la famille des montages avec eux), localsearch, la recherche de
        # fichiers de GNOME (name_to_handle_at, fanotify_*). Les écarter
        # casserait ces applications-là.
        for servi in ("quotactl", "mount", "umount2", "pivot_root", "fsopen",
                      "fsmount", "move_mount", "open_tree", "mount_setattr",
                      "statmount", "listmount", "name_to_handle_at",
                      "fanotify_init", "fanotify_mark", "personality"):
            self.assertIn(servi, filtre_syscalls.autorises(), servi)

    def test_le_mode_mesure_ne_s_active_que_depuis_etc(self):
        # /etc est en lecture seule dans le bac à sable : un Espace ne peut pas
        # le poser lui-même. Il n'ouvre rien des refus (voir les tests
        # d'intégration), mais il laisserait passer les écartés.
        self.assertTrue(filtre_syscalls.MESURE.startswith("/etc/codebyr/"))


if __name__ == "__main__":
    unittest.main()
