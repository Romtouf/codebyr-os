# -*- coding: utf-8 -*-
"""Le filtre réseau à liste blanche (Espace Banque)."""
import os
import socket
import tempfile
import threading
import time
import unittest

from outils import charger

proxy = charger("codebyr-net-proxy")


class ListeBlanche(unittest.TestCase):

    def test_domaine_exact(self):
        self.assertTrue(proxy.autorise("mabanque.fr", ["mabanque.fr"]))
        self.assertFalse(proxy.autorise("autre.fr", ["mabanque.fr"]))

    def test_sous_domaines(self):
        self.assertTrue(proxy.autorise("www.mabanque.fr", ["*.mabanque.fr"]))
        self.assertTrue(proxy.autorise("mabanque.fr", ["*.mabanque.fr"]))
        self.assertFalse(proxy.autorise("mabanque.fr.piege.com", ["*.mabanque.fr"]))

    def test_suffixe_trompeur(self):
        # « mabanque.fr.evil.com » ne doit JAMAIS passer pour « mabanque.fr ».
        self.assertFalse(proxy.autorise("mabanque.fr.evil.com", ["mabanque.fr"]))
        self.assertFalse(proxy.autorise("notmabanque.fr", ["mabanque.fr"]))

    def test_insensible_a_la_casse_et_au_point_final(self):
        self.assertTrue(proxy.autorise("MaBanque.FR.", ["mabanque.fr"]))

    def test_liste_vide_ne_laisse_rien_passer(self):
        self.assertFalse(proxy.autorise("mabanque.fr", []))


class AdressesIPv6(unittest.TestCase):
    """Les adresses IPv6 littérales arrivent entre crochets.

    « CONNECT [2001:db8::1]:443 » donnait l'hôte « [2001:db8::1] », que
    getaddrinfo refuse : aucune adresse IPv6 écrite en clair n'était joignable
    depuis un Espace à liste blanche, même autorisée.
    """

    def test_les_crochets_sont_retires(self):
        self.assertEqual(proxy.hote_propre("[2001:db8::1]"), "2001:db8::1")
        self.assertEqual(proxy.hote_propre("[::1]"), "::1")

    def test_un_nom_ordinaire_est_intact(self):
        self.assertEqual(proxy.hote_propre("MaBanque.FR."), "mabanque.fr")

    def test_une_adresse_ipv6_peut_etre_autorisee(self):
        self.assertTrue(proxy.autorise("[2001:db8::1]", ["2001:db8::1"]))
        self.assertFalse(proxy.autorise("[2001:db8::2]", ["2001:db8::1"]))


class EchecFerme(unittest.TestCase):
    """Un Espace à réseau restreint sans domaine déclaré doit tout bloquer.

    Historique : le filtre ne démarrait pas quand la liste était vide, et
    l'Espace Banque se retrouvait avec un accès Internet complet alors que
    l'interface annonçait une restriction. Échouer FERMÉ n'est pas négociable.
    """

    def _proxy_sans_domaine(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        threading.Thread(target=proxy.main,
                         args=(["codebyr-net-proxy", str(port)],),
                         daemon=True).start()
        for _ in range(50):          # attendre l'écoute, sans dormir bêtement
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                return port
            except OSError:
                time.sleep(0.05)
        self.fail("le filtre n'a pas démarré")

    def test_tout_est_refuse_et_l_utilisateur_est_guide(self):
        port = self._proxy_sans_domaine()
        c = socket.create_connection(("127.0.0.1", port), timeout=5)
        c.sendall(b"GET http://exemple.test/ HTTP/1.1\r\nHost: exemple.test\r\n\r\n")
        reponse = c.recv(4096).decode("utf-8", "replace")
        c.close()
        self.assertIn("403", reponse.splitlines()[0])
        self.assertIn("Configuration Codebyr", reponse)

    def test_https_est_refuse_aussi(self):
        port = self._proxy_sans_domaine()
        c = socket.create_connection(("127.0.0.1", port), timeout=5)
        c.sendall(b"CONNECT exemple.test:443 HTTP/1.1\r\n\r\n")
        reponse = c.recv(4096).decode("utf-8", "replace")
        c.close()
        self.assertIn("403", reponse.splitlines()[0])


@unittest.skipUnless(os.name == "posix",
                     "le passage de descripteur est propre à POSIX")
class SocketHeritee(unittest.TestCase):
    """Le filtre reçoit une socket DÉJÀ en écoute, ouverte par codebyr-space.

    Deux défauts supprimés d'un coup : la course entre « choisir un port libre »
    et « s'y installer » (un autre programme pouvait s'y glisser), et le cas où
    le navigateur démarrait avant le filtre et tombait sur un port muet.
    """

    def test_le_filtre_sert_la_socket_transmise(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(64)
        port = srv.getsockname()[1]
        # Le port répond DÉJÀ, avant même que le filtre ne soit démarré.
        socket.create_connection(("127.0.0.1", port), timeout=2).close()

        threading.Thread(
            target=proxy.main,
            args=(["codebyr-net-proxy", "--fd", str(srv.fileno()),
                   "mabanque.fr"],),
            daemon=True).start()
        time.sleep(0.3)
        c = socket.create_connection(("127.0.0.1", port), timeout=5)
        c.sendall(b"GET / HTTP/1.1\r\nHost: intrus.test\r\n\r\n")
        reponse = c.recv(1024).decode("utf-8", "replace")
        c.close()
        srv.close()
        self.assertIn("403", reponse.splitlines()[0])


class ModeApprentissage(unittest.TestCase):
    """Les domaines refusés sont notés, pour pouvoir être autorisés ensuite.

    Sans ce journal, un site bancaire qui charge une ressource ailleurs (CDN,
    3-D Secure, captcha) donne seulement « ma banque ne marche plus », sans
    aucun moyen pour l'utilisateur de savoir quoi autoriser.
    """

    def test_les_refus_sont_journalises_une_seule_fois(self):
        dossier = tempfile.mkdtemp()
        journal = os.path.join(dossier, "espaces", "banque", "domaines-refuses.txt")
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        threading.Thread(
            target=proxy.main,
            args=(["codebyr-net-proxy", str(port), "--journal", journal,
                   "mabanque.fr"],),
            daemon=True).start()
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.05)

        for hote in ("cdn.exemple.test", "cdn.exemple.test", "3ds.exemple.test"):
            c = socket.create_connection(("127.0.0.1", port), timeout=5)
            c.sendall(("GET / HTTP/1.1\r\nHost: %s\r\n\r\n" % hote).encode())
            try:
                c.recv(256)
            except OSError:
                pass
            c.close()

        for _ in range(20):
            if os.path.exists(journal):
                break
            time.sleep(0.05)
        with open(journal, encoding="utf-8") as f:
            notes = f.read().split()
        self.assertEqual(notes, ["cdn.exemple.test", "3ds.exemple.test"])


if __name__ == "__main__":
    unittest.main()
