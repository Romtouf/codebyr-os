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

    def test_flatpak_est_refuse(self):
        self.assertTrue(compte_dedie.incompatibilites(DEDIE, est_flatpak=True))

    def test_un_espace_jetable_est_accepte(self):
        # Son dossier devient un tmpfs sous son compte (voir codebyr-uid).
        self.assertEqual(compte_dedie.incompatibilites(dict(DEDIE, ephemere=True)), [])

    def test_une_piece_jointe_est_acceptee(self):
        # Elle passe par la boîte d'arrivée de l'Espace (voir _lancer).
        self.assertEqual(compte_dedie.incompatibilites(DEDIE, fichier="/tmp/facture.pdf"), [])

    def test_les_gestes_sur_les_donnees_sont_refuses_avec_une_explication(self):
        for geste in ("install", "add-app"):
            message = compte_dedie.refus_de_geste(geste, DEDIE)
            self.assertIsNotNone(message, geste)
            self.assertIn("Travail", message)
            self.assertIn("dedie", message, "le message doit dire comment revenir")

    def test_ouvrir_et_fermer_restent_possibles(self):
        for geste in ("launch", "close", "list", "apps", "envoyer", "purge", "delete",
                      "export", "import", "contagion"):
            self.assertIsNone(compte_dedie.refus_de_geste(geste, DEDIE), geste)

    def test_les_gestes_refuses_existent_bien_dans_le_lanceur(self):
        # Une faute de frappe dans la liste laisserait passer le vrai geste.
        for geste in compte_dedie.GESTES_PAS_ENCORE_PRETS:
            self.assertIn(geste, space.ACTIONS, geste)

    def test_le_lanceur_refuse_avant_d_agir(self):
        with mock.patch.object(space, "load_espaces", return_value={"travail": DEDIE}), \
                mock.patch.object(space, "cmd_install") as installer, \
                mock.patch.object(space, "_prevenir"):
            code = space.main(["codebyr-space", "install", "travail", "org.exemple.App"])
        self.assertEqual(code, 1)
        installer.assert_not_called()


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
        self.assertIn("runtime_espace=session.runtime", appel)

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


class LesBoites(unittest.TestCase):
    """Les fichiers entrent et sortent d'un Espace dédié sans que root les lise.

    La boîte de départ appartient à l'Espace, la boîte d'arrivée à root ; le
    bureau relève l'une et remplit l'autre SANS ouvrir l'Espace.
    """

    def test_la_boite_de_depart_est_montee_dans_l_espace(self):
        # Sans elle, « envoyer » depuis l'Espace écrirait dans un dossier
        # ordinaire : « Déposé », et le fichier ne partirait jamais.
        lancer = _fonction(_source(), "_lancer", "_rundir")
        bloc = lancer.split("if session:")[1].split("elif not esp.get(\"ephemere\"):")[0]
        self.assertIn("envoi = session.envois", bloc)

    def test_le_bureau_releve_un_espace_dedie_hors_de_son_dossier(self):
        with mock.patch.object(space.comptes, "chemin_envois",
                               return_value="/var/lib/codebyr/envois/1000/travail"):
            self.assertEqual(space._boite_de_depart(DEDIE, "travail"),
                             "/var/lib/codebyr/envois/1000/travail")
        self.assertTrue(space._boite_de_depart(ORDINAIRE, "perso").startswith(space.DATA_ROOT))

    @unittest.skipUnless(POSIX, "fichiers_surs est réservé à Linux")
    def test_la_releve_depose_dans_la_boite_d_arrivee_lisible_par_l_espace(self):
        with tempfile.TemporaryDirectory() as t:
            donnees = os.path.join(t, "donnees")
            depart = os.path.join(donnees, "perso", "envoi", "travail")
            os.makedirs(depart)
            with open(os.path.join(depart, "rapport.txt"), "w") as f:
                f.write("pour Travail")
            arrivee = os.path.join(t, "arrivees", "travail")
            os.makedirs(arrivee)
            espaces = {"perso": ORDINAIRE, "travail": DEDIE}
            with mock.patch.object(space, "DATA_ROOT", donnees), \
                    mock.patch.object(space.comptes, "chemin_arrivees", return_value=arrivee):
                remis = space.relever_envois(espaces)
            self.assertEqual(remis, 1)
            depose = os.path.join(arrivee, "rapport.txt")
            self.assertTrue(os.path.exists(depose))
            self.assertEqual(os.stat(depose).st_mode & 0o777, 0o644,
                             "illisible par le compte de l'Espace")
            self.assertFalse(os.path.exists(os.path.join(donnees, "travail", "home")),
                             "rien ne doit arriver à l'ancien emplacement")

    @unittest.skipUnless(POSIX, "fichiers_surs est réservé à Linux")
    def test_un_espace_jamais_ouvert_sous_son_compte_laisse_attendre(self):
        with tempfile.TemporaryDirectory() as t:
            depart = os.path.join(t, "perso", "envoi", "travail")
            os.makedirs(depart)
            with open(os.path.join(depart, "rapport.txt"), "w") as f:
                f.write("x")
            with mock.patch.object(space, "DATA_ROOT", t), \
                    mock.patch.object(space.comptes, "chemin_arrivees",
                                      return_value=os.path.join(t, "absente")):
                self.assertEqual(space.relever_envois({"perso": ORDINAIRE, "travail": DEDIE}), 0)
            self.assertTrue(os.path.exists(os.path.join(depart, "rapport.txt")),
                            "le fichier doit attendre, pas disparaître")

    @unittest.skipUnless(POSIX, "fichiers_surs est réservé à Linux")
    def test_envoyer_depuis_le_bureau_depose_sans_ouvrir_l_espace(self):
        with tempfile.TemporaryDirectory() as t:
            source = os.path.join(t, "facture.pdf")
            with open(source, "w") as f:
                f.write("%PDF")
            arrivee = os.path.join(t, "arrivee")
            os.makedirs(arrivee)
            with mock.patch.object(space.comptes, "chemin_arrivees", return_value=arrivee), \
                    mock.patch.object(space, "_prevenir"), \
                    mock.patch.object(compte_dedie, "Session") as session:
                code = space._envoyer_vers_compte_dedie(DEDIE, source)
            self.assertEqual(code, 0)
            session.assert_not_called()
            self.assertEqual(os.stat(os.path.join(arrivee, "facture.pdf")).st_mode & 0o777, 0o644)

    @unittest.skipUnless(POSIX, "fichiers_surs est réservé à Linux")
    def test_l_espace_recueille_en_recopiant_et_garde_la_provenance(self):
        with tempfile.TemporaryDirectory() as t:
            home = os.path.join(t, "home")
            arrivee = os.path.join(t, "arrivee")
            lot = os.path.join(arrivee, "Pièce jointe du 2026-09-14 12h00-ab12")
            os.makedirs(home)
            os.makedirs(lot)
            simple = os.path.join(arrivee, "note.txt")
            with open(simple, "w") as f:
                f.write("simple")
            with open(os.path.join(lot, "piece.pdf"), "w") as f:
                f.write("%PDF")
            try:
                os.setxattr(simple, "user.codebyr.origine", b"navigation")
                xattr = True
            except OSError:
                xattr = False
            recus = space._recueillir_arrivees(home, arrivee)
            self.assertEqual(recus, 2)
            partage = os.path.join(home, space.PARTAGE)
            self.assertTrue(os.path.exists(os.path.join(partage, "note.txt")))
            # Le lot arrive sous le même nom : le lanceur ouvre la pièce jointe
            # à un chemin qu'il connaît d'avance.
            self.assertTrue(os.path.exists(os.path.join(
                partage, "Pièce jointe du 2026-09-14 12h00-ab12", "piece.pdf")))
            self.assertEqual(os.listdir(arrivee), [], "la boîte doit être vidée")
            if xattr:
                self.assertEqual(os.getxattr(os.path.join(partage, "note.txt"),
                                             "user.codebyr.origine"), b"navigation")

    @unittest.skipUnless(POSIX, "liens Unix")
    def test_un_lien_glisse_dans_la_boite_n_est_pas_suivi(self):
        with tempfile.TemporaryDirectory() as t:
            home = os.path.join(t, "home")
            arrivee = os.path.join(t, "arrivee")
            secret = os.path.join(t, "secret")
            os.makedirs(home)
            os.makedirs(arrivee)
            with open(secret, "w") as f:
                f.write("secret")
            os.symlink(secret, os.path.join(arrivee, "piege.txt"))
            space._recueillir_arrivees(home, arrivee)
            self.assertFalse(os.path.exists(os.path.join(home, space.PARTAGE, "piege.txt")))

    def test_la_piece_jointe_passe_par_la_boite_d_arrivee(self):
        lancer = _fonction(_source(), "_lancer", "_rundir")
        bloc = lancer.split("if fichier and os.path.isfile(fichier):")[1].split("app_cmd = ")[0]
        self.assertIn("session.arrivees", bloc)
        self.assertIn("mode=0o644", bloc)
        self.assertIn("secrets.token_hex", bloc)


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
                       "runtime": "/run/user/997", "depot": "/d",
                       "ordres": "/d/exec"}],
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
        ordre = _fonction(self.source, "_ordre_interne", "_session_pour_un_geste")
        self.assertIn("finally:", ordre)
        self.assertIn("os.close(a_fermer)", ordre.split("finally:")[1][:200])
        # Et les gestes passent par là, sans recopier le motif du tuyau.
        for geste in ("_demenager_vers_compte_dedie", "_rapatrier_depuis_compte_dedie",
                      "_geste_dans_l_espace"):
            corps = self.source.split("def %s(" % geste)[1].split("\ndef ")[0]
            self.assertNotIn("os.pipe()", corps, geste)

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


class LesGestesSurLesDonnees(unittest.TestCase):

    def setUp(self):
        self.source = _source()

    def test_une_sauvegarde_interrompue_ne_prend_jamais_son_vrai_nom(self):
        exporter = _fonction(self.source, "_exporter_compte_dedie", "_restaurer_compte_dedie")
        self.assertIn(".partielle", exporter)
        self.assertLess(exporter.index("if code != 0 or erreurs:"),
                        exporter.index("os.replace(provisoire, chemin)"))

    def test_la_restauration_ferme_l_espace_d_abord(self):
        restaurer = _fonction(self.source, "_restaurer_compte_dedie", "_effacer_compte_dedie")
        self.assertLess(restaurer.index("cmd_close("), restaurer.index("_geste_dans_l_espace("))

    def test_l_effacement_emporte_aussi_l_etat_fige_du_demenagement(self):
        # Sinon la prochaine ouverture ferait déménager à nouveau ce qu'on vient
        # d'effacer.
        effacer = _fonction(self.source, "_effacer_compte_dedie", "cmd_interne_preparer")
        self.assertLess(effacer.index("_geste_dans_l_espace("),
                        effacer.index("shutil.rmtree(os.path.join(DATA_ROOT"))

    def test_la_suppression_efface_avant_de_retirer_le_compte(self):
        supprimer = _fonction(self.source, "cmd_delete", "cmd_nettoyer_registre")
        self.assertLess(supprimer.index("_effacer_compte_dedie("),
                        supprimer.index("compte_dedie.supprimer("))

    def test_une_restauration_a_moitie_faite_est_defaite(self):
        restaurer = _fonction(self.source, "cmd_interne_restaurer", "cmd_interne_effacer")
        self.assertIn("reversed(mis_de_cote)", restaurer)
        self.assertIn("reversed(poses)", restaurer)


class LeMasqueDesACL(unittest.TestCase):
    """Reproduit dans le WSL avec deux comptes sans privilège, le 14/09/2026.

    Dans la boîte de départ d'un Espace dédié, le droit du bureau vient d'une
    ACL par défaut, dont le masque suit le mode de création : un dossier en
    0700 et un fichier en 0600 donnaient « user:bureau:rwx #effective:--- ».
    Le bureau ne relevait rien, et rien ne le disait.
    """

    def setUp(self):
        self.deposer = _fonction(_source(), "_deposer_pour_envoi", "_envoyer_vers_compte_dedie")

    def test_le_depot_pose_les_droits_du_dossier_par_son_descripteur(self):
        self.assertIn("os.fchmod(fd, 0o770)", self.deposer)
        self.assertLess(self.deposer.index("fichiers_surs.mkdir(dossier)"),
                        self.deposer.index("os.fchmod(fd, 0o770)"))

    def test_le_fichier_depose_reste_lisible_par_le_bureau(self):
        self.assertIn("mode=0o640", self.deposer)

    @unittest.skipUnless(POSIX, "fichiers_surs est réservé à Linux")
    def test_les_modes_sont_vraiment_poses(self):
        with tempfile.TemporaryDirectory() as t:
            source = os.path.join(t, "note.txt")
            with open(source, "w") as f:
                f.write("x")
            boite = os.path.join(t, "boite")
            with mock.patch.object(space, "ENVOI_INTERNE", boite), \
                    mock.patch.object(space, "_prevenir"):
                self.assertEqual(space._deposer_pour_envoi(ORDINAIRE, "travail", source), 0)
            dossier = os.path.join(boite, "perso")
            self.assertEqual(os.stat(dossier).st_mode & 0o777, 0o770)
            self.assertEqual(os.stat(os.path.join(dossier, "note.txt")).st_mode & 0o777, 0o640)

    def test_une_destination_illisible_se_dit_au_journal(self):
        relever = _fonction(_source(), "relever_envois", "_espace_courant")
        self.assertIn('journal("relève impossible de %s vers %s : %s"', relever)


class LeReglageDansLaConfiguration(unittest.TestCase):
    """Le réglage vivait dans un fichier JSON : autant dire nulle part."""

    def setUp(self):
        with open(os.path.join(outils.BIN, "codebyr-config"), encoding="utf-8") as f:
            self.source = f.read()

    def test_la_configuration_propose_le_reglage(self):
        self.assertIn("Compte séparé, par Espace", self.source)

    def test_elle_ecrit_la_cle_que_le_lanceur_lit(self):
        # Deux moitiés du même réglage : si l'une écrit « separe » et l'autre
        # lit « dedie », la case ne fait rien et personne ne le voit.
        self.assertIn('valeur = "dedie" if actif else None', self.source)
        self.assertIn('registre.modifier_espace(esp_id, {"compte": valeur})', self.source)
        self.assertTrue(compte_dedie.demande({"compte": "dedie"}))

    def test_elle_dit_ce_qui_va_se_passer_aux_donnees(self):
        # Un réglage qui déplace des fichiers doit dire qu'il les déplace, et
        # comment revenir en arrière.
        for phrase in ("suivent à sa prochaine ouverture", "reviennent si vous le",
                       "rien n'est effacé"):
            self.assertIn(phrase, self.source, phrase)

    def test_elle_previent_quand_le_service_n_est_pas_la(self):
        self.assertIn("compte_dedie.SOCKET_SERVICE", self.source)
        self.assertIn("n'est pas actif", self.source)
        self.assertIn("row.set_sensitive(service)", self.source)

    def test_elle_annonce_la_limite_des_applications_flatpak(self):
        self.assertIn("applications Flatpak ne s'ouvriront pas", self.source)
