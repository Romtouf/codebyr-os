# -*- coding: utf-8 -*-
"""Disque chiffré : l'identité du système et l'espace d'échange.

Deux défauts constatés sur une installation neuve, le 28 septembre 2026 :

· à chaque démarrage, deux erreurs « cryptsetup » faisaient croire à une
  phrase de passe refusée. C'était l'espace d'échange, chiffré à part par
  l'installeur, qu'il prévoyait d'ouvrir avec un fichier de clé jamais créé
  (/boot séparé et en clair). Il ne s'ouvrait donc jamais : aucune machine
  chiffrée n'avait d'espace d'échange depuis la 1.13.0 ;
· la déviation de /usr/lib/os-release DÉPLAÇAIT un fichier du paquet
  « Essential » base-files, ce que dpkg signalait comme dangereux.

Les réparations ont été éprouvées sur un vrai disque LUKS de test et sur le
cycle de vie complet du paquet. Ces tests gardent leurs règles, lues dans le
code : ce qui les ferait tomber n'échouerait pas bruyamment, mais sur la
machine de quelqu'un, au démarrage.
"""
import os
import re
import unittest

from outils import BIN, RACINE

CALAMARES = os.path.join(RACINE, "live-build", "config",
                         "includes.chroot_after_packages", "etc", "calamares", "modules")


def _lire(*morceaux):
    with open(os.path.join(*morceaux), encoding="utf-8") as f:
        return f.read()


class LEspaceDEchange(unittest.TestCase):

    def setUp(self):
        self.durcir = _lire(BIN, "codebyr-durcir-poste")
        self.reparation = self.durcir.split("# ── 3) Espace d'échange chiffré")[1]

    def test_elle_ne_vise_que_la_signature_exacte_du_defaut(self):
        # « none » + « keyscript=/bin/cat » : une clé attendue, jamais créée.
        self.assertIn('[ "$cle" = "none" ] || continue', self.reparation)
        self.assertIn("*,keyscript=/bin/cat,*", self.reparation)

    def test_chaque_garde_fou_est_la(self):
        for garde in ('= "crypto_LUKS" ] || continue',          # un volume LUKS
                      '$1 == d && $3 == "swap"',                 # fstab : échange
                      "if tenue_ailleurs",                       # rien ne la tient
                      "PARTUUID"):                               # repère stable
            self.assertIn(garde, self.reparation, garde)

    def test_la_ligne_produite_est_une_cle_jetable(self):
        self.assertIn("/dev/urandom plain,cipher=aes-xts-plain64,size=512,swap,discard",
                      self.reparation)

    def test_le_disque_principal_n_est_jamais_touche(self):
        # La seule réécriture de crypttab porte sur la ligne dont le NOM est
        # celui de l'espace d'échange retenu ; le reste est recopié tel quel.
        self.assertIn('$1 == n { print n " PARTUUID="', self.reparation)
        self.assertIn("{ print }", self.reparation)

    def test_seules_les_signatures_luks_de_cette_partition_sont_effacees(self):
        effacements = re.findall(r"wipefs[^\n]*", self.reparation)
        self.assertEqual(len(effacements), 1)
        self.assertIn("-t crypto_LUKS", effacements[0])
        self.assertIn('"$partition"', effacements[0])

    def test_la_reprise_est_retiree_du_demarrage(self):
        self.assertIn("RESUME=none", self.reparation)
        self.assertIn("resume=/dev/mapper/$nom", self.reparation)
        self.assertIn("update-grub", self.reparation)

    def test_pendant_l_installation_calamares_regenere_seul_l_image(self):
        self.assertIn('"${CODEBYR_INSTALLATION:-0}" != "1"', self.reparation)
        nettoyage = _lire(BIN, "codebyr-nettoyage-installation")
        self.assertIn("CODEBYR_INSTALLATION=1 sh /usr/bin/codebyr-durcir-poste", nettoyage)

    def test_l_etape_calamares_a_le_temps_de_regenerer_grub(self):
        delai = re.search(r"^timeout:\s*(\d+)", _lire(CALAMARES, "shellprocess-codebyr.conf"),
                          re.MULTILINE)
        self.assertGreaterEqual(int(delai.group(1)), 300)

    def test_le_script_ne_peut_pas_echouer(self):
        # Un postinst qui sort en erreur bloque la mise à jour de tout le parc.
        self.assertTrue(self.durcir.rstrip().endswith("exit 0"))
        for commande in ("update-grub", "update-initramfs -u -k all"):
            # L'appel lui-même (en début de ligne), suivi d'un « || » de secours.
            appel = re.search(r"\n\s*%s >/dev/null 2>&1 \\\n\s*\|\|" % re.escape(commande),
                              self.reparation)
            self.assertIsNotNone(appel, commande)


class CeQuiOuvreLEspaceDEchange(unittest.TestCase):
    """Sans systemd-cryptsetup, personne n'ouvre /etc/crypttab au démarrage.

    La réparation de l'espace d'échange était juste, et restait sans effet :
    le paquet manquait (Debian 13 l'a sorti de systemd), et chaque démarrage
    attendait l'espace d'échange 90 secondes avant d'abandonner.
    """

    def test_le_paquet_en_depend(self):
        depends = re.search(r"^Depends: (.*)$", _lire(RACINE, "packaging", "build-deb.sh"),
                            re.MULTILINE).group(1)
        self.assertIn("systemd-cryptsetup", [d.strip() for d in depends.split(",")])

    def test_l_image_l_embarque(self):
        liste = _lire(RACINE, "live-build", "config", "package-lists", "codebyr.list.chroot")
        self.assertIn("systemd-cryptsetup", liste.split())


class LaDeviationDeLIdentite(unittest.TestCase):

    def setUp(self):
        self.preinst = _lire(RACINE, "packaging", "codebyr-tools.preinst")
        self.postrm = _lire(RACINE, "packaging", "codebyr-tools.postrm")

    def test_le_fichier_de_base_files_n_est_jamais_deplace(self):
        for script in (self.preinst, self.postrm):
            # Le code seul : les commentaires expliquent justement « --rename ».
            code = "\n".join(l for l in script.splitlines() if not l.lstrip().startswith("#"))
            appels = re.findall(r"dpkg-divert --package[^\n]*\\\n[^\n]*", code)
            self.assertTrue(appels)
            for appel in appels:
                self.assertIn("--no-rename", appel)
                self.assertNotIn(" --rename", appel)

    def test_la_copie_n_est_faite_qu_a_la_creation_de_la_deviation(self):
        # Ensuite, /usr/lib/os-release est celui de Codebyr : le recopier
        # écraserait la copie de base-files par celle de Codebyr.
        garde = 'if [ "$(dpkg-divert --listpackage /usr/lib/os-release)" != "codebyr-tools" ]'
        self.assertIn(garde, self.preinst)
        self.assertLess(self.preinst.index(garde), self.preinst.index("cp -a /usr/lib/os-release"))

    def test_au_retrait_la_copie_revient_avant_la_levee(self):
        retour = self.postrm.index("mv -f /usr/lib/os-release.codebyr-retour /usr/lib/os-release")
        levee = self.postrm.index("--remove --no-rename")
        self.assertLess(retour, levee)


if __name__ == "__main__":
    unittest.main()
