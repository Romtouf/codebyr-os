# -*- coding: utf-8 -*-
"""Ce que l'on voit de Codebyr avant même de s'en servir.

Quatre défauts relevés le 01/10/2026 sur une machine d'essai :

· l'avatar des comptes, sur l'écran de connexion et de verrouillage, était la
  spirale Debian (/etc/skel/.face, livré par desktop-base) ;
· pendant le démarrage, le logo et le nom glissaient vers la gauche : placés
  une seule fois, à la taille d'écran du tout premier instant, ils restaient
  là quand l'écran prenait sa vraie définition ;
· dans l'installeur, la barre latérale ne montrait que le Sceau et « OS » : le
  mot « codebyr » y était écrit dans la couleur même du fond ;
· à l'ouverture de session, GNOME montrait sa vue d'ensemble, dont le dock
  passait par-dessus la fenêtre « Bienvenue » et son bouton « Suivant ».
"""
import os
import re
import unittest
import xml.etree.ElementTree as ET

from outils import ETC, LIB, RACINE

INCLUDES = os.path.join(RACINE, "live-build", "config", "includes.chroot_after_packages")
PLYMOUTH = os.path.join(INCLUDES, "usr", "share", "plymouth", "themes", "codebyr")
BRANDING = os.path.join(ETC, "calamares", "branding", "debian")
EXTENSION = os.path.join(INCLUDES, "usr", "share", "gnome-shell", "extensions",
                         "codebyr@codebyr.io", "extension.js")


def _lire(*morceaux):
    with open(os.path.join(*morceaux), encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n")


class LAvatar(unittest.TestCase):

    def setUp(self):
        self.preinst = _lire(RACINE, "packaging", "codebyr-tools.preinst")
        self.postrm = _lire(RACINE, "packaging", "codebyr-tools.postrm")

    def test_c_est_le_sceau_et_une_image_carree(self):
        racine = ET.parse(os.path.join(LIB, "avatar.svg")).getroot()
        largeur, hauteur = racine.get("viewBox").split()[2:]
        self.assertEqual(largeur, hauteur)

    def test_l_image_ne_le_pose_jamais_directement_dans_etc_skel(self):
        # L'image copie ses fichiers AVANT d'installer le paquet : le preinst
        # aurait rangé le Sceau comme « copie de desktop-base ». Ce fichier
        # étant une conffile de desktop-base, chacune de ses mises à jour
        # l'aurait cru modifié — et unattended-upgrades l'aurait écartée.
        self.assertFalse(os.path.lexists(os.path.join(ETC, "skel", ".face")))
        self.assertFalse(os.path.lexists(os.path.join(ETC, "skel", ".face.icon")))

    def test_le_paquet_le_fabrique(self):
        construction = _lire(RACINE, "packaging", "build-deb.sh")
        self.assertIn('cp "$SRC/usr/share/codebyr/avatar.svg" "$STAGE/etc/skel/.face"', construction)

    def test_la_copie_de_desktop_base_n_est_faite_qu_a_la_creation_de_la_deviation(self):
        garde = 'if [ "$(dpkg-divert --listpackage /etc/skel/.face)" != "codebyr-tools" ]'
        self.assertIn(garde, self.preinst)
        self.assertLess(self.preinst.index(garde), self.preinst.index('cp -a /etc/skel/.face "$DEBIAN_FACE"'))

    def test_au_retrait_l_avatar_de_debian_revient_avant_la_levee(self):
        retour = self.postrm.index("mv -f /etc/skel/.face.codebyr-retour /etc/skel/.face")
        levee = self.postrm.index('--divert "$DEBIAN_FACE" /etc/skel/.face')
        self.assertLess(retour, levee)

    def test_une_mise_a_jour_annulee_avant_la_deviation_la_retire(self):
        bloc = self.postrm[self.postrm.index("abort-upgrade)"):]
        self.assertRegex(bloc, r'lt 1\.17\.2; then\n\s*rendre_l_avatar')


class LEcranDeDemarrage(unittest.TestCase):

    def setUp(self):
        self.script = _lire(PLYMOUTH, "codebyr.script")

    def test_tout_est_replace_quand_l_ecran_change_de_taille(self):
        rafraichir = self.script[self.script.index("fun refresh_callback()"):]
        rafraichir = rafraichir[:rafraichir.index("\n}\n")]
        self.assertIn("Window.GetWidth() != global.screen_w", rafraichir)
        self.assertIn("Window.GetHeight() != global.screen_h", rafraichir)
        self.assertIn("placer();", rafraichir)

    def test_le_message_et_l_invite_suivent_aussi(self):
        # 1.17.2~essai1 ne replaçait que le logo : le message de cryptsetup,
        # arrivé juste avant le changement de définition, glissait encore.
        rafraichir = self.script[self.script.index("fun refresh_callback()"):]
        rafraichir = rafraichir[:rafraichir.index("\n}\n")]
        self.assertIn("message_callback(global.message_texte);", rafraichir)
        self.assertIn("display_password_callback(global.invite_texte, global.invite_nb_puces);",
                      rafraichir)
        # Pour être redessinés, ils gardent ce qu'ils affichent.
        message = self.script[self.script.index("fun message_callback(texte)"):]
        self.assertIn("global.message_texte = texte;", message[:message.index("\n}\n")])
        invite = self.script[self.script.index("fun display_password_callback(prompt, puces)"):]
        invite = invite[:invite.index("\n}\n")]
        self.assertIn("global.invite_texte = prompt;", invite)
        self.assertIn("global.invite_nb_puces = puces;", invite)

    def test_le_placement_lit_la_taille_au_moment_de_placer(self):
        placer = self.script[self.script.index("fun placer()"):]
        placer = placer[:placer.index("\n}\n")]
        for ligne in ("global.screen_w = Window.GetWidth();", "global.screen_h = Window.GetHeight();",
                      "logo.sprite.SetPosition(", "label.sprite.SetPosition("):
            self.assertIn(ligne, placer)

    def test_le_paquet_livre_le_theme(self):
        self.assertIn("usr/share/plymouth/themes/codebyr \\", _lire(RACINE, "packaging", "build-deb.sh"))

    def test_l_image_de_demarrage_n_est_regeneree_que_si_le_theme_change(self):
        postinst = _lire(RACINE, "packaging", "codebyr-tools.postinst")
        bloc = postinst[postinst.index("THEMES=/usr/share/plymouth/themes"):]
        bloc = bloc[:bloc.index("\n\t\t;;\n")]
        self.assertIn('[ "$(cat "$TEMOIN" 2>/dev/null)" != "$EMPREINTE" ]', bloc)
        # Le thème actif fait partie de l'empreinte : changer de langue
        # régénère l'image.
        self.assertIn('echo "$ACTIF"; cat "$THEMES/$ACTIF/$ACTIF.plymouth"', bloc)
        # Ni dans un chroot, ni sur le live, ni avec un thème qui n'est pas
        # l'un de ceux de Codebyr.
        for garde in ("[ -d /run/systemd/system ]", "[ ! -d /run/live ]",
                      "codebyr|codebyr-*) ;;", '*) ACTIF="" ;;'):
            self.assertIn(garde, bloc)
        # APRÈS codebyr-durcir-poste, qui choisit le thème.
        self.assertLess(postinst.index("sh /usr/bin/codebyr-durcir-poste"),
                        postinst.index("THEMES=/usr/share/plymouth/themes"))
        # Exactement « -u » : dans un script de paquet, la génération est
        # alors reportée à la fin d'apt (une seule, même avec un noyau neuf).
        self.assertIn("if /usr/sbin/update-initramfs -u; then", bloc)
        # Le témoin n'est écrit qu'après une génération réussie.
        self.assertLess(bloc.index("update-initramfs -u"), bloc.index('> "$TEMOIN"'))


class LEcranDeDemarrageTraduit(unittest.TestCase):
    """« Phrase de passe du disque » dans la langue du système (1.18.2)."""

    @classmethod
    def setUpClass(cls):
        import sys
        import tempfile
        sys.path.insert(0, os.path.join(RACINE, "packaging"))
        try:
            import traductions
        finally:
            sys.path.pop(0)
        cls.traductions = traductions
        cls.temporaire = tempfile.TemporaryDirectory()
        traductions.compiler(os.path.join(RACINE, "po"), cls.temporaire.name)
        cls.theme = os.path.join(cls.temporaire.name, "usr", "share", "plymouth", "themes", "codebyr-en")

    @classmethod
    def tearDownClass(cls):
        cls.temporaire.cleanup()

    def test_le_paquet_produit_le_theme_anglais(self):
        script = _lire(self.theme, "codebyr-en.script")
        self.assertIn('ligne(traduire("Disk passphrase"),', script)
        self.assertIn('ligne(traduire("Type it, then press Enter"),', script)
        self.assertNotIn('traduire("Phrase de passe du disque")', script)
        # Le reste du script est le même : seules les phrases changent.
        source = _lire(PLYMOUTH, "codebyr.script")
        self.assertEqual(len(script.splitlines()), len(source.splitlines()))
        plymouth = _lire(self.theme, "codebyr-en.plymouth")
        # Le logo est celui du thème français : le hook initramfs copie ImageDir.
        self.assertIn("ImageDir=/usr/share/plymouth/themes/codebyr\n", plymouth)
        self.assertIn("ScriptFile=/usr/share/plymouth/themes/codebyr-en/codebyr-en.script\n", plymouth)

    def test_une_traduction_impropre_a_plymouth_est_refusee(self):
        e = self.traductions.Entree("Phrase de passe du disque")
        e.msgstr = ['Disk "passphrase"']
        with self.assertRaises(ValueError):
            self.traductions.theme_traduit('x = traduire("Phrase de passe du disque");', [e])

    def test_le_theme_suit_la_langue_du_systeme(self):
        durcir = _lire(INCLUDES, "usr", "bin", "codebyr-durcir-poste")
        bloc = durcir[durcir.index("# ── 3 bis) L'écran de démarrage"):durcir.index("# ── 4)")]
        self.assertIn("/etc/default/locale", bloc)
        # Jamais un thème que l'administrateur aurait choisi.
        self.assertIn("codebyr|codebyr-*)", bloc)
        self.assertIn("fr|C|POSIX|\"\") voulu=codebyr ;;", bloc)
        self.assertIn("voulu=codebyr-en", bloc)
        # Pas de régénération ici : le postinst ou l'installeur s'en charge.
        self.assertNotIn("update-initramfs", bloc.split("# le postinst le fait")[1])


class LInstalleur(unittest.TestCase):

    def test_la_barre_laterale_a_son_propre_logo(self):
        branding = _lire(BRANDING, "branding.desc")
        self.assertRegex(branding, r'productLogo:\s+"logo-barre\.svg"')
        self.assertRegex(branding, r'productIcon:\s+"sceau\.svg"')
        for nom in ("logo-barre.svg", "sceau.svg"):
            ET.parse(os.path.join(BRANDING, nom))

    def test_le_nom_y_est_ecrit_en_clair_sur_le_fond_sombre(self):
        fond = re.search(r'SidebarBackground:\s+"(#[0-9A-Fa-f]{6})"',
                         _lire(BRANDING, "branding.desc")).group(1).upper()
        racine = ET.parse(os.path.join(BRANDING, "logo-barre.svg")).getroot()
        textes = [e for e in racine.iter() if e.tag.endswith("}text")]
        self.assertEqual(len(textes), 1)
        self.assertEqual("".join(textes[0].itertext()).split(), ["codebyr", "OS"])
        self.assertNotEqual(textes[0].get("fill").upper(), fond)

    def test_le_logo_est_carre(self):
        # Calamares l'affiche dans un carré de 80 × 80.
        racine = ET.parse(os.path.join(BRANDING, "logo-barre.svg")).getroot()
        largeur, hauteur = racine.get("viewBox").split()[2:]
        self.assertEqual(largeur, hauteur)


class LOuvertureDeSession(unittest.TestCase):

    def setUp(self):
        texte = _lire(EXTENSION)
        self.enable = texte[texte.index("    enable() {"):texte.index("    _rendreVueEnsemble() {")]
        self.disable = texte[texte.index("    disable() {"):]

    def test_la_vue_d_ensemble_est_retiree_le_temps_du_demarrage_seulement(self):
        garde = self.enable.index("if (Main.layoutManager._startingUp) {")
        retrait = self.enable.index("Main.sessionMode.hasOverview = false;")
        self.assertLess(garde, retrait)
        self.assertIn("this._avecVueEnsemble = Main.sessionMode.hasOverview;", self.enable)
        self.assertIn("'startup-complete'", self.enable)

    def test_elle_revient_meme_si_l_extension_est_coupee_avant(self):
        self.assertIn("this._rendreVueEnsemble();", self.disable)


class LesFenetresDuMenu(unittest.TestCase):
    """Les fenêtres du menu du Sceau, sous GNOME 48.

    « Autres applications… » ne s'ouvrait plus, sans un mot : le titre
    traduit appelait remplir(), qu'une variable locale du même nom masquait
    (voir tests/test_traduction.py). L'échec d'une fenêtre se voit désormais ;
    et un contenu défilant est donné comme GNOME 46 et suivants l'attendent,
    par la propriété « child »."""

    def setUp(self):
        self.texte = _lire(EXTENSION)

    def test_un_contenu_defilant_est_donne_par_child(self):
        self.assertNotIn(".add_actor(", self.texte)
        for appel in re.findall(r"new St\.ScrollView\(\{[^}]*\}\)", self.texte):
            self.assertIn("child:", appel)

    def test_les_outils_de_codebyr_ne_s_ouvrent_pas_dans_un_espace(self):
        # Assistant, Configuration, Bienvenue : des outils du bureau. La liste
        # « Autres applications… » les écarte, comme Configuration Codebyr.
        apps = self.texte[self.texte.index("    _appsInstallees() {"):
                          self.texte.index("    _dialogueApps(esp) {")]
        self.assertIn(".startsWith('io.codebyr.')", apps)

    def test_chaque_fenetre_du_menu_dit_son_echec(self):
        appels = re.findall(r"\(\) => this\._(?:ouvrirFenetre\(\(\) => this\._)?dialogue\w+\(", self.texte)
        self.assertEqual(len(appels), 5)
        for appel in appels:
            self.assertIn("_ouvrirFenetre", appel)


class LaVueDEnsemble(unittest.TestCase):
    """Plus d'icône d'application sous chaque fenêtre de la vue d'ensemble :
    elle recouvrait le contenu (le bouton « Suivant » de « Bienvenue »)."""

    def setUp(self):
        self.texte = _lire(EXTENSION)
        self.masquer = self.texte[self.texte.index("    _masquerIconesDesApercus() {"):
                                  self.texte.index("    _rendreIconesDesApercus() {")]

    def test_l_icone_est_masquee_a_chaque_mise_a_l_echelle(self):
        # GNOME 48 (windowPreview.js) : _updateIconScale est appelée à la
        # création de l'aperçu et à chaque ouverture de la vue d'ensemble.
        self.assertIn("overrideMethod(WindowPreview.WindowPreview.prototype, '_updateIconScale',",
                      self.masquer)
        self.assertIn("original.call(this);", self.masquer)
        self.assertIn("this._icon.hide();", self.masquer)
        self.assertIn("this._masquerIconesDesApercus();",
                      self.texte[self.texte.index("    enable() {"):self.texte.index("    _rendreVueEnsemble() {")])

    def test_tout_est_rendu_a_la_desactivation(self):
        disable = self.texte[self.texte.index("    disable() {"):]
        self.assertIn("this._rendreIconesDesApercus();", disable)
        rendre = self.texte[self.texte.index("    _rendreIconesDesApercus() {"):self.texte.index("    disable() {")]
        self.assertIn("this._injections?.clear();", rendre)
        self.assertIn("apercu._icon?.show();", rendre)


if __name__ == "__main__":
    unittest.main()
