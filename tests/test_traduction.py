# -*- coding: utf-8 -*-
"""Codebyr parle d'autres langues que le français (audit, point 5).

Le texte du code est la version française ; po/<langue>.po en contient les
traductions, compilées à la construction du paquet (packaging/traductions.py)
et choisies à l'exécution par usr/share/codebyr/traduction.py.

Ce que ces tests gardent :
· po/en.po suit le code — un texte ajouté sans « extraire » échoue ici ;
· chaque texte a sa traduction anglaise, sans en perdre les « {marques} » ;
· la règle de langue : français, langue traduite, sinon l'anglais ;
· dans un fichier déclaré traduit, aucune phrase n'échappe à _().
"""
import ast
import gettext
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from outils import RACINE

sys.path.insert(0, os.path.join(RACINE, "packaging"))
import traductions  # noqa: E402
import traduction  # noqa: E402

INCLUDES = os.path.join(RACINE, "live-build", "config", "includes.chroot_after_packages")
PO_EN = os.path.join(RACINE, "po", "en.po")

# Les fichiers passés à _(), étape par étape. Un fichier entre ici quand plus
# aucune de ses phrases affichées n'est écrite en dur.
FICHIERS_TRADUITS = [
    "usr/bin/codebyr-assistant",
    "usr/bin/codebyr-bienvenue",
    "usr/bin/codebyr-config",
    "usr/bin/codebyr-space",
    "usr/share/codebyr/archives.py",
    "usr/share/codebyr/autotest.py",
    "usr/share/codebyr/bac_a_sable.py",
    "usr/share/codebyr/compte_dedie.py",
    "usr/share/codebyr/fichiers_surs.py",
    "usr/share/codebyr/filtre_syscalls.py",
    "usr/share/codebyr/navigateur.py",
    "usr/share/codebyr/ordres_espace.py",
    "usr/share/codebyr/page_blocage.py",
    "usr/share/codebyr/permissions_flatpak.py",
    "usr/share/nautilus-python/extensions/codebyr-envoyer.py",
    "usr/share/nautilus-python/extensions/codebyr-jetable.py",
    "usr/share/nautilus-python/extensions/codebyr-provenance.py",
]

# Ce qui reste en français DANS un fichier traduit, et pourquoi. Le journal
# (journal(), noter()) n'y figure pas : il est écarté d'office — il s'adresse
# à qui dépanne, pas à qui utilise.
LAISSES = {
    # Erreur interne, jamais montrée : le processus est simplement ignoré.
    "Processus terminé avant son enregistrement",
    # Le nom d'une section que Flatpak écrit et que le code relit.
    "Session Bus Policy",
    # Une donnée transmise au bouclier, pas un texte affiché.
    "Domaines bancaires protégés par Codebyr.",
    # Diagnostics techniques de libseccomp, rapportés tels quels.
    "Création du filtre seccomp impossible", "Règle seccomp impossible : %s",
    "Chargement seccomp impossible",
}


def _lire(chemin):
    with open(chemin, encoding="utf-8") as f:
        return f.read()


class LaLangueChoisie(unittest.TestCase):

    def _langues(self, **environ):
        return traduction.langues_preferees(environ)

    def test_les_variables_sont_lues_dans_l_ordre_de_gettext(self):
        self.assertEqual(self._langues(LANG="de_DE.UTF-8"), ["de_DE"])
        self.assertEqual(self._langues(LANGUAGE="de:fr", LANG="en_US.UTF-8"), ["de", "fr"])
        self.assertEqual(self._langues(LC_ALL="en_GB.UTF-8@euro", LANG="fr_FR.UTF-8"), ["en_GB"])
        self.assertEqual(self._langues(), [])

    def test_francais_ou_sans_preference_le_texte_du_code(self):
        for langues in (["fr_FR"], ["fr"], ["fr_BE"], ["C"], ["POSIX"], []):
            self.assertIsNone(traduction.choisir(langues, {"en"}), langues)

    def test_une_langue_traduite_sa_traduction(self):
        self.assertEqual(traduction.choisir(["en_US"], {"en"}), "en")
        self.assertEqual(traduction.choisir(["de_DE"], {"en", "de"}), "de")
        self.assertEqual(traduction.choisir(["pt_BR"], {"en", "pt_BR", "pt"}), "pt_BR")

    def test_les_preferences_suivantes_sont_essayees(self):
        self.assertIsNone(traduction.choisir(["de", "fr"], {"en"}))
        self.assertEqual(traduction.choisir(["de", "en"], {"en"}), "en")

    def test_sinon_l_anglais_plutot_que_le_francais(self):
        self.assertEqual(traduction.choisir(["de_DE"], {"en"}), "en")
        self.assertEqual(traduction.choisir(["ja_JP"], {"en"}), "en")

    def test_en_francais_aucun_fichier_n_est_consulte(self):
        # Le service des comptes (AppArmor) et les bacs à sable importent ce
        # module : en français ou sans langue, il ne doit rien ouvrir.
        from unittest import mock
        for environ in ({}, {"LANG": "C.UTF-8"}, {"LANG": "fr_FR.UTF-8"}):
            with mock.patch("os.path.isfile", side_effect=AssertionError("consulté")), \
                    mock.patch("builtins.open", side_effect=AssertionError("ouvert")):
                catalogue = traduction.charger("/nulle/part", environ)
            self.assertIsInstance(catalogue, gettext.NullTranslations)

    def test_le_pluriel_du_francais_sans_traduction(self):
        self.assertIsInstance(traduction._traduction, gettext.NullTranslations)
        self.assertEqual(traduction.n_("{n} fichier", "{n} fichiers", 0), "{n} fichier")
        self.assertEqual(traduction.n_("{n} fichier", "{n} fichiers", 1), "{n} fichier")
        self.assertEqual(traduction.n_("{n} fichier", "{n} fichiers", 2), "{n} fichiers")


class LeCatalogueCompile(unittest.TestCase):
    """Compilé comme build-deb.sh le compile, chargé comme un programme le charge."""

    @classmethod
    def setUpClass(cls):
        cls.temporaire = tempfile.TemporaryDirectory()
        traductions.compiler(os.path.join(RACINE, "po"), cls.temporaire.name)
        cls.locale = os.path.join(cls.temporaire.name, "usr", "share", "locale")

    @classmethod
    def tearDownClass(cls):
        cls.temporaire.cleanup()

    def test_chaque_texte_se_lit_en_anglais(self):
        catalogue = traduction.charger(self.locale, {"LANG": "en_US.UTF-8"})
        self.assertIsInstance(catalogue, gettext.GNUTranslations)
        for e in traductions.lire_po(PO_EN)[2]:
            if e.pluriel is None:
                self.assertEqual(catalogue.gettext(e.msgid), e.msgstr[0])
            else:
                self.assertEqual(catalogue.ngettext(e.msgid, e.pluriel, 1), e.msgstr[0])
                self.assertEqual(catalogue.ngettext(e.msgid, e.pluriel, 2), e.msgstr[1])

    def test_une_langue_sans_traduction_recoit_l_anglais(self):
        catalogue = traduction.charger(self.locale, {"LANG": "de_DE.UTF-8"})
        self.assertEqual(catalogue.gettext("Suivant"), "Next")

    def test_le_francais_recoit_le_texte_du_code(self):
        for environ in ({"LANG": "fr_FR.UTF-8"}, {"LANG": "C.UTF-8"}, {}):
            catalogue = traduction.charger(self.locale, environ)
            self.assertEqual(catalogue.gettext("Suivant"), "Suivant")

    def test_un_dossier_sans_catalogue_ne_casse_rien(self):
        catalogue = traduction.charger(os.path.join(self.temporaire.name, "absent"),
                                       {"LANG": "en_US.UTF-8"})
        self.assertEqual(catalogue.gettext("Suivant"), "Suivant")

    def test_un_catalogue_abime_rend_le_texte_du_code(self):
        with tempfile.TemporaryDirectory() as temporaire:
            dossier = os.path.join(temporaire, "en", "LC_MESSAGES")
            os.makedirs(dossier)
            with open(os.path.join(dossier, "codebyr.mo"), "wb") as f:
                f.write(b"\xde\x12\x04\x95" + b"\xff" * 40)
            catalogue = traduction.charger(temporaire, {"LANG": "en_US.UTF-8"})
            self.assertEqual(catalogue.gettext("Suivant"), "Suivant")

    def test_l_extension_recoit_les_memes_traductions(self):
        import json
        chemin = os.path.join(self.temporaire.name, traductions.EXTENSION, "traductions", "en.json")
        donnees = json.loads(_lire(chemin))
        for e in traductions.lire_po(PO_EN)[2]:
            if e.pluriel is None:
                self.assertEqual(donnees["textes"][e.msgid], e.msgstr[0])
            else:
                self.assertEqual(donnees["pluriels"][e.msgid], e.msgstr)

    def test_la_compilation_est_reproductible(self):
        with tempfile.TemporaryDirectory() as autre:
            traductions.compiler(os.path.join(RACINE, "po"), autre)
            for relatif in ("usr/share/locale/en/LC_MESSAGES/codebyr.mo",
                            traductions.EXTENSION + "/traductions/en.json"):
                with open(os.path.join(autre, relatif), "rb") as a, \
                        open(os.path.join(self.temporaire.name, relatif), "rb") as b:
                    self.assertEqual(a.read(), b.read(), relatif)


class LeFichierAnglais(unittest.TestCase):

    def setUp(self):
        self.entrees = traductions.lire_po(PO_EN)[2]

    def test_il_suit_le_code(self):
        with tempfile.TemporaryDirectory() as temporaire:
            attendu = os.path.join(temporaire, "en.po")
            traductions.ecrire_po(attendu, "en", traductions.po_a_jour(RACINE, "en"))
            self.assertEqual(_lire(PO_EN), _lire(attendu),
                             "po/en.po ne suit plus le code : lancez "
                             "« python3 packaging/traductions.py extraire », puis traduisez")

    def test_chaque_texte_est_traduit(self):
        manquants = [e.msgid for e in self.entrees if not e.traduite]
        self.assertEqual(manquants, [], "textes sans traduction anglaise")

    def test_les_marques_sont_gardees(self):
        for e in self.entrees:
            for source, traduit in zip([e.msgid] + ([e.pluriel] if e.pluriel else []) * (len(e.msgstr) - 1),
                                       e.msgstr):
                self.assertEqual(sorted(re.findall(r"\{\w*\}", source)),
                                 sorted(re.findall(r"\{\w*\}", traduit)), e.msgid)
                self.assertEqual(re.findall(r"%[sd]", source), re.findall(r"%[sd]", traduit), e.msgid)

    def test_un_texte_n_est_pas_a_la_fois_simple_et_pluriel(self):
        # msgfmt et les plateformes de traduction refusent ce doublon.
        simples = {e.msgid for e in self.entrees if e.pluriel is None}
        doubles = [e.msgid for e in self.entrees if e.pluriel is not None and e.msgid in simples]
        self.assertEqual(doubles, [])

    def test_plusieurs_valeurs_ont_des_marques_nommees(self):
        # « %s … %s » fige l'ordre des valeurs : une traduction ne pourrait pas
        # le changer. Une seule valeur peut garder « %s ».
        for e in self.entrees:
            for texte in [e.msgid] + ([e.pluriel] if e.pluriel else []):
                self.assertLess(len(re.findall(r"%[sdr]", texte)), 2, texte)

    def test_aucune_traduction_ne_garde_le_francais_par_megarde(self):
        # Un nom propre (« Codebyr OS ») peut rester ; une phrase non.
        for e in self.entrees:
            if " " in e.msgid and len(e.msgid) > 25:
                self.assertNotEqual(e.msgid, e.msgstr[0], e.msgid)


class LExtraction(unittest.TestCase):

    def test_un_texte_complete_avant_traduction_est_refuse(self):
        for code in ('_(f"Ouvrir {nom}")', "_(texte)", '_("a" + b)', "n_('x')"):
            with self.assertRaises(traductions.TexteNonTraduisible, msg=code):
                traductions.textes_python(code, "essai.py")

    def test_les_appels_python_sont_lus(self):
        code = 'x = _("Un « texte »")\ny = n_("{n} pomme", "{n} pommes", n)\nz = autre._("non")'
        self.assertEqual(traductions.textes_python(code, "essai.py"),
                         [("Un « texte »", None), ("{n} pomme", "{n} pommes")])

    def test_les_appels_js_sont_lus(self):
        code = "a = _('L\\'Espace « {nom} »');\nb = n_('{n} fenêtre', '{n} fenêtres', n);\nc = this._x();"
        self.assertEqual(traductions.textes_js(code, "essai.js"),
                         [("L'Espace « {nom} »", None), ("{n} fenêtre", "{n} fenêtres")])

    def test_les_definitions_et_les_commentaires_js_sont_ignores(self):
        code = ("// Tout passe par _(), puis remplir().\n"
                "/* n_() aussi */\n"
                "function _(texte) { return texte; }\n"
                "function n_(a, b, n) { return a; }\n"
                "const u = 'https://exemple.org'; // _(x)\n"
                "const t = _('Fermer');\n")
        self.assertEqual(traductions.textes_js(code, "essai.js"), [("Fermer", None)])

    def test_un_appel_js_sans_texte_ecrit_est_refuse(self):
        for code in ("_(nom)", '_("guillemets doubles")', "_(`modèle ${x}`)"):
            with self.assertRaises(traductions.TexteNonTraduisible, msg=code):
                traductions.textes_js(code, "essai.js")

    def test_les_appels_shell_sont_lus(self):
        code = ("#!/bin/sh\n"
                "# traduire 'Un commentaire, pas un texte'\n"
                "traduire() {\n"
                "    python3 -B /usr/share/codebyr/traduction.py \"$@\" || printf '%s' \"$1\"\n"
                "}\n"
                "printf '%s\\n' \"$(traduire 'Fichier introuvable : {fichier}' fichier=\"$f\")\"\n"
                "printf '%s\\n' \"$(traduire 'N'\\''utilisez PAS ce fichier.')\"\n")
        self.assertEqual(traductions.textes_shell(code, "essai"),
                         [("Fichier introuvable : {fichier}", None),
                          ("N'utilisez PAS ce fichier.", None)])

    def test_un_appel_shell_sans_texte_ecrit_est_refuse(self):
        for code in ('x="$(traduire "$message")"\n', 'x="$(traduire "double")"\n'):
            with self.assertRaises(traductions.TexteNonTraduisible, msg=code):
                traductions.textes_shell(code, "essai")

    def test_les_scripts_shell_sont_relus(self):
        relus = traductions.sources(RACINE)
        self.assertIn("usr/bin/codebyr-verifier", relus)
        self.assertIn("usr/bin/codebyr-installer", relus)

    def test_un_fichier_po_relu_est_identique(self):
        with tempfile.TemporaryDirectory() as temporaire:
            copie = os.path.join(temporaire, "en.po")
            traductions.ecrire_po(copie, "en", traductions.lire_po(PO_EN)[2])
            self.assertEqual(_lire(copie), _lire(PO_EN))


# Une phrase : commence par une majuscule (ou « ), contient une espace et une
# minuscule. Les identifiants, chemins, classes CSS et SVG n'y ressemblent pas.
PHRASE = re.compile(r"^[«A-ZÀ-ÖØ-Ý][^\n]*\s[^\n]*[a-zà-ÿ]")


def phrases_en_dur(code, nom, laisses=frozenset()):
    """Les phrases écrites dans le code hors de _() et n_() (docstrings, journal
    et textes laissés exclus)."""
    arbre = ast.parse(code, nom)
    exclus = set()
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Call) and isinstance(noeud.func, (ast.Name, ast.Attribute))
                and getattr(noeud.func, "id", getattr(noeud.func, "attr", "")) in ("journal", "noter")):
            exclus.update(id(n) for n in ast.walk(noeud))
        if isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (noeud.body and isinstance(noeud.body[0], ast.Expr)
                    and isinstance(noeud.body[0].value, ast.Constant)):
                exclus.add(id(noeud.body[0].value))
        if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
                and noeud.func.id in ("_", "n_")):
            exclus.update(id(a) for a in noeud.args)
    return [(n.lineno, n.value) for n in ast.walk(arbre)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in exclus and n.value not in laisses and PHRASE.match(n.value)]


EXTENSION_JS = os.path.join(INCLUDES, traductions.EXTENSION, "extension.js")
# Pour le développeur, pas pour l'utilisateur : les notifications de
# diagnostic (DIAG = false) et le journal (« Codebyr: … », par logError).
DIAGNOSTIC_JS = {"Codebyr — fenêtre détectée", "Codebyr — classe mise à jour",
                 "Codebyr — liseré posé"}


def phrases_en_dur_js(code):
    """Les phrases de l'extension écrites hors de _() et n_()."""
    code = traductions.sans_commentaires_js(code)
    code = traductions._APPEL_JS.sub(lambda m: " " * len(m.group(0)), code)
    trouvees = []
    for m in re.finditer(r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"|`((?:[^`\\]|\\.)*)`", code):
        texte = next(g for g in m.groups() if g is not None)
        if (PHRASE.match(texte) and texte not in DIAGNOSTIC_JS
                and not texte.startswith("Codebyr: ")):
            trouvees.append(texte)
    return trouvees


BANC_LANGUE_JS = r"""
// Les deux derniers arguments : « node -e » ne compte pas le script lui-même.
const [casJson, bloc] = process.argv.slice(-2);
const cas = JSON.parse(casJson);
const resultats = [];
for (const [langues, fichiers] of cas) {
    const GLib = {
        path_get_dirname: p => p.replace(/\/[^/]*$/, ''),
        filename_from_uri: u => [u.replace('file://', ''), null],
        get_language_names: () => langues,
        file_get_contents: chemin => {
            if (!(chemin in fichiers))
                throw new Error('absent : ' + chemin);
            return [true, new TextEncoder().encode(fichiers[chemin])];
        },
    };
    const fabrique = new Function('GLib', bloc +
        '\nreturn [_("Suivant"), n_("{n} pomme", "{n} pommes", 0), n_("{n} pomme", "{n} pommes", 2),' +
        ' remplir("{a} et {b}", {a: "$&", b: 2})];');
    resultats.push(fabrique(GLib));
}
console.log(JSON.stringify(resultats));
"""


@unittest.skipUnless(shutil.which("node"), "Node.js requis")
class LaLangueDeLExtension(unittest.TestCase):
    """Le choix de langue de l'extension, exécuté hors de GNOME (faux GLib)."""

    def _resultats(self, cas):
        code = _lire(EXTENSION_JS)
        debut = code.index("// ── Langue")
        fin = code.index("\n}\n", code.index("function remplir(")) + 3
        bloc = code[debut:fin].replace(
            "import.meta.url", "'file:///usr/share/gnome-shell/extensions/codebyr@codebyr.io/extension.js'")
        sortie = subprocess.run(["node", "-e", BANC_LANGUE_JS, "--", json.dumps(cas), bloc],
                                capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(sortie.returncode, 0, sortie.stderr)
        return json.loads(sortie.stdout)

    def test_la_meme_regle_que_les_programmes(self):
        dossier = "/usr/share/gnome-shell/extensions/codebyr@codebyr.io/traductions/"
        anglais = json.dumps({"textes": {"Suivant": "Next"},
                              "pluriels": {"{n} pomme": ["{n} apple", "{n} apples"]}})
        allemand = json.dumps({"textes": {"Suivant": "Weiter"}, "pluriels": {}})
        en = {dossier + "en.json": anglais}
        de_en = {dossier + "en.json": anglais, dossier + "de.json": allemand}
        resultats = self._resultats([
            [["fr_FR", "fr", "C"], en],                 # français
            [["C"], en],                                # sans préférence
            [["en_US", "en", "C"], en],                 # anglais
            [["de_DE", "de", "C"], en],                 # non traduit → anglais
            [["de_DE", "de", "C"], de_en],              # traduit → sa traduction
            [["de", "fr", "C"], en],                    # préférence suivante : français
            [["en_US", "en", "C"], {}],                 # aucun fichier → texte du code
        ])
        self.assertEqual([r[0] for r in resultats],
                         ["Suivant", "Suivant", "Next", "Next", "Weiter", "Suivant", "Suivant"])
        # Pluriels : règle du français sans traduction (« 0 pomme »), de
        # l'anglais avec (« 0 apples »).
        self.assertEqual(resultats[0][1:3], ["{n} pomme", "{n} pommes"])
        self.assertEqual(resultats[2][1:3], ["{n} apples", "{n} apples"])
        # remplir() insère tel quel : « $& » n'est pas interprété.
        self.assertEqual(resultats[0][3], "$& et 2")


NOMS_JS = ("_", "n_", "remplir")


def masquages_js(code):
    """Les redéclarations de _, n_ ou remplir dans l'extension.

    En JavaScript comme en Python, un « const remplir » local masque la
    fonction dans TOUT son bloc, y compris avant lui : « Autres
    applications… » ne s'ouvrait plus (ReferenceError), vu sur la VM le
    01/10/2026."""
    code = traductions.sans_commentaires_js(code)
    trouves = [nom for nom in re.findall(r"\b(?:const|let|var)\s+(\w+)", code) if nom in NOMS_JS]
    parametres = (re.findall(r"\(([^()]*)\)\s*=>", code)
                  + re.findall(r"\b(\w+)\s*=>", code)
                  + re.findall(r"\bfunction\s*\w*\s*\(([^()]*)\)", code)
                  + re.findall(r"\bcatch\s*\((\w+)\)", code)
                  + re.findall(r"^\s+(?!if\b|for\b|while\b|switch\b)\w+\s*\(([^()]*)\)\s*\{",
                               code, re.MULTILINE))
    for liste in parametres:
        trouves += [p for p in re.split(r"[\s,={}\[\]]+", liste) if p in NOMS_JS]
    for nom in NOMS_JS:
        if len(re.findall(r"\bfunction\s+%s\s*\(" % re.escape(nom), code)) != 1:
            trouves.append("function " + nom)
    return trouves


class LesFichiersTraduits(unittest.TestCase):

    def test_l_extension_ne_redeclare_pas_ses_fonctions_de_traduction(self):
        self.assertEqual(masquages_js(_lire(EXTENSION_JS)), [])

    def test_le_garde_fou_js_voit_le_piege(self):
        base = ("function _(t) { return t; }\nfunction n_(a, b, n) { return a; }\n"
                "function remplir(t, v) { return t; }\n")
        self.assertEqual(masquages_js(base), [])
        self.assertEqual(masquages_js(base + "class A {\n    f() {\n        const remplir = x => x;\n    }\n}\n"),
                         ["remplir"])
        self.assertEqual(masquages_js(base + "liste.forEach(_ => 1);\n"), ["_"])
        self.assertEqual(masquages_js(base + "const f = (a, n_) => a;\n"), ["n_"])

    def test_l_extension_ne_garde_aucune_phrase_en_dur(self):
        self.assertEqual(phrases_en_dur_js(_lire(EXTENSION_JS)), [])

    def test_le_garde_fou_js_voit_une_phrase_oubliee(self):
        self.assertEqual(phrases_en_dur_js("x = {label: 'Fermer la fenêtre'};"), ["Fermer la fenêtre"])
        self.assertEqual(phrases_en_dur_js("x = {label: _('Fermer la fenêtre')};"), [])
        self.assertEqual(phrases_en_dur_js("// 'Une phrase en commentaire'\nx = 1;"), [])

    def test_aucune_phrase_affichee_n_echappe_a_la_traduction(self):
        for relatif in FICHIERS_TRADUITS:
            code = _lire(os.path.join(INCLUDES, relatif))
            self.assertEqual(phrases_en_dur(code, relatif, LAISSES), [], relatif)

    def test_ils_chargent_la_traduction(self):
        # _ ou n_ selon ce que le fichier emploie : ruff refuse un import inutile.
        for relatif in FICHIERS_TRADUITS:
            self.assertRegex(_lire(os.path.join(INCLUDES, relatif)),
                             r"(?m)^\s*from traduction import (_|n_)\b", relatif)

    def test_le_garde_fou_voit_une_phrase_oubliee(self):
        self.assertEqual(phrases_en_dur('b = Gtk.Button(label="Ouvrir le dossier")', "x"),
                         [(1, "Ouvrir le dossier")])
        self.assertEqual(phrases_en_dur('b = Gtk.Button(label=_("Ouvrir le dossier"))', "x"), [])


class LesLanceurs(unittest.TestCase):
    """GNOME montre « Name[<langue>] » s'il existe, sinon « Name » : l'inverse
    de gettext. Pour qu'une langue non traduite reçoive l'anglais, la valeur
    par défaut est l'anglaise, et le français est une traduction parmi d'autres."""

    def _lanceurs(self):
        dossiers = [("usr", "share", "applications"), ("etc", "xdg", "autostart")]
        for morceaux in dossiers:
            dossier = os.path.join(INCLUDES, *morceaux)
            for nom in sorted(os.listdir(dossier)):
                if nom.endswith(".desktop") and "codebyr" in nom:
                    yield nom, _lire(os.path.join(dossier, nom))

    def test_anglais_par_defaut_francais_en_traduction(self):
        lanceurs = list(self._lanceurs())
        self.assertGreaterEqual(len(lanceurs), 7)
        for nom, texte in lanceurs:
            champs = dict(l.split("=", 1) for l in texte.splitlines() if "=" in l and not l.startswith("#"))
            for cle in ("Name", "Comment", "Keywords"):
                if cle not in champs:
                    self.assertNotIn(cle + "[fr]", champs, nom)
                    continue
                self.assertIn(cle + "[fr]", champs, "%s : %s[fr] manque" % (nom, cle))
                self.assertNotEqual(champs[cle], champs[cle + "[fr]"], "%s : %s non traduit" % (nom, cle))
                self.assertNotIn(cle + "[en]", champs, "%s : l'anglais est la valeur par défaut" % nom)
            self.assertIn("Name", champs, nom)


def fonctions_qui_masquent_la_traduction(code, nom):
    """[(ligne, fonction)] des fonctions où « _ » (ou « n_ ») est une variable
    locale ET où _() est appelée. En Python, une affectation fait du nom une
    variable locale de TOUTE la fonction : « env, _ = … » plus bas, et chaque
    _("…") de la fonction échoue, même ceux d'avant (UnboundLocalError)."""
    trouvees = []
    for f in ast.walk(ast.parse(code, nom)):
        if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        a = f.args
        locaux = {x.arg for x in a.args + a.kwonlyargs + a.posonlyargs}
        locaux |= {x.arg for x in (a.vararg, a.kwarg) if x}
        appelle = False
        for bloc in (f.body if isinstance(f.body, list) else [f.body]):
            for n in ast.walk(bloc):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                    locaux.add(n.id)
                elif isinstance(n, ast.ExceptHandler) and n.name:
                    locaux.add(n.name)
                elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                      and n.func.id in ("_", "n_")):
                    appelle = True
        if appelle and locaux & {"_", "n_"}:
            trouvees.append((f.lineno, getattr(f, "name", "lambda")))
    return trouvees


class AucuneVariableNeMasqueLaTraduction(unittest.TestCase):

    def test_dans_aucun_fichier(self):
        for relatif in traductions.sources(RACINE):
            chemin = os.path.join(INCLUDES, relatif)
            if not relatif.endswith(".py") and traductions._langage(chemin) != "python":
                continue
            code = _lire(chemin)
            self.assertEqual(fonctions_qui_masquent_la_traduction(code, relatif), [], relatif)

    def test_le_garde_fou_voit_le_piege(self):
        code = "def f():\n    print(_('a'))\n    env, _ = g()\n"
        self.assertEqual(fonctions_qui_masquent_la_traduction(code, "x"), [(1, "f")])
        self.assertEqual(fonctions_qui_masquent_la_traduction(
            "def f():\n    env, _x = g()\n    print(_('a'))\n", "x"), [])


class LaPageDeBlocage(unittest.TestCase):
    """Le filtre réseau ne lit pas les traductions (AppArmor) : codebyr-space
    les lui donne. Son français et celui de page_blocage.py ne font qu'un."""

    @classmethod
    def setUpClass(cls):
        from outils import charger
        import page_blocage
        cls.filtre = charger("codebyr-net-proxy")
        cls.page_blocage = page_blocage

    def test_le_francais_est_le_meme_des_deux_cotes(self):
        self.assertEqual(self.page_blocage.textes(), self.filtre.TEXTES)

    def test_des_textes_traduits_sont_acceptes(self):
        anglais = {"langue": "en", "banque_titre": "This is not your bank's site",
                   "banque_detail": "<code>%s</code> is not on your list."}
        recus = self.filtre.textes_recus(
            {self.page_blocage.VARIABLE: json.dumps(anglais)})
        self.assertEqual(recus["langue"], "en")
        self.assertEqual(recus["banque_titre"], anglais["banque_titre"])
        self.assertEqual(recus["vide_titre"], self.filtre.TEXTES["vide_titre"])

    def test_un_texte_douteux_garde_le_francais(self):
        f = self.filtre
        for recu in ("pas du json", "[1, 2]",
                     json.dumps({"banque_detail": "sans marque"}),
                     json.dumps({"banque_detail": "%s et %s"}),
                     json.dumps({"banque_detail": "100 % %s"}),
                     json.dumps({"banque_titre": 42}),
                     json.dumps({"langue": "en\"><script>"})):
            recus = f.textes_recus({self.page_blocage.VARIABLE: recu})
            self.assertEqual(recus, f.TEXTES, recu)

    def test_la_page_echappe_toujours_le_site(self):
        f = self.filtre
        envoye = []

        class Client:
            def sendall(self, donnees):
                envoye.append(donnees)

        ancien = f.TEXTES_PAGE
        try:
            f.TEXTES_PAGE = f.textes_recus({self.page_blocage.VARIABLE: json.dumps(
                {"langue": "en", "banque_detail": "<code>%s</code> is not on your list."})})
            f.bloque(Client(), "<img src=x>", patterns=["banque.fr"])
        finally:
            f.TEXTES_PAGE = ancien
        page = envoye[0].decode("utf-8")
        self.assertIn('<html lang="en">', page)
        self.assertIn("<code>&lt;img src=x&gt;</code> is not on your list.", page)

    def test_codebyr_space_les_donne_au_lancement(self):
        code = _lire(os.path.join(INCLUDES, "usr", "bin", "codebyr-space"))
        self.assertIn("env=page_blocage.environnement(os.environ))", code)


class _CatalogueAnglais(gettext.NullTranslations):
    TEXTES = {"Banque": "Bank", "Calculatrice": "Calculator", "Fichiers": "Files"}

    def gettext(self, message):
        return self.TEXTES.get(message, message)


class LesNomsLivres(unittest.TestCase):
    """Les noms du registre livré (« Banque », « Calculatrice ») suivent la
    langue ; ceux de l'utilisateur, jamais. Et une liste lue traduite puis
    réécrite garde ses noms d'origine dans le fichier de l'utilisateur."""

    SYSTEME = {
        "espaces": [{"id": "banque", "nom": "Banque", "couleur": "#2FA36B"},
                    {"id": "travail", "nom": "Travail", "couleur": "#8F6CF0"}],
        "apps": [{"nom": "Calculatrice", "cmd": "gnome-calculator"},
                 {"nom": "Fichiers", "cmd": "nautilus"}],
    }

    def setUp(self):
        from unittest import mock
        import registre
        self.registre = registre
        self.dossier = tempfile.TemporaryDirectory()
        self.systeme = os.path.join(self.dossier.name, "systeme.json")
        self.utilisateur = os.path.join(self.dossier.name, "utilisateur.json")
        with open(self.systeme, "w", encoding="utf-8") as f:
            json.dump(self.SYSTEME, f, ensure_ascii=False)
        for cible, valeur in ((registre, ("SYSTEME", self.systeme)),
                              (registre, ("UTILISATEUR", self.utilisateur)),
                              (traduction, ("_traduction", _CatalogueAnglais()))):
            correctif = mock.patch.object(cible, valeur[0], valeur[1])
            correctif.start()
            self.addCleanup(correctif.stop)
        self.addCleanup(self.dossier.cleanup)

    def _ecrire_utilisateur(self, data):
        with open(self.utilisateur, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def test_les_noms_livres_sont_traduits(self):
        vue = self.registre.charger()
        self.assertEqual([e["nom"] for e in vue["espaces"]], ["Bank", "Travail"])
        self.assertEqual([a["nom"] for a in vue["apps"]], ["Calculator", "Files"])

    def test_les_noms_de_l_utilisateur_ne_le_sont_jamais(self):
        self._ecrire_utilisateur({"espaces": [
            {"id": "travail", "nom": "Banque"},                       # renommé par lui
            {"id": "perso2", "nom": "Banque", "couleur": "#4E8FEF"},  # créé par lui
        ], "apps": [{"nom": "Calculatrice", "cmd": "mon-script"}]})
        vue = self.registre.charger()
        noms = {e["id"]: e["nom"] for e in vue["espaces"]}
        self.assertEqual(noms, {"banque": "Bank", "travail": "Banque", "perso2": "Banque"})
        # Même nom qu'une application livrée, mais pas la même commande.
        self.assertEqual(vue["apps"][0]["nom"], "Calculatrice")

    def test_une_liste_relue_et_reecrite_garde_ses_noms_d_origine(self):
        # Configuration Codebyr : la liste commune lue (traduite), un ajout,
        # puis réécrite.
        apps = self.registre.charger()["apps"]
        apps.append({"nom": "Kalk", "cmd": "kalk"})
        self.registre.ecrire_apps_communes(apps)
        with open(self.utilisateur, encoding="utf-8") as f:
            ecrit = json.load(f)
        self.assertEqual([a["nom"] for a in ecrit["apps"]], ["Calculatrice", "Fichiers", "Kalk"])
        self.assertNotIn("_nom_source", json.dumps(ecrit))
        # Et relue : traduite de nouveau.
        self.assertEqual([a["nom"] for a in self.registre.charger()["apps"]],
                         ["Calculator", "Files", "Kalk"])

    def test_un_reglage_ne_fige_pas_le_nom_traduit(self):
        banque = self.registre.espaces()["banque"]
        self.registre.modifier_espace("banque", {"audio": False, "apps": [
            dict(a) for a in self.registre.charger()["apps"]]})
        with open(self.utilisateur, encoding="utf-8") as f:
            ecrit = json.load(f)
        entree = ecrit["espaces"][0]
        self.assertNotIn("nom", entree)
        self.assertEqual([a["nom"] for a in entree["apps"]], ["Calculatrice", "Fichiers"])
        self.assertEqual(banque["nom"], "Bank")

    def test_en_francais_rien_ne_change(self):
        from unittest import mock
        with mock.patch.object(traduction, "_traduction", gettext.NullTranslations()):
            vue = self.registre.charger()
        self.assertEqual([e["nom"] for e in vue["espaces"]], ["Banque", "Travail"])
        self.assertNotIn("_nom_source", json.dumps(vue))

    def test_l_extension_suit_la_meme_regle(self):
        code = _lire(EXTENSION_JS)
        self.assertIn("if (espace.nom === base.nom)\n            espace.nom = nomLivre(base.nom);", code)
        self.assertIn("apps: avecNomsTraduits(usr.apps.length ? usr.apps : sys.apps, livrees)", code)

    def test_les_noms_du_registre_livre_sont_au_catalogue(self):
        msgids = {e.msgid for e in traductions.lire_po(PO_EN)[2]}
        noms = traductions.noms_du_registre(RACINE)
        self.assertIn("Calculatrice", noms)
        self.assertEqual([n for n in noms if n not in msgids], [])


DIAPORAMA = os.path.join(INCLUDES, traductions.DIAPORAMA)


class LeDiaporamaDeLInstalleur(unittest.TestCase):
    """Calamares ne lit pas nos catalogues : le diaporama porte ses traductions
    en lui-même, écrites par « extraire »."""

    def test_ses_traductions_sont_a_jour(self):
        self.assertEqual(_lire(DIAPORAMA), traductions.diaporama_a_jour(RACINE),
                         "lancez « python3 packaging/traductions.py extraire »")

    def test_plus_de_bac_a_sable_materiel(self):
        # Les Espaces reposent sur le noyau, pas sur du matériel : le
        # diaporama ne le prétend plus.
        self.assertNotIn("Bac à sable matériel", _lire(DIAPORAMA))

    @unittest.skipUnless(shutil.which("node"), "Node.js requis")
    def test_la_langue_de_la_session(self):
        code = _lire(DIAPORAMA)
        table = re.search(r"readonly property var traductions: (\(.*\))\n", code).group(1)
        debut = code.index("    function traduire(texte) {")
        fin = code.index("\n    }\n", debut) + 6
        banc = ("const resultats = [];\n"
                "for (const nom of ['fr_FR', 'en_US', 'de_DE', 'C']) {\n"
                "  const Qt = {locale: () => ({name: nom})};\n"
                "  const traductions = " + table + ";\n"
                "  " + code[debut:fin] + "\n"
                "  resultats.push(traduire('Bienvenue dans Codebyr OS\\n\\nLa sécurité par "
                "compartimentation, simple pour tout le monde.').split('\\n')[0]);\n"
                "}\nconsole.log(JSON.stringify(resultats));\n")
        sortie = subprocess.run(["node", "-e", banc], capture_output=True, text=True,
                                encoding="utf-8", timeout=30)
        self.assertEqual(sortie.returncode, 0, sortie.stderr)
        self.assertEqual(json.loads(sortie.stdout),
                         ["Bienvenue dans Codebyr OS", "Welcome to Codebyr OS",
                          "Welcome to Codebyr OS", "Bienvenue dans Codebyr OS"])


class LeMenuDeDemarrageDuLive(unittest.TestCase):
    """Une session live en anglais, au menu de démarrage de l'ISO : le premier
    écran qu'un testeur étranger voit."""

    OPTIONS = "@APPEND_LIVE@ locales=en_US.UTF-8 keyboard-layouts=us"

    def test_grub_uefi(self):
        grub = _lire(os.path.join(RACINE, "live-build", "config", "bootloaders", "grub-pc", "grub.cfg"))
        self.assertIn("linux\t@KERNEL_LIVE@ " + self.OPTIONS, grub)

    def test_syslinux_bios(self):
        live = _lire(os.path.join(RACINE, "live-build", "config", "bootloaders",
                                  "syslinux_common", "live.cfg.in"))
        self.assertIn("append " + self.OPTIONS, live)

    def test_les_options_suivent_celles_de_l_image(self):
        # Ajoutées APRÈS @APPEND_LIVE@ : live-config garde la dernière valeur,
        # et les protections du noyau restent celles de auto/config, jamais
        # recopiées à la main.
        config = _lire(os.path.join(RACINE, "live-build", "auto", "config"))
        self.assertIn("locales=fr_FR.UTF-8 keyboard-layouts=fr", config)


class LesNomsDesApplications(unittest.TestCase):
    """La liste des applications installées (Configuration Codebyr) suit la
    langue de la session ; elle lisait toujours « Name[fr] »."""

    def test_le_nom_suit_la_langue_de_la_session(self):
        import applications
        entree = {"Name": "Files", "Name[fr]": "Fichiers", "Name[de]": "Dateien",
                  "Name[pt_BR]": "Arquivos"}
        for langues, attendu in ((["de_DE"], "Dateien"), (["pt_BR"], "Arquivos"),
                                 (["en_US"], "Files"), (["ja_JP"], "Files"),
                                 (["fr_FR"], "Fichiers"), (["C"], "Fichiers"), ([], "Fichiers"),
                                 (["ja_JP", "de_DE"], "Dateien")):
            self.assertEqual(applications.nom_localise(entree, langues), attendu, langues)
        self.assertEqual(applications.nom_localise({"Name": "Kalk"}, ["fr_FR"]), "Kalk")


class LaConstruction(unittest.TestCase):

    def test_le_paquet_compile_les_langues(self):
        construction = _lire(os.path.join(RACINE, "packaging", "build-deb.sh"))
        self.assertIn('python3 -B "$REPO/packaging/traductions.py" compiler "$REPO/po" "$STAGE"',
                      construction)

    def test_l_iso_emporte_les_traductions(self):
        # build.sh n'extrait du commit que les dossiers qu'il nomme.
        construction = _lire(os.path.join(RACINE, "live-build", "scripts", "build.sh"))
        self.assertIn("VERSION live-build branding packaging po | tar -x", construction)

    def test_une_traduction_non_commitee_ne_part_pas(self):
        publication = _lire(os.path.join(RACINE, "packaging", "publish-apt.sh"))
        self.assertIn("status --porcelain -- VERSION packaging live-build po", publication)


if __name__ == "__main__":
    unittest.main()
