# -*- coding: utf-8 -*-
"""Les notifications d'un Espace arrivent à l'écran, sans lui donner le bus.

Depuis la 1.1.0, un Espace a un bus de session privé : c'est ce qui a fermé la
faille la plus grave du projet (le bus de l'hôte y donnait accès à systemd
--user, donc à l'exécution hors du bac à sable). Contrepartie : plus personne
n'y fournissait « org.freedesktop.Notifications ».

Le relais rend les notifications SANS toucher à ce bus. Ces tests gardent les
deux moitiés : que le texte passe, et que rien d'autre ne passe.
"""
import json
import os
import socket
import tempfile
import threading
import time
import unittest

from outils import BIN, LIB, RACINE  # noqa: F401 — place les modules partagés
import relais_notifications as relais  # noqa: E402

ESPACES_LIB = os.path.join(LIB, "bus", "dbus-1", "services",
                           "org.freedesktop.Notifications.service")


def _lire(chemin):
    with open(chemin, encoding="utf-8") as f:
        return f.read()


class TexteAffiche(unittest.TestCase):
    """Ce qu'un Espace peut faire apparaître à l'écran."""

    def test_les_balises_sont_retirees(self):
        # GNOME interprète un sous-ensemble de HTML : une application hostile
        # s'en servirait pour maquiller son message (gras, lien, faux bouton).
        self.assertEqual(relais.nettoyer("<b>Alerte</b> <a href='x'>ici</a>", 100),
                         "bAlerte/b a href='x'ici/a")

    def test_les_caracteres_de_controle_disparaissent(self):
        self.assertEqual(relais.nettoyer("deux\nlignes\ret\x00nul", 100),
                         "deux lignes et nul")

    def test_le_texte_est_borne(self):
        long = relais.nettoyer("a" * 500, 120)
        self.assertEqual(len(long), 120)
        self.assertTrue(long.endswith("…"))

    def test_un_texte_vide_reste_vide(self):
        self.assertEqual(relais.nettoyer(None, 50), "")


class Debit(unittest.TestCase):
    """Une application hostile ne doit pas pouvoir noyer l'écran."""

    def test_au_dela_du_quota_les_notifications_sont_ecartees(self):
        horloge = [1000.0]
        limiteur = relais.Limiteur(maximum=3, fenetre=10, horloge=lambda: horloge[0])
        self.assertEqual([limiteur.autorise() for _ in range(4)],
                         [True, True, True, False])

    def test_la_fenetre_glisse(self):
        horloge = [1000.0]
        limiteur = relais.Limiteur(maximum=2, fenetre=10, horloge=lambda: horloge[0])
        limiteur.autorise(), limiteur.autorise()
        self.assertFalse(limiteur.autorise())
        horloge[0] += 11
        self.assertTrue(limiteur.autorise())


class Traitement(unittest.TestCase):

    def setUp(self):
        self.vues = []

    def _montrer(self, espace, resume, corps):
        self.vues.append((espace, resume, corps))

    def _traiter(self, charge, espace="Jetable", limiteur=None):
        return relais.traiter(json.dumps(charge).encode("utf-8"), espace,
                              self._montrer, limiteur)

    def test_l_entete_est_impose_par_l_hote(self):
        # Le nom annoncé par l'application est ignoré : une notification venue
        # de Jetable ne doit jamais pouvoir s'afficher « Banque ».
        self._traiter({"resume": "Coucou", "corps": "", "app_name": "Banque"})
        self.assertEqual(self.vues, [("Jetable", "Coucou", "")])

    def test_une_demande_illisible_est_refusee(self):
        self.assertFalse(relais.traiter(b"pas du json", "Travail", self._montrer))
        self.assertFalse(relais.traiter(b'"une chaine"', "Travail", self._montrer))
        self.assertEqual(self.vues, [])

    def test_une_demande_vide_est_refusee(self):
        self.assertFalse(self._traiter({"resume": "", "corps": "   "}))
        self.assertEqual(self.vues, [])

    def test_le_corps_seul_devient_le_titre(self):
        self._traiter({"resume": "", "corps": "Téléchargement terminé"})
        self.assertEqual(self.vues, [("Jetable", "Téléchargement terminé", "")])

    def test_le_quota_s_applique(self):
        limiteur = relais.Limiteur(maximum=1, fenetre=100)
        self.assertTrue(self._traiter({"resume": "une"}, limiteur=limiteur))
        self.assertFalse(self._traiter({"resume": "deux"}, limiteur=limiteur))
        self.assertEqual(len(self.vues), 1)


@unittest.skipUnless(hasattr(socket, "AF_UNIX"), "sockets Unix — Linux")
class DeBoutEnBout(unittest.TestCase):
    """Le chemin réel : l'Espace envoie, l'hôte affiche."""

    def setUp(self):
        self.dossier = tempfile.mkdtemp()
        self.chemin = os.path.join(self.dossier, "notif")
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(self.chemin)
        self.srv.listen(4)
        self.vues = []
        threading.Thread(
            target=relais.servir,
            args=(self.srv, "Banque", lambda e, r, c: self.vues.append((e, r, c))),
            daemon=True).start()
        self.addCleanup(self.srv.close)

    def _attendre(self, combien, delai=3.0):
        fin = time.monotonic() + delai
        while time.monotonic() < fin and len(self.vues) < combien:
            time.sleep(0.02)
        return self.vues

    def test_une_notification_traverse(self):
        self.assertTrue(relais.envoyer("Virement reçu", "150 €", self.chemin))
        self.assertEqual(self._attendre(1), [("Banque", "Virement reçu", "150 €")])

    def test_le_texte_est_nettoye_en_chemin(self):
        relais.envoyer("<b>faux</b>", "ligne1\nligne2", self.chemin)
        self.assertEqual(self._attendre(1), [("Banque", "bfaux/b", "ligne1 ligne2")])

    def test_sans_socket_l_envoi_echoue_en_silence(self):
        # Une notification n'est pas critique : un Espace ne doit pas planter
        # parce que l'hôte n'écoute plus.
        self.assertFalse(relais.envoyer("x", "y", os.path.join(self.dossier, "absent")))


class LeBusPriveResteIntact(unittest.TestCase):
    """La correction ne doit pas rouvrir la faille qu'elle contourne."""

    def setUp(self):
        self.space = _lire(os.path.join(BIN, "codebyr-space"))
        self.sable = _lire(os.path.join(LIB, "bac_a_sable.py"))

    def test_le_bus_prive_est_toujours_donne_a_l_espace(self):
        self.assertIn("dbus-run-session", self.space)

    def test_le_bus_de_l_hote_n_entre_toujours_pas(self):
        self.assertIn('"--unsetenv", "DBUS_SESSION_BUS_ADDRESS"', self.sable)
        self.assertNotIn("xdg-dbus-proxy", self.space)

    def test_seule_une_socket_entre_dans_l_espace(self):
        self.assertIn('bwrap += ["--ro-bind", notifications, "/run/codebyr-notif"]',
                      self.sable)

    def test_le_service_n_est_declare_que_pour_les_espaces(self):
        # Déclaré dans /usr/share/dbus-1/services, il remplacerait aussi le
        # service de notifications du BUREAU si GNOME Shell redémarrait.
        self.assertTrue(os.path.exists(ESPACES_LIB))
        declaration = _lire(ESPACES_LIB)
        self.assertIn("Name=org.freedesktop.Notifications", declaration)
        self.assertIn("relais_notifications.py --service", declaration)
        self.assertIn('env["XDG_DATA_DIRS"] = "/usr/share/codebyr/bus:"', self.space)

    def test_le_service_refuse_de_tourner_hors_d_un_espace(self):
        ancien = os.environ.pop("CODEBYR_ESPACE", None)
        try:
            self.assertEqual(relais.service(), 1)
        finally:
            if ancien is not None:
                os.environ["CODEBYR_ESPACE"] = ancien

    def test_ni_action_ni_icone_de_l_application(self):
        source = _lire(os.path.join(LIB, "relais_notifications.py"))
        # Notify reçoit huit arguments ; seuls le résumé et le corps sont
        # transmis. Une action rouvrirait un canal de retour vers l'Espace.
        self.assertIn("_, _, _, resume, corps, _, _, _ = params.unpack()", source)
        self.assertIn("--icon=dialog-information", source)


if __name__ == "__main__":
    unittest.main()
