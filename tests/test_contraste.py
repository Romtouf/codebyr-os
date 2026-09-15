# -*- coding: utf-8 -*-
"""Contraste de la charte graphique — mesuré, jamais supposé.

Une couleur de marque se choisit à l'œil, sur un grand aplat, dans de bonnes
conditions. Elle est ensuite lue en petit, par des gens dont la vue baisse, sur
des écrans mal réglés. L'écart entre les deux ne se voit pas : il se calcule.

Ces tests ne prétendent pas juger l'esthétique. Ils gardent deux choses :
- que les couleurs des Espaces restent distinguables entre elles, puisque tout
  le système d'isolation repose sur le fait qu'on les reconnaisse ;
- que les valeurs mesurées ne dérivent pas en silence lors d'une retouche.
"""
import os
import re
import unittest

from outils import RACINE

# Seuil AA du WCAG pour du texte ordinaire.
AA = 4.5
FOND_CLAIR = "#FFFFFF"
FOND_SOMBRE = "#0B1419"


def luminance(hexa):
    hexa = hexa.lstrip("#")
    canaux = [int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    canaux = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
              for c in canaux]
    return 0.2126 * canaux[0] + 0.7152 * canaux[1] + 0.0722 * canaux[2]


def contraste(a, b):
    haut, bas = sorted((luminance(a), luminance(b)), reverse=True)
    return (haut + 0.05) / (bas + 0.05)


def jetons():
    """Les couleurs déclarées dans branding/tokens.css, par nom."""
    chemin = os.path.join(RACINE, "branding", "tokens.css")
    with open(chemin, encoding="utf-8") as f:
        source = f.read()
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6})", source))


class Formule(unittest.TestCase):
    """La mesure elle-même, éprouvée sur des cas connus."""

    def test_noir_sur_blanc(self):
        self.assertAlmostEqual(contraste("#000000", "#FFFFFF"), 21.0, places=2)

    def test_identiques(self):
        self.assertAlmostEqual(contraste("#3A7BD5", "#3A7BD5"), 1.0, places=6)

    def test_symetrique(self):
        self.assertAlmostEqual(contraste("#0B87A0", "#FFFFFF"),
                               contraste("#FFFFFF", "#0B87A0"), places=9)


class CouleursDesEspaces(unittest.TestCase):
    """Elles ne sont jamais décoratives : elles disent où l'on se trouve.

    Un utilisateur qui confond deux liserés croit travailler dans un Espace
    alors qu'il est dans un autre. C'est le seul repère visuel du cloisonnement.
    """

    ESPACES = ("--esp-personnel", "--esp-travail", "--esp-banque",
               "--esp-navigation", "--esp-jetable", "--esp-systeme")

    def setUp(self):
        self.jetons = jetons()

    def test_toutes_declarees(self):
        for nom in self.ESPACES:
            self.assertIn(nom, self.jetons, "couleur d'Espace absente : %s" % nom)

    def test_toutes_distinctes(self):
        valeurs = [self.jetons[n].upper() for n in self.ESPACES]
        self.assertEqual(len(set(valeurs)), len(valeurs),
                         "deux Espaces partagent une couleur")

    # Défauts CONNUS et mesurés, pas ignorés : une couleur de marque ne se
    # corrige pas en douce, c'est une décision de conception. L'Ambre de
    # Navigation y a figuré à 2.376 jusqu'au 13/09/2026 ; elle en est sortie en
    # passant de #E09A32 à #BF7600.
    CONNUS = {}

    def test_visibles_sur_les_deux_fonds(self):
        """Un liseré invisible sur un fond ne cloisonne plus rien.

        Seuil volontairement bas (3.0, celui des éléments non textuels) : ce
        sont des traits et des pastilles, pas du texte.
        """
        for nom in self.ESPACES:
            couleur = self.jetons[nom]
            for fond in (FOND_CLAIR, FOND_SOMBRE):
                mesure = contraste(couleur, fond)
                plancher = self.CONNUS.get(nom, 3.0) if fond == FOND_CLAIR else 3.0
                self.assertGreaterEqual(
                    mesure, plancher,
                    "%s (%s) ne ressort pas sur %s : %.2f"
                    % (nom, couleur, fond, mesure))

    def test_les_defauts_connus_ne_sont_pas_oublies(self):
        """Un défaut corrigé doit sortir de la liste, sinon elle ment.

        Une liste d'exceptions que personne ne relit finit par excuser des
        régressions qu'elle n'a jamais eu pour but de couvrir.
        """
        for nom, mesure_attendue in self.CONNUS.items():
            reelle = contraste(self.jetons[nom], FOND_CLAIR)
            self.assertLess(
                reelle, 3.0,
                "%s satisfait désormais le seuil (%.2f) : retirez-le de CONNUS "
                "et de docs/chantiers.md" % (nom, reelle))
            self.assertAlmostEqual(
                reelle, mesure_attendue, places=3,
                msg="la valeur de %s a changé sans que le constat soit mis à "
                    "jour (%.2f au lieu de %.2f)" % (nom, reelle, mesure_attendue))


# ── Daltonisme ─────────────────────────────────────────────────────────────
#
# Simulation de Machado, Oliveira et Fernandes (2009), sévérité complète, puis
# écart de couleur CIEDE2000 entre les deux couleurs simulées. En dessous de
# quelques unités, deux pastilles de 10 pixels se confondent.

_SIMULATION = {
    "deutéranopie": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413),
                     (-0.011820, 0.042940, 0.968881)),
    "protanopie": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216),
                   (-0.003882, -0.048116, 1.051998)),
}


def _lineaire(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _encode(c):
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _rgb_lineaire(hexa):
    hexa = hexa.lstrip("#")
    return [_lineaire(int(hexa[i:i + 2], 16) / 255) for i in (0, 2, 4)]


def simuler(hexa, vision):
    m = _SIMULATION[vision]
    v = _rgb_lineaire(hexa)
    return [_encode(sum(m[r][k] * v[k] for k in range(3))) for r in range(3)]


def _lab(rgb_encode):
    import math
    r, g, b = [_lineaire(c) for c in rgb_encode]
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def ecart(rgb1, rgb2):
    """CIEDE2000."""
    import math
    L1, a1, b1 = _lab(rgb1)
    L2, a2, b2 = _lab(rgb2)
    cm = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(cm ** 7 / (cm ** 7 + 25 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dlp, dcp = L2 - L1, c2p - c1p
    dh = h2p - h1p
    if c1p * c2p == 0:
        dh = 0
    elif dh > 180:
        dh -= 360
    elif dh < -180:
        dh += 360
    dhp = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dh / 2))
    lm, cmp_ = (L1 + L2) / 2, (c1p + c2p) / 2
    hs = h1p + h2p
    if c1p * c2p == 0:
        hm = hs
    elif abs(h1p - h2p) > 180:
        hm = (hs + 360) / 2 if hs < 360 else (hs - 360) / 2
    else:
        hm = hs / 2
    t = (1 - 0.17 * math.cos(math.radians(hm - 30)) + 0.24 * math.cos(math.radians(2 * hm))
         + 0.32 * math.cos(math.radians(3 * hm + 6)) - 0.20 * math.cos(math.radians(4 * hm - 63)))
    dth = 30 * math.exp(-((hm - 275) / 25) ** 2)
    rc = 2 * math.sqrt(cmp_ ** 7 / (cmp_ ** 7 + 25 ** 7))
    sl = 1 + 0.015 * (lm - 50) ** 2 / math.sqrt(20 + (lm - 50) ** 2)
    sc, sh = 1 + 0.045 * cmp_, 1 + 0.015 * cmp_ * t
    rt = -math.sin(math.radians(2 * dth)) * rc
    return math.sqrt((dlp / sl) ** 2 + (dcp / sc) ** 2 + (dhp / sh) ** 2
                     + rt * (dcp / sc) * (dhp / sh))


class Daltonisme(unittest.TestCase):
    """Environ 8 % des hommes voient mal les rouges et les verts.

    Pour eux, la couleur d'un Espace peut en rejoindre une autre. Ce test garde
    ce qui a été choisi pour l'éviter, et chiffre ce qui ne l'est pas encore.
    """

    def setUp(self):
        self.jetons = jetons()

    def _ecart(self, a, b, vision):
        return ecart(simuler(self.jetons[a], vision), simuler(self.jetons[b], vision))

    def test_navigation_reste_distincte_de_jetable(self):
        # Assombrir l'Ambre pour la rendre visible sur fond clair la rapproche
        # du rouge de Jetable chez un deutéranope. #BF7600 a été retenue parce
        # qu'elle s'en écarte le plus à contraste égal (7,8, contre 6,3 pour
        # #BA7B1C). Jetable garde de toute façon son trait pointillé.
        self.assertGreaterEqual(
            self._ecart("--esp-navigation", "--esp-jetable", "deutéranopie"), 7.5)

    # Défaut CONNU et mesuré. Azur (Personnel) et Améthyste (Travail) se
    # confondent pour un deutéranope, et presque pour un protanope. Compensé
    # depuis la 1.12.2 par le NOM écrit (étiquette de fenêtre, et barre du haut
    # pour la fenêtre active — voir EtiquetteDuNom) ; les teintes, elles,
    # restent à distinguer. Consigné dans docs/chantiers.md.
    CONFUSIONS_CONNUES = {("--esp-personnel", "--esp-travail", "deutéranopie"): 2.7,
                          ("--esp-personnel", "--esp-travail", "protanopie"): 6.7}

    def test_les_confusions_connues_sont_chiffrees_et_n_empirent_pas(self):
        for (a, b, vision), mesure in self.CONFUSIONS_CONNUES.items():
            self.assertAlmostEqual(self._ecart(a, b, vision), mesure, delta=0.1,
                                   msg="%s / %s en %s a changé : mettez à jour le "
                                       "constat (et docs/chantiers.md)" % (a, b, vision))


class EtiquetteDuNom(unittest.TestCase):
    """Le nom de l'Espace, écrit en haut à gauche de chaque fenêtre.

    Pour qui ne distingue pas Azur d'Améthyste, c'est lui qui dit si l'on est
    dans Personnel ou dans Travail. Il était déjà là, mais en 10 px, et il
    disparaissait sous la barre supérieure dès qu'une fenêtre touchait le haut
    de l'écran — le cas le plus courant pour un navigateur.
    """

    def setUp(self):
        chemin = os.path.join(RACINE, "live-build", "config",
                              "includes.chroot_after_packages", "usr", "share",
                              "gnome-shell", "extensions", "codebyr@codebyr.io",
                              "extension.js")
        with open(chemin, encoding="utf-8") as f:
            self.code = f.read()
        debut = self.code.index("const Lisere = GObject.registerClass(")
        self.lisere = self.code[debut:self.code.index("class Coloriage", debut)]

    def test_l_etiquette_n_est_pas_l_enfant_d_une_surface_de_dessin(self):
        # Un St.DrawingArea ne peint que son dessin Cairo, jamais ses enfants :
        # l'étiquette, placée dedans, a été invisible de la 1.0.4 à la 1.12.1.
        self.assertIn("class Lisere extends St.Widget", self.lisere)
        self.assertNotIn("extends St.DrawingArea", self.lisere)
        self.assertIn("this._trait = new St.DrawingArea", self.lisere)
        self.assertNotIn("this._trait.add_child", self.lisere)
        self.assertIn("this.add_child(this._etiq)", self.lisere)

    def test_le_nom_est_ecrit_en_texte_sombre_et_lisible(self):
        self.assertIn("text: espace.nom", self.lisere)
        self.assertIn("color: #0A1318", self.lisere)
        taille = int(re.search(r"font-size: (\d+)px", self.lisere).group(1))
        self.assertGreaterEqual(taille, 12, "l'étiquette du nom redevient illisible")

    def test_le_texte_sombre_se_lit_sur_toutes_les_couleurs_d_espace(self):
        jetons_ = jetons()
        for nom in CouleursDesEspaces.ESPACES:
            if nom == "--esp-systeme":
                continue    # réservée au système, jamais portée par un Espace
            self.assertGreaterEqual(contraste(jetons_[nom], "#0A1318"), AA, nom)

    def test_en_haut_de_l_ecran_l_etiquette_s_efface_sans_rien_recouvrir(self):
        # Rangée dans une fenêtre agrandie, elle recouvrait le premier bouton
        # de l'application (Fichiers, 13/09/2026). Elle s'efface ; le nom de
        # l'Espace actif est alors lu dans la barre du haut.
        self.assertIn("get_work_area_current_monitor()", self.code)
        self.assertIn("majGeometrie(win.get_frame_rect(), zone)", self.code)
        self.assertIn("rect.y - Math.ceil(h / 2) < zone.y", self.lisere)
        self.assertIn("this._etiq.hide()", self.lisere)
        self.assertNotIn("EP + 2", self.lisere)

    def test_le_nom_de_l_espace_actif_est_ecrit_a_cote_du_sceau(self):
        self.assertIn("afficherEspace(esp)", self.code)
        self.assertIn("this._repereNom.text = esp.nom", self.code)
        self.assertIn("'notify::focus-window'", self.code)
        self.assertIn("esp => this._indicateur?.afficherEspace(esp)", self.code)
        # Lecteurs d'écran : le nom est aussi annoncé, pas seulement affiché.
        self.assertIn("'Codebyr — Espace actif : ' + esp.nom", self.code)


class SceauDuPanneau(unittest.TestCase):
    """Le Sceau du panneau : dessiné, et à la couleur du thème.

    Le 23/08/2026, trois essais successifs avaient laissé l'icône invisible,
    chacun plus sûr de lui que le précédent. La cause n'a été comprise que le
    15/09/2026 : l'icône était un fichier SVG dessiné en TRAITS, alors que la
    recoloration symbolique de GNOME agit sur le REMPLISSAGE. La passer en
    « fill » remplissait les arcs au lieu de les colorer — d'où les taches et
    les disparitions.

    La couleur restait donc écrite en dur, un gris moyen choisi pour être
    visible sur les deux panneaux sans être beau sur aucun. Le Sceau est
    maintenant DESSINÉ avec Cairo, comme le liseré : il prend la couleur du
    texte de la barre, donc il suit le thème par construction, et la question
    du contraste ne se pose plus — c'est celle du texte voisin.

    Ces tests gardent cette propriété. S'ils tombent, on est en train de
    revenir à une couleur figée.
    """

    def setUp(self):
        chemin = os.path.join(RACINE, "live-build", "config",
                              "includes.chroot_after_packages", "usr", "share",
                              "gnome-shell", "extensions", "codebyr@codebyr.io",
                              "extension.js")
        with open(chemin, encoding="utf-8") as f:
            self.code = f.read()
        self.sceau = self.code.split("function sceauDeLaBarre(")[1].split("\n}")[0]

    def test_le_sceau_est_dessine_et_non_charge_d_un_fichier(self):
        self.assertIn("St.DrawingArea", self.sceau)
        self.assertNotIn("codebyr-symbolic.svg", self.code)

    def test_il_prend_la_couleur_du_theme(self):
        # C'est tout l'objet du changement : une couleur écrite en dur est
        # terne sur un panneau noir, ou invisible sur un panneau clair.
        self.assertIn("get_theme_node().get_foreground_color()", self.sceau)
        self.assertNotIn("#5c5c5c", self.code)
        for regle in re.findall(r"setSourceRGBA\(([^)]*)\)", self.sceau):
            self.assertIn("c.", regle, "couleur figée dans le Sceau : " + regle)

    def test_il_suit_la_taille_qu_on_lui_donne(self):
        # Sur un écran à forte densité, la barre demande plus de points : un
        # dessin calé sur 16 en dur y serait minuscule.
        self.assertIn("get_surface_size()", self.sceau)
        self.assertIn("SCEAU_COTE", self.sceau)

    def test_le_dessin_libere_son_contexte(self):
        # Même règle que le liseré : un contexte Cairo non libéré fuit dans le
        # compositeur, qui redessine la barre en permanence.
        self.assertIn("cr.$dispose()", self.sceau)
        self.assertIn("finally", self.sceau)


class AccentSentinelle(unittest.TestCase):
    """Le constat qui a fait écarter le thème GTK — gardé chiffré.

    GTK 4.18 ne connaît pas « prefers-color-scheme » : une surcharge CSS impose
    UNE valeur aux deux modes. Or la Sentinelle n'atteint AA que d'un côté à la
    fois. Ce test empêche que ce constat se périme sans qu'on le remarque : si
    une retouche de la charte le rendait faux, le thème redeviendrait possible
    et il faudrait rouvrir le chantier.
    """

    def test_aucune_valeur_unique_ne_convient_aux_deux_modes(self):
        jeu = jetons()
        clair = jeu["--cb-accent"]
        conforme_clair = contraste(clair, FOND_CLAIR) >= AA
        conforme_sombre = contraste(clair, FOND_SOMBRE) >= AA
        self.assertFalse(
            conforme_clair and conforme_sombre,
            "l'accent %s satisfait désormais AA dans les deux modes : le thème "
            "GTK écarté dans docs/architecture.md redevient possible, rouvrez "
            "le chantier" % clair)

    def test_le_constat_est_ecrit_dans_l_architecture(self):
        """Une décision d'architecture non écrite se reprend tous les six mois."""
        chemin = os.path.join(RACINE, "docs", "architecture.md")
        with open(chemin, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("prefers-color-scheme", source)
        self.assertIn("étudié puis écarté", source)


if __name__ == "__main__":
    unittest.main()
