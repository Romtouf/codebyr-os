# -*- coding: utf-8 -*-
"""Le dock (1.21.0) : toujours visible, une pastille par fenêtre à la couleur de son Espace.

Choisi sur maquette le 02/10/2026 (variante A). Le dock est Dash to Dock,
empaqueté par Debian ; les pastilles sont posées par l'extension Codebyr sur
les icônes d'application de GNOME, dont celles du dock héritent.

Les réglages du dock ont été compilés en mode strict contre le vrai schéma de
Dash to Dock (version 100, celle de Debian 13) et ceux de GNOME 48, le
02/10/2026 : toutes les clés et valeurs sont valides.
"""
import json
import os
import re
import shutil
import subprocess
import unittest

from outils import BIN, RACINE

LIVRE = os.path.join(RACINE, "live-build", "config", "includes.chroot_after_packages")
OVERRIDE = os.path.join(LIVRE, "usr", "share", "glib-2.0", "schemas", "90_codebyr.gschema.override")
EXTENSION = os.path.join(LIVRE, "usr", "share", "gnome-shell", "extensions", "codebyr@codebyr.io",
                         "extension.js")
UUID_DOCK = "dash-to-dock@micxgx.gmail.com"


def _lire(chemin):
    with open(chemin, encoding="utf-8") as f:
        return f.read()


def _section(texte, nom):
    debut = texte.index("[%s]" % nom)
    suite = re.search(r"^\[", texte[debut + 1:], re.M)
    bloc = texte[debut:debut + 1 + suite.start()] if suite else texte[debut:]
    return dict(l.split("=", 1) for l in bloc.splitlines()[1:]
                if l.strip() and not l.startswith("#"))


class LeDock(unittest.TestCase):

    def test_active_par_defaut_avec_codebyr(self):
        shell = _section(_lire(OVERRIDE), "org.gnome.shell")
        self.assertEqual(shell["enabled-extensions"],
                         "['codebyr@codebyr.io', '%s']" % UUID_DOCK)

    def test_toujours_visible_en_bas(self):
        dock = _section(_lire(OVERRIDE), "org.gnome.shell.extensions.dash-to-dock")
        for cle, valeur in {"dock-position": "'BOTTOM'", "dock-fixed": "true",
                            "intellihide": "false", "autohide": "false"}.items():
            self.assertEqual(dock[cle], valeur, cle)

    def test_il_garde_l_indicateur_que_codebyr_remplace(self):
        # Ses propres points (« DOTS »…) se dessineraient PAR-DESSUS les
        # pastilles des Espaces, d'une seule couleur.
        dock = _section(_lire(OVERRIDE), "org.gnome.shell.extensions.dash-to-dock")
        self.assertEqual(dock["running-indicator-style"], "'DEFAULT'")

    def test_livre_par_l_image(self):
        # Le paquet ne l'exige pas encore : voir test_packaging,
        # test_aucune_dependance_debian_que_la_mise_a_jour_ne_sache_installer.
        liste = _lire(os.path.join(RACINE, "live-build", "config", "package-lists",
                                   "codebyr.list.chroot"))
        self.assertIn("\ngnome-shell-extension-dashtodock\n", liste)


class FirefoxSousSonIcone(unittest.TestCase):
    """Les fenêtres de Firefox d'un Espace se rangent sous l'icône Firefox :
    plus d'identifiant par Espace (« codebyr-banque »), que GNOME ne savait
    rattacher à aucune application."""

    def test_identifiant_ordinaire(self):
        # Les deux fixent l'identifiant de la fenêtre sous Wayland : l'un par
        # l'environnement, l'autre par la ligne de commande (vu sur la VM le
        # 02/10/2026 : retirer le premier ne suffisait pas).
        code = "\n".join(l for l in _lire(os.path.join(BIN, "codebyr-space")).splitlines()
                         if not l.lstrip().startswith("#"))
        self.assertNotIn("MOZ_APP_REMOTINGNAME", code)
        self.assertNotIn('"--class"', code)
        self.assertNotIn('"--name"', code)

    def test_la_commande_de_firefox_reste_telle_quelle(self):
        import outils
        space = outils.charger("codebyr-space")
        commande = ["/usr/bin/firefox-esr", "https://exemple.invalid"]
        self.assertEqual(space.build_command({"id": "banque"}, "/tmp/h", commande), commande)

    def test_l_espace_ne_se_reconnait_pas_a_l_identifiant(self):
        # Ce qui rendait l'identifiant nécessaire : il ne l'est plus.
        self.assertNotIn("espacePourFenetre", _lire(EXTENSION))


@unittest.skipUnless(shutil.which("node"), "node absent : l'extension ne peut pas être exécutée")
class LesPastilles(unittest.TestCase):
    """pastillesDe et stylePastille, les fonctions mêmes de l'extension."""

    def _executer(self, programme):
        source = _lire(EXTENSION)
        fonctions = "\n".join(
            re.search(r"(?:const %s = [^\n]*\n)" % n if n.isupper() else
                      r"function " + n + r"\([\s\S]*?\n\}", source).group()
            for n in ("COULEUR_DEFAUT", "FORME_COULEUR", "couleurSure", "PASTILLES_MAX",
                      "PASTILLE_NEUTRE", "pastillesDe", "stylePastille"))
        r = subprocess.run(["node", "-e", fonctions + "\n" + programme],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_une_pastille_par_fenetre_a_la_couleur_de_son_espace(self):
        r = self._executer("""
const banque = {couleur: '#2FA36B'}, navigation = {couleur: '#BF7600'};
const f1 = {}, f2 = {}, f3 = {};
const espaces = new Map([[f1, banque], [f2, navigation]]);
console.log(JSON.stringify(pastillesDe([f1, f2, f3], w => espaces.get(w) || null, f2)));
""")
        self.assertEqual(r, [{"couleur": "#2FA36B", "active": False},
                             {"couleur": "#BF7600", "active": True},
                             {"couleur": "#ffffff", "active": False}])

    def test_cinq_au_plus(self):
        r = self._executer("""
const f = [1, 2, 3, 4, 5, 6, 7].map(() => ({}));
console.log(JSON.stringify(pastillesDe(f, () => null, null).length));
""")
        self.assertEqual(r, 5)

    def test_une_couleur_douteuse_ne_passe_pas_dans_le_style(self):
        # La couleur vient du registre, que l'utilisateur écrit : elle entre
        # dans une feuille de style. Seule une couleur #rrggbb passe.
        r = self._executer("""
const piege = {couleur: 'red; background-image: url(file:///etc/shadow)'};
const p = pastillesDe([{}], () => piege, null);
console.log(JSON.stringify([p[0].couleur, stylePastille(p[0])]));
""")
        self.assertEqual(r[0], "#888888")
        self.assertNotIn("url(", r[1])

    def test_meme_taille_la_fenetre_active_cerclee_de_blanc(self):
        # Une pastille plus grande pour la fenêtre active passait pour une
        # erreur (vu sur la VM le 02/10/2026) : même taille, même bordure.
        r = self._executer("""
console.log(JSON.stringify([stylePastille({couleur: '#4E8FEF', active: false}),
                            stylePastille({couleur: '#4E8FEF', active: true})]));
""")
        taille = lambda s: re.findall(r"(?:width|height|border-radius): \d+px|border: \d+px", s)
        self.assertEqual(taille(r[0]), taille(r[1]))
        self.assertIn("border: 1px solid #4E8FEF", r[0])
        self.assertIn("border: 1px solid #ffffff", r[1])


class LeBranchement(unittest.TestCase):
    """Les pastilles se posent sur la classe de GNOME, pas dans le dock."""

    def setUp(self):
        self.source = _lire(EXTENSION)
        self.classe = self.source.split("class Pastilles {", 1)[1].split("\n}\n", 1)[0]

    def test_sur_l_icone_d_application_de_gnome(self):
        self.assertIn("import * as AppDisplay from 'resource:///org/gnome/shell/ui/appDisplay.js';",
                      self.source)
        self.assertIn("overrideMethod(AppDisplay.AppIcon.prototype, '_init'", self.classe)
        self.assertIn("instanceof AppDisplay.AppIcon", self.classe)

    def test_rendu_tel_quel_a_la_desactivation(self):
        detruire = self.classe.split("detruire() {", 1)[1]
        self.assertIn("this._injections.clear();", detruire)
        self.assertIn("icone._dot.opacity = 255;", detruire)
        self.assertIn("this._pastilles?.detruire();", self.source)

    def test_l_espace_d_une_fenetre_vient_du_liseré(self):
        # Établi par filiation des processus, jamais par la classe de fenêtre.
        self.assertIn("this._coloriage.espaceDe(w)", self.classe)
        espace_de = self.source.split("    espaceDe(win) {", 1)[1].split("\n    }\n", 1)[0]
        self.assertIn("rec && rec.lisere ? rec.esp : null", espace_de)


class LAltTab(unittest.TestCase):
    """Les mêmes pastilles dans Alt+Tab, et le nom de l'Espace sous chaque
    vignette de fenêtre.

    Points d'accroche relevés dans js/ui/altTab.js de GNOME Shell 48.7, celui
    de Debian 13 (identique à la 48.4), le 02/10/2026."""

    ACCROCHES = ("AltTab.AppSwitcherPopup.prototype, '_init'",
                 "AltTab.AppSwitcherPopup.prototype, '_createThumbnails'",
                 "AltTab.WindowIcon.prototype, '_init'")

    def setUp(self):
        self.source = _lire(EXTENSION)
        self.classe = self.source.split("class Pastilles {", 1)[1].split("\n}\n", 1)[0]

    def test_accroches(self):
        self.assertIn("import * as AltTab from 'resource:///org/gnome/shell/ui/altTab.js';",
                      self.source)
        for accroche in self.ACCROCHES:
            self.assertIn("overrideMethod(" + accroche, self.classe)

    def test_une_erreur_ne_prive_jamais_d_alt_tab(self):
        # GNOME fait d'abord son travail ; le nôtre vient après, sous try.
        for accroche in self.ACCROCHES:
            corps = self.classe.split(accroche, 1)[1].split("});", 1)[0]
            self.assertLess(corps.index("original.call(this, ...args);"), corps.index("try {"))
            self.assertIn("logError(e,", corps)

    def test_les_couleurs_et_l_espace_comme_dans_le_dock(self):
        for methode in ("_decorerAltTab(", "_decorerVignettes("):
            corps = self.classe.split("    " + methode, 1)[1].split("\n    }\n", 1)[0]
            self.assertIn("pastillesDe(", corps)
        self.assertIn("this._coloriage.espaceDe(win)", self.classe)

    def test_le_nom_de_l_espace_passe_en_texte(self):
        # Le nom vient du registre, que l'utilisateur écrit.
        rangee = self.source.split("function rangeePastilles(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("text: nom,", rangee)
        for balisage in ("markup", "clutter_text"):
            self.assertNotIn(balisage, rangee)


if __name__ == "__main__":
    unittest.main()
