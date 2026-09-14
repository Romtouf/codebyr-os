# -*- coding: utf-8 -*-
"""Le lanceur face au compte dédié : ce qu'il refuse, et ce qu'il ne fait jamais.

Le branchement de `codebyr-space` sur le service des comptes d'Espaces ajoute
une seconde façon d'ouvrir un Espace. Les deux règles qui comptent :

· un Espace qui demande un compte dédié et ne peut pas l'obtenir NE S'OUVRE
  PAS — il ne retombe jamais sous le compte du bureau « en attendant » ;
· un geste qui n'est pas encore prêt sous compte dédié est REFUSÉ avec une
  explication, jamais tenté à moitié sur un dossier qui n'est plus le bon.
"""
import json
import os
import socket
import tempfile
import threading
import unittest
from unittest import mock

import outils
from outils import LIB  # noqa: F401 — place les modules partagés
import compte_dedie  # noqa: E402

space = outils.charger("codebyr-space")

DEDIE = {"id": "travail", "nom": "Travail", "couleur": "#3366CC", "compte": "dedie"}
ORDINAIRE = {"id": "perso", "nom": "Personnel", "couleur": "#228833"}
POSIX = os.name == "posix" and hasattr(socket, "AF_UNIX")


def _source():
    with open(os.path.join(outils.BIN, "codebyr-space"), encoding="utf-8") as f:
        return f.read()


def _fonction(source, nom, suivante):
    return source.split("def %s(" % nom)[1].split("def %s(" % suivante)[0]


class LaDemande(unittest.TestCase):

    def test_seul_le_reglage_explicite_active_le_compte_dedie(self):
        self.assertTrue(compte_dedie.demande(DEDIE))
        for esp in (ORDINAIRE, {"compte": "oui"}, {"compte": True}, None, "dedie"):
            self.assertFalse(compte_dedie.demande(esp), repr(esp))

    def test_aucun_espace_livre_ne_le_demande(self):
        # Réglage d'essai tant que le chantier n'est pas fini : l'activer par
        # défaut sur un Espace livré ferait perdre à ses utilisateurs l'accès
        # à leurs données existantes, qui ne sont pas encore migrées.
        chemin = os.path.join(outils.ETC, "codebyr", "espaces.json")
        with open(chemin, encoding="utf-8") as f:
            livres = json.load(f)["espaces"]
        for esp in livres:
            self.assertFalse(compte_dedie.demande(esp), esp.get("id"))


class CeQuiNEstPasEncorePret(unittest.TestCase):

    def test_un_espace_ordinaire_n_est_jamais_refuse(self):
        self.assertEqual(compte_dedie.incompatibilites(
            dict(ORDINAIRE, ephemere=True), fichier="/tmp/x", est_flatpak=True), [])

    def test_jetable_piece_jointe_et_flatpak_sont_refuses(self):
        for options in ({"esp": dict(DEDIE, ephemere=True)},
                        {"esp": DEDIE, "fichier": "/tmp/facture.pdf"},
                        {"esp": DEDIE, "est_flatpak": True}):
            esp = options.pop("esp")
            self.assertTrue(compte_dedie.incompatibilites(esp, **options), options)

    def test_les_gestes_sur_les_donnees_sont_refuses_avec_une_explication(self):
        for geste in ("purge", "delete", "export", "import", "envoyer",
                      "contagion", "install", "add-app"):
            message = compte_dedie.refus_de_geste(geste, DEDIE)
            self.assertIsNotNone(message, geste)
            self.assertIn("Travail", message)
            self.assertIn("dedie", message, "le message doit dire comment revenir")

    def test_ouvrir_et_fermer_restent_possibles(self):
        for geste in ("launch", "close", "list", "apps"):
            self.assertIsNone(compte_dedie.refus_de_geste(geste, DEDIE), geste)

    def test_les_gestes_refuses_existent_bien_dans_le_lanceur(self):
        # Une faute de frappe dans la liste laisserait passer le vrai geste.
        for geste in compte_dedie.GESTES_PAS_ENCORE_PRETS:
            self.assertIn(geste, space.ACTIONS, geste)

    def test_le_lanceur_refuse_avant_d_agir(self):
        with mock.patch.object(space, "load_espaces", return_value={"travail": DEDIE}), \
                mock.patch.object(space, "cmd_purge") as purge, \
                mock.patch.object(space, "_prevenir"):
            code = space.main(["codebyr-space", "purge", "travail"])
        self.assertEqual(code, 1)
        purge.assert_not_called()


class JamaisDeReplieSousLeCompteDuBureau(unittest.TestCase):

    def setUp(self):
        self.source = _source()

    def test_un_service_absent_ne_fait_pas_ouvrir_l_espace_autrement(self):
        lancer = _fonction(self.source, "cmd_launch", "_lancer")
        # Le seul chemin vers le lancement ordinaire est l'absence de demande :
        # il n'apparaît qu'une fois, DANS le bloc « pas de compte dédié ».
        self.assertEqual(lancer.count("_lancer(espaces, esp, extra, fichier, None)"), 1)
        bloc_ordinaire = lancer.split("if not compte_dedie.demande(esp):")[1].split(
            "compte_dedie.Session(")[0]
        self.assertIn("_lancer(espaces, esp, extra, fichier, None)", bloc_ordinaire)
        self.assertIn("except compte_dedie.Indisponible as exc:\n        return _refuser_compte_dedie(esp, str(exc))", lancer)

    def test_le_service_absent_refuse_vraiment(self):
        with mock.patch.object(compte_dedie, "Session",
                               side_effect=compte_dedie.Indisponible("absent")), \
                mock.patch.object(space, "_lancer") as lancer, \
                mock.patch.object(space, "_prevenir"), \
                mock.patch.object(space.shutil, "which", return_value="/usr/bin/bwrap"), \
                mock.patch.object(space.applications, "resoudre", return_value=["nautilus"]):
            code = space.cmd_launch({"travail": DEDIE}, "travail", [])
        self.assertEqual(code, 1)
        lancer.assert_not_called()

    def test_la_tenue_est_rendue_quel_que_soit_le_chemin_de_sortie(self):
        session = mock.Mock()
        with mock.patch.object(compte_dedie, "Session", return_value=session), \
                mock.patch.object(space, "_lancer", side_effect=OSError("panne")), \
                mock.patch.object(space.shutil, "which", return_value="/usr/bin/bwrap"), \
                mock.patch.object(space.applications, "resoudre", return_value=["nautilus"]):
            with self.assertRaises(OSError):
                space.cmd_launch({"travail": DEDIE}, "travail", [])
        session.rendre.assert_called_once_with()


class LOrdreDesChoses(unittest.TestCase):

    def setUp(self):
        self.lancer = _fonction(_source(), "_lancer", "_rundir")

    def test_l_espace_prepare_son_profil_avant_que_le_filtre_existe(self):
        # Dans l'ordre inverse, un filtre absent laissait Banque avec Internet
        # en entier : le navigateur ne pointait vers aucun proxy.
        self.assertLess(self.lancer.index("_preparer_depuis_l_espace("),
                        self.lancer.index("_demarrer_filtre_reseau("))

    def test_la_socket_d_ordres_n_entre_jamais_dans_le_bac_a_sable(self):
        appel = self.lancer.split("bac_a_sable.wrap_bwrap(")[1].split(")\n")[0]
        self.assertNotIn("ordres", appel)
        self.assertIn("passerelle=session.passerelle", appel)

    def test_le_bureau_n_ecrit_plus_dans_le_dossier_d_un_espace_dedie(self):
        bloc = self.lancer.split("if session:")[1].split("elif not esp.get(\"ephemere\"):")[0]
        self.assertNotIn("_preparer_ouverture(", bloc)
        self.assertNotIn("modeles.installer(", bloc)
        self.assertIn("and not session", self.lancer.split("_installer_bouclier(esp, home, espaces)")[0][-200:])


class LaPreparationDepuisLEspace(unittest.TestCase):

    def test_refuse_de_tourner_sous_un_compte_qui_n_est_pas_un_espace(self):
        faux = mock.Mock(pw_name="romtouf", pw_dir="/home/romtouf")
        with mock.patch("pwd.getpwuid", return_value=faux), \
                mock.patch.object(space, "_preparer_ouverture") as ouverture:
            code = space.cmd_interne_preparer("{}")
        self.assertEqual(code, 2)
        ouverture.assert_not_called()

    @unittest.skipUnless(POSIX, "comptes Unix")
    def test_ecrit_dans_le_dossier_du_compte_pas_dans_celui_qu_on_annonce(self):
        with tempfile.TemporaryDirectory() as vrai, tempfile.TemporaryDirectory() as leurre:
            faux = mock.Mock(pw_name="cbyr-1000-travail", pw_dir=vrai)
            with mock.patch("pwd.getpwuid", return_value=faux), \
                    mock.patch.dict(os.environ, {"HOME": leurre}), \
                    mock.patch.object(space, "types_ouvreur", return_value=["application/pdf"]), \
                    mock.patch.object(space, "_ouvreur_associe", return_value=True), \
                    mock.patch.object(space, "_preparer_ouverture") as ouverture, \
                    mock.patch.object(space.modeles, "installer") as modeles:
                code = space.cmd_interne_preparer(json.dumps({"firefox": False}))
        self.assertEqual(code, 0)
        ouverture.assert_called_once_with(vrai)
        modeles.assert_called_once_with(vrai)

    def test_des_associations_non_posees_ne_passent_pas_pour_une_reussite(self):
        # Constaté le 14/09/2026 : elles n'étaient pas écrites, et la
        # préparation se disait réussie. Ce sont elles qui ouvrent sous cloche.
        faux = mock.Mock(pw_name="cbyr-1000-travail", pw_dir="/var/lib/x")
        with mock.patch("pwd.getpwuid", return_value=faux), \
                mock.patch.object(space, "types_ouvreur", return_value=["application/pdf"]), \
                mock.patch.object(space, "_ouvreur_associe", return_value=False), \
                mock.patch.object(space, "_preparer_ouverture"), \
                mock.patch.object(space.modeles, "installer"):
            code = space.cmd_interne_preparer(json.dumps({"firefox": False}))
        self.assertEqual(code, 1)

    def test_n_apparait_pas_dans_l_aide(self):
        self.assertNotIn(space.INTERNE_PREPARER, space.ACTIONS)


class LaBoiteDEnvoi(unittest.TestCase):

    def test_un_envoi_depuis_un_espace_dedie_est_refuse_sans_rien_deposer(self):
        # Aucune boîte n'y est montée : sans ce refus, « Déposé » s'afficherait
        # et le fichier ne partirait jamais (erreur corrigée le 24/08/2026).
        with tempfile.TemporaryDirectory() as t:
            source = os.path.join(t, "note.txt")
            with open(source, "w") as f:
                f.write("x")
            boite = os.path.join(t, "boite")
            with mock.patch.object(space, "ENVOI_INTERNE", boite), \
                    mock.patch.dict(os.environ, {"CODEBYR_COMPTE_DEDIE": "1"}), \
                    mock.patch.object(space, "_prevenir"):
                code = space._deposer_pour_envoi(DEDIE, "travail", source)
            self.assertEqual(code, 1)
            self.assertFalse(os.path.exists(boite))

    def test_la_releve_laisse_attendre_les_fichiers_d_un_espace_dedie(self):
        source = _fonction(_source(), "relever_envois", "_espace_courant")
        garde = source.index("compte_dedie.demande(espaces[dest])")
        self.assertLess(garde, source.index("cible = os.path.join(DATA_ROOT, dest"))


@unittest.skipUnless(POSIX, "sockets Unix")
class LeDialogue(unittest.TestCase):
    """Le client face à un faux service et un faux premier processus."""

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin = os.path.join(self.dossier.name, "service")
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(self.chemin)
        self.srv.listen(4)
        self.recu = []
        self.fin_de_tenue = threading.Event()

    def tearDown(self):
        self.srv.close()
        self.dossier.cleanup()

    def _servir(self, reponses, tenir=False):
        def boucle():
            client, _ = self.srv.accept()
            with client:
                self.recu.append(json.loads(client.recv(65536).decode()))
                for r in reponses:
                    client.sendall((json.dumps(r) + "\n").encode())
                if tenir:
                    while client.recv(64):
                        pass
                    self.fin_de_tenue.set()
        threading.Thread(target=boucle, daemon=True).start()

    def test_la_session_tient_jusqu_a_ce_qu_on_la_rende(self):
        self._servir([{"ok": True, "compte": "cbyr-1000-travail",
                       "home": "/var/lib/codebyr/espaces/1000/travail",
                       "passerelle": "/p", "depot": "/d", "ordres": "/d/exec"}],
                     tenir=True)
        session = compte_dedie.Session("travail", "wayland-0", True, "2G", 800,
                                       chemin=self.chemin)
        self.assertEqual(self.recu[0]["action"], "ouvrir")
        self.assertEqual(session.ordres, "/d/exec")
        self.assertFalse(self.fin_de_tenue.wait(0.3), "rendue trop tôt")
        session.rendre()
        self.assertTrue(self.fin_de_tenue.wait(5), "jamais rendue")

    def test_un_refus_du_service_devient_indisponible(self):
        self._servir([{"ok": False, "erreur": "impossible"}])
        with self.assertRaises(compte_dedie.Indisponible):
            compte_dedie.Session("travail", "wayland-0", False, "2G", 800,
                                 chemin=self.chemin)

    def test_un_service_absent_devient_indisponible(self):
        with self.assertRaises(compte_dedie.Indisponible) as ctx:
            compte_dedie.Session("travail", "wayland-0", False, "2G", 800,
                                 chemin=os.path.join(self.dossier.name, "absent"))
        self.assertIn("pas installé", str(ctx.exception))

    def test_executer_rapporte_le_pid_puis_le_code(self):
        self._servir([{"ok": True, "pid": 4242}, {"fin": 7}])
        vus = []
        code = compte_dedie.executer(self.chemin, ["/bin/true"], {"A": "1"},
                                     au_lancement=vus.append)
        self.assertEqual((code, vus), (7, [4242]))
        self.assertEqual(self.recu[0], {"argv": ["/bin/true"], "env": {"A": "1"}})

    def test_un_espace_referme_en_route_ne_passe_pas_pour_un_succes(self):
        self._servir([{"ok": True, "pid": 4242}])      # puis la connexion tombe
        code = compte_dedie.executer(self.chemin, ["/bin/true"], {})
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()


class LeJournalDesRefus(unittest.TestCase):
    """Constaté le 14/09/2026 : sous compte dédié, aucun refus n'était noté."""

    @unittest.skipUnless(POSIX, "fichiers_surs est réservé à Linux")
    def test_son_dossier_existe_avant_que_le_filtre_demarre(self):
        # Le profil AppArmor du filtre l'autorise à écrire ce fichier, pas à
        # créer de dossier. C'est donc au lanceur de le créer, avant.
        esp = dict(DEDIE, reseau={"mode": "liste-blanche", "domaines": ["banque.fr"]})
        with tempfile.TemporaryDirectory() as t:
            vu = {}

            def demarrage(*args, **kwargs):
                vu["dossier"] = os.path.isdir(os.path.join(t, "donnees", "travail"))
                return mock.Mock()

            with mock.patch.object(space, "DATA_ROOT", os.path.join(t, "donnees")), \
                    mock.patch.object(space.subprocess, "Popen", side_effect=demarrage), \
                    mock.patch.object(space, "_prevenir"):
                space._demarrer_filtre_reseau(esp, os.path.join(t, "home"), ["firefox-esr"],
                                              os.path.join(t, "proxy"), compte_dedie_=True)
        self.assertTrue(vu.get("dossier"), "le filtre a démarré sans dossier de journal")

    def test_un_journal_impossible_a_ecrire_se_signale_une_fois(self):
        proxy = outils.charger("codebyr-net-proxy")
        with tempfile.TemporaryDirectory() as t:
            obstacle = os.path.join(t, "fichier")
            with open(obstacle, "w") as f:
                f.write("x")
            with mock.patch.object(proxy, "JOURNAL", os.path.join(obstacle, "sous", "refus.txt")), \
                    mock.patch.object(proxy, "_VERROU", threading.Lock()), \
                    mock.patch.object(proxy, "_VUS", set()), \
                    mock.patch.object(proxy, "_JOURNAL_SIGNALE", False), \
                    mock.patch.object(proxy.sys, "stderr") as sortie:
                proxy.journaliser("exemple.com")
                proxy.journaliser("autre.com")
        messages = [c.args[0] for c in sortie.write.call_args_list]
        self.assertEqual(len(messages), 1, messages)
        self.assertIn("journal des refus", messages[0])


class LaRegleDesDonneesDEspace(unittest.TestCase):
    """Ce qu'une archive d'Espace peut poser en changeant de compte.

    De vraies archives, piégées comme le ferait un Espace compromis au retour
    vers le bureau.
    """

    def _archive(self, construire):
        import io
        import tarfile
        tampon = io.BytesIO()
        with tarfile.open(fileobj=tampon, mode="w") as tar:
            construire(tar)
        tampon.seek(0)
        return tarfile.open(fileobj=tampon, mode="r")

    def _extraire(self, construire):
        import tarfile
        destination = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, destination, True)
        with self._archive(construire) as tar:
            try:
                space._extraire_archive(tar, destination, space._filtre_dossier_d_espace)
            except (tarfile.TarError, ValueError, OSError) as exc:
                return destination, exc
        return destination, None

    @staticmethod
    def _entree(tar, nom, genre, cible="", contenu=b""):
        import io
        import tarfile
        info = tarfile.TarInfo(nom)
        info.type = genre
        info.linkname = cible
        info.size = len(contenu)
        tar.addfile(info, io.BytesIO(contenu) if contenu else None)

    @unittest.skipUnless(POSIX, "liens Unix")
    def test_un_lien_symbolique_vers_un_chemin_absolu_passe(self):
        # Sans cela, un seul lien de ce genre bloquait tout le déménagement.
        import tarfile
        destination, erreur = self._extraire(
            lambda tar: self._entree(tar, "./applications", tarfile.SYMTYPE,
                                     "/usr/share/applications"))
        self.assertIsNone(erreur)
        self.assertEqual(os.readlink(os.path.join(destination, "applications")),
                         "/usr/share/applications")

    def test_un_lien_dur_vers_l_exterieur_est_refuse(self):
        # Au retour vers le bureau, il donnerait à l'Espace un fichier du
        # bureau — sa clé SSH, par exemple.
        import tarfile
        _, erreur = self._extraire(
            lambda tar: self._entree(tar, "./cle", tarfile.LNKTYPE, "/etc/passwd"))
        self.assertIsNotNone(erreur)

    def test_un_nom_qui_sort_du_dossier_est_refuse(self):
        import tarfile
        _, erreur = self._extraire(
            lambda tar: self._entree(tar, "../dehors", tarfile.REGTYPE, contenu=b"x"))
        self.assertIsNotNone(erreur)

    @unittest.skipUnless(POSIX, "liens Unix")
    def test_on_n_ecrit_jamais_a_travers_un_lien_pose_par_l_archive(self):
        import tarfile
        dehors = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, dehors, True)

        def piege(tar):
            self._entree(tar, "./passage", tarfile.SYMTYPE, dehors)
            self._entree(tar, "./passage/intrus", tarfile.REGTYPE, contenu=b"x")

        _, erreur = self._extraire(piege)
        self.assertIsNotNone(erreur)
        self.assertFalse(os.path.exists(os.path.join(dehors, "intrus")))

    def test_un_fichier_special_est_refuse(self):
        import tarfile
        _, erreur = self._extraire(
            lambda tar: self._entree(tar, "./tube", tarfile.FIFOTYPE))
        self.assertIsNotNone(erreur)

    def test_la_restauration_ordinaire_garde_sa_regle_stricte(self):
        # Seul ce qui change de compte bénéficie de la règle d'Espace.
        source = _source()
        importer = source.split("def cmd_import(")[1].split("\nFLATHUB_REPO")[0]
        self.assertIn("_extraire_archive(tar, neuf)\n", importer)


class LeDemenagement(unittest.TestCase):
    """Les données suivent l'Espace sous son compte, et reviennent si on l'en retire."""

    def setUp(self):
        self.source = _source()

    def test_il_passe_avant_la_preparation_du_dossier(self):
        # La préparation complète les associations de l'Espace : elle doit
        # trouver celles qu'il avait déjà, donc arriver après ses données.
        lancer = _fonction(self.source, "_lancer", "_rundir")
        self.assertLess(lancer.index("_demenager_vers_compte_dedie("),
                        lancer.index("_preparer_depuis_l_espace("))

    def test_le_retour_passe_avant_toute_ouverture_ordinaire(self):
        launch = _fonction(self.source, "cmd_launch", "_lancer")
        bloc = launch.split("if not compte_dedie.demande(esp):")[1]
        self.assertLess(bloc.index("_rapatrier_depuis_compte_dedie("),
                        bloc.index("_lancer(espaces, esp, extra, fichier, None)"))

    def test_le_dossier_dedie_apparait_au_meme_chemin_qu_avant(self):
        # Les applications gardent des chemins absolus (téléchargements de
        # Firefox, fichiers récents) : un autre chemin les laisserait pointer
        # dans le vide après le déménagement.
        lancer = _fonction(self.source, "_lancer", "_rundir")
        appel = lancer.split("bac_a_sable.wrap_bwrap(")[1].split("if renforce:")[0]
        self.assertNotIn("chez=", appel)

    def test_le_bout_du_tuyau_est_toujours_ferme(self):
        # Sans cela, un ordre qui échoue laissait l'emballeur attendre à jamais
        # un lecteur disparu (vu dans le WSL le 14/09/2026).
        demenager = _fonction(self.source, "_demenager_vers_compte_dedie",
                              "_rapatrier_depuis_compte_dedie")
        self.assertIn("finally:", demenager)
        self.assertIn("os.close(lecture)", demenager.split("finally:")[1][:400])

    @unittest.skipUnless(POSIX, "fichiers_surs est réservé à Linux")
    def test_un_demenagement_rate_n_ouvre_pas_l_espace(self):
        with tempfile.TemporaryDirectory() as t:
            ancien = os.path.join(t, "espaces", "travail", "home")
            os.makedirs(ancien)
            with open(os.path.join(ancien, "note.txt"), "w") as f:
                f.write("précieux")
            session = mock.Mock(ordres="/nulle-part", home=os.path.join(t, "dedie", "1000", "travail"),
                                compte="cbyr-1000-travail")
            os.makedirs(session.home)
            with mock.patch.object(space, "DATA_ROOT", os.path.join(t, "espaces")), \
                    mock.patch.object(space, "_prevenir"), \
                    mock.patch.object(compte_dedie, "executer", return_value=1):
                ouvert = space._demenager_vers_compte_dedie(DEDIE, session)
            self.assertFalse(ouvert)
            self.assertFalse(os.path.exists(os.path.join(t, "espaces", "travail",
                                                         space.MARQUEUR_DEMENAGEMENT)))
            with open(os.path.join(ancien, "note.txt")) as f:
                self.assertEqual(f.read(), "précieux")

    def test_un_espace_jamais_ouvert_n_a_rien_a_demenager(self):
        with tempfile.TemporaryDirectory() as t, \
                mock.patch.object(space, "DATA_ROOT", t), \
                mock.patch.object(compte_dedie, "executer") as executer:
            self.assertTrue(space._demenager_vers_compte_dedie(DEDIE, mock.Mock()))
        executer.assert_not_called()

    def test_sans_service_le_retour_refuse_plutot_que_de_montrer_l_etat_fige(self):
        with tempfile.TemporaryDirectory() as t:
            os.makedirs(os.path.join(t, "travail"))
            with open(os.path.join(t, "travail", space.MARQUEUR_DEMENAGEMENT), "w") as f:
                f.write("{}")
            with mock.patch.object(space, "DATA_ROOT", t), \
                    mock.patch.object(compte_dedie, "Session",
                                      side_effect=compte_dedie.Indisponible("absent")):
                self.assertFalse(space._rapatrier_depuis_compte_dedie(ORDINAIRE | {"id": "travail"}))


class LesFluxDuPremierProcessus(unittest.TestCase):

    def setUp(self):
        with open(os.path.join(outils.RACINE, "live-build", "config",
                               "includes.chroot_after_packages", "usr", "lib", "codebyr",
                               "codebyr-espace-init"), encoding="utf-8") as f:
            self.source = f.read()

    def test_seules_l_entree_et_la_sortie_standard_peuvent_etre_transmises(self):
        self.assertIn('FLUX = ("entree", "sortie")', self.source)

    def test_sans_flux_la_commande_ne_lit_rien(self):
        # Une application lancée dans un Espace ne doit pas hériter d'une
        # entrée standard ouverte vers on ne sait quoi.
        self.assertIn('stdin=recus.get("entree", subprocess.DEVNULL)', self.source)

    def test_les_descripteurs_recus_sont_refermes(self):
        servir = self.source.split("def servir_un(")[1].split("def attendre(")[0]
        self.assertIn("for fd in descripteurs:", servir.split("finally:")[1])
