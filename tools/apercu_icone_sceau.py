#!/usr/bin/env python3
"""Aperçu : à quoi ressemble le Sceau dans la barre du haut, avant de le livrer.

NON INSTALLÉ. À lancer depuis une session graphique :

    python3 tools/apercu_icone_sceau.py

L'icône du Sceau est jugée terne et petite. Trois tentatives ont échoué en
août 2026, dont deux l'ont rendue invisible, et chacune a coûté une
publication complète puis une déconnexion pour voir le résultat.

Cet outil montre les variantes CÔTE À CÔTE, à la taille réelle de la barre et
agrandies, sur fond sombre ET clair. On choisit en regardant, pas en imaginant.

Ce qu'il faut savoir sur l'échec d'août, et que cette fenêtre rend visible :
l'icône livrée est dessinée en TRAITS (stroke), avec une couleur écrite en dur.
La recoloration symbolique de GNOME, elle, agit sur le REMPLISSAGE — d'où une
icône qui reste grise, ou qui devient une tache. Les variantes ci-dessous sont
dessinées avec Cairo, exactement comme le fera l'extension : la couleur vient
alors du thème, et l'épaisseur est choisie pour la taille réelle.
"""
import math
import sys

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

# Le Sceau : trois arcs d'un même cercle, séparés par des coupures, et un point
# au centre. Les angles viennent du dessin d'origine (branding/le-sceau.svg),
# relevés ici en degrés pour rester lisibles.
ARCS = [(18, 108), (138, 228), (258, 348)]


def dessiner(cr, taille, epaisseur, rayon_point, marge, couleur):
    """Dessine le Sceau dans un carré de « taille » points.

    `epaisseur` et `rayon_point` sont donnés en points à cette taille : c'est
    ce qui décide de la lisibilité une fois dans la barre, pas les proportions
    du fichier d'origine.
    """
    cr.set_source_rgba(*couleur)
    centre = taille / 2.0
    rayon = centre - marge - epaisseur / 2.0
    cr.set_line_width(epaisseur)
    cr.set_line_cap(1)          # rond : les extrémités d'arc ne sont pas coupées net
    for depart, fin in ARCS:
        cr.new_sub_path()
        cr.arc(centre, centre, rayon, math.radians(depart), math.radians(fin))
        cr.stroke()
    cr.arc(centre, centre, rayon_point, 0, 2 * math.pi)
    cr.fill()


# Chaque variante : nom, épaisseur du trait, rayon du point, marge — tous en
# points pour une icône de 16, la taille réelle d'une icône de barre.
VARIANTES = [
    ("A. Aujourd'hui (gris fixe)", 1.9, 1.4, 1.2, (0.36, 0.36, 0.36, 1.0)),
    ("B. Couleur du thème", 1.9, 1.4, 1.2, None),
    ("C. Trait plus gras", 2.3, 1.7, 0.8, None),
    ("D. Plus gras, plus grand", 2.6, 1.9, 0.4, None),
]
TAILLE = 16.0


class Bande(Gtk.DrawingArea):
    """Une bande de fond, avec les quatre variantes dessinées dessus."""

    def __init__(self, fond, encre, agrandissement):
        super().__init__()
        self._fond = fond
        self._encre = encre
        self._k = agrandissement
        self.set_content_height(int(TAILLE * agrandissement) + 24)
        self.set_draw_func(self._peindre)

    def _peindre(self, _zone, cr, largeur, hauteur):
        cr.set_source_rgba(*self._fond)
        cr.paint()
        pas = largeur / len(VARIANTES)
        for i, (_nom, epaisseur, point, marge, couleur) in enumerate(VARIANTES):
            cr.save()
            cote = TAILLE * self._k
            cr.translate(i * pas + (pas - cote) / 2.0, (hauteur - cote) / 2.0)
            cr.scale(self._k, self._k)
            dessiner(cr, TAILLE, epaisseur, point, marge, couleur or self._encre)
            cr.restore()


def demarrer(app):
    fenetre = Gtk.ApplicationWindow(application=app, title="Le Sceau dans la barre")
    fenetre.set_default_size(640, 420)
    boite = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                    margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)

    titres = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, homogeneous=True)
    for nom, _e, _p, _m, _c in VARIANTES:
        titres.append(Gtk.Label(label=nom, wrap=True, justify=2))
    boite.append(titres)

    noir = (0.0, 0.0, 0.0, 1.0)
    blanc_panneau = (0.98, 0.98, 0.98, 1.0)
    for legende, fond, encre, k in (
            ("Barre sombre — taille réelle (16 px)", noir, (1, 1, 1, 1), 1),
            ("Barre sombre — agrandie 8×", noir, (1, 1, 1, 1), 8),
            ("Barre claire — taille réelle (16 px)", blanc_panneau, (0.1, 0.1, 0.1, 1), 1),
            ("Barre claire — agrandie 8×", blanc_panneau, (0.1, 0.1, 0.1, 1), 8)):
        boite.append(Gtk.Label(label=legende, xalign=0))
        boite.append(Bande(fond, encre, k))

    boite.append(Gtk.Label(
        label="Dites-moi la lettre retenue (A, B, C ou D).", xalign=0))
    fenetre.set_child(boite)
    fenetre.present()


def main():
    app = Gtk.Application(application_id="io.codebyr.ApercuSceau")
    app.connect("activate", demarrer)
    return app.run([])


if __name__ == "__main__":
    sys.exit(main())
