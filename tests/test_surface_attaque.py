# -*- coding: utf-8 -*-
"""Ce qu'un programme hostile peut atteindre — les écarts fermés le 13/09/2026.

Une relecture de sécurité du 12 septembre a comparé ce que Codebyr PROMET à
ce que le code APPLIQUE. Cinq écarts en sont sortis ; chaque classe ci-dessous
en garde un fermé.

  1. Navigation — le navigateur du quotidien, donc l'Espace le plus exposé au
     web hostile — tournait SANS Blindage : ni filtre d'appels système, ni
     abandon des privilèges, ni session neuve.
  2. Le filtre réseau jugeait un NOM, jamais l'adresse où il mène. Tournant
     sur l'hôte, il pouvait servir de passage vers le réseau local.
  3. L'extension GNOME collait l'identifiant d'un Espace dans une ligne de
     commande, et sa couleur dans une feuille de style, sans les vérifier.
  4. La carte graphique était offerte à tous les Espaces, sans condition.
  5. Plusieurs portes du noyau restaient ouvertes à tout le système.
"""
import json
import os
import re
import socket
import tempfile
import threading
import time
import unittest

from outils import BIN, ETC, RACINE, charger
import bac_a_sable   # noqa: E402 — chemin posé par outils
import registre      # noqa: E402

proxy = charger("codebyr-net-proxy")

EXTENSION = os.path.join(
    RACINE, "live-build", "config", "includes.chroot_after_packages", "usr",
    "share", "gnome-shell", "extensions", "codebyr@codebyr.io", "extension.js")
REGISTRE_LIVRE = os.path.join(ETC, "codebyr", "espaces.json")
SYSCTL = os.path.join(ETC, "sysctl.d", "91-codebyr-noyau.conf")


def _lire(chemin):
    with open(chemin, encoding="utf-8") as f:
        return f.read()


def _espaces_livres():
    return {e["id"]: e for e in json.loads(_lire(REGISTRE_LIVRE))["espaces"]}


# ── 1. Blindage de Navigation ──────────────────────────────────────────────

class NavigateursBlindes(unittest.TestCase):
    """Tout Espace qui navigue sur le web est blindé par défaut.

    La règle est formulée sur ce que fait l'Espace, pas sur son nom : un
    Espace navigateur ajouté demain au registre livré devra l'être aussi.
    """

    def test_tout_espace_navigateur_livre_est_blinde(self):
        navigateurs = {i: e for i, e in _espaces_livres().items()
                       if "firefox" in e.get("app", "")}
        self.assertIn("navigation", navigateurs)
        for esp_id, e in navigateurs.items():
            self.assertEqual(e.get("blindage"), "renforce",
                             "l'Espace « %s » navigue sur le web sans Blindage"
                             % esp_id)

    def test_le_choix_explicite_de_l_utilisateur_reste_respecte(self):
        """Blinder par défaut ne doit pas écraser un « non » déjà exprimé."""
        with tempfile.TemporaryDirectory() as d:
            anciens = registre.SYSTEME, registre.UTILISATEUR
            try:
                registre.SYSTEME = REGISTRE_LIVRE
                registre.UTILISATEUR = os.path.join(d, "utilisateur.json")
                self.assertEqual(registre.espaces()["navigation"]["blindage"],
                                 "renforce")
                registre.modifier_espace("navigation", {"blindage": None})
                self.assertIsNone(registre.espaces()["navigation"]["blindage"])
            finally:
                registre.SYSTEME, registre.UTILISATEUR = anciens


class PlafondsDuNavigateur(unittest.TestCase):
    """Blinder Navigation ne doit pas faire tuer le navigateur du quotidien.

    Le Blindage plafonne l'Espace à 2 Go sans échange et 800 tâches. Pensé
    pour Banque, ce plafond aurait tué Firefox en plein usage : pour systemd,
    une tâche est un fil d'exécution, et une quinzaine de sites ouverts en
    dépasse 800. Navigation déclare donc ses propres plafonds.
    """

    def _argv(self, esp):
        return bac_a_sable.plafonner_ressources(
            ["firefox"], *bac_a_sable.plafonds_de(esp))

    def test_banque_et_jetable_gardent_les_plafonds_d_origine(self):
        espaces = _espaces_livres()
        for esp_id in ("banque", "jetable"):
            self.assertEqual(bac_a_sable.plafonds_de(espaces[esp_id]), ("2G", 800),
                             esp_id)

    def test_navigation_a_des_plafonds_a_la_mesure_d_un_navigateur(self):
        memoire, taches = bac_a_sable.plafonds_de(_espaces_livres()["navigation"])
        self.assertEqual(memoire, "75%")
        self.assertGreaterEqual(taches, 4096)

    def test_une_valeur_mal_formee_retombe_sur_le_defaut(self):
        # Ni lever la protection, ni empêcher l'ouverture.
        for plafonds in ({"memoire": "2G -p CPUQuota=1%"}, {"memoire": "infinity"},
                         {"memoire": "0G"}, {"memoire": "150%"}, {"memoire": 2},
                         {"taches": "4096"}, {"taches": 10}, {"taches": 10**6},
                         {"taches": True}, "pas un dictionnaire"):
            self.assertEqual(bac_a_sable.plafonds_de({"plafonds": plafonds}),
                             ("2G", 800), plafonds)

    def test_les_plafonds_arrivent_a_systemd(self):
        anciens = bac_a_sable._SCOPE_DISPO
        self.addCleanup(setattr, bac_a_sable, "_SCOPE_DISPO", anciens)
        bac_a_sable._SCOPE_DISPO = True
        argv = self._argv(_espaces_livres()["navigation"])
        self.assertIn("MemoryMax=75%", argv)
        self.assertIn("TasksMax=4096", argv)
        self.assertIn("MemorySwapMax=0", argv)
        self.assertEqual(argv[argv.index("--") + 1:], ["firefox"])

    def test_codebyr_space_transmet_les_plafonds_de_l_espace(self):
        source = _lire(os.path.join(BIN, "codebyr-space"))
        self.assertIn("plafonner_ressources(run, *bac_a_sable.plafonds_de(esp))", source)


# ── 2. Filtre réseau et réseau local ───────────────────────────────────────

class AdressesInternes(unittest.TestCase):

    def test_ce_qui_n_est_pas_internet_est_interne(self):
        for ip in ("127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.1.1",
                   "169.254.169.254",       # métadonnées des hébergeurs cloud
                   "100.64.0.1",            # NAT des opérateurs
                   "0.0.0.0", "::1", "fe80::1%eth0", "fc00::1",
                   "224.0.0.1", "ff02::1"):
            self.assertTrue(proxy.adresse_interne(ip), ip)

    def test_une_adresse_ipv4_deguisee_en_ipv6_est_jugee_sur_ce_qu_elle_cache(self):
        self.assertTrue(proxy.adresse_interne("::ffff:127.0.0.1"))
        self.assertTrue(proxy.adresse_interne("::ffff:192.168.1.1"))
        self.assertFalse(proxy.adresse_interne("::ffff:1.1.1.1"))

    def test_les_adresses_publiques_passent(self):
        for ip in ("1.1.1.1", "93.184.215.14", "2606:4700::1111"):
            self.assertFalse(proxy.adresse_interne(ip), ip)

    def test_une_adresse_illisible_est_refusee(self):
        self.assertTrue(proxy.adresse_interne("pas-une-adresse"))


class PassageVersLeReseauLocal(unittest.TestCase):
    """Un domaine AUTORISÉ qui mène au réseau local doit rester fermé.

    Le scénario : un domaine en liste blanche, ou n'importe quel sous-domaine
    couvert par « *. », que son propriétaire fait pointer vers 127.0.0.1 ou
    vers la box. Le filtre, qui tourne sur l'hôte, s'y connectait pour le
    compte de l'Espace. « localhost » joue ici ce rôle : autorisé, et interne.
    """

    def setUp(self):
        # Un vrai service local, que la connexion atteindrait si elle passait.
        self.cible = socket.socket()
        self.cible.bind(("127.0.0.1", 0))
        self.cible.listen(4)
        self.cible.settimeout(0.3)
        self.port_cible = self.cible.getsockname()[1]
        self.addCleanup(self.cible.close)

    def _jamais_joint(self):
        with self.assertRaises(socket.timeout,
                               msg="le service local a été joint à travers le filtre"):
            self.cible.accept()[0].close()

    def _filtre(self, *domaines):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        threading.Thread(target=proxy.main,
                         args=(["codebyr-net-proxy", str(port)] + list(domaines),),
                         daemon=True).start()
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                return port
            except OSError:
                time.sleep(0.05)
        self.fail("le filtre n'a pas démarré")

    def test_la_connexion_directe_est_refusee(self):
        with self.assertRaises(proxy.AdresseInterne):
            proxy.connecter("localhost", self.port_cible)
        with self.assertRaises(proxy.AdresseInterne):
            proxy.connecter("127.0.0.1", self.port_cible)
        self._jamais_joint()

    def test_en_https_la_page_explique_le_refus(self):
        port = self._filtre("localhost")
        c = socket.create_connection(("127.0.0.1", port), timeout=5)
        c.sendall(("CONNECT localhost:%d HTTP/1.1\r\n\r\n" % self.port_cible).encode())
        reponse = b""
        while True:
            bloc = c.recv(4096)
            if not bloc:
                break
            reponse += bloc
        c.close()
        texte = reponse.decode("utf-8", "replace")
        self.assertIn("403", texte.splitlines()[0])
        self.assertIn("réseau local", texte)
        self._jamais_joint()

    def test_en_http_simple_aussi(self):
        port = self._filtre("localhost")
        c = socket.create_connection(("127.0.0.1", port), timeout=5)
        c.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
        premiere = c.recv(1024).decode("utf-8", "replace").splitlines()[0]
        c.close()
        self.assertIn("403", premiere)

    def test_en_socks_aussi(self):
        port = self._filtre("localhost")
        c = socket.create_connection(("127.0.0.1", port), timeout=5)
        c.sendall(bytes([5, 1, 0]))
        c.recv(2)
        nom = b"localhost"
        c.sendall(bytes([5, 1, 0, 3, len(nom)]) + nom
                  + self.port_cible.to_bytes(2, "big"))
        reponse = c.recv(10)
        c.close()
        self.assertEqual(reponse[1], proxy.SOCKS_REFUS)
        self._jamais_joint()

    def test_plus_aucune_connexion_ne_contourne_la_verification(self):
        """Toute sortie passe par connecter() : un seul endroit à garder."""
        self.assertNotIn("create_connection", _lire(os.path.join(BIN, "codebyr-net-proxy")))


# ── 3. Extension GNOME ─────────────────────────────────────────────────────

class ExtensionGnome(unittest.TestCase):

    def setUp(self):
        self.code = _lire(EXTENSION)

    def test_l_identifiant_est_toujours_echappe(self):
        # « ... ' + id » ou « ' ' + id » : l'identifiant collé tel quel.
        brut = re.findall(r"codebyr-space[^'\n]*'\s*\+\s*id\b|'\s'\s*\+\s*id\b",
                          self.code)
        self.assertEqual(brut, [], "identifiant non échappé : %s" % brut)
        self.assertGreaterEqual(self.code.count("GLib.shell_quote(id)"), 3)

    def test_la_couleur_est_validee_a_la_lecture_du_registre(self):
        corps = self.code[self.code.index("function fusionner()"):
                          self.code.index("function chargerEspaces()")]
        self.assertEqual(corps.count("couleurSure(espace.couleur)"), 2,
                         "les Espaces système ET utilisateur doivent passer par "
                         "couleurSure")


class CreationEspace(unittest.TestCase):
    """Un registre ne doit pas contenir ce qu'on refuserait d'y lire."""

    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.addCleanup(self._d.cleanup)
        anciens = registre.SYSTEME, registre.UTILISATEUR
        self.addCleanup(lambda: setattr(registre, "SYSTEME", anciens[0]))
        self.addCleanup(lambda: setattr(registre, "UTILISATEUR", anciens[1]))
        registre.SYSTEME = os.path.join(self._d.name, "systeme.json")
        registre.UTILISATEUR = os.path.join(self._d.name, "utilisateur.json")
        self.space = charger("codebyr-space")

    def test_une_couleur_qui_ajoute_du_style_est_refusee(self):
        for couleur in ("red; background-image: url(x)", "#2FA36B; color: red",
                        "#2FA36B\n", "#12345", "bleu"):
            self.assertEqual(self.space.cmd_create("Essai", couleur), 2, repr(couleur))
        self.assertFalse(os.path.exists(registre.UTILISATEUR),
                         "une couleur refusée a quand même été écrite")

    def test_une_couleur_ordinaire_passe(self):
        self.assertEqual(self.space.cmd_create("Essai", "#2FA36B"), 0)
        self.assertEqual(self.space.cmd_create("Autre", "abc"), 0)   # « # » ajouté


# ── 4. Carte graphique ─────────────────────────────────────────────────────

class CarteGraphique(unittest.TestCase):

    def _argv(self, **kw):
        return bac_a_sable.wrap_bwrap("/tmp/espace-home", ["firefox"],
                                      {"XDG_RUNTIME_DIR": "/run/user/1000"}, **kw)

    def test_retiree_sur_demande_et_presente_sinon(self):
        self.assertNotIn("/dev/dri", self._argv(gpu=False))
        self.assertNotIn("/dev/dri", self._argv(renforce=True, hors_ligne=True, gpu=False))
        self.assertIn("/dev/dri", self._argv())

    def test_liee_apres_la_creation_de_dev(self):
        # « --dev » crée un /dev neuf : un montage placé AVANT y disparaîtrait,
        # et la carte graphique manquerait partout, sans erreur visible.
        argv = self._argv()
        self.assertLess(argv.index("--dev"), argv.index("/dev/dri"))

    def test_navigation_la_garde_banque_et_jetable_non(self):
        # Navigation sert à regarder des vidéos ; ni Banque ni Jetable n'en ont
        # besoin, et ce sont les Espaces les plus exposés.
        espaces = _espaces_livres()
        self.assertIsNot(espaces["navigation"].get("gpu", True), False)
        self.assertIs(espaces["banque"].get("gpu"), False)
        self.assertIs(espaces["jetable"].get("gpu"), False)

    def test_une_piece_jointe_n_a_jamais_la_carte_graphique(self):
        source = _lire(os.path.join(BIN, "codebyr-space"))
        bloc = source[source.index("# Sous cloche"):]
        bloc = bloc[:bloc.index("app_cmd = ")]
        self.assertIn("gpu = False", bloc)

    def test_la_verification_d_isolation_le_controle(self):
        situations = {t: (o, a) for t, o, a in bac_a_sable.SITUATIONS}
        for titre, (options, attendu) in situations.items():
            if attendu.get("gpu") is False:
                self.assertIs(options.get("gpu"), False, titre)
        self.assertTrue(any(a.get("gpu") is False for _o, a in situations.values()))

    def test_une_machine_sans_carte_graphique_n_echoue_pas_a_tort(self):
        titre, _options, attendu = bac_a_sable.SITUATIONS[0]
        mesures = {cle: bool(v) for cle, v in attendu.items()}
        mesures["gpu"] = False                # machine virtuelle, par exemple
        self.assertTrue(all(ok for _l, _m, ok in bac_a_sable.evaluer(mesures, attendu)),
                        titre)

    def test_une_cle_oubliee_n_est_pas_prise_pour_non_exigee(self):
        # Seul un None EXPLICITE dispense d'un contrôle. Une porte de sortie
        # oubliée dans une situation ne doit jamais passer en silence.
        attendu = dict(bac_a_sable.SITUATIONS[0][2])
        del attendu["bus_hote"]
        mesures = {cle: bool(v) for cle, v in bac_a_sable.SITUATIONS[0][2].items()}
        with self.assertRaises(KeyError):
            bac_a_sable.evaluer(mesures, attendu)

    def test_une_carte_graphique_presente_dans_banque_est_un_echec(self):
        attendu = {t: a for t, _o, a in bac_a_sable.SITUATIONS}[
            "Espace blindé, sans micro ni carte graphique (Banque)"]
        mesures = dict(attendu, gpu=True)
        echecs = [l for l, _m, ok in bac_a_sable.evaluer(mesures, attendu) if not ok]
        self.assertEqual(echecs, ["Carte graphique (accès direct)"])


# ── 5. Réglages du noyau ───────────────────────────────────────────────────

class ReglagesNoyau(unittest.TestCase):

    ATTENDUS = {
        "kernel.unprivileged_bpf_disabled": "1",
        "net.core.bpf_jit_harden": "2",
        "kernel.kexec_load_disabled": "1",
        "vm.unprivileged_userfaultfd": "0",
        "dev.tty.ldisc_autoload": "0",
        "dev.tty.legacy_tiocsti": "0",
        "kernel.perf_event_paranoid": "3",
    }

    def _reglages(self):
        valeurs = {}
        for ligne in _lire(SYSCTL).splitlines():
            ligne = ligne.strip()
            if not ligne or ligne.startswith(("#", ";")):
                continue
            cle, _, valeur = ligne.partition("=")
            valeurs[cle.strip().lstrip("-")] = valeur.strip()
        return valeurs

    def test_chaque_reglage_a_la_bonne_valeur(self):
        self.assertEqual(self._reglages(), self.ATTENDUS)

    def test_livre_par_le_paquet_et_pas_seulement_par_l_image(self):
        # Ce qui ne vit que dans l'ISO n'atteint jamais une machine installée.
        self.assertIn("etc/sysctl.d/91-codebyr-noyau.conf",
                      _lire(os.path.join(RACINE, "packaging", "build-deb.sh")))

    def test_applique_des_la_mise_a_jour(self):
        postinst = _lire(os.path.join(RACINE, "packaging", "codebyr-tools.postinst"))
        self.assertIn("/usr/lib/systemd/systemd-sysctl", postinst)
        self.assertIn("91-codebyr-noyau.conf", postinst)
        # systemd-sysctl n'est pas dans le PATH sur Debian : le chercher par
        # « command -v » rendait la condition toujours fausse.
        self.assertNotIn("command -v systemd-sysctl", postinst)

    @unittest.skipUnless(os.path.isdir("/proc/sys"), "noyau Linux requis")
    def test_chaque_reglage_existe_dans_le_noyau(self):
        # Une faute de frappe dans un nom de réglage ne produit aucune erreur au
        # démarrage : la protection manque, simplement. Seul legacy_tiocsti a
        # le droit d'être inconnu (noyaux antérieurs à 6.2, d'où son « - »).
        for cle in self.ATTENDUS:
            if cle == "dev.tty.legacy_tiocsti":
                continue
            self.assertTrue(os.path.exists("/proc/sys/" + cle.replace(".", "/")), cle)


if __name__ == "__main__":
    unittest.main()
