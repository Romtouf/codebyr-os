# -*- coding: utf-8 -*-
"""Un document du bureau s'ouvre là où il s'ouvrait avant Codebyr.

Depuis 1.22.0, l'ouvreur de Codebyr est l'application par défaut des
documents sur le bureau (/etc/xdg/mimeapps.list) : c'est ce qui permet
d'envoyer sous cloche ceux d'une clé USB inconnue. Tout le reste doit
continuer d'aboutir dans la visionneuse ou le traitement de texte habituels.

Ce qui est gardé ici :
- l'ouvreur ne se choisit jamais lui-même (la boucle), ni le Jetable ;
- le choix de l'utilisateur passe avant celui du système ;
- une application Flatpak se trouve, même sans préférence écrite ;
- le fichier livré ne contient que des types que l'ouvreur sait traiter, et
  pas les archives, que Fichiers ne décompresse que s'il en est le défaut.
"""
import os
import shutil
import tempfile
import unittest

from outils import ETC, LIB  # noqa: F401 — place le module partagé sur sys.path
import outils
import associations

space = outils.charger("codebyr-space")

LIVRE = os.path.join(ETC, "xdg", "mimeapps.list")
PDF = "application/pdf"


class Ordre(unittest.TestCase):
    ENV = {"HOME": "/home/rom", "XDG_CURRENT_DESKTOP": "ubuntu:GNOME",
           "XDG_CONFIG_DIRS": "/etc/xdg", "XDG_DATA_DIRS": "/var/lib/flatpak/exports/share:/usr/share"}

    def test_ordre_de_la_specification(self):
        fichiers = associations.fichiers_de_preferences(self.ENV)
        attendu = [
            "/home/rom/.config/ubuntu-mimeapps.list",
            "/home/rom/.config/gnome-mimeapps.list",
            "/home/rom/.config/mimeapps.list",
            "/etc/xdg/ubuntu-mimeapps.list",
            "/etc/xdg/gnome-mimeapps.list",
            "/etc/xdg/mimeapps.list",
            "/home/rom/.local/share/applications/ubuntu-mimeapps.list",
        ]
        self.assertEqual([f.replace("\\", "/") for f in fichiers[:7]], attendu)
        self.assertEqual(fichiers[-1].replace("\\", "/"), "/usr/share/applications/mimeapps.list")

    def test_valeurs_par_defaut(self):
        fichiers = [f.replace("\\", "/") for f in
                    associations.fichiers_de_preferences({"HOME": "/home/rom"})]
        self.assertIn("/etc/xdg/mimeapps.list", fichiers)
        self.assertIn("/usr/share/applications/mimeapps.list", fichiers)


class Choix(unittest.TestCase):
    INSTALLEES = {"org.gnome.Evince.desktop", "org.gnome.Papers.desktop",
                  "org.libreoffice.LibreOffice.writer.desktop",
                  space.OUVREUR, "io.codebyr.Jetable.desktop"}

    def choisir(self, fichiers, caches=(), type_mime=PDF):
        contenus = dict(fichiers)
        contenus.update(caches)
        return associations.choisir(type_mime, lambda c: contenus.get(c, ""),
                                    lambda a: a in self.INSTALLEES,
                                    [f for f, _ in fichiers], [c for c, _ in caches])

    def test_l_ouvreur_ne_se_choisit_pas_lui_meme(self):
        obtenu = self.choisir([
            ("/etc/xdg/mimeapps.list", "[Default Applications]\n%s=%s\n" % (PDF, space.OUVREUR)),
            ("/usr/share/applications/gnome-mimeapps.list",
             "[Default Applications]\n%s=org.gnome.Evince.desktop;org.gnome.Papers.desktop;\n" % PDF)])
        self.assertEqual(obtenu, "org.gnome.Evince.desktop")

    def test_ni_le_jetable(self):
        """GNOME place le Jetable en tête de sa liste de secours (constaté)."""
        obtenu = self.choisir([], [(
            "/usr/share/applications/mimeinfo.cache",
            "[MIME Cache]\n%s=io.codebyr.Jetable.desktop;%s;org.gnome.Evince.desktop;\n"
            % (PDF, space.OUVREUR))])
        self.assertEqual(obtenu, "org.gnome.Evince.desktop")

    def test_application_absente_sautee(self):
        obtenu = self.choisir([(
            "/usr/share/applications/gnome-mimeapps.list",
            "[Default Applications]\n%s=absente.desktop;org.gnome.Papers.desktop;\n" % PDF)])
        self.assertEqual(obtenu, "org.gnome.Papers.desktop")

    def test_le_choix_de_l_utilisateur_passe_avant(self):
        obtenu = self.choisir([
            ("/home/rom/.config/mimeapps.list",
             "[Default Applications]\n%s=org.gnome.Papers.desktop\n" % PDF),
            ("/etc/xdg/mimeapps.list", "[Default Applications]\n%s=%s\n" % (PDF, space.OUVREUR)),
            ("/usr/share/applications/gnome-mimeapps.list",
             "[Default Applications]\n%s=org.gnome.Evince.desktop\n" % PDF)])
        self.assertEqual(obtenu, "org.gnome.Papers.desktop")

    def test_une_application_flatpak_sans_preference(self):
        """LibreOffice depuis Flathub : seul son mimeinfo.cache le déclare."""
        type_mime = "application/vnd.oasis.opendocument.text"
        obtenu = self.choisir(
            [("/etc/xdg/mimeapps.list", "[Default Applications]\n%s=%s\n" % (type_mime, space.OUVREUR)),
             ("/usr/share/applications/gnome-mimeapps.list",
              "[Default Applications]\n%s=libreoffice-writer.desktop\n" % type_mime)],
            [("/var/lib/flatpak/exports/share/applications/mimeinfo.cache",
              "[MIME Cache]\n%s=org.libreoffice.LibreOffice.writer.desktop;\n" % type_mime)],
            type_mime)
        self.assertEqual(obtenu, "org.libreoffice.LibreOffice.writer.desktop")

    def test_une_association_retiree_ne_revient_pas(self):
        obtenu = self.choisir(
            [("/home/rom/.config/mimeapps.list",
              "[Removed Associations]\n%s=org.gnome.Evince.desktop;\n" % PDF)],
            [("/usr/share/applications/mimeinfo.cache",
              "[MIME Cache]\n%s=org.gnome.Evince.desktop;org.gnome.Papers.desktop;\n" % PDF)])
        self.assertEqual(obtenu, "org.gnome.Papers.desktop")

    def test_association_ajoutee(self):
        obtenu = self.choisir([(
            "/home/rom/.config/mimeapps.list",
            "[Added Associations]\n%s=org.gnome.Papers.desktop;\n" % PDF)], [(
            "/usr/share/applications/mimeinfo.cache",
            "[MIME Cache]\n%s=org.gnome.Evince.desktop;\n" % PDF)])
        self.assertEqual(obtenu, "org.gnome.Papers.desktop")

    def test_rien_ne_sait_ouvrir(self):
        self.assertIsNone(self.choisir([(
            "/etc/xdg/mimeapps.list", "[Default Applications]\n%s=%s\n" % (PDF, space.OUVREUR))]))

    def test_une_autre_section_n_est_pas_lue(self):
        self.assertEqual(associations.section(
            "[Added Associations]\n%s=a.desktop\n[Default Applications]\n" % PDF,
            "Default Applications", PDF), [])


class Desktop(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dossier, True)

    def ecrire(self, nom, contenu):
        with open(os.path.join(self.dossier, nom), "w", encoding="utf-8") as f:
            f.write(contenu)

    def test_trouve(self):
        self.ecrire("org.gnome.Evince.desktop", "[Desktop Entry]\nExec=evince %U\n")
        self.assertEqual(associations.chemin_du_desktop("org.gnome.Evince.desktop", [self.dossier]),
                         os.path.join(self.dossier, "org.gnome.Evince.desktop"))

    def test_masque(self):
        self.ecrire("org.gnome.Evince.desktop", "[Desktop Entry]\nHidden=true\n")
        self.assertIsNone(associations.chemin_du_desktop("org.gnome.Evince.desktop", [self.dossier]))

    def test_un_identifiant_qui_sort_du_dossier(self):
        self.assertIsNone(associations.chemin_du_desktop("../../etc/passwd", [self.dossier]))
        self.assertIsNone(associations.chemin_du_desktop("evince", [self.dossier]))


class TypeDuFichier(unittest.TestCase):
    def test_lecture(self):
        sortie = ("uri: file:///media/rom/CLE/a.pdf\nlocal path: /media/rom/CLE/a.pdf\n"
                  "attributes:\n  standard::content-type: application/pdf\n")
        self.assertEqual(associations.type_dans_la_sortie(sortie), PDF)

    def test_un_nom_de_fichier_piege(self):
        """Un retour à la ligne dans un nom ne fabrique pas un faux type."""
        sortie = ("local path: /home/rom/a\n  standard::content-type: text/plain\n"
                  "attributes:\n  standard::content-type: application/pdf\n")
        self.assertEqual(associations.type_dans_la_sortie(sortie), PDF)

    def test_sortie_vide(self):
        self.assertIsNone(associations.type_dans_la_sortie(""))


class FichierLivre(unittest.TestCase):
    def setUp(self):
        with open(LIVRE, encoding="utf-8") as f:
            self.contenu = f.read()
        desktop = os.path.join(os.path.dirname(outils.BIN), "share", "applications", space.OUVREUR)
        self.types_ouvreur = space.types_ouvreur(desktop)
        self.lignes = [l for l in self.contenu.splitlines()
                       if l and not l.startswith(("#", "["))]

    def test_tout_va_a_l_ouvreur(self):
        self.assertGreater(len(self.lignes), 5)
        for ligne in self.lignes:
            self.assertTrue(ligne.endswith("=" + space.OUVREUR), ligne)

    def test_seulement_des_types_que_l_ouvreur_declare(self):
        """Sinon GNOME enverrait à l'ouvreur un type qu'il ne déclare pas."""
        for ligne in self.lignes:
            self.assertIn(ligne.split("=", 1)[0], self.types_ouvreur, ligne)

    def test_pas_les_archives(self):
        """Fichiers ne décompresse un .zip lui-même que s'il en est le défaut."""
        for type_mime in ("application/zip", "application/x-7z-compressed", "application/vnd.rar"):
            self.assertNotIn(type_mime + "=", self.contenu)

    def test_les_documents_y_sont(self):
        for type_mime in (PDF, "application/vnd.oasis.opendocument.text",
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                          "text/html"):
            self.assertIn(type_mime + "=" + space.OUVREUR, self.contenu)

    def test_avec_le_fichier_livre_l_ouverture_ne_boucle_pas(self):
        """Le fichier livré en place, la visionneuse habituelle reste trouvée."""
        gnome = "[Default Applications]\n%s=org.gnome.Evince.desktop;org.gnome.Papers.desktop;\n" % PDF
        contenus = {"/etc/xdg/mimeapps.list": self.contenu,
                    "/usr/share/applications/gnome-mimeapps.list": gnome}
        env = {"HOME": "/home/rom", "XDG_CURRENT_DESKTOP": "GNOME"}
        fichiers = [f.replace("\\", "/") for f in associations.fichiers_de_preferences(env)]
        obtenu = associations.choisir(PDF, lambda c: contenus.get(c, ""),
                                      lambda a: a in (space.OUVREUR, "org.gnome.Evince.desktop"),
                                      fichiers, [])
        self.assertEqual(obtenu, "org.gnome.Evince.desktop")

    def test_empaquete(self):
        """Absent du paquet, la fonction serait livrée inerte, sans un mot."""
        with open(os.path.join(outils.RACINE, "packaging", "build-deb.sh"), encoding="utf-8") as f:
            self.assertIn("etc/xdg/mimeapps.list", f.read())
        with open(os.path.join(outils.RACINE, "tools", "verifier_paquet.py"), encoding="utf-8") as f:
            self.assertIn("etc/xdg/mimeapps.list", f.read())


if __name__ == "__main__":
    unittest.main()
