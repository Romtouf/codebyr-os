# -*- coding: utf-8 -*-
"""Le filtre réseau confiné par AppArmor — et confiné pour de vrai.

Le filtre (codebyr-net-proxy) est le seul programme qui parle au réseau pour
le compte d'un Espace restreint, depuis l'hôte. Son profil réduit ce qu'une
faille dans son analyse des requêtes donnerait à un attaquant.

Un profil AppArmor se dégrade sans bruit : une règle trop large ajoutée
« pour que ça marche », une abstraction commode qui ouvre le dossier
personnel, un profil qui ne se charge plus et laisse le programme libre. Ces
tests gardent chacune de ces portes fermées.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from outils import BIN, ETC, RACINE, charger

PROFIL = os.path.join(ETC, "apparmor.d", "codebyr-net-proxy")
FILTRE = os.path.join(BIN, "codebyr-net-proxy")
PARSEUR = "/usr/sbin/apparmor_parser"


def _lire(chemin):
    with open(chemin, encoding="utf-8") as f:
        return f.read()


def _regles():
    """Les lignes de règles du profil, sans commentaires ni lignes vides."""
    regles = []
    for ligne in _lire(PROFIL).splitlines():
        ligne = ligne.split("#", 1)[0].strip() if not ligne.lstrip().startswith("#") else ""
        if ligne:
            regles.append(ligne)
    return regles


class Rattachement(unittest.TestCase):

    def test_le_profil_s_attache_au_filtre_installe(self):
        self.assertRegex(_lire(PROFIL),
                         r"(?m)^profile codebyr-net-proxy /usr/bin/codebyr-net-proxy \{")

    def test_le_filtre_est_un_script_lance_directement(self):
        # AppArmor rattache un script lancé directement au chemin du SCRIPT.
        # Lancé en « python3 /usr/bin/codebyr-net-proxy », il serait rattaché à
        # l'interpréteur — et le profil ne s'appliquerait jamais.
        source = _lire(os.path.join(BIN, "codebyr-space"))
        self.assertIn('subprocess.Popen(["codebyr-net-proxy", "--fd"', source)


class PythonSansDossierPersonnel(unittest.TestCase):
    """Un .pth dans ~/.local/lib/python3.* est exécuté au démarrage de Python."""

    def test_le_filtre_demarre_en_mode_isole(self):
        self.assertEqual(_lire(FILTRE).splitlines()[0], "#!/usr/bin/python3 -IS")

    def test_l_abstraction_python_standard_n_est_pas_incluse(self):
        # Elle autorise ~/.local/lib/python3.* : précisément ce qu'on refuse.
        self.assertNotIn("abstractions/python", _lire(PROFIL))

    def test_aucune_bibliotheque_python_du_dossier_personnel(self):
        for regle in _regles():
            self.assertNotRegex(regle, r"@\{HOME\}.*python", regle)


class CeQueLeFiltrePeutFaire(unittest.TestCase):

    def test_aucune_capacite_ni_changement_de_profil(self):
        for regle in _regles():
            self.assertFalse(regle.startswith("capability"), regle)
            # ux/Ux : exécuter hors confinement ; px/cx : passer à un autre
            # profil. Seul « ix » (l'interpréteur, dans CE profil) est admis.
            self.assertNotRegex(regle, r"\s[a-z]*[uUpPcC]x,$", regle)

    def test_seul_l_interpreteur_peut_etre_execute(self):
        executables = [r for r in _regles() if re.search(r"\s[a-z]*ix,$", r)]
        self.assertEqual(executables, ["/usr/bin/python3.[0-9]* rix,"])

    def test_le_seul_fichier_ecrit_est_le_journal_des_refus(self):
        ecritures = [r for r in _regles()
                     if not r.startswith(("deny", "include", "unix", "network",
                                          "signal", "ptrace", "profile", "abi"))
                     and re.search(r"\s[rmk]*[wa][rmk]*,$", r)]
        self.assertEqual(ecritures, [
            "owner @{HOME}/.local/share/codebyr/espaces/*/domaines-refuses.txt w,",
            "owner /dev/pts/[0-9]* rw,",
        ])

    def test_le_chemin_du_journal_suit_la_convention_de_codebyr_space(self):
        space = charger("codebyr-space")
        chemin = space.journal_refus("banque")
        attendu = os.path.join(os.path.expanduser("~"), ".local", "share",
                               "codebyr", "espaces", "banque", "domaines-refuses.txt")
        self.assertEqual(chemin, attendu,
                         "codebyr-space a changé de convention : le profil "
                         "AppArmor n'autoriserait plus l'écriture du journal")

    def test_la_socket_heritee_est_acceptee_sans_pouvoir_en_creer(self):
        unix = [r for r in _regles() if r.startswith("unix")]
        self.assertEqual(len(unix), 1)
        self.assertIn("accept", unix[0])
        for interdit in ("create", "bind", "connect", "listen"):
            self.assertNotIn(interdit, unix[0])

    def test_le_filtre_accepte_d_etre_arrete(self):
        # Sans cette règle, un filtre confiné refuserait le SIGTERM de
        # codebyr-space et survivrait à chaque fermeture de Banque.
        self.assertIn("signal (receive) set=(term, kill, int, hup) peer=unconfined,",
                      _regles())


class Livraison(unittest.TestCase):

    def test_livre_par_le_paquet(self):
        self.assertIn("etc/apparmor.d/codebyr-net-proxy",
                      _lire(os.path.join(RACINE, "packaging", "build-deb.sh")))

    def test_charge_des_la_mise_a_jour_par_chemins_absolus(self):
        postinst = _lire(os.path.join(RACINE, "packaging", "codebyr-tools.postinst"))
        self.assertIn("/usr/sbin/apparmor_parser --replace", postinst)
        self.assertIn("/usr/bin/aa-enabled", postinst)
        self.assertNotIn("command -v apparmor_parser", postinst)


@unittest.skipUnless(os.path.exists(PARSEUR) and os.path.isdir("/etc/apparmor.d/abstractions"),
                     "compilateur AppArmor absent")
class Compilation(unittest.TestCase):
    """Un profil qui ne compile pas n'est jamais chargé : le filtre tourne
    alors NON confiné, et rien ne le signale à l'utilisateur."""

    def _compiler(self, chemin):
        return subprocess.run(
            [PARSEUR, "--skip-kernel-load", "--skip-cache", "-I", "/etc/apparmor.d", chemin],
            capture_output=True, text=True, timeout=60)

    def test_le_profil_compile(self):
        with tempfile.TemporaryDirectory() as d:
            copie = shutil.copy(PROFIL, os.path.join(d, "codebyr-net-proxy"))
            r = self._compiler(copie)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_le_controle_detecte_un_profil_casse(self):
        with tempfile.TemporaryDirectory() as d:
            casse = os.path.join(d, "casse")
            with open(casse, "w", encoding="utf-8") as f:
                f.write(_lire(PROFIL).replace("network inet stream,", "network inet stream"))
            self.assertNotEqual(self._compiler(casse).returncode, 0)


if __name__ == "__main__":
    unittest.main()
