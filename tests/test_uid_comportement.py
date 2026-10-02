# -*- coding: utf-8 -*-
"""Le service root codebyr-uid, éprouvé par ce qu'il FAIT.

Analyse externe du 01/10/2026, point 2.2 : une bonne partie des tests du
service vérifiaient son texte (« SO_PEERCRED est dans le code ») plutôt que
son comportement. Ceux-ci le font tourner pour de vrai, en root, avec de vrais
useradd, mount, setfacl et setpriv, dans une machine à part (voir
tests/uid_harnais.py) — et regardent ce qui reste après.

Ce que chaque scénario garde :
  · cycle    — ouvrir pose montages, droits, dépôt et premier processus sous
               plafond ; fermer retire tout, droits du compte de l'Espace sur
               les sockets du bureau compris ;
  · jetable  — le dossier est en mémoire, et son contenu part à la fermeture ;
  · echec    — une préparation qui échoue après avoir posé sockets et droits
               défait tout (constaté le 14/09/2026, quand rien n'était défait) ;
  · liens    — un lien piégé dans le dossier d'exécution du bureau, dans celui
               de l'Espace, ou à la place du dépôt n'est jamais suivi ;
  · abandon  — un Espace laissé ouvert par un service arrêté est refermé dès
               qu'il n'a plus d'application, et pas avant.

Le tout dans deux machines : /run découpé comme le fait logind, et /run d'un
seul tenant — là où os.path.ismount ne voyait pas les montages liés, et où la
fermeture laissait l'accès à l'affichage du bureau (trouvé par ce banc le
02/10/2026, corrigé par codebyr-uid, monte()).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HARNAIS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uid_harnais.py")
OUTILS = ("unshare", "mount", "setpriv", "setfacl", "getfacl", "useradd")
POSSIBLE = (os.environ.get("CODEBYR_TEST_LINUX") == "1" and hasattr(os, "geteuid")
            and os.geteuid() == 0 and all(shutil.which(o) for o in OUTILS))


def _scenario(nom, run):
    temporaire = tempfile.mkdtemp(prefix="codebyr-uid-banc-")
    try:
        resultat = subprocess.run(
            ["unshare", "--mount", "--propagation", "private",
             sys.executable, "-B", HARNAIS, nom, temporaire],
            capture_output=True, text=True, timeout=180,
            env=dict(os.environ, CODEBYR_BANC_RUN=run))
    finally:
        shutil.rmtree(temporaire, ignore_errors=True)
    if resultat.returncode != 0:
        raise AssertionError("banc %s (%s) : %s" % (nom, run, resultat.stderr[-3000:]))
    return json.loads(resultat.stdout.strip().splitlines()[-1])


RANGE = {"runtime": False, "montages": [], "droits_wayland": [], "droits_pipewire": [],
         "depot": False, "ordres": False, "processus": 0, "ouverts": []}


class _LeService:
    RUN = None

    @classmethod
    def setUpClass(cls):
        cls.r = {nom: _scenario(nom, cls.RUN)
                 for nom in ("cycle", "jetable", "echec", "liens", "abandon")}

    def assertRange(self, etat, contexte):
        self.assertTrue(etat["compte"], contexte)
        self.assertEqual({k: etat[k] for k in RANGE}, RANGE, contexte)

    # ── cycle ────────────────────────────────────────────────────────────────
    def test_ouvrir_pose_ce_qu_il_faut(self):
        c = self.r["cycle"]
        self.assertTrue(c["ouvert"]["reponse"]["ok"], c)
        p = c["pendant"]
        uid = p["uid_espace"]
        self.assertTrue(p["systeme"], "un compte d'Espace est un compte système")
        self.assertEqual(p["home"], {"mode": "0o700", "a_l_espace": True, "monte": False})
        self.assertEqual(p["montages"], ["/run/user/%d/pipewire-0" % uid,
                                         "/run/user/%d/wayland-0" % uid])
        self.assertEqual(p["droits_wayland"], [uid])
        self.assertEqual(p["droits_pipewire"], [uid])
        self.assertTrue(p["depot"] and p["ordres"])
        self.assertEqual(p["processus"], 1)

    def test_le_premier_processus_est_sous_plafond_et_sans_privilege(self):
        portee = self.r["cycle"]["portees"][0]
        for option in ("--scope", "MemoryMax=2G", "MemorySwapMax=0", "TasksMax=800"):
            self.assertIn(option, portee)
        self.assertIn("codebyr-espace-%s.scope" % self.r["cycle"]["ouvert"]["reponse"]["compte"],
                      portee)

    def test_fermer_retire_tout(self):
        c = self.r["cycle"]
        self.assertEqual(c["ferme"], {"reponse": {"ok": True}}, c["journal"])
        self.assertRange(c["apres"], "après fermeture")
        # Le dossier de l'Espace, lui, reste : ce sont ses données.
        self.assertEqual(c["apres"]["home"]["mode"], "0o700")

    # ── jetable ──────────────────────────────────────────────────────────────
    def test_le_jetable_vit_en_memoire_et_s_efface(self):
        j = self.r["jetable"]
        self.assertTrue(j["pendant"]["home"]["monte"])
        self.assertFalse(j["apres"]["home"]["monte"])
        self.assertFalse(j["secret_reste"], "le contenu du Jetable a survécu à sa fermeture")
        self.assertRange(j["apres"], "jetable refermé")

    # ── echec ────────────────────────────────────────────────────────────────
    def test_une_preparation_ratee_defait_tout(self):
        e = self.r["echec"]
        self.assertEqual(e["ouvert"].get("exception"), "OSError", e["ouvert"])
        self.assertRange(e["apres"], "préparation défaite")

    # ── liens ────────────────────────────────────────────────────────────────
    def test_un_lien_chez_le_bureau_n_est_pas_suivi(self):
        b = self.r["liens"]["bureau"]
        self.assertEqual(b["ouvert"].get("exception"), "ValueError", b["ouvert"])
        self.assertRange(b["apres"], "lien chez le bureau")

    def test_un_lien_chez_l_espace_n_est_pas_suivi(self):
        e = self.r["liens"]["espace"]
        self.assertTrue(e["premiere"]["reponse"]["ok"])
        self.assertEqual(e["seconde"].get("exception"), "ValueError", e["seconde"])
        # Rien n'a été présenté ni accordé à la place du lien ; l'Espace déjà
        # ouvert n'a pas été refermé sous les yeux de l'utilisateur.
        uid = e["pendant"]["uid_espace"]
        self.assertEqual(e["pendant"]["montages"], ["/run/user/%d/wayland-0" % uid])
        self.assertEqual(e["pendant"]["droits_pipewire"], [])
        self.assertEqual(e["pendant"]["processus"], 1)
        self.assertEqual(e["ferme"], {"reponse": {"ok": True}})
        self.assertRange(e["apres"], "lien chez l'Espace")

    def test_un_depot_remplace_par_un_lien_est_refuse(self):
        d = self.r["liens"]["depot"]
        self.assertEqual(d["ouvert"].get("exception"), "ValueError", d["ouvert"])
        self.assertTrue(d["lien_intact"])

    def test_la_cible_des_liens_est_intacte(self):
        l = self.r["liens"]
        self.assertEqual(l["apres"], {"shadow": l["avant"]["shadow"], "shadow_monte": False,
                                      "droits_shadow": [], "etc": l["avant"]["etc"],
                                      "droits_etc": []})

    # ── abandon ──────────────────────────────────────────────────────────────
    def test_un_espace_abandonne_et_vide_est_referme(self):
        a = self.r["abandon"]["sans_application"]
        self.assertEqual(a["avant"]["processus"], 1)
        self.assertEqual(a["avant"]["ouverts"], [])
        self.assertRange(a["apres"], "abandonné, sans application")

    def test_un_espace_abandonne_encore_utilise_attend_sa_derniere_application(self):
        a = self.r["abandon"]["avec_application"]
        self.assertEqual(a["applications"], 1)
        self.assertTrue(a["garde"]["runtime"])
        self.assertEqual(len(a["garde"]["montages"]), 2)
        self.assertRange(a["apres"], "abandonné, dernière application fermée")

    def test_rien_n_a_ete_tu_au_journal(self):
        for nom, r in self.r.items():
            fautes = [m for m in r["journal"] if "incompl" in m or "impossible à défaire" in m]
            self.assertEqual(fautes, [], nom)


@unittest.skipUnless(POSSIBLE, "root sous Linux (CODEBYR_TEST_LINUX=1) avec %s" % ", ".join(OUTILS))
class CommeLogindLeDecoupe(_LeService, unittest.TestCase):
    RUN = "logind"


@unittest.skipUnless(POSSIBLE, "root sous Linux (CODEBYR_TEST_LINUX=1) avec %s" % ", ".join(OUTILS))
class AvecUnSeulRun(_LeService, unittest.TestCase):
    RUN = "un-seul"


if __name__ == "__main__":
    unittest.main()
