# -*- coding: utf-8 -*-
"""Une application Flatpak qui sortirait de son Espace ne s'y ouvre pas.

Dans un Espace ordinaire, une application Flatpak n'est pas dans le bac à
sable de Codebyr : ses permissions s'exercent sous le compte du bureau. Celles
qui la font sortir de l'Espace doivent la faire refuser — sinon le liseré de
l'Espace annonce une isolation qui n'existe pas.
"""
import os
import tempfile
import unittest
from unittest import mock

import outils
import permissions_flatpak as pf

space = outils.charger("codebyr-space")

# Sorties réelles de « flatpak info --show-permissions », à l'identique de leur
# forme (fichier de clés GLib).
CALCULATRICE = """[Context]
shared=ipc;
sockets=x11;wayland;fallback-x11;
devices=dri;

[Session Bus Policy]
org.gtk.vfs.*=talk
org.freedesktop.Notifications=talk
"""

EDITEUR_TOUT_TERRAIN = """[Context]
shared=network;ipc;
sockets=x11;wayland;pulseaudio;ssh-auth;
devices=all;
filesystems=host;

[Session Bus Policy]
org.freedesktop.Flatpak=talk
org.freedesktop.secrets=talk

[Environment]
ELECTRON_TRASH=gio
"""


class LIdentifiant(unittest.TestCase):
    """L'application que lance la commande, et pas son dernier argument."""

    def test_forme_simple(self):
        self.assertEqual(pf.identifiant(["flatpak", "run", "org.gnome.Calculator"]),
                         "org.gnome.Calculator")

    def test_commande_d_un_lanceur_avec_transmission_de_fichiers(self):
        # Ce que « Autres applications… » transmet, %U retiré : le dernier
        # argument est « @@ ». On cherchait une application de ce nom.
        argv = ["/usr/bin/flatpak", "run", "--branch=stable", "--arch=x86_64",
                "--command=gnome-text-editor", "--file-forwarding",
                "org.gnome.TextEditor", "@@u", "@@"]
        self.assertEqual(pf.identifiant(argv), "org.gnome.TextEditor")

    def test_references_completes(self):
        self.assertEqual(pf.identifiant(["flatpak", "run", "app/org.x.Y/x86_64/stable"]), "org.x.Y")
        self.assertEqual(pf.identifiant(["flatpak", "run", "org.x.Y//beta"]), "org.x.Y")

    def test_pas_de_run(self):
        self.assertIsNone(pf.identifiant(["flatpak", "list"]))
        self.assertIsNone(pf.identifiant(["flatpak", "run", "--branch=stable"]))


class CeQuiFaitSortirDeLEspace(unittest.TestCase):

    def test_une_application_sage_passe(self):
        self.assertEqual(pf.sorties(pf.lire(CALCULATRICE), False), [])

    def test_le_bus_du_bureau(self):
        perms = {"Context": {"sockets": "wayland;session-bus;"}}
        self.assertEqual(pf.sorties(perms, True), [pf.LE_BUS])

    def test_flatpak_spawn_host_systemd_et_dconf(self):
        for nom in ("org.freedesktop.Flatpak", "org.freedesktop.systemd1", "ca.desrt.dconf"):
            for niveau in ("talk", "own"):
                perms = {"Session Bus Policy": {nom: niveau}}
                self.assertTrue(pf.sorties(perms, True), (nom, niveau))

    def test_voir_un_service_n_est_pas_lui_parler(self):
        perms = {"Session Bus Policy": {"org.freedesktop.Flatpak": "see"}}
        self.assertEqual(pf.sorties(perms, False), [])

    def test_les_jokers_de_bus(self):
        self.assertTrue(pf.sorties({"Session Bus Policy": {"org.freedesktop.*": "talk"}}, True))
        self.assertTrue(pf.sorties({"Session Bus Policy": {"org.freedesktop.Flatpak.*": "talk"}}, True))
        # « org.freedesktop.Flatpakx » n'est pas « org.freedesktop.Flatpak ».
        self.assertEqual(pf.sorties({"Session Bus Policy": {"org.freedesktop.Flatpakx": "talk"}}, True), [])

    def test_le_systeme_de_fichiers_entier_meme_en_lecture(self):
        for entree in ("host", "host:ro", "/", "/home", "/home/romtouf:ro"):
            perms = {"Context": {"filesystems": entree}}
            self.assertEqual(pf.sorties(perms, True), [pf.TOUT_VOIR], entree)

    def test_le_dossier_d_execution_du_bureau(self):
        for entree in ("xdg-run", "xdg-run/bus", "xdg-run/systemd:ro", "/run/user/1000"):
            perms = {"Context": {"filesystems": entree}}
            self.assertEqual(pf.sorties(perms, True), [pf.LE_BUS], entree)
        # Le son ou un dossier propre à l'application ne mènent pas au bus.
        perms = {"Context": {"filesystems": "xdg-run/pipewire-0:ro;xdg-run/app/org.x.Y:create"}}
        self.assertEqual(pf.sorties(perms, True), [])

    def test_une_permission_retiree_ne_compte_pas(self):
        perms = {"Context": {"filesystems": "!host;!home;", "sockets": "!session-bus;"}}
        self.assertEqual(pf.sorties(perms, False), [])

    def test_le_dossier_personnel_depend_d_ou_l_application_est_installee(self):
        # Installée DANS l'Espace, elle reçoit le dossier de l'Espace pour HOME :
        # « home » y désigne ce dossier-là.
        for entree in ("home", "~", "xdg-config", "xdg-data", "~/.config/autostart",
                       "xdg-data/applications", "~/.local/bin:rw", "~/.bashrc"):
            perms = {"Context": {"filesystems": entree}}
            self.assertEqual(pf.sorties(perms, True), [], entree)
            self.assertEqual(pf.sorties(perms, False), [pf.LE_DOSSIER], entree)

    def test_un_dossier_a_cote_de_ce_qui_compte_n_est_pas_refuse(self):
        # Steam écrit dans ~/.local/share/Steam : ni les Espaces, ni les
        # lanceurs, ni le démarrage de session.
        for entree in ("~/.local/share/Steam:create", "xdg-download", "xdg-music:ro",
                       "~/Jeux", "xdg-data/Steam"):
            perms = {"Context": {"filesystems": entree}}
            self.assertEqual(pf.sorties(perms, False), [], entree)

    def test_une_application_electron_typique(self):
        raisons = pf.sorties(pf.lire(EDITEUR_TOUT_TERRAIN), True)
        self.assertIn(pf.TOUT_VOIR, raisons)
        self.assertIn(pf.BUS_QUI_FONT_SORTIR["org.freedesktop.Flatpak"], raisons)

    def test_les_options_ajoutees_a_la_ligne_de_commande(self):
        argv = ["flatpak", "run", "--filesystem=host", "--command=x", "org.x.Y", "--socket=zz"]
        raisons = pf.options_accordees(argv)
        self.assertEqual(len(raisons), 1)       # ce qui suit l'application est à elle
        self.assertIn("--filesystem=host", raisons[0])
        self.assertEqual(pf.options_accordees(["flatpak", "run", "--branch=stable", "org.x.Y"]), [])


class LaCompatibiliteAvecLEspace(unittest.TestCase):
    """Ce qui refuse toute application Flatpak, quelles que soient ses permissions."""

    BANQUE = {"id": "banque", "reseau": {"mode": "liste-blanche", "domaines": []}}
    JETABLE = {"id": "jetable", "ephemere": True}
    TRAVAIL = {"id": "travail"}

    def test_un_espace_ordinaire_accepte(self):
        self.assertIsNone(pf.incompatibilite(self.TRAVAIL, False, False, False))

    def test_le_reseau_restreint_ou_coupe_refuse_toujours(self):
        for sous_compte in (False, True):
            self.assertTrue(pf.incompatibilite(self.BANQUE, True, False, sous_compte))
            self.assertTrue(pf.incompatibilite(self.TRAVAIL, True, True, sous_compte))

    def test_le_jetable_refuse_toujours(self):
        for sous_compte in (False, True):
            self.assertTrue(pf.incompatibilite(self.JETABLE, True, False, sous_compte))

    def test_le_blindage_n_accepte_que_sous_compte_separe(self):
        # Personnel et Travail sont blindés depuis la 1.16.1 : sans cette
        # exception, plus aucun Espace livré n'accepterait Flatpak.
        self.assertIn("Compte séparé", pf.incompatibilite(self.TRAVAIL, True, False, False))
        self.assertIsNone(pf.incompatibilite(self.TRAVAIL, True, False, True))


class LeLanceur(unittest.TestCase):
    """Dans un Espace ordinaire, le refus a lieu AVANT tout lancement."""

    ESPACES = {"travail": {"id": "travail", "nom": "Travail", "couleur": "#8F6CF0"}}

    def _lancer(self, permissions):
        dossier = tempfile.TemporaryDirectory(prefix="codebyr-essai-")
        self.addCleanup(dossier.cleanup)
        with mock.patch.object(space.shutil, "which", return_value="/usr/bin/bwrap"), \
                mock.patch.object(space, "_preparer_ouverture"), \
                mock.patch.object(space.modeles, "installer"), \
                mock.patch.object(space, "relever_envois"), \
                mock.patch.object(space, "boite_envoi",
                                  return_value=os.path.join(dossier.name, "envoi")), \
                mock.patch.object(space, "espace_home", return_value=dossier.name), \
                mock.patch.object(space, "_flatpak_app_dans_espace", return_value=False), \
                mock.patch.object(space.permissions_flatpak, "lire_permissions",
                                  return_value=permissions), \
                mock.patch.object(space, "_prevenir") as prevenir, \
                mock.patch.object(space, "journal"), \
                mock.patch.object(space.subprocess, "Popen") as lancement:
            lancement.return_value.wait.return_value = 0
            lancement.return_value.pid = os.getpid()
            code = space.cmd_launch(self.ESPACES, "travail",
                                    ["flatpak", "run", "com.exemple.Editeur"])
        return code, prevenir, lancement

    def test_une_application_qui_sortirait_est_refusee_sans_etre_lancee(self):
        code, prevenir, lancement = self._lancer(pf.lire(EDITEUR_TOUT_TERRAIN))
        self.assertEqual(code, 1)
        lancement.assert_not_called()
        titre, message = prevenir.call_args[0]
        self.assertIn("ne s'ouvre pas dans Travail", titre)
        self.assertIn("Compte séparé", message)

    def test_des_permissions_illisibles_font_refuser(self):
        code, _prevenir, lancement = self._lancer(None)
        self.assertEqual(code, 1)
        lancement.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "marqueurs de processus Linux")
    def test_une_application_sage_s_ouvre(self):
        code, _prevenir, lancement = self._lancer(pf.lire(CALCULATRICE))
        self.assertEqual(code, 0)
        lancement.assert_called_once()


if __name__ == "__main__":
    unittest.main()
