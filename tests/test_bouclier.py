# -*- coding: utf-8 -*-
"""Le bouclier anti-hameçonnage (extension Firefox).

Point d'attention particulier : le `.xpi` **signé par Mozilla** est un fichier
scellé. Modifier `content.js` dans le dépôt ne change RIEN sur les machines
tant que l'extension n'a pas été re-signée : c'est le .xpi signé que Firefox
installe, par la politique du paquet. Ce test compare donc les deux, pour qu'un correctif du
bouclier ne puisse pas rester lettre morte sans qu'on le voie.
"""
import glob
import json
import os
import random
import re
import shutil
import subprocess
import unittest
import zipfile

from outils import RACINE

SRC = os.path.join(RACINE, "live-build", "config",
                   "includes.chroot_after_packages", "usr", "share",
                   "codebyr", "antiphishing")
SIGNES = os.path.join(SRC, "signed")


class Manifeste(unittest.TestCase):

    def setUp(self):
        with open(os.path.join(SRC, "manifest.json"), encoding="utf-8") as f:
            self.manifeste = json.load(f)

    def test_identifiant_stable(self):
        # Cet identifiant est celui du manifeste de stockage managé écrit par
        # navigateur.py : les deux doivent coïncider, sinon l'extension ne
        # reçoit jamais la liste des domaines protégés.
        self.assertEqual(
            self.manifeste["browser_specific_settings"]["gecko"]["id"],
            "antiphishing@codebyr.io")
        import navigateur
        self.assertEqual(navigateur.BOUCLIER_ID, "antiphishing@codebyr.io")

    def test_permissions_minimales(self):
        self.assertEqual(self.manifeste["permissions"], ["storage"])


class CodeStatique(unittest.TestCase):
    """L'extension doit rester signable : aucune donnée injectée dans le code."""

    def setUp(self):
        with open(os.path.join(SRC, "content.js"), encoding="utf-8") as f:
            self.code = f.read()

    def test_les_domaines_viennent_du_stockage_manage(self):
        self.assertIn("storage.managed", self.code)

    def test_pas_de_domaine_en_dur(self):
        # Un domaine écrit dans le code signifierait qu'on le réécrit avant
        # installation — donc une extension non signable.
        suspects = re.findall(r'"[a-z0-9-]+\.(?:fr|com|net|org|be|ch)"', self.code)
        self.assertEqual(suspects, [], "domaines en dur : %s" % suspects)

    def test_pas_d_innerhtml_avec_des_donnees_du_site(self):
        # On construit l'avertissement avec textContent : le nom d'hôte affiché
        # vient du site visité, il n'a rien à faire dans du HTML interprété.
        self.assertEqual(re.findall(r"\.innerHTML\s*=", self.code), [])


HARNAIS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bouclier_harnais.cjs")


def _node(demande):
    r = subprocess.run(["node", HARNAIS], input=json.dumps(demande), capture_output=True,
                       text=True, encoding="utf-8", timeout=60)
    if r.returncode != 0:
        raise AssertionError("banc d'essai du bouclier : %s" % r.stderr)
    return json.loads(r.stdout)


@unittest.skipUnless(shutil.which("node"), "node absent : le bouclier ne peut pas être exécuté")
class Detection(unittest.TestCase):
    """Le VRAI content.js, exécuté comme Firefox l'exécute, face à des adresses.

    Relevé par l'audit du 29/09/2026 : le navigateur donne le nom d'hôte en
    punycode. « mаbanque.fr » avec un « а » cyrillique arrivait comme
    « xn--mbanque-2fg.fr », ne ressemblait plus à rien, et le bouclier se
    taisait — sur l'attaque qu'il existe pour arrêter. Les adresses piégées
    sont écrites ici en codes : à l'œil, elles sont identiques aux vraies.
    """

    # Le registre n'accepte que de l'ASCII (registre.normaliser_domaine) : un
    # domaine accentué, « société-exemple.fr », y est inscrit en punycode.
    PROTEGES = ["mabanque.fr", "revolut.com", "paypal.com", "xn--socit-exemple-ehbb.fr"]
    ATTENDUS = [
        ("https://mabanque.fr/", False, "le site officiel"),
        ("https://www.mabanque.fr/", False, "un sous-domaine officiel"),
        ("https://mabanque.com/", True, "même nom, autre extension"),
        ("https://nabanque.fr/", True, "faute de frappe"),
        ("https://mabanque.piege.com/", True, "le nom en étiquette"),
        ("https://revolution.com/", False, "le nom dans un mot, pas en étiquette"),
        ("https://mаbanque.fr/", True, "un « а » cyrillique"),
        ("https://раураӏ.com/", True, "« paypal » tout en cyrillique"),
        ("https://ραyραl.com/", True, "« paypal » en partie grec"),
        ("https://mabánque.fr/", True, "un accent ajouté"),
        ("https://mаbаnquе-sесurе.com/", True,
         "alphabets mêlés, nom en préfixe"),
        ("https://ｍａｂａｎｑｕｅ.com/", True, "pleine chasse"),
        ("https://münchen.de/", False, "un domaine international ordinaire"),
        ("https://пример.рф/", False,
         "un domaine cyrillique ordinaire"),
        ("https://société-exemple.fr/", False, "un domaine protégé accentué, officiel"),
        ("https://societe-exemple.fr/", True, "le même, sans ses accents"),
    ]

    def setUp(self):
        self.resultats = {r["adresse"]: r for r in _node({
            "mode": "adresses", "proteges": self.PROTEGES,
            "adresses": [a for a, _alerte, _cas in self.ATTENDUS]})}

    def test_chaque_adresse(self):
        for adresse, alerte, cas in self.ATTENDUS:
            with self.subTest(cas=cas):
                r = self.resultats[adresse]
                self.assertEqual(r["alerte"], alerte, "%s (%s)" % (cas, r["hote"]))

    def test_l_alerte_montre_l_adresse_telle_qu_elle_s_ecrit(self):
        # À l'écran, « mаbanque.fr » est « mabanque.fr » : l'alerte dit ce que
        # l'adresse est vraiment, et seulement quand elle trompe l'œil.
        piege = self.resultats["https://mаbanque.fr/"]
        self.assertTrue(any("s'écrit « xn--" in t for t in piege["textes"]), piege["textes"])
        simple = self.resultats["https://mabanque.com/"]
        self.assertFalse(any("s'écrit «" in t for t in simple["textes"]), simple["textes"])

    def test_le_decodeur_rend_ce_que_rend_celui_de_node(self):
        # RFC 3492, contre l'implémentation de référence de node (ICU), sur des
        # étiquettes tirées de plusieurs alphabets — la graine est fixe.
        alphabets = ["abcdefghijklmnopqrstuvwxyz0123456789-",
                     "àâäçéèêëîïôöùûüÿñ",
                     "".join(chr(c) for c in range(0x0430, 0x0450)),
                     "".join(chr(c) for c in range(0x03b1, 0x03ca)),
                     "".join(chr(c) for c in range(0x0561, 0x0587)),
                     "".join(chr(c) for c in range(0x4e00, 0x4e40))]
        hasard = random.Random(20260929)
        etiquettes = ["münchen", "пример", "bücher",
                      "ñandú", "例え"]
        for _ in range(400):
            melange = "".join(hasard.sample(alphabets, hasard.randint(1, 3)))
            etiquettes.append("".join(hasard.choice(melange)
                                      for _ in range(hasard.randint(1, 20))).strip("-"))
        r = _node({"mode": "punycode", "etiquettes": [e for e in etiquettes if e]})
        self.assertEqual(r["ecarts"], [])
        # Un test qui n'a rien comparé ne prouve rien.
        self.assertGreater(r["comparees"], 300)


class ProfilUtilise(unittest.TestCase):
    """Le bouclier doit aller dans le profil que Firefox OUVRE.

    Constaté le 29/09/2026 sur la VM : aucune alerte dans Navigation, pas même
    sur « mabanque.com ». Firefox y avait été ouvert avant qu'une banque soit
    déclarée ; il s'était créé son propre profil, et le bouclier était déposé
    dans « codebyr.default », que personne n'ouvrait. La liste des banques
    étant vide par défaut, c'était le cas de quiconque ouvrait le navigateur
    avant de déclarer la sienne.
    """

    def setUp(self):
        import outils  # noqa: F401 — place le module partagé sur sys.path
        import navigateur
        self.navigateur = navigateur

    def test_le_profil_marque_par_defaut(self):
        texte = ("[Install4F96D1932A9F858E]\nDefault=autre.default\n\n"
                 "[Profile1]\nName=codebyr\nIsRelative=1\nPath=codebyr.default\n\n"
                 "[Profile0]\nName=default-esr\nIsRelative=1\nPath=ab12cd.default-esr\n"
                 "Default=1\n\n[General]\nStartWithLastProfile=1\nVersion=2\n")
        self.assertEqual(self.navigateur.profil_par_defaut(texte), "ab12cd.default-esr")

    def test_le_seul_profil_quand_aucun_n_est_marque(self):
        texte = "[Profile0]\nName=x\nIsRelative=1\nPath=xy.default\n"
        self.assertEqual(self.navigateur.profil_par_defaut(texte), "xy.default")

    def test_un_chemin_qui_sortirait_du_dossier_est_ignore(self):
        # profiles.ini est écrit par l'Espace : il ne doit pas pouvoir faire
        # écrire le lanceur hors de chez lui.
        for chemin, relatif in (("../../.config/autostart", "1"), ("/home/romtouf", "0"),
                                ("a/b", "1"), ("..", "1"), ("", "1")):
            texte = "[Profile0]\nIsRelative=%s\nPath=%s\nDefault=1\n" % (relatif, chemin)
            self.assertIsNone(self.navigateur.profil_par_defaut(texte), chemin)
        self.assertIsNone(self.navigateur.profil_par_defaut("pas un fichier ini [[["))


@unittest.skipUnless(os.name == "posix", "fichiers_surs travaille par descripteur de dossier")
class InstallationDansLeProfil(unittest.TestCase):

    def setUp(self):
        import tempfile
        import outils  # noqa: F401 — place le module partagé sur sys.path
        import navigateur
        self.navigateur = navigateur
        self._bouclier_dir = navigateur.BOUCLIER_DIR
        self._tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self._tmp.name, "home")
        os.makedirs(self.home)
        bouclier = os.path.join(self._tmp.name, "antiphishing")
        os.makedirs(os.path.join(bouclier, "signed"))
        with open(os.path.join(bouclier, "signed", "essai-1.3.xpi"), "wb") as f:
            f.write(b"PK xpi d'essai")
        # Module partagé, donc chargé une seule fois : on rend la valeur après.
        navigateur.BOUCLIER_DIR = bouclier
        self.ff = os.path.join(self.home, ".mozilla", "firefox")

    def tearDown(self):
        self.navigateur.BOUCLIER_DIR = self._bouclier_dir
        self._tmp.cleanup()

    def _xpi(self, profil):
        return os.path.join(self.ff, profil, "extensions", "antiphishing@codebyr.io.xpi")

    def _lire(self, *chemin):
        with open(os.path.join(*chemin), encoding="utf-8") as f:
            return f.read()

    def _domaines(self):
        stock = os.path.join(self.home, ".mozilla", "managed-storage", "antiphishing@codebyr.io.json")
        return json.loads(self._lire(stock))["data"]["domaines"]

    def _profil_existant(self, nom, extensions_json=None, copie=False):
        os.makedirs(os.path.join(self.ff, nom, "extensions"))
        with open(os.path.join(self.ff, "profiles.ini"), "w", encoding="utf-8") as f:
            f.write("[Profile0]\nName=x\nIsRelative=1\nPath=%s\nDefault=1\n" % nom)
        if extensions_json is not None:
            with open(os.path.join(self.ff, nom, "extensions.json"), "w", encoding="utf-8") as f:
                json.dump(extensions_json, f)
        if copie:
            with open(self._xpi(nom), "wb") as f:
                f.write(b"PK copie")

    def test_premier_lancement_sans_banque_le_profil_de_codebyr_est_pose(self):
        self.navigateur.installer_bouclier_pour(self.home, [])
        self.assertIn("Path=codebyr.default", self._lire(self.ff, "profiles.ini"))
        # Liste écrite même vide : une banque retirée ne reste pas protégée.
        self.assertEqual(self._domaines(), [])

    def test_codebyr_ne_depose_plus_l_extension_c_est_firefox_qui_l_installe(self):
        # Par la politique du paquet (dossier distribution) : son circuit
        # d'installation est le seul qui accorde le droit de lire les pages.
        self.navigateur.installer_bouclier_pour(self.home, ["mabanque.fr"])
        self.assertFalse(os.path.exists(self._xpi("codebyr.default")))
        self.assertEqual(self._domaines(), ["mabanque.fr"])

    def test_le_garde_fou_de_firefox_contre_les_extensions_deposees_est_retabli(self):
        # Codebyr posait autoDisableScopes à 0 pour SON extension : toute autre
        # extension glissée dans le profil s'activait alors sans rien demander.
        self.navigateur.installer_bouclier_pour(self.home, ["mabanque.fr"])
        prefs = self._lire(self.ff, "codebyr.default", "user.js")
        self.assertIn('user_pref("extensions.autoDisableScopes", 3);', prefs)
        self.assertNotIn('"extensions.autoDisableScopes", 0', prefs)

    def test_les_reglages_vont_dans_le_profil_que_firefox_s_est_cree(self):
        self._profil_existant("ab12cd.default-esr")
        ini = self._lire(self.ff, "profiles.ini")
        self.navigateur.installer_bouclier_pour(self.home, ["mabanque.fr"])
        self.assertIn("autoDisableScopes", self._lire(self.ff, "ab12cd.default-esr", "user.js"))
        self.assertFalse(os.path.exists(os.path.join(self.ff, "codebyr.default")))
        self.assertEqual(self._lire(self.ff, "profiles.ini"), ini, "le choix de Firefox est gardé")

    def test_la_copie_deposee_a_l_ancienne_est_retiree(self):
        # Déposée par Codebyr jusqu'en 1.16.3, souvent sans droit sur les pages.
        # Firefox refuse de réinstaller par la politique une version présente :
        # sans ce retrait, elle resterait muette à vie (constaté sur la VM).
        self._profil_existant("ab12cd.default-esr", {"addons": [
            {"id": "antiphishing@codebyr.io", "version": "1.3",
             "installTelemetryInfo": {"source": "app-profile", "method": "sideload"}}]},
            copie=True)
        self.navigateur.installer_bouclier_pour(self.home, ["mabanque.fr"])
        self.assertFalse(os.path.exists(self._xpi("ab12cd.default-esr")))

    def test_la_copie_installee_par_firefox_est_gardee(self):
        self._profil_existant("ab12cd.default-esr", {"addons": [
            {"id": "antiphishing@codebyr.io", "version": "1.3",
             "installTelemetryInfo": {"source": "enterprise-policy"}}]}, copie=True)
        self.navigateur.installer_bouclier_pour(self.home, ["mabanque.fr"])
        self.assertTrue(os.path.isfile(self._xpi("ab12cd.default-esr")))

    def test_un_profiles_ini_piege_ne_fait_rien_ecrire_ailleurs(self):
        os.makedirs(self.ff)
        with open(os.path.join(self.ff, "profiles.ini"), "w", encoding="utf-8") as f:
            f.write("[Profile0]\nIsRelative=1\nPath=../../dehors\nDefault=1\n")
        self.navigateur.installer_bouclier_pour(self.home, ["mabanque.fr"])
        self.assertTrue(os.path.isfile(os.path.join(self.ff, "codebyr.default", "user.js")))
        self.assertFalse(os.path.exists(os.path.join(self.home, "dehors")))


class PolitiqueFirefox(unittest.TestCase):
    """La politique qui fait installer le bouclier par Firefox lui-même.

    Mesuré le 29/09/2026 sur Firefox 140 ESR : placée dans le dossier
    distribution, elle installe l'extension signée par le circuit ordinaire, qui
    lui accorde le droit de lire les pages ; /etc/firefox-esr/policies n'est pas
    lu par ce Firefox.
    """

    CHEMIN = os.path.join(RACINE, "live-build", "config", "includes.chroot_after_packages",
                          "usr", "lib", "firefox-esr", "distribution", "policies.json")

    def test_elle_designe_le_xpi_signe_livre(self):
        with open(self.CHEMIN, encoding="utf-8") as f:
            reglage = json.load(f)["policies"]["ExtensionSettings"]["antiphishing@codebyr.io"]
        signes = [os.path.basename(x) for x in glob.glob(os.path.join(SIGNES, "*.xpi"))]
        self.assertEqual(len(signes), 1, signes)
        self.assertEqual(reglage["install_url"],
                         "file:///usr/share/codebyr/antiphishing/signed/" + signes[0],
                         "la politique doit désigner le .xpi livré — sign-extension.sh "
                         "la met à jour à chaque signature")
        self.assertEqual(reglage["installation_mode"], "normal_installed")

    def test_elle_part_avec_le_paquet(self):
        with open(os.path.join(RACINE, "packaging", "build-deb.sh"), encoding="utf-8") as f:
            self.assertIn("usr/lib/firefox-esr/distribution/policies.json", f.read())

    def test_la_signature_la_tient_a_jour(self):
        with open(os.path.join(RACINE, "live-build", "scripts", "sign-extension.sh"),
                  encoding="utf-8") as f:
            self.assertIn("distribution/policies.json", f.read())


class XpiSigne(unittest.TestCase):

    def _xpi(self):
        trouves = sorted(glob.glob(os.path.join(SIGNES, "*.xpi")))
        if not trouves:
            self.fail("aucun .xpi signé livré")
        return trouves[0]

    RAPPEL = ("\nLe bouclier réellement installé sur les machines est celui du "
              ".xpi signé : tant qu'il n'est pas régénéré, un correctif du "
              "bouclier n'a AUCUN effet.\n"
              "  → AMO_KEY=... AMO_SECRET=... bash live-build/scripts/sign-extension.sh\n"
              "  puis remplacer le .xpi dans %s" % SIGNES)

    def test_le_code_du_xpi_signe_correspond_a_la_source(self):
        xpi = self._xpi()
        with zipfile.ZipFile(xpi) as z:
            self.assertIn("content.js", z.namelist())
            embarque = z.read("content.js").replace(b"\r\n", b"\n")
        with open(os.path.join(SRC, "content.js"), "rb") as f:
            source = f.read().replace(b"\r\n", b"\n")
        self.assertEqual(embarque, source,
                         "content.js diffère du .xpi signé." + self.RAPPEL)

    def test_la_version_du_xpi_signe_correspond_au_manifeste(self):
        # AMO ré-encode le JSON (échappements \\uXXXX) : on compare le SENS,
        # pas les octets.
        xpi = self._xpi()
        with zipfile.ZipFile(xpi) as z:
            embarque = json.loads(z.read("manifest.json").decode("utf-8"))
        with open(os.path.join(SRC, "manifest.json"), encoding="utf-8") as f:
            source = json.load(f)
        for cle in ("manifest_version", "content_scripts", "host_permissions", "browser_specific_settings"):
            self.assertEqual(embarque.get(cle), source.get(cle),
                             "Manifeste signé différent : " + cle + self.RAPPEL)
        self.assertEqual(embarque.get("version"), source.get("version"),
                         "version du manifeste ≠ version signée." + self.RAPPEL)
        self.assertEqual(embarque.get("permissions"), source.get("permissions"),
                         "permissions ≠ celles du .xpi signé." + self.RAPPEL)


if __name__ == "__main__":
    unittest.main()
