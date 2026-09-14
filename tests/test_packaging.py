# -*- coding: utf-8 -*-
"""Le paquet codebyr-tools doit embarquer TOUT le userland Codebyr.

C'est le seul chemin de correctif vers les machines déjà installées : un outil
oublié dans la liste de `build-deb.sh` n'atteindra jamais un poste existant,
même après un « apt upgrade ». Le bug est silencieux — d'où ce test.
"""
import glob
import os
import re
import unittest

from outils import BIN, RACINE

BUILD_DEB = os.path.join(RACINE, "packaging", "build-deb.sh")

# Outils volontairement ABSENTS du paquet, parce qu'ils n'ont de sens que sur le
# support live et jamais sur une machine installée :
#   · codebyr-installer            lance Calamares, qui est désinstallé à la fin
#                                  de l'installation ;
#   · codebyr-nettoyage-installation  supprime le compte de démonstration
#                                  (« userdel -r user ») — un script à ne pas
#                                  laisser traîner sur un poste en service.
HORS_PAQUET = {
    "usr/bin/codebyr-installer",
    "usr/bin/codebyr-nettoyage-installation",
}


def chemins_du_paquet():
    """Les chemins listés dans la boucle « for chemin in ... » de build-deb.sh."""
    with open(BUILD_DEB, encoding="utf-8") as f:
        source = f.read()
    bloc = re.search(r"for chemin in \\\n(.*?)\ndo\n", source, re.S)
    assert bloc, "boucle « for chemin in » introuvable dans build-deb.sh"
    return [l.strip().rstrip("\\").strip() for l in bloc.group(1).splitlines()
            if l.strip().rstrip("\\").strip()]


class Paquet(unittest.TestCase):

    def setUp(self):
        self.chemins = chemins_du_paquet()
        self.src = os.path.join(RACINE, "live-build", "config",
                                "includes.chroot_after_packages")

    def test_les_chemins_listes_existent(self):
        for chemin in self.chemins:
            self.assertTrue(os.path.exists(os.path.join(self.src, chemin)),
                            "listé dans build-deb.sh mais absent du dépôt : %s" % chemin)

    def test_aucun_outil_codebyr_oublie(self):
        listes = set(self.chemins)
        for f in sorted(glob.glob(os.path.join(BIN, "codebyr-*"))):
            nom = "usr/bin/" + os.path.basename(f)
            if os.path.isdir(f) or nom in HORS_PAQUET:
                continue
            self.assertIn(nom, listes,
                          "%s n'est pas embarqué dans codebyr-tools : les machines "
                          "déjà installées ne le recevront jamais." % nom)

    def test_le_module_partage_est_embarque(self):
        # Sans /usr/share/codebyr/registre.py, TOUS les outils Codebyr échouent
        # dès l'import : le paquet doit l'emporter, pas seulement les scripts.
        couvert = any(c in ("usr/share/codebyr", "usr/share/codebyr/registre.py")
                      for c in self.chemins)
        self.assertTrue(couvert,
                        "le module partagé registre.py n'est pas dans le paquet : "
                        "les outils planteraient à l'import sur les machines "
                        "mises à jour. Chemins listés : %s" % self.chemins)

    def test_le_postinst_rattrape_les_machines_existantes(self):
        with open(os.path.join(RACINE, "packaging", "codebyr-tools.postinst"),
                  encoding="utf-8") as f:
            postinst = f.read()
        self.assertIn("codebyr-durcir-poste", postinst,
                      "sans cet appel, les correctifs de durcissement ne "
                      "toucheraient que les nouvelles installations")

    def test_la_construction_refuse_de_reutiliser_un_arbre_deja_bati(self):
        """Le piège à ISO périmée, constaté en vrai le 20/08/2026.

        live-build note chaque étape terminée dans `.build/`, et le `rsync` de
        `build.sh` exclut ce dossier. Relancer une construction sur un arbre
        déjà bâti fait donc sauter toutes les étapes : lb annonce « Build
        completed successfully » en 90 secondes sans rien reconstruire. Ce
        jour-là, l'arbre contenait encore le userland de la 1.0.7.

        Deux garde-fous doivent rester en place : le nettoyage automatique des
        jalons, et la preuve que l'ISO récupérée sort bien de CETTE
        construction.

        Cette preuve ne peut PAS être une comparaison de dates. live-build
        construit de façon reproductible : il fixe SOURCE_DATE_EPOCH au
        démarrage de « lb build » et xorriso en estampille l'image. La date de
        l'ISO est donc celle du début, jamais postérieure à un repère pris au
        même instant — le test « l'ISO est-elle plus récente ? » était faux à
        tous les coups. Le 20/08/2026 il a rejeté une image parfaitement
        valide et fait relancer une construction d'une heure pour rien.

        La preuve tient désormais à l'existence : on efface toute ISO avant de
        construire, donc ce qui se trouve là ensuite ne peut venir que d'ici.
        """
        with open(os.path.join(RACINE, "live-build", "scripts", "build.sh"),
                  encoding="utf-8") as f:
            source = f.read()
        self.assertIn("lb clean", source)
        self.assertIn('$WORK/.build', source,
                      "le script doit détecter les jalons d'une construction "
                      "précédente")
        self.assertIn('rm -f "$WORK"/*.iso', source,
                      "l'ISO doit être effacée AVANT la construction : c'est "
                      "ce qui prouve que celle trouvée après en provient")
        self.assertNotIn("-nt", source,
                         "comparer les dates est faux : live-build estampille "
                         "l'ISO à l'instant du début (SOURCE_DATE_EPOCH)")

    def test_le_controle_de_phrase_de_passe_lit_la_bonne_colonne(self):
        """Un garde-fou qui ne peut pas se déclencher est pire qu'aucun.

        `gpg-connect-agent keyinfo --list` renvoie :
            S KEYINFO <keygrip> D - - <cache> <protection> <fpr> <ttl> <flags>
        soit $7 = cache (0/1/-) et $8 = protection (P/C/-).

        Le script lisait $7 : il cherchait un « C » dans une colonne qui n'en
        contient jamais. Il annonçait donc « protection indéterminée » sur une
        clé nue, et n'aurait jamais refusé de signer.
        """
        with open(os.path.join(RACINE, "packaging", "publish-apt.sh"),
                  encoding="utf-8") as f:
            source = f.read()
        self.assertIn("{print $8}", source,
                      "la protection de la clé est en colonne 8, pas 7")
        self.assertNotIn("{print $7}", source)

    def test_la_publication_refuse_un_paquet_perime(self):
        """Publier ce qui traîne dans dist/ n'est pas publier son travail.

        Le 23/08/2026, la 1.5.0 est partie avec la version précédente de
        l'icône du panneau : le .deb avait été construit avant le correctif et
        personne ne pouvait le voir — le numéro de version, lui, était juste.

        Même piège que l'ISO périmée dans build.sh : un artefact daté qu'on
        republie en croyant republier le code.
        """
        with open(os.path.join(RACINE, "packaging", "publish-apt.sh"),
                  encoding="utf-8") as f:
            source = f.read()
        self.assertIn("-newer", source,
                      "la publication doit comparer la date du paquet à celle "
                      "des sources")
        self.assertIn("plus ancien que le code", source)

    def test_la_publication_refuse_une_signature_unique(self):
        """Signer sans la clé maîtresse bloque définitivement des machines.

        Une machine installée avec une ISO antérieure à la sous-clé a un
        trousseau qui l'ignore. Pour le réparer il lui faut codebyr-tools ≥
        1.3, dont le postinst rafraîchit le trousseau — mais pour recevoir ce
        paquet, apt doit vérifier une signature qu'il ne sait pas vérifier.
        Elle ne se répare qu'à la main, sur place.

        Le script se contentait d'avertir. Le 20/08/2026 l'avertissement a
        défilé vingt lignes au-dessus d'un « Bonne signature » final, et le
        dépôt à signature unique a été produit sans que personne ne le
        remarque. Il doit donc REFUSER, et non prévenir.
        """
        with open(os.path.join(RACINE, "packaging", "publish-apt.sh"),
                  encoding="utf-8") as f:
            source = f.read()
        self.assertIn("CODEBYR_TRANSITION_TERMINEE", source,
                      "la signature par la sous-clé seule doit exiger une "
                      "autorisation explicite")
        debut = source.index('if [ "$etat_maitresse" = "#" ]')
        fin = source.index("else", debut)
        self.assertIn("exit 1", source[debut:fin],
                      "sans la clé maîtresse, le script doit s'arrêter avant "
                      "de générer quoi que ce soit")

    def test_les_dependances_arrivent_sans_intervention(self):
        """Une dépendance nouvelle doit pouvoir s'installer TOUTE SEULE.

        Promesse du projet : personne ne tape de commande pour recevoir une
        mise à jour. Or unattended-upgrades vérifie l'origine de CHAQUE paquet
        du lot, y compris les dépendances qu'il tire lui-même (sanity_problem :
        « pkg %s is not in an allowed origin »). Si l'archive Debian n'est pas
        autorisée, ajouter une dépendance Debian à codebyr-tools ne casse pas
        l'installation : elle fait abandonner la mise à jour ENTIÈRE, en
        silence, sur tout le parc.

        Ce qui sauve Codebyr, c'est que le fichier 51 AJOUTE son origine à
        celles de Debian. Un « #clear » suffirait à tout rompre sans qu'aucun
        autre test ne s'en aperçoive : d'où celui-ci.
        """
        conf = os.path.join(self.src, "etc", "apt", "apt.conf.d",
                            "51codebyr-unattended")
        with open(conf, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("origin=Codebyr OS", source)
        self.assertNotIn("#clear", source,
                         "purger la liste retirerait l'archive Debian des "
                         "origines autorisées : plus aucune dépendance "
                         "nouvelle ne pourrait s'installer seule")

    def test_la_cle_publique_voyage_avec_l_image(self):
        """Une procédure de vérification qu'on ne peut pas suivre ne vaut rien.

        La release v1.5.5 est partie sans `codebyr-signing-key.asc`, alors que
        ses propres instructions commencent par « gpg --import
        codebyr-signing-key.asc ». Depuis un poste vierge, la commande échoue,
        puis la vérification échoue faute de clé publique.

        Personne du côté du projet ne pouvait le voir : le mainteneur a cette
        clé importée depuis des mois. Il a fallu un regard extérieur, sur une
        machine qui ne l'avait pas.

        La cause tenait à une phrase : le script disait « et
        codebyr-signing-key.asc dans le dépôt », ce qui se lit « elle y est
        déjà, rien à joindre ».
        """
        with open(os.path.join(RACINE, "live-build", "scripts",
                               "sign-release.sh"), encoding="utf-8") as f:
            source = f.read()
        self.assertIn('cp -f "$CLE_PUB" "$DIST/"', source,
                      "la clé publique doit être déposée à côté des sommes, "
                      "pour être publiée avec elles")
        self.assertIn("dist/codebyr-signing-key.asc", source,
                      "la commande de publication doit lister la clé")

    def test_aucun_fichier_livre_en_fins_de_ligne_windows(self):
        """Un « \\r » au bout du shebang rend le script INEXÉCUTABLE.

            env: 'python3\\r': Aucun fichier ou dossier de ce nom

        Sur Codebyr, cela veut dire qu'aucun Espace ne s'ouvre — la fonction
        centrale du système. Constaté le 24/08/2026 sur une installation
        fraîche, après que des scripts d'édition eurent réécrit des fichiers en
        mode texte sous Windows. git avertissait à chaque commit ; personne n'a
        lu l'avertissement.

        Ce test le rend impossible à ignorer.
        """
        fautifs = []
        for dossier, _, fichiers in os.walk(self.src):
            for nom in fichiers:
                chemin = os.path.join(dossier, nom)
                if os.path.splitext(nom)[1] in (".png", ".jpg", ".xpi", ".gpg"):
                    continue
                try:
                    with open(chemin, "rb") as f:
                        debut = f.read(4096)
                except OSError:
                    continue
                if b"\r\n" in debut:
                    fautifs.append(os.path.relpath(chemin, self.src))
        self.assertEqual(fautifs, [],
                         "fins de ligne Windows dans des fichiers livrés : %s"
                         % ", ".join(sorted(fautifs)))

    def test_pas_de_cache_python_dans_l_image(self):
        # Un __pycache__ traîné depuis un poste de développement finirait copié
        # tel quel dans l'ISO.
        parasites = glob.glob(os.path.join(self.src, "**", "__pycache__"),
                              recursive=True)
        self.assertEqual(parasites, [], "caches Python à supprimer : %s" % parasites)


class LanceursGraphiques(unittest.TestCase):
    """Une fenêtre sans lanceur du même nom n'est rattachée à aucune application.

    GNOME associe une fenêtre à son application par le NOM du fichier .desktop,
    qui doit valoir exactement l'identifiant déclaré par le programme. Sans lui,
    le dock et la vue d'ensemble affichent l'icône générique — un losange gris —
    au lieu de celle de Codebyr. Constaté le 13/09/2026 : la fenêtre de
    bienvenue n'avait qu'une entrée dans /etc/xdg/autostart, qui ne sert pas à
    ce rattachement.
    """

    def setUp(self):
        self.racine = os.path.join(RACINE, "live-build", "config",
                                   "includes.chroot_after_packages")

    def _identifiants(self):
        trouves = {}
        for chemin in sorted(glob.glob(os.path.join(BIN, "codebyr-*"))):
            with open(chemin, encoding="utf-8") as f:
                source = f.read()
            m = re.search(r'application_id="([^"]+)"', source)
            if m:
                trouves[os.path.basename(chemin)] = m.group(1)
        return trouves

    def test_chaque_application_graphique_a_son_lanceur(self):
        identifiants = self._identifiants()
        self.assertIn("codebyr-bienvenue", identifiants, "outil introuvable")
        for outil, appid in identifiants.items():
            lanceur = os.path.join(self.racine, "usr", "share", "applications",
                                   appid + ".desktop")
            self.assertTrue(os.path.exists(lanceur),
                            "%s se déclare « %s » mais aucun lanceur de ce nom "
                            "n'est livré : GNOME affichera l'icône générique"
                            % (outil, appid))

    def test_le_paquet_rafraichit_le_cache_d_icones(self):
        # Dès qu'un cache d'icônes existe, GTK s'y fie et ignore les fichiers
        # absents : une icône livrée par le paquet resterait invisible,
        # remplacée par l'icône générique du bureau. Constaté le 13/09/2026.
        with open(os.path.join(RACINE, "packaging", "codebyr-tools.postinst"),
                  encoding="utf-8") as f:
            postinst = f.read()
        self.assertIn("update-icon-caches", postinst)
        self.assertIn("/usr/share/icons/hicolor", postinst)

    def test_la_fenetre_annonce_son_identite_au_bureau(self):
        # Sous Wayland, GTK annonce le NOM DE PROGRAMME : sans set_prgname,
        # la fenêtre se présente comme « codebyr-bienvenue » et GNOME ne
        # trouve aucun lanceur de ce nom (icône générique).
        for outil, appid in self._identifiants().items():
            with open(os.path.join(BIN, outil), encoding="utf-8") as f:
                source = f.read()
            self.assertIn('GLib.set_prgname("%s")' % appid, source,
                          "%s n'annonce pas son identité au bureau" % outil)

    def test_chaque_lanceur_a_son_icone(self):
        dossier = os.path.join(self.racine, "usr", "share", "applications")
        for nom in sorted(os.listdir(dossier)):
            with open(os.path.join(dossier, nom), encoding="utf-8") as f:
                icone = re.search(r"(?m)^Icon=(.+)$", f.read()).group(1).strip()
            if icone.startswith("io.codebyr."):
                svg = os.path.join(self.racine, "usr", "share", "icons", "hicolor",
                                   "scalable", "apps", icone + ".svg")
                self.assertTrue(os.path.exists(svg), "%s : icône absente (%s)" % (nom, icone))


if __name__ == "__main__":
    unittest.main()


class LeServiceDesComptes(unittest.TestCase):
    """Le service des comptes d'Espaces doit ARRIVER et être ACTIVÉ.

    Livré sans ses unités systemd, il ne démarrerait jamais ; livré sans être
    activé, le premier Espace à compte dédié répondrait « le service n'est pas
    installé » sur une machine où il l'est.
    """

    def setUp(self):
        with open(BUILD_DEB, encoding="utf-8") as f:
            self.build = f.read()
        with open(os.path.join(RACINE, "packaging", "codebyr-tools.postinst"),
                  encoding="utf-8") as f:
            self.postinst = f.read()

    def test_le_service_et_le_premier_processus_sont_livres(self):
        self.assertIn("usr/lib/codebyr", self.build)

    def test_les_deux_unites_sont_livrees(self):
        for unite in ("codebyr-uid.socket", "codebyr-uid.service"):
            self.assertIn("usr/lib/systemd/system/%s" % unite, self.build, unite)

    def test_ils_arrivent_executables(self):
        # Sans le bit d'exécution, root ne peut pas lancer le service, et le
        # premier processus d'un Espace ne démarre pas.
        self.assertIn('find "$STAGE/usr/lib/codebyr" -type f -exec chmod 755', self.build)

    def test_la_socket_est_activee_a_l_installation(self):
        self.assertIn("systemctl enable --now codebyr-uid.socket", self.postinst)
        # Chemin absolu, comme systemd-sysctl : « command -v » avait déjà
        # laissé un réglage ne jamais s'appliquer, sans la moindre trace.
        self.assertIn("/usr/bin/systemctl enable --now", self.postinst)
        self.assertIn("/usr/bin/systemctl daemon-reload", self.postinst)

    def test_rien_ne_tourne_tant_qu_aucun_espace_ne_le_demande(self):
        # Activation par socket : le service démarre à la première connexion.
        chemin = os.path.join(RACINE, "live-build", "config",
                              "includes.chroot_after_packages", "usr", "lib",
                              "systemd", "system", "codebyr-uid.service")
        with open(chemin, encoding="utf-8") as f:
            service = f.read()
        self.assertIn("Requires=codebyr-uid.socket", service)
        self.assertNotIn("WantedBy=multi-user.target\n[", service)
