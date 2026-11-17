# -*- coding: utf-8 -*-
"""La sauvegarde chiffrée : ce qui sort de la machine ne livre rien.

Le vrai gpg est appelé : un chiffrement qu'on ne voit pas déchiffrer n'est
pas une sauvegarde.
"""
import os
import shutil
import subprocess
import tempfile
import time
import unittest

import outils
from outils import BIN, LIB, RACINE

import sauvegarde

PHRASE = "correct cheval pile agrafe"


def _lire(chemin, mode="r"):
    with open(chemin, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as f:
        return f.read()


class LaPhraseDePasse(unittest.TestCase):

    def test_un_plancher_de_longueur(self):
        self.assertFalse(sauvegarde.phrase_acceptable("court")[0])
        self.assertFalse(sauvegarde.phrase_acceptable("")[0])
        self.assertTrue(sauvegarde.phrase_acceptable("x" * sauvegarde.PHRASE_MINIMALE)[0])
        self.assertGreaterEqual(sauvegarde.PHRASE_MINIMALE, 12)

    def test_pas_de_saut_de_ligne(self):
        # Elle voyage sur une ligne (entrée standard, tube) : la suite serait
        # perdue en silence, et la sauvegarde chiffrée par une autre phrase.
        self.assertFalse(sauvegarde.phrase_acceptable("douze caracteres\nau moins")[0])

    def test_jamais_sur_la_ligne_de_commande(self):
        # Une ligne de commande se lit par tous les comptes (/proc/<pid>/cmdline).
        for operation in ("chiffrer", "dechiffrer"):
            ligne = sauvegarde.commande(operation, 7, "/tmp/s", "/tmp/g")
            self.assertEqual(ligne[ligne.index("--passphrase-fd") + 1], "7")
            self.assertNotIn("--passphrase", ligne)
            self.assertIn("--no-symkey-cache", ligne)

    def test_chiffrement_fort(self):
        ligne = sauvegarde.commande("chiffrer", 7, "/tmp/s", "/tmp/g")
        self.assertEqual(ligne[ligne.index("--cipher-algo") + 1], "AES256")
        self.assertEqual(ligne[ligne.index("--s2k-mode") + 1], "3")
        self.assertEqual(ligne[ligne.index("--s2k-count") + 1], "65011712")


class LesNoms(unittest.TestCase):

    def test_le_dossier_porte_sa_date(self):
        instant = time.struct_time((2026, 11, 17, 9, 5, 0, 1, 321, 0))
        self.assertEqual(sauvegarde.nom_du_dossier(instant), "Sauvegarde-Codebyr-20261117-0905")

    def test_l_espace_se_lit_dans_le_nom_du_fichier(self):
        self.assertEqual(sauvegarde.espace_du_fichier("/media/cle/S/coffre.tar.gz.gpg"), "coffre")
        self.assertIsNone(sauvegarde.espace_du_fichier("/media/cle/S/reglages.json.gpg"))
        # Un nom qu'aucun Espace ne peut porter n'en désigne aucun.
        self.assertIsNone(sauvegarde.espace_du_fichier("/x/.tar.gz.gpg"))
        self.assertIsNone(sauvegarde.espace_du_fichier("/x/Mon Espace.tar.gz.gpg"))
        # Seul le nom du fichier compte, jamais le chemin qui y mène.
        self.assertEqual(sauvegarde.espace_du_fichier("/x/../../travail.tar.gz.gpg"), "travail")


@unittest.skipUnless(shutil.which("gpg"), "gpg absent : le chiffrement ne peut pas être éprouvé")
class LeChiffrement(unittest.TestCase):

    def setUp(self):
        self.dossier = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)
        self.archive = os.path.join(self.dossier, "coffre.tar.gz.gpg")
        self.clair = b"secret du coffre\n" * 4000

    def _chiffrer(self):
        with sauvegarde.Chiffrement(self.archive, PHRASE) as flux:
            flux.write(self.clair)

    def test_aller_et_retour(self):
        self._chiffrer()
        chiffre = _lire(self.archive, "rb")
        self.assertNotIn(b"secret du coffre", chiffre)
        sortie = os.path.join(self.dossier, "clair")
        sauvegarde.dechiffrer(self.archive, PHRASE, sortie)
        self.assertEqual(_lire(sortie, "rb"), self.clair)

    def test_se_relit_sans_codebyr(self):
        # Aucun format maison : le gpg de n'importe quel Linux suffit.
        self._chiffrer()
        gpg = tempfile.mkdtemp(dir=self.dossier)
        r = subprocess.run(["gpg", "--batch", "--quiet", "--homedir", gpg, "--pinentry-mode",
                            "loopback", "--passphrase", PHRASE, "-d", self.archive],
                           capture_output=True)
        subprocess.run(["gpgconf", "--homedir", gpg, "--kill", "all"], capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, self.clair)

    def test_une_mauvaise_phrase_ne_rend_rien(self):
        self._chiffrer()
        sortie = os.path.join(self.dossier, "clair")
        with self.assertRaises(sauvegarde.Echec):
            sauvegarde.dechiffrer(self.archive, "une autre phrase de passe", sortie)
        self.assertFalse(os.path.exists(sortie))

    def test_une_archive_alteree_est_refusee(self):
        self._chiffrer()
        octets = bytearray(_lire(self.archive, "rb"))
        octets[len(octets) // 2] ^= 0x55
        with open(self.archive, "wb") as f:
            f.write(octets)
        sortie = os.path.join(self.dossier, "clair")
        with self.assertRaises(sauvegarde.Echec):
            sauvegarde.dechiffrer(self.archive, PHRASE, sortie)
        self.assertFalse(os.path.exists(sortie))

    def test_une_sauvegarde_interrompue_ne_laisse_rien(self):
        with self.assertRaises(RuntimeError):
            with sauvegarde.Chiffrement(self.archive, PHRASE) as flux:
                flux.write(b"debut")
                raise RuntimeError("support retiré")
        self.assertEqual(os.listdir(self.dossier), [])

    def test_un_support_impossible_est_un_echec_dit(self):
        ailleurs = os.path.join(self.dossier, "absent", "x.tar.gz.gpg")
        with self.assertRaises(sauvegarde.Echec):
            with sauvegarde.Chiffrement(ailleurs, PHRASE) as flux:
                flux.write(self.clair)

    def test_aucun_trousseau_ne_reste(self):
        avant = set(os.listdir(tempfile.gettempdir()))
        self._chiffrer()
        apres = {n for n in os.listdir(tempfile.gettempdir()) if n.startswith("codebyr-gpg-")}
        self.assertEqual(apres - avant, set())


@unittest.skipUnless(shutil.which("gpg") and hasattr(os, "O_NOFOLLOW") and os.supports_dir_fd,
                     "gpg et accès disque par descripteurs — Linux")
class DeBoutEnBout(unittest.TestCase):
    """codebyr-space sauvegarder, puis restaurer-sauvegarde, sur un Espace ordinaire."""

    ESPACES = {"travail": {"id": "travail", "nom": "Travail"},
               "jetable": {"id": "jetable", "nom": "Jetable", "ephemere": True}}

    def setUp(self):
        import chemins
        import registre
        self.space = outils.charger("codebyr-space")
        self.base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.base, True)
        self.addCleanup(setattr, chemins, "DONNEES", chemins.DONNEES)
        chemins.DONNEES = os.path.join(self.base, "espaces")
        self.home = os.path.join(chemins.DONNEES, "travail", "home")
        os.makedirs(self.home)
        with open(os.path.join(self.home, "notes.txt"), "w", encoding="utf-8") as f:
            f.write("ce que je veux retrouver")
        self.cle = os.path.join(self.base, "cle-usb")
        os.mkdir(self.cle)
        # Les réglages de l'utilisateur, et un dossier de travail à nous.
        self.addCleanup(setattr, registre, "couche", registre.couche)
        registre.couche = lambda: {"espaces": [{"id": "achats", "nom": "Achats",
                                                "couleur": "#43C7DF"}], "apps": []}
        self.addCleanup(setattr, self.space, "_dossier_de_travail", self.space._dossier_de_travail)
        self.space._dossier_de_travail = lambda: tempfile.mkdtemp(dir=self.base)
        self.addCleanup(setattr, self.space, "cmd_close", self.space.cmd_close)
        self.space.cmd_close = lambda espaces, esp_id: 0

    def _avec_phrase(self, phrase, fonction, *args):
        import io as io_
        import sys
        entree, sortie, erreurs = sys.stdin, sys.stdout, sys.stderr
        sys.stdin, sys.stdout, sys.stderr = io_.StringIO(phrase + "\n"), io_.StringIO(), io_.StringIO()
        try:
            return fonction(*args), sys.stderr.getvalue()
        finally:
            sys.stdin, sys.stdout, sys.stderr = entree, sortie, erreurs

    def _sauvegarder(self):
        code, _erreurs = self._avec_phrase(PHRASE, self.space.cmd_sauvegarder, self.ESPACES, self.cle)
        self.assertEqual(code, 0)
        dossier = os.path.join(self.cle, os.listdir(self.cle)[0])
        return dossier

    def test_la_sauvegarde_ne_contient_rien_en_clair(self):
        dossier = self._sauvegarder()
        self.assertTrue(os.path.basename(dossier).startswith("Sauvegarde-Codebyr-"))
        # Le Jetable n'a rien à garder ; les réglages et le mode d'emploi suivent.
        self.assertEqual(sorted(os.listdir(dossier)),
                         ["LISEZ-MOI.txt", "reglages.json.gpg", "travail.tar.gz.gpg"])
        for nom in ("travail.tar.gz.gpg", "reglages.json.gpg"):
            contenu = _lire(os.path.join(dossier, nom), "rb")
            for clair in (b"ce que je veux retrouver", b"notes.txt", b"Achats"):
                self.assertNotIn(clair, contenu)
        self.assertIn("gpg -d", _lire(os.path.join(dossier, "LISEZ-MOI.txt")))

    def test_ce_qui_est_sauvegarde_revient(self):
        dossier = self._sauvegarder()
        os.unlink(os.path.join(self.home, "notes.txt"))
        with open(os.path.join(self.home, "apres.txt"), "w", encoding="utf-8") as f:
            f.write("écrit après la sauvegarde")
        code, erreurs = self._avec_phrase(PHRASE, self.space.cmd_restaurer_sauvegarde, self.ESPACES,
                                          os.path.join(dossier, "travail.tar.gz.gpg"))
        self.assertEqual(code, 0, erreurs)
        self.assertEqual(_lire(os.path.join(self.home, "notes.txt")), "ce que je veux retrouver")
        self.assertNotIn("apres.txt", os.listdir(self.home))
        # Et l'état d'avant la restauration est gardé de côté, pas détruit.
        cote = [n for n in os.listdir(os.path.dirname(self.home)) if n.startswith("avant-restauration-")]
        self.assertEqual(len(cote), 1)

    def test_une_mauvaise_phrase_ne_touche_a_rien(self):
        dossier = self._sauvegarder()
        with open(os.path.join(self.home, "notes.txt"), "w", encoding="utf-8") as f:
            f.write("état actuel")
        code, erreurs = self._avec_phrase("pas la bonne phrase de passe",
                                          self.space.cmd_restaurer_sauvegarde, self.ESPACES,
                                          os.path.join(dossier, "travail.tar.gz.gpg"))
        self.assertEqual(code, 1)
        self.assertEqual(_lire(os.path.join(self.home, "notes.txt")), "état actuel")
        # Rien de déchiffré ne traîne.
        self.assertEqual([n for n in os.listdir(self.base) if n.startswith("tmp")], [])

    def test_une_phrase_trop_courte_est_refusee_avant_tout(self):
        code, erreurs = self._avec_phrase("court", self.space.cmd_sauvegarder, self.ESPACES, self.cle)
        self.assertEqual(code, 2)
        self.assertEqual(os.listdir(self.cle), [])

    def test_un_espace_cree_par_l_utilisateur_revient_avec_sa_sauvegarde(self):
        import registre
        ajoutes = []
        self.addCleanup(setattr, registre, "ajouter_espace", registre.ajouter_espace)
        registre.ajouter_espace = ajoutes.append
        dossier = self._sauvegarder()
        shutil.copy(os.path.join(dossier, "travail.tar.gz.gpg"),
                    os.path.join(dossier, "achats.tar.gz.gpg"))
        travail = tempfile.mkdtemp(dir=self.base)
        self.assertTrue(self.space._recreer_espace(
            os.path.join(dossier, "achats.tar.gz.gpg"), "achats", PHRASE, travail))
        # Recréé comme à la création : sous son propre compte, rien d'autre repris.
        self.assertEqual(ajoutes, [{"id": "achats", "nom": "Achats", "couleur": "#43C7DF",
                                    "app": "org.gnome.Nautilus.desktop", "ephemere": False,
                                    "compte": "dedie"}])
        self.assertFalse(self.space._recreer_espace(
            os.path.join(dossier, "achats.tar.gz.gpg"), "inconnu", PHRASE, travail))
        self.assertFalse(self.space._recreer_espace(
            os.path.join(dossier, "achats.tar.gz.gpg"), "achats", "mauvaise phrase de passe", travail))


class LeBranchement(unittest.TestCase):

    def test_la_phrase_n_est_jamais_un_argument(self):
        source = _lire(os.path.join(BIN, "codebyr-space"))
        self.assertIn("return sys.stdin.readline()", source)
        for action in ("sauvegarder", "restaurer-sauvegarde"):
            usage = outils.charger("codebyr-space").ACTIONS[action][1]
            self.assertIn("entrée standard", usage)

    def test_le_dechiffrement_passe_par_le_disque_pas_par_la_memoire(self):
        # /tmp est en mémoire vive : une archive de plusieurs gigaoctets n'y tient pas.
        source = _lire(os.path.join(BIN, "codebyr-space"))
        corps = source.split("def _dossier_de_travail():", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('".cache", "codebyr"', corps)
        self.assertIn("mode=0o700", corps)

    def test_la_configuration_passe_la_phrase_par_l_entree_standard(self):
        config = _lire(os.path.join(BIN, "codebyr-config"))
        lancer = config.split("    def _lancer(self, commande, phrase, reussi, rate):", 1)[1]
        lancer = lancer.split("\n    def ", 1)[0]
        self.assertIn('proc.communicate_utf8_async(phrase + "\\n", None, fini)', lancer)
        for appel in ('["codebyr-space", "sauvegarder", dossier]',
                      '["codebyr-space", "restaurer-sauvegarde", chemin]'):
            self.assertIn(appel, config)

    def test_la_phrase_d_une_sauvegarde_se_tape_deux_fois(self):
        # Une faute de frappe rendrait la sauvegarde irrécupérable.
        config = _lire(os.path.join(BIN, "codebyr-config"))
        corps = config.split("    def _demander_phrase(", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("seconde.get_text() == phrase", corps)
        self.assertIn("sauvegarde.phrase_acceptable(phrase)", corps)
        self.assertIn('set_response_enabled("valider"', corps)

    def test_gpg_est_exige_par_le_paquet(self):
        import re
        depend = re.search(r"^Depends: (.*)$",
                           _lire(os.path.join(RACINE, "packaging", "build-deb.sh")), re.M).group(1)
        self.assertIn("gpg", [d.strip() for d in depend.split(",")])
        self.assertTrue(os.path.isfile(os.path.join(LIB, "sauvegarde.py")))


if __name__ == "__main__":
    unittest.main()
