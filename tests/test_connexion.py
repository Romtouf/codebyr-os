# -*- coding: utf-8 -*-
"""L'écran de connexion aux couleurs de Codebyr, sans thème de GNOME sur mesure.

GNOME 48 n'a aucun réglage pour ce fond : il vient du thème de GNOME Shell
(#lockDialogGroup), et un thème remplacé casse à chaque version de GNOME. Une
extension système ajoute sa feuille de style, et ne déclare que le mode
« gdm » : GNOME Shell (js/ui/extensionSystem.js, 48.7) ne charge une extension
que dans les modes qu'elle déclare, et la session de l'écran de connexion lit
enabled-extensions comme les autres — elle n'en fixe aucune (vérifié dans
/usr/share/gdm/dconf de l'image).
"""
import json
import os
import re
import unittest

from outils import RACINE

LIVRE = os.path.join(RACINE, "live-build", "config", "includes.chroot_after_packages")
EXTENSION = os.path.join(LIVRE, "usr", "share", "gnome-shell", "extensions",
                         "codebyr-connexion@codebyr.io")
OVERRIDE = os.path.join(LIVRE, "usr", "share", "glib-2.0", "schemas", "90_codebyr.gschema.override")


def _lire(chemin):
    with open(chemin, encoding="utf-8") as f:
        return f.read()


class LEcranDeConnexion(unittest.TestCase):

    def test_seulement_sur_l_ecran_de_connexion(self):
        meta = json.loads(_lire(os.path.join(EXTENSION, "metadata.json")))
        self.assertEqual(meta["uuid"], "codebyr-connexion@codebyr.io")
        # « user » ou « unlock-dialog » la feraient aussi agir dans les sessions.
        self.assertEqual(meta["session-modes"], ["gdm"])
        self.assertIn("48", meta["shell-version"])

    def test_activee_par_defaut(self):
        reglage = re.search(r"^enabled-extensions=(.*)$", _lire(OVERRIDE), re.M).group(1)
        self.assertIn("'codebyr-connexion@codebyr.io'", reglage)

    def test_le_fond_est_celui_du_verrouillage(self):
        css = _lire(os.path.join(EXTENSION, "stylesheet.css"))
        self.assertIn("#lockDialogGroup", css)
        image = re.search(r'url\("file://([^"]+)"\)', css).group(1)
        # Le même fond sombre que l'écran de verrouillage et le mode sombre.
        self.assertIn("picture-uri-dark='file://%s'" % image, _lire(OVERRIDE))
        # Et une couleur de repli, si l'image venait à manquer.
        self.assertRegex(css, r"background-color: #[0-9A-Fa-f]{6};")

    def test_rien_d_autre_que_la_feuille_de_style(self):
        code = _lire(os.path.join(EXTENSION, "extension.js"))
        corps = code.split("export default class", 1)[1]
        self.assertRegex(corps, r"enable\(\) \{\}")
        self.assertRegex(corps, r"disable\(\) \{\}")

    def test_livree_par_le_paquet(self):
        self.assertIn("usr/share/gnome-shell/extensions/codebyr-connexion@codebyr.io",
                      _lire(os.path.join(RACINE, "packaging", "build-deb.sh")))


if __name__ == "__main__":
    unittest.main()
