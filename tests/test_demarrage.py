# -*- coding: utf-8 -*-
"""Le démarrage sans couture : du logo du fabricant à celui de Codebyr.

Mesuré le 01/10/2026 sur la VM : GRUB montrait son menu 5 secondes à chaque
démarrage, pour un seul système ; puis « Loading Linux … » et « Loading
initial ramdisk … » en blanc sur noir ; puis une erreur du noyau propre à
VMware (piix4_smbus), malgré « quiet » ; puis, sous la phrase de passe,
« cryptsetup: luks-f49e6cb5-…: set up successfully ».

Validé sur la VM le même jour : rien entre le logo VMware et celui de
Codebyr ; une phrase de passe fausse affiche « Phrase de passe incorrecte.
Réessayez. » ; Fn + F4 ouvre le menu, gris clair sur noir.

Chaque pièce est exécutée ici pour de vrai quand un shell est disponible :
le réglage de GRUB, le script qui rend le menu quand un autre système est
installé, et l'enveloppe du script des entrées Linux — sur la sortie
authentique du 10_linux de Debian 13 (grub-common 2.12), obtenue le
01/10/2026 avec un faux disque : /boot à part, racine chiffrée.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from outils import ETC, RACINE

REGLAGE = os.path.join(ETC, "default", "grub.d", "91-codebyr-demarrage.cfg")
MENU = os.path.join(ETC, "grub.d", "35_codebyr_menu")
ENVELOPPE = os.path.join(RACINE, "packaging", "grub", "10_linux")
PLYMOUTH = os.path.join(RACINE, "live-build", "config", "includes.chroot_after_packages",
                        "usr", "share", "plymouth", "themes", "codebyr", "codebyr.script")
PAQUET = os.path.join(RACINE, "packaging")
DEBIAN_10_LINUX = "/etc/grub.d/debian/10_linux"

SH = shutil.which("sh")

# Sortie réelle du 10_linux de Debian 13, réduite à une entrée de chaque
# sorte : par défaut, options avancées, dépannage.
SORTIE_DEBIAN = """\
function gfxmode {
\tset gfxpayload="${1}"
}
set linux_gfx_mode=
export linux_gfx_mode
menuentry 'Codebyr GNU/Linux' --class codebyr --class gnu-linux --class gnu --class os $menuentry_id_option 'gnulinux-simple-854f8abd-7bf8-42fb-a488-c5ea1eb0c801' {
\tload_video
\tinsmod gzio
\tif [ x$grub_platform = xxen ]; then insmod xzio; insmod lzopio; fi
\tinsmod part_gpt
\tinsmod ext2
\tset root='hd0,gpt2'
\tif [ x$feature_platform_search_hint = xy ]; then
\t  search --no-floppy --fs-uuid --set=root --hint-bios=hd0,gpt2 --hint-efi=hd0,gpt2 --hint-baremetal=ahci0,gpt2 854f8abd-7bf8-42fb-a488-c5ea1eb0c801
\telse
\t  search --no-floppy --fs-uuid --set=root 854f8abd-7bf8-42fb-a488-c5ea1eb0c801
\tfi
\techo\t'Loading Linux 6.12.111+deb13-amd64 ...'
\tlinux\t/vmlinuz-6.12.111+deb13-amd64 root=/dev/mapper/luks-f49e6cb5 ro slab_nomerge page_alloc.shuffle=1 quiet splash loglevel=3
\techo\t'Loading initial ramdisk ...'
\tinitrd\t/initrd.img-6.12.111+deb13-amd64
}
submenu 'Advanced options for Codebyr GNU/Linux' $menuentry_id_option 'gnulinux-advanced-854f8abd-7bf8-42fb-a488-c5ea1eb0c801' {
\tmenuentry 'Codebyr GNU/Linux, with Linux 6.12.111+deb13-amd64' --class codebyr --class gnu-linux --class gnu --class os $menuentry_id_option 'gnulinux-6.12.111+deb13-amd64-advanced-854f8abd-7bf8-42fb-a488-c5ea1eb0c801' {
\t\tload_video
\t\tinsmod gzio
\t\tset root='hd0,gpt2'
\t\techo\t'Loading Linux 6.12.111+deb13-amd64 ...'
\t\tlinux\t/vmlinuz-6.12.111+deb13-amd64 root=/dev/mapper/luks-f49e6cb5 ro slab_nomerge page_alloc.shuffle=1 quiet splash loglevel=3
\t\techo\t'Loading initial ramdisk ...'
\t\tinitrd\t/initrd.img-6.12.111+deb13-amd64
\t}
\tmenuentry 'Codebyr GNU/Linux, with Linux 6.12.111+deb13-amd64 (recovery mode)' --class codebyr --class gnu-linux --class gnu --class os $menuentry_id_option 'gnulinux-6.12.111+deb13-amd64-recovery-854f8abd-7bf8-42fb-a488-c5ea1eb0c801' {
\t\tload_video
\t\tinsmod gzio
\t\tset root='hd0,gpt2'
\t\techo\t'Loading Linux 6.12.111+deb13-amd64 ...'
\t\tlinux\t/vmlinuz-6.12.111+deb13-amd64 root=/dev/mapper/luks-f49e6cb5 ro single dis_ucode_ldr slab_nomerge page_alloc.shuffle=1
\t\techo\t'Loading initial ramdisk ...'
\t\tinitrd\t/initrd.img-6.12.111+deb13-amd64
\t}
}
"""


def _lire(chemin):
    with open(chemin, encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n")


def _posix(chemin):
    # Sous Windows (Git Bash), « C:/… » couperait PATH en deux au « : ».
    chemin = chemin.replace("\\", "/")
    lecteur = re.match(r"^([A-Za-z]):/", chemin)
    if os.name == "nt" and lecteur:
        chemin = "/%s/%s" % (lecteur.group(1).lower(), chemin[3:])
    return chemin


def _executable(chemin, contenu):
    with open(chemin, "w", encoding="utf-8", newline="\n") as f:
        f.write(contenu)
    os.chmod(chemin, 0o755)


@unittest.skipUnless(SH, "pas de shell POSIX")
class LeReglageDeGrub(unittest.TestCase):
    """91-codebyr-demarrage.cfg, lu par update-grub comme il le fait : après
    /etc/default/grub, dans le même shell."""

    def _apres(self, avant):
        script = (avant + "\n. '%s'\n" % _posix(REGLAGE)
                  + 'printf "%s|" "${GRUB_TIMEOUT_STYLE-}" "${GRUB_TIMEOUT-}" '
                    '"${GRUB_TERMINAL_OUTPUT-}" "${GRUB_CMDLINE_LINUX_DEFAULT-}"\n'
                  + 'sh -c \'printf "%s" "${CODEBYR_MENU_CACHE-}"\'\n')
        resultat = subprocess.run([SH, "-c", script], capture_output=True, text=True)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        return resultat.stdout.split("|")

    def test_la_machine_de_debian_demarre_sans_menu_ni_texte(self):
        # /etc/default/grub de Debian et de l'installeur, inchangé.
        style, delai, sortie, options, marque = self._apres(
            'GRUB_TIMEOUT=5\nGRUB_CMDLINE_LINUX_DEFAULT="quiet splash"')
        self.assertEqual(style, "hidden")
        # Une seconde à l'affût, pour F4 : jamais zéro.
        self.assertEqual(delai, "1")
        self.assertEqual(sortie, "console")
        self.assertEqual(options, "quiet splash loglevel=3")
        # Exporté : 35_codebyr_menu, un autre processus, doit le voir.
        self.assertEqual(marque, "5")

    def test_un_delai_choisi_reste_le_sien(self):
        style, delai, sortie, _o, marque = self._apres(
            'GRUB_TIMEOUT=10\nGRUB_CMDLINE_LINUX_DEFAULT="quiet splash"')
        self.assertEqual((style, delai, sortie, marque), ("", "10", "", ""))

    def test_un_menu_demande_reste_visible(self):
        style, delai, _s, _o, marque = self._apres(
            'GRUB_TIMEOUT=5\nGRUB_TIMEOUT_STYLE=menu\nGRUB_CMDLINE_LINUX_DEFAULT="quiet"')
        self.assertEqual((style, delai, marque), ("menu", "5", ""))

    def test_une_console_choisie_reste_la_sienne(self):
        for avant in ('GRUB_TERMINAL_OUTPUT=gfxterm', 'GRUB_TERMINAL=console'):
            with self.subTest(avant=avant):
                style, _d, sortie, _o, _m = self._apres('GRUB_TIMEOUT=5\n' + avant)
                self.assertEqual(style, "hidden")
                self.assertEqual(sortie, "gfxterm" if "OUTPUT" in avant else "")

    def test_qui_a_retire_quiet_veut_lire(self):
        for options in ("splash", "quiet splash loglevel=7", "quietude"):
            with self.subTest(options=options):
                _s, _d, _t, apres, _m = self._apres(
                    'GRUB_TIMEOUT=5\nGRUB_CMDLINE_LINUX_DEFAULT="%s"' % options)
                self.assertEqual(apres, options)


@unittest.skipUnless(SH, "pas de shell POSIX")
class LeMenuRevientPourChoisir(unittest.TestCase):
    """35_codebyr_menu : le menu caché revient quand os-prober trouve un autre
    système — celui que 30_os-prober vient d'ajouter au menu."""

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="codebyr-menu-")
        self.addCleanup(shutil.rmtree, self.dossier)
        _executable(os.path.join(self.dossier, "linux-boot-prober"), "#!/bin/sh\nexit 0\n")

    def _menu(self, trouve, env, sortie_prober=0):
        _executable(os.path.join(self.dossier, "os-prober"),
                    "#!/bin/sh\nprintf '%%s' '%s'\nexit %d\n" % (trouve, sortie_prober))
        variables = "".join("%s='%s'; export %s; " % (k, v, k) for k, v in env.items())
        script = ('PATH="%s:$PATH"; export PATH; %s exec sh "%s"'
                  % (_posix(self.dossier), variables, _posix(MENU)))
        resultat = subprocess.run([SH, "-c", script], capture_output=True, text=True)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        return resultat.stdout

    WINDOWS = "/dev/sda1@/EFI/Microsoft/Boot/bootmgfw.efi:Windows Boot Manager:Windows:efi"

    def test_un_autre_systeme_rend_le_menu_visible(self):
        sortie = self._menu(self.WINDOWS, {"CODEBYR_MENU_CACHE": "5",
                                           "GRUB_DISABLE_OS_PROBER": "false"})
        self.assertIn("set timeout_style=menu", sortie)
        self.assertIn("set timeout=5", sortie)
        # Du script GRUB, pas du shell : la variable est échappée.
        self.assertIn("if [ x$feature_timeout_style = xy ] ; then", sortie)

    def test_seul_le_menu_reste_cache(self):
        self.assertEqual(self._menu("", {"CODEBYR_MENU_CACHE": "5",
                                         "GRUB_DISABLE_OS_PROBER": "false"}), "")

    def test_os_prober_en_echec_ne_casse_rien(self):
        # update-grub échouerait, et le nouveau noyau ne s'installerait pas.
        self.assertEqual(self._menu("", {"CODEBYR_MENU_CACHE": "5",
                                         "GRUB_DISABLE_OS_PROBER": "false"}, 1), "")

    def test_rien_quand_codebyr_n_a_pas_cache_le_menu(self):
        self.assertEqual(self._menu(self.WINDOWS, {"GRUB_DISABLE_OS_PROBER": "false"}), "")

    def test_rien_quand_os_prober_est_coupe(self):
        # 30_os-prober n'a alors rien ajouté au menu.
        self.assertEqual(self._menu(self.WINDOWS, {"CODEBYR_MENU_CACHE": "5",
                                                   "GRUB_DISABLE_OS_PROBER": "true"}), "")

    def test_dans_la_console_le_menu_n_est_plus_bleu_debian(self):
        sortie = self._menu("", {"CODEBYR_MENU_CACHE": "5", "GRUB_TERMINAL_OUTPUT": "console",
                                 "GRUB_DISABLE_OS_PROBER": "false"})
        self.assertEqual(sortie, "set menu_color_normal=light-gray/black\n"
                                 "set menu_color_highlight=black/light-cyan\n")
        # La console graphique d'un administrateur garde le thème de Debian
        # (fond d'écran et couleurs assorties).
        self.assertEqual(self._menu("", {"CODEBYR_MENU_CACHE": "5",
                                         "GRUB_TERMINAL_OUTPUT": "gfxterm",
                                         "GRUB_DISABLE_OS_PROBER": "false"}), "")

    def test_le_delai_n_est_jamais_du_code(self):
        sortie = self._menu(self.WINDOWS, {"CODEBYR_MENU_CACHE": "5; reboot",
                                           "GRUB_DISABLE_OS_PROBER": "false"})
        self.assertEqual(sortie, "")


@unittest.skipUnless(SH and shutil.which("awk"), "pas de shell POSIX")
class LesEntreesLinuxSansMessages(unittest.TestCase):
    """L'enveloppe de 10_linux : la sortie de Debian, moins les deux messages
    de l'entrée par défaut — et rien d'autre."""

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="codebyr-10linux-")
        self.addCleanup(shutil.rmtree, self.dossier)
        self.debian = os.path.join(self.dossier, "10_linux_debian")
        self.enveloppe = os.path.join(self.dossier, "10_linux")
        texte = _lire(ENVELOPPE)
        self.assertEqual(texte.count("DEBIAN=%s\n" % DEBIAN_10_LINUX), 1)
        _executable(self.enveloppe,
                    texte.replace("DEBIAN=%s\n" % DEBIAN_10_LINUX,
                                  "DEBIAN='%s'\n" % _posix(self.debian)))

    def _debian(self, sortie, code=0):
        donnees = os.path.join(self.dossier, "sortie")
        with open(donnees, "w", encoding="utf-8", newline="\n") as f:
            f.write(sortie)
        _executable(self.debian, "#!/bin/sh\ncat '%s'\nexit %d\n" % (_posix(donnees), code))

    def _enveloppe(self):
        return subprocess.run([SH, _posix(self.enveloppe)], capture_output=True, text=True)

    def test_l_entree_par_defaut_perd_ses_deux_messages_et_rien_d_autre(self):
        self._debian(SORTIE_DEBIAN)
        resultat = self._enveloppe()
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        avant = SORTIE_DEBIAN.splitlines()
        apres = resultat.stdout.splitlines()
        retirees = [l for l in avant if l not in apres]
        self.assertEqual(retirees, ["\techo\t'Loading Linux 6.12.111+deb13-amd64 ...'",
                                    "\techo\t'Loading initial ramdisk ...'"])
        # Tout le reste, dans le même ordre.
        self.assertEqual(apres, [l for l in avant if l not in retirees])

    def test_les_options_avancees_et_le_depannage_les_gardent(self):
        self._debian(SORTIE_DEBIAN)
        apres = self._enveloppe().stdout
        self.assertEqual(apres.count("\t\techo\t'Loading Linux"), 2)
        self.assertEqual(apres.count("\t\techo\t'Loading initial ramdisk ...'"), 2)

    def test_chaque_noyau_reste_demarrable(self):
        self._debian(SORTIE_DEBIAN)
        apres = self._enveloppe().stdout
        for commande in ("linux", "initrd", "menuentry", "submenu", "search"):
            self.assertEqual(len(re.findall(r"^\s*%s\s" % commande, apres, re.M)),
                             len(re.findall(r"^\s*%s\s" % commande, SORTIE_DEBIAN, re.M)),
                             commande)

    def test_un_message_traduit_avec_apostrophe(self):
        # grub_quote écrit une apostrophe « '\\'' » : le message reste une
        # seule ligne « echo », retirée comme les autres.
        francais = SORTIE_DEBIAN.replace(
            "\techo\t'Loading initial ramdisk ...'\n\tinitrd",
            "\techo\t'Chargement de l'\\''image initiale…'\n\tinitrd", 1)
        self._debian(francais)
        self.assertNotIn("Chargement", self._enveloppe().stdout)

    def test_un_echec_de_debian_fait_echouer_update_grub(self):
        # update-grub garde alors l'ancienne configuration, qui démarre.
        self._debian(SORTIE_DEBIAN, code=3)
        self.assertNotEqual(self._enveloppe().returncode, 0)

    def test_sans_le_script_de_debian_rien_n_est_ecrit(self):
        resultat = self._enveloppe()
        self.assertNotEqual(resultat.returncode, 0)
        self.assertEqual(resultat.stdout, "")

    def test_jamais_il_ne_s_appelle_lui_meme(self):
        _executable(self.debian, _lire(ENVELOPPE))
        resultat = self._enveloppe()
        self.assertNotEqual(resultat.returncode, 0)
        self.assertEqual(resultat.stdout, "")


class LeDetournementDe10Linux(unittest.TestCase):
    """Le 10_linux de grub-common est détourné, comme /etc/skel/.face."""

    def setUp(self):
        self.preinst = _lire(os.path.join(PAQUET, "codebyr-tools.preinst"))
        self.postrm = _lire(os.path.join(PAQUET, "codebyr-tools.postrm"))
        self.postinst = _lire(os.path.join(PAQUET, "codebyr-tools.postinst"))
        self.construction = _lire(os.path.join(PAQUET, "build-deb.sh"))

    def test_un_seul_chemin_pour_le_script_de_debian(self):
        for texte in (self.preinst, self.postrm, _lire(ENVELOPPE)):
            self.assertIn(DEBIAN_10_LINUX, texte)

    def test_la_copie_de_debian_est_hors_de_portee_de_grub_mkconfig(self):
        # grub-mkconfig n'exécute que les fichiers posés directement dans
        # /etc/grub.d : un sous-dossier n'est jamais parcouru.
        self.assertEqual(os.path.dirname(os.path.dirname(DEBIAN_10_LINUX)), "/etc/grub.d")

    def test_le_preinst_detourne_sans_deplacer(self):
        self.assertIn('dpkg-divert --package codebyr-tools --add --no-rename \\\n'
                      '\t\t\t\t--divert "$DEBIAN_10_LINUX" /etc/grub.d/10_linux', self.preinst)
        # Jamais l'enveloppe rangée comme « script de Debian ».
        self.assertIn('! grep -q "codebyr:enveloppe-10_linux" /etc/grub.d/10_linux', self.preinst)

    def test_le_postrm_rend_le_script_et_regenere(self):
        self.assertIn('--divert "$DEBIAN_10_LINUX" /etc/grub.d/10_linux', self.postrm)
        # La copie de retour porte un nom que grub-mkconfig ignore.
        self.assertIn("/etc/grub.d/10_linux.dpkg-codebyr-retour", self.postrm)
        self.assertIn('if dpkg --compare-versions "$2" lt 1.19.0; then\n\t\t\trendre_10_linux',
                      self.postrm)
        retrait = self.postrm.split("remove|abort-install|disappear)", 1)[1].split(";;", 1)[0]
        self.assertIn("rendre_10_linux", retrait)
        self.assertIn("regenerer_grub", retrait)

    def test_l_image_ne_livre_jamais_l_enveloppe(self):
        self.assertFalse(os.path.exists(os.path.join(ETC, "grub.d", "10_linux")))
        self.assertIn('"$REPO/packaging/grub/10_linux" > "$STAGE/etc/grub.d/10_linux"',
                      self.construction)

    def test_les_scripts_de_grub_sont_executables(self):
        self.assertIn('find "$STAGE/etc/grub.d" -type f -exec chmod 755 {} +',
                      self.construction)
        for chemin in ("etc/default/grub.d/91-codebyr-demarrage.cfg",
                       "etc/grub.d/35_codebyr_menu"):
            self.assertIn("\t%s \\\n" % chemin, self.construction)

    def test_grub_est_regenere_quand_un_de_ses_fichiers_change(self):
        bloc = self.postinst.split("GRUB_CODEBYR=", 1)[1].split("\n\t\t# ", 1)[0]
        for fichier in ("/etc/default/grub.d/90-codebyr-noyau.cfg",
                        "/etc/default/grub.d/91-codebyr-demarrage.cfg",
                        "/etc/grub.d/35_codebyr_menu", "/etc/grub.d/10_linux"):
            self.assertIn(fichier, bloc.split("\n", 1)[0])
        # Seulement sur une machine installée et démarrée ; pas de dates.
        for garde in ("/boot/grub/grub.cfg", "/run/systemd/system", "! -d /run/live",
                      "/var/lib/codebyr/grub.sha256",
                      "! grep -q 'slab_nomerge page_alloc.shuffle=1' /boot/grub/grub.cfg"):
            self.assertIn(garde, bloc)
        self.assertNotIn("-nt", bloc)
        self.assertNotIn("-newer", bloc)
        # Le témoin n'est écrit qu'après une régénération réussie.
        self.assertLess(bloc.index("if /usr/sbin/update-grub"), bloc.index('> "$GRUB_TEMOIN"'))


class LesMessagesDeCryptsetup(unittest.TestCase):
    """Sous la phrase de passe, plus de « cryptsetup: luks-…: set up
    successfully » ; les refus, eux, sont dits dans la langue du système."""

    def setUp(self):
        self.script = _lire(PLYMOUTH)
        self.message = self.script.split("fun message_callback(texte) {", 1)[1].split("\n}\n", 1)[0]

    def test_les_textes_exacts_de_debian(self):
        # cryptsetup-initramfs 2:2.7.5 (Debian 13), scripts/local-top/cryptroot,
        # préfixés de « cryptsetup: » par cryptsetup_message.
        for fin in (": set up successfully",
                    ": cryptsetup failed, bad password or options?",
                    ": maximum number of tries exceeded"):
            self.assertIn('finit_par(texte, "%s")' % fin, self.message)

    def test_le_succes_est_tu(self):
        succes = self.message.split(": set up successfully", 1)[1].split("} else {", 1)[0]
        self.assertIn("global.message_affiche = 0;", succes)
        self.assertNotIn("ligne(", succes)

    def test_les_refus_sont_traduits(self):
        self.assertIn('traduire("Phrase de passe incorrecte. Réessayez.")', self.message)
        self.assertIn("traduire(\"Trop d'essais. Redémarrez l'ordinateur pour réessayer.\")",
                      self.message)

    def test_une_chaine_n_est_lue_qu_a_travers_string(self):
        # Dans le langage de Plymouth, « texte.Length() » remplace texte par un
        # objet vide : la comparaison échouerait toujours, en silence.
        code = "\n".join(l for l in self.script.splitlines() if not l.lstrip().startswith("//"))
        appels = re.findall(r"\.(?:Length|SubString|CharAt)\(", code)
        par_string = re.findall(r"\bString\([^()]*\)\.(?:Length|SubString|CharAt)\(", code)
        self.assertTrue(appels)
        self.assertEqual(len(appels), len(par_string))


if __name__ == "__main__":
    unittest.main()
