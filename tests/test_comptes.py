# -*- coding: utf-8 -*-
"""Un compte Unix par Espace : les décisions du service privilégié.

Ce service tourne en root. Une erreur ici ne coûte pas une fonctionnalité,
elle donne la machine. Chaque règle est donc éprouvée séparément, et chaque
test dit ce qui arriverait si elle tombait.
"""
import ast
import os
import re
import subprocess
import unittest

from outils import LIB, RACINE  # noqa: F401 — place les modules partagés
import comptes  # noqa: E402

SERVICE = os.path.join(RACINE, "live-build", "config",
                       "includes.chroot_after_packages", "usr", "lib", "codebyr",
                       "codebyr-uid")
INIT = os.path.join(RACINE, "live-build", "config",
                    "includes.chroot_after_packages", "usr", "lib", "codebyr",
                    "codebyr-espace-init")
UNITES = os.path.join(RACINE, "live-build", "config",
                      "includes.chroot_after_packages", "usr", "lib", "systemd", "system")


def _lire(chemin):
    with open(chemin, encoding="utf-8") as f:
        return f.read()


def _code(chemin):
    """La source SANS les commentaires ni les docstrings — le code seul.

    Un test qui cherche « shell=True » dans la source brute le trouve dans le
    commentaire qui explique pourquoi on n'en veut pas, et passe au rouge pour
    la meilleure des raisons. On lit donc le code, pas ce qui l'entoure.

    Les chaînes, elles, RESTENT : un chemin écrit en dur est du code, et c'est
    justement ce que plusieurs de ces tests cherchent.
    """
    arbre = ast.parse(_lire(chemin))
    for noeud in ast.walk(arbre):
        corps = getattr(noeud, "body", None)
        if (isinstance(corps, list) and corps
                and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)
                and isinstance(corps[0].value.value, str)):
            corps.pop(0)
    return ast.unparse(arbre)


class NomDuCompte(unittest.TestCase):

    def test_le_proprietaire_fait_partie_du_nom(self):
        # Deux utilisateurs de la même machine n'ont jamais le même Espace
        # « travail » : sans l'UID dans le nom, ils partageraient le compte,
        # donc les fichiers.
        self.assertEqual(comptes.nom_compte(1000, "travail"), "cbyr-1000-travail")
        self.assertNotEqual(comptes.nom_compte(1000, "travail"),
                            comptes.nom_compte(1001, "travail"))

    def test_un_compte_systeme_ne_peut_pas_posseder_d_espace(self):
        for uid in (0, 1, 999, -1):
            with self.assertRaises(ValueError, msg="UID %d" % uid):
                comptes.nom_compte(uid, "travail")

    def test_les_identifiants_tordus_sont_refuses(self):
        for espace in ("../root", "trav ail", "Travail", "", "a" * 21,
                       "travail\n", "-travail", "travail/x"):
            with self.assertRaises(ValueError, msg=repr(espace)):
                comptes.nom_compte(1000, espace)

    def test_le_nom_tient_dans_la_limite_unix(self):
        self.assertLessEqual(len(comptes.nom_compte(65534, "a" * 20)), 32)


class QuiADroitDeDemander(unittest.TestCase):

    def test_un_utilisateur_du_bureau_a_le_droit(self):
        autorise, _ = comptes.demandeur_autorise(1000, "romtouf")
        self.assertTrue(autorise)

    def test_un_espace_ne_demande_rien(self):
        # Sinon « jetable » ferait ouvrir « banque » et lirait ses fichiers :
        # le chantier se retournerait contre lui-même.
        autorise, raison = comptes.demandeur_autorise(998, "cbyr-1000-jetable")
        self.assertFalse(autorise)
        self.assertIn("Espace", raison)

    def test_les_comptes_systeme_sont_refuses(self):
        for uid, nom in ((0, "root"), (33, "www-data"), (999, "systemd-network")):
            autorise, _ = comptes.demandeur_autorise(uid, nom)
            self.assertFalse(autorise, nom)

    def test_le_nom_seul_ne_suffit_pas_a_passer(self):
        # Un compte d'Espace reste refusé même si son UID est élevé.
        autorise, _ = comptes.demandeur_autorise(4242, "cbyr-1000-banque")
        self.assertFalse(autorise)


class Chemins(unittest.TestCase):

    def test_le_dossier_d_un_espace_est_range_par_proprietaire(self):
        self.assertEqual(comptes.chemin_home(1000, "banque"),
                         "/var/lib/codebyr/espaces/1000/banque")

    def test_les_dossiers_sont_hors_du_dossier_personnel_du_bureau(self):
        # Sous /home, le compte du bureau pourrait renommer ou remplacer le
        # dossier d'un Espace — donc décider de ce que l'Espace lit.
        self.assertTrue(comptes.chemin_home(1000, "banque").startswith("/var/lib/"))

    def test_aucun_identifiant_tordu_n_entre_dans_un_chemin(self):
        for espace in ("../../etc", "a/b", ".."):
            with self.assertRaises(ValueError, msg=espace):
                comptes.chemin_home(1000, espace)

    def test_la_passerelle_n_existe_que_pour_un_espace(self):
        self.assertEqual(comptes.chemin_passerelle("cbyr-1000-banque"),
                         "/run/codebyr/passerelles/cbyr-1000-banque")
        for compte in ("romtouf", "root", "", "cbyr"):
            with self.assertRaises(ValueError, msg=compte):
                comptes.chemin_passerelle(compte)

    def test_le_depot_n_existe_que_pour_un_espace(self):
        self.assertEqual(comptes.chemin_depot("cbyr-1000-banque"),
                         "/run/codebyr/depots/cbyr-1000-banque")
        for compte in ("romtouf", "root", "", "cbyr", "../etc"):
            with self.assertRaises(ValueError, msg=compte):
                comptes.chemin_depot(compte)

    def test_depot_et_passerelle_ne_se_confondent_pas(self):
        # Les deux vont dans des sens opposés : l'un porte les sockets du
        # bureau vers l'Espace, l'autre ceux que le bureau sert à l'Espace.
        # Les mélanger reviendrait à laisser un Espace écrire là où root
        # présente les sockets du bureau.
        self.assertNotEqual(comptes.chemin_depot("cbyr-1000-banque"),
                            comptes.chemin_passerelle("cbyr-1000-banque"))

    def test_un_depot_ne_contient_jamais_le_bus_de_session(self):
        self.assertNotIn("bus", comptes.SOCKETS_DU_BUREAU)
        for arrivee in comptes.SOCKETS_DU_BUREAU.values():
            self.assertFalse(arrivee.startswith("/run/user/"), arrivee)

    def test_le_socket_du_bureau_est_construit_jamais_recu(self):
        self.assertEqual(comptes.socket_du_bureau(1000, "wayland-0"),
                         "/run/user/1000/wayland-0")
        self.assertEqual(comptes.socket_du_bureau(1000, "pipewire"),
                         "/run/user/1000/pipewire-0")
        for nom in ("../bus", "bus", "/etc/passwd", "wayland-0/../bus", "systemd"):
            with self.assertRaises(ValueError, msg=nom):
                comptes.socket_du_bureau(1000, nom)


class Plafonds(unittest.TestCase):
    """Ce qui entre dans une commande lancée par root se valide ici."""

    def test_les_valeurs_saines_passent(self):
        self.assertEqual(comptes.plafonds_valides("75%", 4096), ("75%", 4096))
        self.assertEqual(comptes.plafonds_valides("2G", 800), ("2G", 800))

    def test_une_valeur_tordue_retombe_sur_le_defaut(self):
        # Ni refus ni exception : un plafond incompris ne doit ni lever la
        # protection, ni empêcher l'ouverture d'un Espace.
        for memoire in ("; rm -rf /", "0G", "200%", "2 G", "", None, 42, True,
                        "2G\n", "$(id)"):
            valeur, _ = comptes.plafonds_valides(memoire, 800)
            self.assertEqual(valeur, comptes.MEMOIRE_DEFAUT, repr(memoire))

    def test_un_nombre_de_taches_tordu_retombe_sur_le_defaut(self):
        for taches in (0, -1, 1, 99999, True, "800", None, 3.5):
            _, valeur = comptes.plafonds_valides("2G", taches)
            self.assertEqual(valeur, comptes.TACHES_DEFAUT, repr(taches))


class LaPortee(unittest.TestCase):

    def test_une_portee_par_espace(self):
        self.assertEqual(comptes.unite_de_l_espace("cbyr-1000-banque"),
                         "codebyr-espace-cbyr-1000-banque.scope")
        self.assertNotEqual(comptes.unite_de_l_espace("cbyr-1000-banque"),
                            comptes.unite_de_l_espace("cbyr-1001-banque"))

    def test_aucun_compte_ordinaire_n_a_de_portee(self):
        for compte in ("romtouf", "root", "", "cbyr", "../../etc"):
            with self.assertRaises(ValueError, msg=compte):
                comptes.unite_de_l_espace(compte)


class LaSocketDOrdres(unittest.TestCase):
    """Elle commande l'Espace : elle ne doit jamais entrer dans le bac à sable."""

    def test_elle_n_est_pas_montee_dans_l_espace(self):
        # Sinon un programme échappé de bubblewrap se relancerait hors du bac
        # à sable — le chantier rendrait l'évasion plus confortable.
        self.assertNotIn(comptes.SOCKET_EXEC, comptes.SOCKETS_DU_BUREAU)

    def test_le_bac_a_sable_ne_la_monte_nulle_part(self):
        with open(os.path.join(LIB, "bac_a_sable.py"), encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn("SOCKET_EXEC", source)
        self.assertNotIn("/exec", source)


class CeQuiTraverse(unittest.TestCase):
    """La liste de ce qu'un Espace reçoit. Ce qui n'y est pas ne passe jamais."""

    def test_l_affichage_toujours_le_son_sur_demande(self):
        self.assertEqual(comptes.passages("wayland-0", son=False),
                         [("wayland-0", "wayland-0")])
        self.assertEqual(comptes.passages("wayland-0", son=True),
                         [("wayland-0", "wayland-0"), ("pipewire", "pipewire-0")])

    def test_le_bus_de_session_n_y_est_jamais(self):
        # C'est lui qui donnait accès à systemd --user, donc à l'exécution
        # hors du bac à sable (faille fermée en 1.1.0).
        for son in (True, False):
            fichiers = [f for _, f in comptes.passages("wayland-0", son)]
            self.assertNotIn("bus", fichiers)

    def test_un_affichage_tordu_est_refuse(self):
        for nom in ("../bus", "/run/user/1000/bus", "wayland-0 ", "wayland",
                    "wayland-0\n", ""):
            with self.assertRaises(ValueError, msg=repr(nom)):
                comptes.passages(nom, son=False)


class LeService(unittest.TestCase):
    """Ce que le service s'interdit, lu dans son code."""

    def setUp(self):
        self.source = _lire(SERVICE)

    def test_l_identite_vient_du_noyau(self):
        self.assertIn("SO_PEERCRED", self.source)
        # Le client ne fournit jamais son UID : il n'est pas cru sur parole.
        self.assertNotIn('demande.get("uid")', self.source)
        self.assertNotIn('demande.get("compte")', self.source)

    def test_aucun_chemin_ne_vient_du_client(self):
        for interdit in ('demande.get("home")', 'demande.get("chemin")',
                         'demande.get("socket")', 'demande.get("passerelle")'):
            self.assertNotIn(interdit, self.source, interdit)

    def test_le_service_n_execute_aucune_commande_du_client(self):
        # Il prépare, il n'exécute pas : pas de shell, pas de commande reçue.
        self.assertNotIn("shell=True", self.source)
        self.assertNotIn('demande.get("commande")', self.source)

    def test_les_droits_sont_poses_sur_un_socket_jamais_sur_un_dossier(self):
        self.assertIn("Accorde (ou retire) l'accès d'UN compte à UN socket",
                      self.source)

    def test_l_espace_ne_fait_que_traverser_le_depot(self):
        # « x » et rien d'autre. Avec « r », l'Espace découvrirait les sockets
        # que le bureau y dépose ; avec « w », il en fabriquerait une pour se
        # faire passer pour l'hôte auprès d'un autre Espace.
        self.assertIn("u:%d:rwx,u:%d:x,m::rwx", self.source)
        self.assertNotIn("u:%d:rwx,u:%d:rx", self.source)
        self.assertNotIn("u:%d:rwx,u:%d:rwx", self.source)

    def test_les_droits_du_depot_sont_poses_en_entier(self):
        # « --set » et non « -m » : un droit oublié d'une ouverture précédente
        # ne doit pas survivre à la suivante.
        self.assertIn('"--set"', self.source)

    def test_le_dossier_d_execution_du_bureau_n_est_jamais_ouvert(self):
        # setfacl sur /run/user/<uid> rendrait joignables tous les sockets
        # qu'il protège, à commencer par le bus de session. Mesuré le
        # 14/09/2026 sur la VM : c'est exactement ce qui arrivait.
        self.assertNotRegex(self.source, r"setfacl[^\n]*run/user")
        self.assertNotRegex(self.source, r"droit_sur_socket\([^)]*runtime")


class LePremierProcessus(unittest.TestCase):
    """codebyr-espace-init — ce que root lance, et lui seul."""

    def setUp(self):
        self.source = _lire(INIT)
        self.code = _code(INIT)
        self.service = _lire(SERVICE)

    def test_root_ne_lance_qu_un_chemin_ecrit_en_clair(self):
        # Le chemin est une constante du service. S'il pouvait venir de la
        # demande, le client choisirait ce que root exécute.
        self.assertIn('"/usr/lib/codebyr/codebyr-espace-init"', self.service)
        for interdit in ('demande.get("init")', 'demande.get("argv")',
                         'demande.get("programme")'):
            self.assertNotIn(interdit, self.service, interdit)

    def test_le_service_attend_qu_il_ecoute_avant_de_dire_l_espace_pret(self):
        # Vu le 14/09/2026 : le premier processus ne démarrait pas, le service
        # répondait « ok » quand même, et le bureau attendait indéfiniment une
        # réponse sur la socket d'ordres — que ROOT avait créée et mise en
        # écoute, si bien qu'elle acceptait les connexions sans personne
        # derrière. Un échec de lancement doit être un échec, pas une attente.
        self.assertIn("os.pipe()", self.service)
        self.assertIn("select.select", self.service)

    def test_il_n_annonce_qu_apres_ce_qui_peut_echouer(self):
        # Une annonce faite trop tôt ne dirait plus « j'écoute » mais
        # « j'ai démarré », ce qui n'est pas la même promesse.
        code = _code(INIT)
        self.assertLess(code.index("socket.socket(fileno="),
                        code.index("os.write("))

    def test_il_refuse_de_tourner_en_root(self):
        # S'il y tournait, tout le chantier serait vide de sens : il exécute
        # justement ce que le bureau lui envoie.
        self.assertIn("os.geteuid() == 0", self.source)

    def test_il_n_execute_jamais_par_un_shell(self):
        self.assertNotIn("shell=True", self.code)
        self.assertNotIn("os.system", self.code)

    def test_il_verifie_qui_lui_parle_aupres_du_noyau(self):
        self.assertIn("SO_PEERCRED", self.code)

    def test_il_ne_demande_jamais_rien_a_root(self):
        # Il est en bout de chaîne : rien ne doit remonter vers le service.
        # Le chemin de la socket du service n'apparaît nulle part dans son
        # code : il ne peut donc pas la joindre. (Son message d'usage cite le
        # service par son nom, ce qui est un renseignement, pas un appel.)
        self.assertNotIn("/run/codebyr-uid", self.code)
        # Il n'ouvre aucune connexion : il ne fait qu'accepter, sur une socket
        # qu'il a reçue déjà ouverte. Il ne peut donc joindre personne.
        self.assertNotIn(".connect(", self.code)
        self.assertIn("socket.socket(fileno=", self.code)


class DroitsDExecution(unittest.TestCase):
    """Root exécute ces deux fichiers : sans le bit, aucun Espace ne s'ouvre.

    Le dépôt est consulté depuis Windows comme depuis Linux, et seul l'index
    de git garde ce bit de façon fiable dans les deux cas. On le lit donc là.
    """

    def test_le_service_et_le_premier_processus_sont_executables(self):
        try:
            sortie = subprocess.run(
                ["git", "ls-files", "-s", "--", SERVICE, INIT],
                cwd=RACINE, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            self.skipTest("git indisponible")
        if sortie.returncode != 0 or not sortie.stdout.strip():
            self.skipTest("dépôt git indisponible")
        for ligne in sortie.stdout.splitlines():
            self.assertTrue(ligne.startswith("100755"),
                            "non exécutable dans le dépôt : %s" % ligne)


class LesTenues(unittest.TestCase):
    """Combien de lanceurs tiennent un Espace ouvert, et quand le refermer."""

    def test_fermer_une_fenetre_ne_ferme_pas_les_autres(self):
        t = comptes.Tenues()
        premiere = t.prendre("cbyr-1000-travail")
        seconde = t.prendre("cbyr-1000-travail")
        self.assertFalse(t.rendre(premiere), "l'autre fenêtre est encore ouverte")
        self.assertTrue(t.rendre(seconde), "c'était la dernière")

    def test_les_espaces_se_comptent_separement(self):
        t = comptes.Tenues()
        travail = t.prendre("cbyr-1000-travail")
        t.prendre("cbyr-1000-banque")
        self.assertTrue(t.rendre(travail))

    def test_une_tenue_en_retard_ne_referme_pas_l_espace_rouvert(self):
        # L'utilisateur ferme l'Espace d'un geste, puis le rouvre aussitôt.
        # Le lanceur de la première ouverture rend sa tenue en retard : il ne
        # doit pas refermer l'Espace qui vient d'être rouvert.
        t = comptes.Tenues()
        ancienne = t.prendre("cbyr-1000-travail")
        t.oublier("cbyr-1000-travail")
        nouvelle = t.prendre("cbyr-1000-travail")
        self.assertFalse(t.rendre(ancienne))
        self.assertTrue(t.rendre(nouvelle))

    def test_root_ne_se_laisse_pas_noyer(self):
        t = comptes.Tenues(maximum=3)
        for _ in range(3):
            self.assertIsNotNone(t.prendre("cbyr-1000-travail"))
        self.assertIsNone(t.prendre("cbyr-1000-banque"))

    def test_le_service_tient_par_la_connexion_pas_par_un_message(self):
        # Un compteur tenu par des messages « j'ai fini » fuirait au premier
        # plantage du lanceur : l'Espace resterait ouvert, et son compte
        # garderait l'accès à l'affichage jusqu'au redémarrage.
        code = _code(SERVICE)
        tenir = code.split("def tenir(")[1].split("def servir_client(")[0]
        self.assertIn("client.recv(", tenir)
        self.assertIn("TENUES.rendre(", tenir)

    def test_la_tenue_est_prise_sous_le_verrou_de_la_preparation(self):
        code = _code(SERVICE)
        client = code.split("def servir_client(")[1].split("def servir(")[0]
        bloc = client.split("with VERROU:")[1]
        self.assertLess(bloc.index("traiter("), bloc.index("TENUES.prendre("))
        self.assertLess(bloc.index("TENUES.prendre("), bloc.index("client.sendall("))


class LApplicationNeSurvitPasASonLanceur(unittest.TestCase):

    def test_le_premier_processus_guette_aussi_le_depart_du_lanceur(self):
        # Un proc.wait() seul ne voyait le départ du lanceur qu'après la fin de
        # l'application : un navigateur de Banque restait ouvert, filtre mort.
        code = _code(INIT)
        attendre = code.split("def attendre(")[1].split("def arreter(")[0]
        self.assertIn("os.pidfd_open(", attendre)
        self.assertIn("select.select(", attendre)


class RienNeSurvitAUnEchec(unittest.TestCase):
    """Vu le 14/09/2026 sur la VM, dans cet ordre.

    Une préparation a échoué à mi-chemin : le socket Wayland était monté dans
    la passerelle et le droit accordé, rien n'a été défait. L'essai suivant a
    monté un second socket PAR-DESSUS ; la fermeture n'en a retiré qu'un, et
    s'est dite réussie quand même.
    """

    def setUp(self):
        self.code = _code(SERVICE)

    def test_une_preparation_qui_echoue_defait_ce_qu_elle_a_pose(self):
        preparer = self.code.split("def preparer(")[1].split("def _preparer(")[0]
        self.assertIn("except Exception", preparer)
        self.assertIn("fermer(", preparer)
        self.assertIn("raise", preparer)

    def test_un_espace_deja_ouvert_n_est_pas_referme_par_un_echec(self):
        preparer = self.code.split("def preparer(")[1].split("def _preparer(")[0]
        self.assertIn("deja_ouvert", preparer)

    def test_un_montage_ne_s_empile_jamais_sur_un_autre(self):
        presenter = self.code.split("def presenter(")[1].split("def retirer(")[0]
        self.assertLess(presenter.index("umount"), presenter.index("--bind"))

    def test_la_fermeture_ne_se_dit_pas_reussie_quand_elle_ne_l_est_pas(self):
        fermer = self.code.split("def fermer(")[1].split("def traiter(")[0]
        self.assertIn("'incomplet'", fermer)
        # Plus aucun échec avalé en silence dans le rangement.
        self.assertIsNone(re.search(r"^\s*pass$", fermer, re.M))

    def test_le_retrait_du_droit_ne_peut_pas_echouer_en_silence(self):
        fermer = self.code.split("def fermer(")[1].split("def traiter(")[0]
        bloc = fermer.split("except subprocess.CalledProcessError")[1][:200]
        self.assertIn("echecs.append", bloc)


class LesUnites(unittest.TestCase):

    def test_le_service_est_demarre_a_la_demande(self):
        socket_unite = _lire(os.path.join(UNITES, "codebyr-uid.socket"))
        self.assertIn("ListenStream=/run/codebyr-uid.sock", socket_unite)
        self.assertIn("WantedBy=sockets.target", socket_unite)

    def test_aucun_espace_de_noms_prive_ne_cache_les_montages(self):
        # PrivateMounts, PrivateTmp ou ProtectHome enfermeraient les montages
        # liés dans un espace de noms privé : les Espaces ne verraient plus
        # rien, sans message d'erreur.
        service = _lire(os.path.join(UNITES, "codebyr-uid.service"))
        for interdit in ("PrivateMounts=yes", "PrivateTmp=yes", "ProtectHome=yes",
                         "ProtectSystem=strict"):
            self.assertNotIn(interdit, service, interdit)
        self.assertIn("NoNewPrivileges=yes", service)


if __name__ == "__main__":
    unittest.main()
