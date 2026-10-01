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
import os
import re
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
    "usr/bin/codebyr-bienvenue",
]


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

    def test_un_appel_js_sans_texte_ecrit_est_refuse(self):
        for code in ("_(nom)", '_("guillemets doubles")', "_(`modèle ${x}`)"):
            with self.assertRaises(traductions.TexteNonTraduisible, msg=code):
                traductions.textes_js(code, "essai.js")

    def test_un_fichier_po_relu_est_identique(self):
        with tempfile.TemporaryDirectory() as temporaire:
            copie = os.path.join(temporaire, "en.po")
            traductions.ecrire_po(copie, "en", traductions.lire_po(PO_EN)[2])
            self.assertEqual(_lire(copie), _lire(PO_EN))


# Une phrase : commence par une majuscule (ou « ), contient une espace et une
# minuscule. Les identifiants, chemins, classes CSS et SVG n'y ressemblent pas.
PHRASE = re.compile(r"^[«A-ZÀ-ÖØ-Ý][^\n]*\s[^\n]*[a-zà-ÿ]")


def phrases_en_dur(code, nom):
    """Les phrases écrites dans le code hors de _() et n_() (docstrings exclues)."""
    arbre = ast.parse(code, nom)
    exclus = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (noeud.body and isinstance(noeud.body[0], ast.Expr)
                    and isinstance(noeud.body[0].value, ast.Constant)):
                exclus.add(id(noeud.body[0].value))
        if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
                and noeud.func.id in ("_", "n_")):
            exclus.update(id(a) for a in noeud.args)
    return [(n.lineno, n.value) for n in ast.walk(arbre)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in exclus and PHRASE.match(n.value)]


class LesFichiersTraduits(unittest.TestCase):

    def test_aucune_phrase_affichee_n_echappe_a_la_traduction(self):
        for relatif in FICHIERS_TRADUITS:
            code = _lire(os.path.join(INCLUDES, relatif))
            self.assertEqual(phrases_en_dur(code, relatif), [], relatif)

    def test_ils_chargent_la_traduction(self):
        for relatif in FICHIERS_TRADUITS:
            self.assertIn("from traduction import _", _lire(os.path.join(INCLUDES, relatif)), relatif)

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
