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

    # Défaut CONNU et mesuré, pas ignoré. L'Ambre de l'Espace Navigation ne
    # ressort pas sur fond clair : 2.376 pour un seuil de 3.0. C'est la pastille
    # de barre de titre qui en souffre, posée sur un bandeau presque blanc.
    # Corriger une couleur de marque est une décision de conception, pas une
    # correction technique : consignée dans docs/chantiers.md, avec la valeur
    # proposée. Le test garde le reste et surveille que ça n'empire pas.
    CONNUS = {"--esp-navigation": 2.376}

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


class SceauDuPanneau(unittest.TestCase):
    """Le Sceau doit se voir. C'est le point d'entrée de tout le système.

    Le 23/08/2026 il est devenu INVISIBLE : passé en #2e3436, la couleur de base
    d'Adwaita, il comptait sur la recoloration symbolique de GNOME — qui ne
    s'applique pas à une icône chargée depuis un fichier. Contraste obtenu sur
    le panneau du thème sombre : 1.7.

    Et aucune couleur fixe ne pouvait convenir : le panneau vaut #fafafb en
    thème clair et #000000 en sombre. Il faut donc deux icônes, et les choisir.
    """

    PANNEAU_CLAIR = "#fafafb"
    PANNEAU_SOMBRE = "#000000"
    ICONES = os.path.join(
        RACINE, "live-build", "config", "includes.chroot_after_packages",
        "usr", "share", "gnome-shell", "extensions", "codebyr@codebyr.io", "icons")

    def _couleur(self, fichier):
        with open(os.path.join(self.ICONES, fichier), encoding="utf-8") as f:
            trouve = re.findall(r'fill="(#[0-9A-Fa-f]{6})"', f.read())
        self.assertTrue(trouve, "aucun remplissage dans %s" % fichier)
        return trouve[-1]

    def test_les_deux_variantes_existent(self):
        for fichier in ("codebyr-symbolic.svg", "codebyr-clair-symbolic.svg"):
            self.assertTrue(os.path.exists(os.path.join(self.ICONES, fichier)),
                            "variante manquante : %s" % fichier)

    def test_chaque_variante_se_voit_sur_son_panneau(self):
        for fichier, panneau in (("codebyr-symbolic.svg", self.PANNEAU_CLAIR),
                                 ("codebyr-clair-symbolic.svg", self.PANNEAU_SOMBRE)):
            mesure = contraste(self._couleur(fichier), panneau)
            self.assertGreaterEqual(
                mesure, 4.5,
                "%s ne ressort pas sur %s : %.2f" % (fichier, panneau, mesure))

    def test_l_extension_mesure_le_panneau_au_lieu_de_le_deduire(self):
        """Déduire s'est trompé deux fois. Mesurer ne se trompe pas.

        Premier essai : couleur fixe, invisible sur le panneau noir. Deuxième :
        choix d'après « color-scheme », qui vaut « default » sur Codebyr — le
        thème CLAIR des applications — alors que GNOME affiche malgré tout un
        panneau NOIR. Le Sceau sombre y était de nouveau invisible.

        Le panneau, lui, sait de quelle couleur il est.
        """
        chemin = os.path.join(
            RACINE, "live-build", "config", "includes.chroot_after_packages",
            "usr", "share", "gnome-shell", "extensions", "codebyr@codebyr.io",
            "extension.js")
        with open(chemin, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("get_background_color", source,
                      "la couleur du panneau doit être MESURÉE, pas déduite "
                      "d'un réglage")
        self.assertIn("codebyr-clair-symbolic.svg", source)
        self.assertIn("style-changed", source,
                      "le style du panneau n'est pas prêt à la création de "
                      "l'indicateur : il faut repasser quand il l'est")

    def test_le_defaut_est_le_sceau_clair(self):
        """Si la mesure échoue, se tromper du côté du panneau noir.

        C'est celui de GNOME par défaut, et c'est celui du poste où le Sceau a
        disparu deux fois. Un défaut mal choisi ici redonne exactement le bogue.
        """
        chemin = os.path.join(
            RACINE, "live-build", "config", "includes.chroot_after_packages",
            "usr", "share", "gnome-shell", "extensions", "codebyr@codebyr.io",
            "extension.js")
        with open(chemin, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("let sombre = true;", source,
                      "en cas d'échec de mesure, le Sceau doit être clair")


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
