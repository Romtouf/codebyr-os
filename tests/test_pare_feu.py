# -*- coding: utf-8 -*-
"""Le pare-feu : rien n'entre qui n'a pas été demandé — sauf mDNS et DHCPv6.

Analyse externe du 01/10/2026, point 3.5. Le suivi des connexions ne
rattache pas leurs réponses à leur question : on interroge un GROUPE, et la
réponse vient d'une autre adresse. Le pare-feu des images 1.0 à 1.20.0 les
jetait donc — plus de découverte des imprimantes du réseau (Avahi et
cups-browsed sont dans l'image), plus de DHCPv6. Et il était écrit par
l'image seule : une correction n'atteignait aucune machine installée.

Le test réel monte deux machines (des espaces de noms réseau reliés par une
paire veth), charge le vrai pare-feu sur l'une et lui envoie de vrais paquets
depuis l'autre — avec l'ancien pare-feu aussi, pour prouver ce qu'il jetait.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

from outils import BIN, RACINE

LIVRE = os.path.join(RACINE, "live-build", "config", "includes.chroot_after_packages")
NOUVEAU = os.path.join(LIVRE, "usr", "share", "codebyr", "nftables.conf")
DURCIR = os.path.join(BIN, "codebyr-durcir-poste")
HOOK = os.path.join(RACINE, "live-build", "config", "hooks", "normal", "0200-hardening.hook.chroot")

# Le pare-feu des images 1.0 à 1.20.0, tel qu'il est sur les machines.
ANCIEN = textwrap.dedent("""\
    #!/usr/sbin/nft -f
    flush ruleset
    table inet filter {
    \tchain input {
    \t\ttype filter hook input priority 0; policy drop;
    \t\tct state established,related accept
    \t\tiif "lo" accept
    \t\tct state invalid drop
    \t\tip protocol icmp accept
    \t\tip6 nexthdr ipv6-icmp accept
    \t\t# Phase 2 : les Espaces déclareront ici leurs autorisations réseau.
    \t}
    \tchain forward { type filter hook forward priority 0; policy drop; }
    \tchain output  { type filter hook output priority 0; policy accept; }
    }
    """)
EMPREINTE_ANCIEN = "940ec40eab267d032896959f2bd3af7b0dc80177193803e04111200dc1ea98b9"


def _lire(chemin):
    with open(chemin, encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n")


class LesRegles(unittest.TestCase):

    def test_l_ancien_est_reconnu_a_son_empreinte(self):
        self.assertEqual(hashlib.sha256(ANCIEN.encode()).hexdigest(), EMPREINTE_ANCIEN)
        self.assertIn(EMPREINTE_ANCIEN + ")", _lire(DURCIR))

    def test_l_entree_reste_fermee_et_les_ouvertures_sont_etroites(self):
        regles = [l.strip() for l in _lire(NOUVEAU).splitlines()
                  if l.strip() and not l.strip().startswith("#")]
        self.assertIn("type filter hook input priority 0; policy drop;", regles)
        acceptees = [l for l in regles if l.endswith(" accept")
                     and not l.startswith(("ct state", "iif", "ip protocol icmp", "ip6 nexthdr"))]
        self.assertEqual(acceptees, [
            "ip daddr 224.0.0.251 udp dport 5353 accept",
            "ip6 daddr ff02::fb udp dport 5353 accept",
            "ip6 saddr fe80::/10 udp sport 547 udp dport 546 accept",
        ])

    def test_l_image_installe_le_fichier_du_paquet(self):
        hook = _lire(HOOK)
        self.assertIn("install -m 0755 /usr/share/codebyr/nftables.conf /etc/nftables.conf", hook)
        self.assertNotIn("cat > /etc/nftables.conf", hook)


@unittest.skipUnless(shutil.which("sh") and shutil.which("sha256sum") and shutil.which("cmp"),
                     "shell POSIX")
class LaMiseAJourDesMachines(unittest.TestCase):
    """La section 5 de codebyr-durcir-poste, exécutée sur des fichiers à part."""

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="codebyr-parefeu-")
        self.addCleanup(shutil.rmtree, self.dossier)
        self.etc = os.path.join(self.dossier, "nftables.conf")
        texte = _lire(DURCIR)
        debut = texte.index("PAREFEU=/etc/nftables.conf")
        section = texte[debut:texte.index("\nexit 0", debut)]
        # Ni service à recharger ici : on éprouve le choix, pas le chargement.
        self.section = (section.replace("/etc/nftables.conf", self.etc.replace("\\", "/"))
                        .replace("/usr/share/codebyr/nftables.conf", NOUVEAU.replace("\\", "/"))
                        .replace("[ -d /run/systemd/system ]", "false"))

    def _poser(self, contenu):
        with open(self.etc, "w", encoding="utf-8", newline="\n") as f:
            f.write(contenu)

    def _durcir(self):
        r = subprocess.run(["sh", "-c", self.section], capture_output=True, text=True,
                           encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout, _lire(self.etc)

    def test_l_ancien_pare_feu_de_codebyr_est_remplace(self):
        self._poser(ANCIEN)
        sortie, apres = self._durcir()
        self.assertEqual(apres, _lire(NOUVEAU))
        self.assertIn("pare-feu mis à jour", sortie)
        self.assertFalse(os.path.exists(self.etc + ".codebyr-neuf"))

    def test_un_pare_feu_de_l_administrateur_reste_le_sien(self):
        reglage = ANCIEN.replace("ip protocol icmp accept", "ip protocol icmp accept\n\t\ttcp dport 22 accept")
        self._poser(reglage)
        sortie, apres = self._durcir()
        self.assertEqual(apres, reglage)
        self.assertEqual(sortie, "")

    def test_deja_a_jour_rien_ne_bouge(self):
        self._poser(_lire(NOUVEAU))
        sortie, apres = self._durcir()
        self.assertEqual((sortie, apres), ("", _lire(NOUVEAU)))


# ── Le vrai pare-feu, sur un vrai réseau (simulé) ────────────────────────────
POSTE, RESEAU = "cbyr-pf-poste", "cbyr-pf-reseau"

ECOUTE = r"""
import socket, struct, sys
famille, adresse, port, groupe = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
if famille == "4":
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", port))
    if groupe != "-":
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                     socket.inet_aton(groupe) + socket.inet_aton(adresse))
else:
    s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("::", port))
    if groupe != "-":
        index = socket.if_nametoindex("cbyr-pf-a")
        s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP,
                     socket.inet_pton(socket.AF_INET6, groupe) + struct.pack("@I", index))
s.settimeout(2)
print("pret", flush=True)
try:
    s.recvfrom(64)
    print("recu")
except socket.timeout:
    print("rien")
"""

ENVOI = r"""
import socket, sys
famille, source, sport, destination, dport = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], int(sys.argv[5])
if famille == "4":
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((source, sport))
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(source))
    s.sendto(b"codebyr", (destination, dport))
else:
    s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    index = socket.if_nametoindex("cbyr-pf-b")
    s.bind((source, sport, 0, index if source.startswith("fe80") else 0))
    s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, index)
    s.sendto(b"codebyr", (destination, dport, 0, index))
"""

# (cas, famille, adresse d'écoute, port, groupe, source, port source, destination)
CAS = [
    ("mDNS IPv4, au groupe", "4", "10.77.0.1", 5353, "224.0.0.251", "10.77.0.2", 5353, "224.0.0.251"),
    ("mDNS IPv6, au groupe", "6", "-", 5353, "ff02::fb", "fd77::2", 5353, "ff02::fb"),
    ("DHCPv6, serveur du lien local", "6", "-", 546, "-", "fe80::2", 547, "fe80::1"),
    ("mDNS, mais en direct", "4", "10.77.0.1", 5353, "-", "10.77.0.2", 5353, "10.77.0.1"),
    ("DHCPv6, d'une adresse globale", "6", "-", 546, "-", "fd77::2", 547, "fd77::1"),
    ("DHCPv6, d'un autre port", "6", "-", 546, "-", "fe80::2", 4000, "fe80::1"),
    ("un port quelconque", "4", "10.77.0.1", 2222, "-", "10.77.0.2", 4000, "10.77.0.1"),
]
OUVERTS = {"mDNS IPv4, au groupe", "mDNS IPv6, au groupe", "DHCPv6, serveur du lien local"}


def _ip(*args, ns=None):
    argv = (["ip", "netns", "exec", ns] if ns else []) + list(args)
    subprocess.run(argv, check=True, capture_output=True)


def _peut_monter_un_reseau():
    if not (os.environ.get("CODEBYR_TEST_LINUX") == "1" and hasattr(os, "geteuid")
            and os.geteuid() == 0 and shutil.which("ip") and shutil.which("nft")):
        return False
    try:
        _ip("ip", "netns", "add", "cbyr-pf-sonde")
        _ip("ip", "netns", "exec", "cbyr-pf-sonde", "nft", "list", "ruleset")
        return True
    except (subprocess.CalledProcessError, OSError):
        return False
    finally:
        subprocess.run(["ip", "netns", "del", "cbyr-pf-sonde"], capture_output=True)


@unittest.skipUnless(sys.platform.startswith("linux") and _peut_monter_un_reseau(),
                     "root sous Linux (CODEBYR_TEST_LINUX=1) avec ip et nft")
class SurUnVraiReseau(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        for ns in (POSTE, RESEAU):
            subprocess.run(["ip", "netns", "del", ns], capture_output=True)
            _ip("ip", "netns", "add", ns)
        _ip("ip", "link", "add", "cbyr-pf-a", "type", "veth", "peer", "name", "cbyr-pf-b")
        _ip("ip", "link", "set", "cbyr-pf-a", "netns", POSTE)
        _ip("ip", "link", "set", "cbyr-pf-b", "netns", RESEAU)
        for ns, lien, n in ((POSTE, "cbyr-pf-a", 1), (RESEAU, "cbyr-pf-b", 2)):
            _ip("ip", "addr", "add", "10.77.0.%d/24" % n, "dev", lien, ns=ns)
            _ip("ip", "-6", "addr", "add", "fe80::%d/64" % n, "dev", lien, "nodad", ns=ns)
            _ip("ip", "-6", "addr", "add", "fd77::%d/64" % n, "dev", lien, "nodad", ns=ns)
            _ip("ip", "link", "set", lien, "up", "multicast", "on", ns=ns)
            _ip("ip", "link", "set", "lo", "up", ns=ns)
        cls.dossier = tempfile.mkdtemp(prefix="codebyr-parefeu-")
        cls.ancien = os.path.join(cls.dossier, "ancien.conf")
        with open(cls.ancien, "w", encoding="utf-8") as f:
            f.write(ANCIEN)
        cls.resultats = {"nouveau": cls._mesurer(NOUVEAU), "ancien": cls._mesurer(cls.ancien)}

    @classmethod
    def tearDownClass(cls):
        for ns in (POSTE, RESEAU):
            subprocess.run(["ip", "netns", "del", ns], capture_output=True)
        shutil.rmtree(cls.dossier, ignore_errors=True)

    @classmethod
    def _mesurer(cls, regles):
        _ip("nft", "-f", regles, ns=POSTE)
        vus = {}
        for nom, famille, adresse, port, groupe, source, sport, destination in CAS:
            ecoute = subprocess.Popen(["ip", "netns", "exec", POSTE, sys.executable, "-c", ECOUTE,
                                       famille, adresse, str(port), groupe],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            assert ecoute.stdout.readline().strip() == "pret", ecoute.stderr.read()
            _ip(sys.executable, "-c", ENVOI, famille, source, str(sport), destination, str(port),
                ns=RESEAU)
            sortie, erreurs = ecoute.communicate(timeout=10)
            vus[nom] = sortie.strip() or erreurs.strip()
        return vus

    def test_le_pare_feu_laisse_passer_mdns_et_dhcpv6_et_rien_d_autre(self):
        for nom, *_reste in CAS:
            with self.subTest(cas=nom):
                self.assertEqual(self.resultats["nouveau"][nom],
                                 "recu" if nom in OUVERTS else "rien")

    def test_l_ancien_jetait_tout(self):
        # Sans ce témoin, un test qui passe ne prouverait pas que les ouvertures
        # manquaient : les mêmes paquets, l'ancien pare-feu, tout est jeté.
        for nom, *_reste in CAS:
            with self.subTest(cas=nom):
                self.assertEqual(self.resultats["ancien"][nom], "rien")


if __name__ == "__main__":
    unittest.main()
