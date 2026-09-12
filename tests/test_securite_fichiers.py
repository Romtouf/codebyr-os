"""Régressions reproduites dans des dossiers témoins, jamais sur les données réelles."""
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

import outils
import fichiers_surs
import modeles

space = outils.charger("codebyr-space")


@unittest.skipUnless(os.name == "posix", "Descripteurs Linux")
class Frontieres(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / "espaces"
        self.espaces = {e: {"id": e, "nom": e} for e in ("navigation", "travail")}
        self.addCleanup(patch.stopall)
        patch.object(space, "DATA_ROOT", str(self.data)).start()
        patch.object(space, "cmd_close", return_value=0).start()
        self.secret = self.root / "hote" / "secret"
        self.secret.parent.mkdir()
        self.secret.write_text("secret à préserver")

    def test_boite_symbolique_ne_deplace_pas_un_secret(self):
        boite = self.data / "navigation" / "envoi"
        boite.mkdir(parents=True)
        (boite / "travail").symlink_to(self.secret.parent, target_is_directory=True)
        self.assertEqual(space.relever_envois(self.espaces), 0)
        self.assertEqual(self.secret.read_text(), "secret à préserver")

    def test_fichier_symbolique_et_lien_dur_refuses(self):
        boite = self.data / "navigation" / "envoi" / "travail"
        boite.mkdir(parents=True)
        (boite / "lien").symlink_to(self.secret)
        os.link(self.secret, boite / "dur")
        self.assertEqual(space.relever_envois(self.espaces), 0)
        self.assertTrue(self.secret.exists())

    def test_destination_symbolique_refusee(self):
        boite = self.data / "navigation" / "envoi" / "travail"
        boite.mkdir(parents=True)
        (boite / "injection").write_text("attaque")
        home = self.data / "travail" / "home"
        home.mkdir(parents=True)
        (home / space.PARTAGE).symlink_to(self.secret.parent, target_is_directory=True)
        self.assertEqual(space.relever_envois(self.espaces), 0)
        self.assertFalse((self.secret.parent / "injection").exists())

    def test_ecriture_ne_tronque_pas_un_lien_dur(self):
        cible = self.root / "preferences"
        os.link(self.secret, cible)
        with fichiers_surs.ouvrir(cible, "w") as f:
            f.write("nouveau")
        self.assertEqual(self.secret.read_text(), "secret à préserver")
        self.assertEqual(cible.read_text(), "nouveau")

    def test_preferences_proxy_anciennes_remplacees(self):
        cible = self.root / "user.js"
        cible.write_text('user_pref("network.proxy.http_port", 17890);\n'
                         'user_pref("network.proxy.http_port", 45678);\n'
                         'user_pref("browser.startup.page", 0);\n')
        space._ajouter_prefs(str(cible), ['user_pref("network.proxy.http_port", 17890);'])
        texte = cible.read_text()
        self.assertNotIn("45678", texte)
        self.assertEqual(texte.count("network.proxy.http_port"), 1)
        self.assertIn("browser.startup.page", texte)

    def test_copie_exclusive_preserve_un_nom_occupe(self):
        cible = self.root / "reception"
        cible.mkdir()
        (cible / "document").write_text("original")
        nom = fichiers_surs.copier_unique(str(self.secret), str(cible), "document")
        self.assertEqual(nom, "document (2)")
        self.assertEqual((cible / "document").read_text(), "original")

    def test_fifo_refuse_sans_bloquer(self):
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        with self.assertRaises(OSError):
            with fichiers_surs.ouvrir(fifo):
                self.fail("Un FIFO ne doit pas être ouvert comme un document")

    def test_remplacement_du_parent_ne_redirige_pas_ecriture(self):
        dossier = self.root / "config"
        dossier.mkdir()
        with fichiers_surs.ouvrir(dossier / "injection", "w") as f:
            dossier.rename(self.root / "ancien")
            dossier.symlink_to(self.secret.parent, target_is_directory=True)
            f.write("test")
        self.assertFalse((self.secret.parent / "injection").exists())
        self.assertEqual((self.root / "ancien" / "injection").read_text(), "test")

    def test_modeles_ne_sortent_pas_du_home(self):
        home = self.root / "home"
        (home / ".config").mkdir(parents=True)
        src = self.root / "modeles"
        src.mkdir()
        (src / "injection").write_text("test")
        for declare in ("$HOME/../hote", str(self.secret.parent)):
            (home / ".config" / "user-dirs.dirs").write_text(
                'XDG_TEMPLATES_DIR="%s"' % declare)
            self.assertEqual(modeles.installer(str(home), str(src)), 0)
            self.assertFalse((self.secret.parent / "injection").exists())

    def test_archive_corrompue_preserve_donnees(self):
        home = self.data / "travail" / "home"
        home.mkdir(parents=True)
        (home / "document").write_text("original")
        archive = self.root / "invalide.tar.gz"
        archive.write_bytes(b"invalide")
        self.assertEqual(space.cmd_import(self.espaces, "travail", str(archive)), 1)
        self.assertEqual((home / "document").read_text(), "original")

    def test_flatpak_refuse_dans_un_espace_blinde(self):
        esp = {"travail": dict(self.espaces["travail"], couleur="#8F6CF0", blindage="renforce")}
        with patch.object(space.shutil, "which", return_value="/usr/bin/bwrap"), patch.object(
                space, "_prevenir"), patch.object(space.subprocess, "Popen") as lancement:
            self.assertEqual(space.cmd_launch(esp, "travail", ["flatpak", "run", "exemple.App"]), 1)
            lancement.assert_not_called()

    def test_disparition_de_bwrap_ne_cree_pas_de_repli(self):
        appels = []

        def disponible(nom):
            if nom == "bwrap":
                appels.append(nom)
                return "/usr/bin/bwrap" if len(appels) == 1 else None
            return None

        proc = Mock(pid=os.getpid())
        proc.wait.return_value = 0
        esp = {"travail": dict(self.espaces["travail"], couleur="#8F6CF0")}
        with patch.object(space.shutil, "which", side_effect=disponible), patch.object(
                space, "_rundir", return_value=str(self.root / "runtime")), patch.object(
                space.subprocess, "Popen", return_value=proc) as lancement:
            self.assertEqual(space.cmd_launch(esp, "travail", ["/usr/bin/true"]), 0)
            self.assertEqual(lancement.call_args.args[0][0], "bwrap")

    def test_jetable_indisponible_ne_declenche_pas_une_ouverture_normale(self):
        lancement = Mock(side_effect=OSError("indisponible"))
        with patch.object(space, "_espace_courant", return_value="travail"), patch.object(
                space.provenance, "origine", return_value="navigation"), patch.object(space, "_prevenir"):
            self.assertEqual(space.cmd_ouvrir(self.espaces, str(self.secret), lancement), 1)
            self.assertEqual(lancement.call_count, 1)

    def test_ouverture_normale_ne_rappelle_pas_son_association(self):
        lancement = Mock()
        with patch.object(space.provenance, "origine", return_value=None), patch.object(
                space, "_visionneuse_pour", return_value=["evince"]):
            self.assertEqual(space.cmd_ouvrir(self.espaces, str(self.secret), lancement), 0)
            lancement.assert_called_once_with(["evince", str(self.secret)])

    def test_archive_traversante_preserve_donnees(self):
        home = self.data / "travail" / "home"
        home.mkdir(parents=True)
        (home / "document").write_text("original")
        archive = self.root / "attaque.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            info = tarfile.TarInfo("../../injection")
            info.size = 1
            tar.addfile(info, io.BytesIO(b"x"))
        self.assertEqual(space.cmd_import(self.espaces, "travail", str(archive)), 1)
        self.assertEqual((home / "document").read_text(), "original")

    def test_restauration_valide_conserve_ancien_home(self):
        home = self.data / "travail" / "home"
        home.mkdir(parents=True)
        (home / "document").write_text("original")
        archive = self.root / "valide.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            info = tarfile.TarInfo("document")
            info.size = 1
            tar.addfile(info, io.BytesIO(b"x"))
        self.assertEqual(space.cmd_import(self.espaces, "travail", str(archive)), 0)
        self.assertEqual((home / "document").read_text(), "x")
        anciens = list(home.parent.glob("avant-restauration-*/document"))
        self.assertEqual(len(anciens), 1)
        self.assertEqual(anciens[0].read_text(), "original")


class EchecFerme(unittest.TestCase):
    def test_bwrap_absent_ne_lance_rien(self):
        with patch.object(space.shutil, "which", return_value=None), patch.object(
                space.subprocess, "Popen") as lancement:
            self.assertEqual(space.cmd_launch(
                {"jetable": {"id": "jetable", "nom": "Jetable"}}, "jetable", []), 1)
            lancement.assert_not_called()
