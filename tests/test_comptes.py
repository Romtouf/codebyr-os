# -*- coding: utf-8 -*-
"""Un compte Unix par Espace : les décisions du service privilégié.

Ce service tourne en root. Une erreur ici ne coûte pas une fonctionnalité,
elle donne la machine. Chaque règle est donc éprouvée séparément, et chaque
test dit ce qui arriverait si elle tombait.
"""
import os
import re
import unittest

from outils import LIB, RACINE  # noqa: F401 — place les modules partagés
import comptes  # noqa: E402

SERVICE = os.path.join(RACINE, "live-build", "config",
                       "includes.chroot_after_packages", "usr", "lib", "codebyr",
                       "codebyr-uid")
UNITES = os.path.join(RACINE, "live-build", "config",
                      "includes.chroot_after_packages", "usr", "lib", "systemd", "system")


def _lire(chemin):
    with open(chemin, encoding="utf-8") as f:
        return f.read()


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

    def test_le_socket_du_bureau_est_construit_jamais_recu(self):
        self.assertEqual(comptes.socket_du_bureau(1000, "wayland-0"),
                         "/run/user/1000/wayland-0")
        self.assertEqual(comptes.socket_du_bureau(1000, "pipewire"),
                         "/run/user/1000/pipewire-0")
        for nom in ("../bus", "bus", "/etc/passwd", "wayland-0/../bus", "systemd"):
            with self.assertRaises(ValueError, msg=nom):
                comptes.socket_du_bureau(1000, nom)


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

    def test_le_dossier_d_execution_du_bureau_n_est_jamais_ouvert(self):
        # setfacl sur /run/user/<uid> rendrait joignables tous les sockets
        # qu'il protège, à commencer par le bus de session. Mesuré le
        # 14/09/2026 sur la VM : c'est exactement ce qui arrivait.
        self.assertNotRegex(self.source, r"setfacl[^\n]*run/user")
        self.assertNotRegex(self.source, r"droit_sur_socket\([^)]*runtime")


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
