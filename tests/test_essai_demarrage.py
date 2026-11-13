# -*- coding: utf-8 -*-
"""L'essai de démarrage de l'image (CI) : inerte partout ailleurs."""
import os
import re
import unittest

from outils import RACINE

import comptes

LIVRE = os.path.join(RACINE, "live-build", "config", "includes.chroot_after_packages")
SERVICE = os.path.join(LIVRE, "usr", "lib", "systemd", "system", "codebyr-essai-demarrage.service")
SCRIPT = os.path.join(LIVRE, "usr", "libexec", "codebyr-essai-demarrage")
LANCEUR = os.path.join(RACINE, "tools", "essai_demarrage.sh")


def _lire(chemin):
    with open(chemin, encoding="utf-8") as f:
        return f.read()


class Inerte(unittest.TestCase):
    """Le service ne doit rien faire sur une vraie machine."""

    def test_reveille_par_la_seule_ligne_du_noyau(self):
        service = _lire(SERVICE)
        self.assertIn("ConditionKernelCommandLine=codebyr.essai=1", service)
        self.assertIn("ExecStart=/usr/libexec/codebyr-essai-demarrage", service)
        self.assertIn("codebyr.essai=1", _lire(LANCEUR))

    def test_ni_dans_le_paquet_ni_sur_le_systeme_installe(self):
        # Le paquet atteint toutes les machines : l'essai n'y a pas sa place.
        construction = _lire(os.path.join(RACINE, "packaging", "build-deb.sh"))
        self.assertNotIn("codebyr-essai-demarrage", construction)
        self.assertNotIn("usr/libexec", construction)
        nettoyage = _lire(os.path.join(LIVRE, "usr", "bin", "codebyr-nettoyage-installation"))
        self.assertIn("systemctl disable codebyr-essai-demarrage.service", nettoyage)
        for chemin in ("/usr/lib/systemd/system/codebyr-essai-demarrage.service",
                       "/usr/libexec/codebyr-essai-demarrage"):
            self.assertIn(chemin, nettoyage)

    def test_active_dans_l_image(self):
        crochet = _lire(os.path.join(RACINE, "live-build", "config", "hooks", "normal",
                                     "0950-essai-demarrage.hook.chroot"))
        self.assertIn("systemctl enable codebyr-essai-demarrage.service", crochet)
        self.assertIn("chmod 0755 /usr/libexec/codebyr-essai-demarrage", crochet)


class LeMicrocodeDeLImage(unittest.TestCase):
    """Construite sur une machine Intel, l'ISO n'avait aucun microcode AMD, et
    ne se reconstruisait plus à l'identique ailleurs (vu le 13/11/2026 : WSL
    sur Intel, GitHub sur AMD, deux initrd différents)."""

    def setUp(self):
        self.crochet = _lire(os.path.join(RACINE, "live-build", "config", "hooks", "normal",
                                          "9000-microcode-initrd.hook.chroot"))

    def test_les_deux_fabricants_quelle_que_soit_la_machine(self):
        self.assertIn('echo "AMD64UCODE_INITRAMFS=early" >> "$REGLAGE"', self.crochet)
        self.assertIn("update-initramfs -k all -t -u", self.crochet)

    def test_le_reglage_du_paquet_est_rendu_a_l_identique(self):
        # Modifié, il ferait poser une question à chaque mise à jour du
        # microcode — que la mise à jour automatique laisserait alors de côté.
        avant = self.crochet.index("cp -p \"$REGLAGE\" /tmp/codebyr-amd64-microcode")
        apres = self.crochet.index("cp -p /tmp/codebyr-amd64-microcode \"$REGLAGE\"")
        self.assertLess(avant, self.crochet.index("update-initramfs"))
        self.assertGreater(apres, self.crochet.index("update-initramfs"))

    def test_live_build_ne_la_refait_pas_derriere(self):
        self.assertTrue(self.crochet.rstrip().endswith("touch /initrd.img_has_already_been_regenerated"))

    def test_dernier_crochet(self):
        crochets = sorted(os.listdir(os.path.join(RACINE, "live-build", "config", "hooks", "normal")))
        self.assertEqual(crochets[-1], "9000-microcode-initrd.hook.chroot")


class LeVerdict(unittest.TestCase):

    def setUp(self):
        self.script = _lire(SCRIPT)
        self.lanceur = _lire(LANCEUR)

    def test_meme_langage_des_deux_cotes(self):
        for marque in ("CODEBYR-ESSAI OK", "CODEBYR-ESSAI ECHEC", "CODEBYR-ESSAI FIN"):
            self.assertIn(marque.split()[-1], self.script)
        self.assertIn('grep -aq "CODEBYR-ESSAI FIN"', self.lanceur)
        self.assertIn('grep -aq "CODEBYR-ESSAI ECHEC"', self.lanceur)
        # Une seule ligne de verdict par contrôle, et la fin toujours écrite.
        self.assertIn('ok() { echo "CODEBYR-ESSAI OK $*"; }', self.script)
        self.assertIn('ko() { echo "CODEBYR-ESSAI ECHEC $*"', self.script)
        self.assertTrue(self.script.rstrip().endswith("exit 0"))

    def test_ce_qui_est_observe(self):
        for controle in ("gnome-extensions info", "JS ERROR", "verifier-isolation",
                         "codebyr-space launch travail", "intel-microcode",
                         "qml6-module-qtquick", "VERSION_CODENAME"):
            self.assertIn(controle, self.script)

    def test_le_compte_de_l_espace_est_celui_du_service(self):
        compte = re.search(r"^compte=(\S+)$", self.script, re.M).group(1)
        self.assertEqual(compte, comptes.nom_compte(1000, "travail"))

    def test_un_port_serie_a_lui_seul(self):
        # Sur ttyS0, la console, systemd ouvre une invite de connexion qui
        # coupait la parole à l'essai (vu dans la CI, 13/11/2026).
        self.assertIn("TTYPath=/dev/ttyS1", _lire(SERVICE))
        self.assertIn('-serial file:"$console" -serial file:"$journal"', self.lanceur)

    def test_lance_par_la_ci_hors_du_conteneur(self):
        flux = _lire(os.path.join(RACINE, ".github", "workflows", "construire-iso.yml"))
        job = flux.split("\n  demarrage:\n", 1)[1]
        self.assertIn("needs: iso", job)
        self.assertIn("bash tools/essai_demarrage.sh dist/*.iso", job)
        self.assertNotIn("container:", job)
        self.assertIn("/dev/kvm", self.lanceur)


if __name__ == "__main__":
    unittest.main()
