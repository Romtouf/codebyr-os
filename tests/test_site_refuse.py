# -*- coding: utf-8 -*-
"""Bouclier 1.6 : un site refusé par le filtre d'un Espace s'explique.

Vu sur la VM le 13/11/2026 : dans l'Espace Banque, un site HTTPS hors de la
liste n'affichait que l'erreur de Firefox, « La connexion a été refusée par le
serveur proxy » — Firefox ne montre jamais le contenu d'un refus de CONNECT.
Le bouclier remplace l'onglet par une page de l'extension. Il explique, il ne
protège pas : le refus reste l'affaire du filtre réseau, hors du navigateur.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

import outils
from outils import LIB

import navigateur

SRC = os.path.join(LIB, "antiphishing")


def _lire(nom):
    with open(os.path.join(SRC, nom), encoding="utf-8") as f:
        return f.read()


HARNAIS = r"""
const vm = require("vm");
const entree = JSON.parse(process.argv[1]);
let ecouteur = null;
const mises_a_jour = [], demandes = [];
const browser = {
    runtime: {getURL: (p) => "moz-extension://uuid/" + p},
    storage: {managed: {get: async () => entree.stockage}},
    tabs: {onUpdated: {addListener: (f) => { ecouteur = f; }},
           update: async (id, proprietes) => { mises_a_jour.push({id, proprietes}); }},
};
const fetch = (adresse) => { demandes.push(adresse); return Promise.reject(new Error("refus")); };
vm.runInContext(entree.code, vm.createContext({browser, URL, URLSearchParams, fetch}));
(async () => {
    for (const adresse of entree.adresses)
        await ecouteur(4, adresse === null ? {status: "complete"} : {url: adresse});
    console.log(JSON.stringify({mises_a_jour, demandes}));
})();
"""


def _filtre(stockage, adresses):
    r = subprocess.run(["node", "-e", HARNAIS,
                        json.dumps({"code": _lire("filtre.js"), "stockage": stockage,
                                    "adresses": adresses})],
                       capture_output=True, text=True, encoding="utf-8", timeout=20)
    if r.returncode:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout)


BANQUE = {"filtre": ["mabanque.fr", "*.mabanque.fr"], "espace": "Banque"}


@unittest.skipUnless(shutil.which("node"), "node absent : l'extension ne peut pas être exécutée")
class LExplication(unittest.TestCase):

    def test_un_site_hors_de_la_liste_recoit_la_page(self):
        r = _filtre(BANQUE, ["https://fr.wikipedia.org/wiki/Banque"])
        self.assertEqual(len(r["mises_a_jour"]), 1)
        maj = r["mises_a_jour"][0]
        self.assertEqual(maj["id"], 4)
        self.assertTrue(maj["proprietes"]["loadReplace"])
        self.assertEqual(maj["proprietes"]["url"],
                         "moz-extension://uuid/refus.html?hote=fr.wikipedia.org&espace=Banque")
        # Le filtre voit la demande : c'est lui qui la note dans « Sites bloqués ».
        self.assertEqual(r["demandes"], ["https://fr.wikipedia.org/"])

    def test_un_site_de_la_liste_s_ouvre_sans_rien(self):
        r = _filtre(BANQUE, ["https://mabanque.fr/", "https://www.mabanque.fr/comptes",
                             "about:blank", "moz-extension://uuid/refus.html?hote=x", None])
        self.assertEqual(r, {"mises_a_jour": [], "demandes": []})

    def test_hors_d_un_espace_a_liste_il_ne_fait_rien(self):
        # Navigation, Personnel… : pas de clé « filtre », donc aucun refus à
        # expliquer. Une liste VIDE, elle, refuse tout (Banque non configurée).
        self.assertEqual(_filtre({"domaines": ["mabanque.fr"]}, ["https://exemple.org/"])["mises_a_jour"], [])
        self.assertEqual(len(_filtre({"filtre": [], "espace": "Banque"},
                                     ["https://exemple.org/"])["mises_a_jour"]), 1)

    def test_meme_regle_que_le_filtre_reseau(self):
        # Deux règles qui divergent : une page expliquée alors qu'elle se
        # serait ouverte, ou l'erreur de Firefox pour un site refusé.
        proxy = outils.charger("codebyr-net-proxy")
        motifs = ["mabanque.fr", "*.autre.fr", "seul.fr"]
        hotes = ["mabanque.fr", "www.mabanque.fr", "autre.fr", "a.b.autre.fr", "pasautre.fr",
                 "seul.fr", "www.seul.fr", "MABANQUE.FR", "mabanque.fr.piege.com"]
        r = _filtre({"filtre": motifs, "espace": "B"}, ["https://%s/" % h for h in hotes])
        expliques = {m["proprietes"]["url"].split("hote=")[1].split("&")[0] for m in r["mises_a_jour"]}
        refuses = {h.lower() for h in hotes if not proxy.autorise(h, motifs)}
        self.assertEqual(expliques, refuses)
        self.assertIn("www.mabanque.fr", refuses)      # un nom seul ne couvre que lui


class LaPage(unittest.TestCase):

    def test_elle_explique_et_n_autorise_rien(self):
        # La liste se modifie hors du navigateur : aucune page n'a à l'élargir.
        code = _lire("refus.js")
        for interdit in ("storage", "sendMessage", "innerHTML", "codebyrApprouver"):
            self.assertNotIn(interdit, code)
        self.assertIn("el.textContent = contenu", code)
        self.assertNotIn("<script>", _lire("refus.html"))

    def test_ses_textes_existent_dans_les_deux_langues(self):
        import re
        cles = set(re.findall(r'texte\("(refus_\w+)"', _lire("refus.js")))
        self.assertGreaterEqual(len(cles), 7)
        for langue in ("fr", "en"):
            messages = json.loads(_lire(os.path.join("_locales", langue, "messages.json")))
            self.assertLessEqual(cles, set(messages), langue)

    def test_le_filtre_ne_peut_pas_modifier_la_liste(self):
        code = _lire("filtre.js")
        self.assertIn("api.storage.managed.get(", code)
        for ecriture in ("storage.local", ".set(", "sendMessage"):
            self.assertNotIn(ecriture, code)


class LaListeDonneeAuBouclier(unittest.TestCase):

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)

    def _donnees(self):
        with open(os.path.join(self.home, ".mozilla", "managed-storage",
                               navigateur.BOUCLIER_ID + ".json"), encoding="utf-8") as f:
            return json.load(f)["data"]

    def test_seul_un_espace_a_liste_la_recoit(self):
        banque = {"nom": "Banque", "reseau": {"mode": "liste-blanche",
                                              "domaines": ["mabanque.fr", "*.mabanque.fr"]}}
        self.assertEqual(navigateur.filtre_de(banque), ["mabanque.fr", "*.mabanque.fr"])
        self.assertIsNone(navigateur.filtre_de({"nom": "Navigation"}))
        self.assertIsNone(navigateur.filtre_de({"reseau": {"mode": "coupe"}}))
        navigateur.ecrire_stockage_manage(self.home, ["mabanque.fr"])
        self.assertEqual(self._donnees(), {"domaines": ["mabanque.fr"]})
        navigateur.ecrire_stockage_manage(self.home, ["mabanque.fr"],
                                          navigateur.filtre_de(banque), "Banque")
        self.assertEqual(self._donnees(), {"domaines": ["mabanque.fr"], "espace": "Banque",
                                           "filtre": ["mabanque.fr", "*.mabanque.fr"]})

    def test_transmise_aussi_sous_compte_separe(self):
        with open(os.path.join(LIB, "ordres_espace.py"), encoding="utf-8") as f:
            self.assertIn('"filtre": navigateur.filtre_de(esp),', f.read())
        with open(os.path.join(outils.BIN, "codebyr-space"), encoding="utf-8") as f:
            space = f.read()
        self.assertIn("navigateur.installer_bouclier(home, espaces, esp)", space)
        self.assertIn('filtre = charge.get("filtre")', space)


if __name__ == "__main__":
    unittest.main()
