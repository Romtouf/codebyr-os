# -*- coding: utf-8 -*-
"""Le compte invité : aucun groupe qui donne du matériel ou le réseau.

Jusqu'à la 1.19.0, l'image le mettait dans audio, video, plugdev et netdev.
Sous Debian, une règle polkit de NetworkManager donne à netdev le droit de
modifier les connexions réseau de la machine sans mot de passe : l'invité
pouvait changer le DNS du Wi-Fi du propriétaire, et cela survivait à sa
session. audio et video ouvraient micro et caméra depuis une session laissée
en arrière-plan. Ce que ces groupes donnent, logind l'accorde déjà à la
session ACTIVE (analyse externe du 01/10/2026, vérifiée sur le système de
l'ISO 1.18.2).

Le rattrapage des machines installées est joué pour de vrai (vrai gpasswd)
dans une copie privée de /etc, quand le test tourne en root sous Linux.
"""
import os
import shutil
import subprocess
import tempfile
import unittest

from outils import BIN, LIB, RACINE  # noqa: F401 — place le module partagé sur sys.path
import autotest  # noqa: E402

INTERDITS = {"netdev", "audio", "video", "plugdev"}


def _lire(chemin):
    with open(chemin, encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n")


class LeVerificateurDuPoste(unittest.TestCase):

    def test_chaque_groupe_interdit_est_signale(self):
        self.assertEqual(set(autotest.GROUPES_INTERDITS_INVITE), INTERDITS)
        for groupe in sorted(INTERDITS):
            ok, detail = autotest.analyser_groupes_invite(["invite", groupe])
            self.assertFalse(ok, groupe)
            self.assertIn(groupe, detail)

    def test_sans_groupe_c_est_conforme(self):
        self.assertTrue(autotest.analyser_groupes_invite([])[0])
        self.assertTrue(autotest.analyser_groupes_invite(["invite"])[0])

    def test_pas_d_invite_pas_d_anomalie(self):
        self.assertTrue(autotest.analyser_groupes_invite(None)[0])

    def test_le_controle_est_affiche(self):
        self.assertIn("groupes_invite", dict(autotest.LIBELLES))


class LImage(unittest.TestCase):

    def test_l_invite_est_cree_sans_groupe_supplementaire(self):
        hook = _lire(os.path.join(RACINE, "live-build", "config", "hooks", "normal",
                                  "0400-invite.hook.chroot"))
        code = "\n".join(l for l in hook.splitlines() if not l.lstrip().startswith("#"))
        creation = code.split("useradd", 1)[1].split("invite\n", 1)[0]
        self.assertNotIn("--groups", creation)
        self.assertNotIn("-G", creation)
        for groupe in INTERDITS:
            self.assertNotIn(groupe, creation)


SCRIPT = os.path.join(BIN, "codebyr-durcir-poste")


def _boucle_de_rattrapage():
    texte = _lire(SCRIPT)
    debut = texte.index("\tfor groupe in netdev audio video plugdev; do")
    fin = texte.index("\tdone\n", debut) + len("\tdone\n")
    return texte[debut:fin]


class LeRattrapage(unittest.TestCase):

    def test_les_quatre_groupes_sont_quittes(self):
        boucle = _boucle_de_rattrapage()
        for groupe in INTERDITS:
            self.assertIn(groupe, boucle.split("\n", 1)[0])
        self.assertIn('gpasswd -d invite "$groupe"', boucle)

    def test_dans_la_section_de_l_invite(self):
        texte = _lire(SCRIPT)
        section = texte.index("if id invite >/dev/null 2>&1; then")
        self.assertLess(section, texte.index(_boucle_de_rattrapage()))


@unittest.skipUnless(os.environ.get("CODEBYR_TEST_LINUX") == "1" and hasattr(os, "geteuid")
                     and os.geteuid() == 0 and shutil.which("unshare")
                     and shutil.which("gpasswd") and shutil.which("useradd"),
                     "root sous Linux, unshare et les outils de comptes")
class LeRattrapageReel(unittest.TestCase):
    """La boucle du script, exécutée avec le vrai gpasswd, sur une copie de
    /etc montée par-dessus l'originale dans un espace de montage privé : la
    machine qui fait le test n'est pas touchée."""

    def test_l_invite_sort_des_groupes_et_garde_le_sien(self):
        dossier = tempfile.mkdtemp(prefix="codebyr-invite-")
        self.addCleanup(shutil.rmtree, dossier, True)
        preparation = (
            'set -e\n'
            'cp -a /etc "$1/etc"\n'
            'mount --make-rprivate /\n'
            'mount --bind "$1/etc" /etc\n'
            'for g in netdev audio video plugdev; do groupadd -f "$g"; done\n'
            'id invite >/dev/null 2>&1 || useradd -M -U -s /bin/sh invite\n'
            'usermod -aG netdev,audio,video,plugdev invite\n'
            'echo "AVANT $(id -nG invite)"\n'
            + _boucle_de_rattrapage() +
            'echo "APRES $(id -nG invite)"\n')
        resultat = subprocess.run(["unshare", "--mount", "sh", "-c", preparation, "_", dossier],
                                  capture_output=True, text=True, timeout=60)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        lignes = dict(l.split(" ", 1) for l in resultat.stdout.splitlines()
                      if l.startswith(("AVANT ", "APRES ")))
        self.assertTrue(INTERDITS <= set(lignes["AVANT"].split()), resultat.stdout)
        self.assertEqual(set(lignes["APRES"].split()) & INTERDITS, set(), resultat.stdout)
        self.assertIn("invite", lignes["APRES"].split())
        for groupe in INTERDITS:
            self.assertIn("le compte invité quitte le groupe « %s »" % groupe, resultat.stdout)


if __name__ == "__main__":
    unittest.main()
