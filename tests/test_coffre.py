# -*- coding: utf-8 -*-
"""L'Espace Coffre : les mots de passe, sans aucun réseau.

Un gestionnaire de mots de passe est la cible la plus précieuse d'une machine.
Dans son Espace, sous son propre compte, sans réseau : un programme piégé
ailleurs ne lit pas le coffre, et le coffre ne peut rien envoyer. Un mot de
passe en sort par le presse-papiers, par le geste explicite « Transférer le
presse-papiers vers… » du menu du Sceau.
"""
import json
import os
import re
import unittest

from outils import BIN, ETC, RACINE

LIVRE = os.path.join(RACINE, "live-build", "config", "includes.chroot_after_packages")


def _lire(chemin):
    with open(chemin, encoding="utf-8") as f:
        return f.read()


def _coffre():
    registre = json.loads(_lire(os.path.join(ETC, "codebyr", "espaces.json")))
    return {e["id"]: e for e in registre["espaces"]}["coffre"]


class LeCoffre(unittest.TestCase):

    def test_aucun_reseau(self):
        # « coupe » : espace de noms réseau isolé, sans interface (bac_a_sable).
        self.assertEqual(_coffre()["reseau"], {"mode": "coupe"})
        space = _lire(os.path.join(BIN, "codebyr-space"))
        self.assertIn('.get("mode") in ("coupe", "hors-ligne")', space)

    def test_sous_son_compte_blinde_sans_micro_ni_carte_graphique(self):
        coffre = _coffre()
        self.assertEqual(coffre["compte"], "dedie")
        self.assertEqual(coffre["blindage"], "renforce")
        self.assertIs(coffre["audio"], False)
        self.assertIs(coffre["gpu"], False)
        self.assertIs(coffre["ephemere"], False)

    def test_son_menu_ouvre_le_gestionnaire_et_non_un_navigateur(self):
        commandes = [a["cmd"] for a in _coffre()["apps"]]
        self.assertEqual(commandes[0], "keepassxc")
        self.assertNotIn("firefox-esr", commandes)

    def test_le_gestionnaire_sans_fonction_reseau_est_livre(self):
        # keepassxc-minimal : ni greffon de navigateur, ni vérification en
        # ligne. qtwayland5 : sans lui, Qt ne s'affiche que par X11, qu'un
        # Espace ne voit pas — l'application ne s'ouvrirait pas.
        liste = _lire(os.path.join(RACINE, "live-build", "config", "package-lists",
                                   "logiciels.list.chroot")).split()
        depend = re.search(r"^Depends: (.*)$",
                           _lire(os.path.join(RACINE, "packaging", "build-deb.sh")), re.M).group(1)
        depend = [d.strip() for d in depend.split(",")]
        for paquet in ("keepassxc-minimal", "qtwayland5"):
            self.assertIn(paquet, liste)
            self.assertIn(paquet, depend)
        self.assertNotIn("keepassxc-full", liste)

    def test_qt_passe_par_wayland_dans_un_espace(self):
        space = _lire(os.path.join(BIN, "codebyr-space"))
        self.assertIn('env.setdefault("QT_QPA_PLATFORM", "wayland;xcb")', space)

    def test_sa_couleur_est_celle_de_la_charte(self):
        jetons = _lire(os.path.join(RACINE, "branding", "tokens.css"))
        self.assertIn("--esp-coffre: %s;" % _coffre()["couleur"], jetons)
        self.assertIn('"%s"' % _coffre()["couleur"], _lire(os.path.join(BIN, "codebyr-bienvenue")))

    def test_le_presse_papiers_n_en_sort_que_par_le_geste_explicite(self):
        # Blindé, donc « sensible » : quitter le Coffre vide le presse-papiers,
        # sauf transfert autorisé depuis le menu du Sceau.
        extension = _lire(os.path.join(LIVRE, "usr", "share", "gnome-shell", "extensions",
                                       "codebyr@codebyr.io", "extension.js"))
        sensible = extension.split("    _sensible(id) {", 1)[1].split("\n    }\n", 1)[0]
        self.assertIn("esp.blindage === 'renforce'", sensible)


class LeDiaporama(unittest.TestCase):

    def test_la_diapositive_couvre_toute_la_zone(self):
        # Calamares place la diapositive en retrait : le fond restait blanc
        # autour (vu à l'essai de l'ISO 1.21.2).
        qml = _lire(os.path.join(ETC, "calamares", "branding", "debian", "show.qml"))
        self.assertEqual(qml.count("width: parent.masterWidth; height: parent.masterHeight"), 4)
        self.assertNotIn('anchors.fill: parent\n            color: "#0E1B24"', qml)


if __name__ == "__main__":
    unittest.main()
