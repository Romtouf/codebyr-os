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

    def test_pas_de_cache_python_dans_l_image(self):
        # Un __pycache__ traîné depuis un poste de développement finirait copié
        # tel quel dans l'ISO.
        parasites = glob.glob(os.path.join(self.src, "**", "__pycache__"),
                              recursive=True)
        self.assertEqual(parasites, [], "caches Python à supprimer : %s" % parasites)


if __name__ == "__main__":
    unittest.main()
