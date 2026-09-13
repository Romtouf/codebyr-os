# -*- coding: utf-8 -*-
"""Éléments d'interface partagés par les outils graphiques de Codebyr.

── POURQUOI CE MODULE ──────────────────────────────────────────────────────
Les pastilles de couleur des Espaces étaient dessinées deux fois, dans
« codebyr-bienvenue » et dans « codebyr-config », en attachant une feuille de
style à CHAQUE widget :

    p.get_style_context().add_provider(css, …)

GTK 4 déprécie cette façon de faire — elle affichait deux avertissements à
chaque lancement, et disparaîtra avec GTK 5. La méthode prévue déclare la
règle pour tout l'affichage ; on nomme donc une classe CSS par couleur, posée
une seule fois, et les widgets s'y rattachent.

Une couleur d'Espace n'est jamais décorative : c'est le repère qui dit où l'on
se trouve. Mieux vaut une seule implémentation, ici, que deux qui divergent.
"""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

_CLASSES_POSEES = set()


def classe_pastille(couleur, rayon):
    """Nom d'une classe CSS pour cette couleur, déclarée au besoin."""
    nom = "codebyr-pastille-%s-%d" % (couleur.lstrip("#").lower(), rayon)
    if nom not in _CLASSES_POSEES:
        css = Gtk.CssProvider()
        css.load_from_data(
            (".%s{background:%s;border-radius:%dpx;}" % (nom, couleur, rayon)).encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        _CLASSES_POSEES.add(nom)
    return nom


def pastille(couleur, taille):
    """Une pastille ronde de la couleur d'un Espace."""
    p = Gtk.Box()
    p.set_size_request(taille, taille)
    p.set_valign(Gtk.Align.CENTER)
    p.add_css_class(classe_pastille(couleur, taille // 2))
    return p
