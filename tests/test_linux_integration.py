"""Intégration réelle : CODEBYR_TEST_LINUX=1 python3 -m unittest discover -s tests.

Les deux comptes du prototype doivent avoir été créés par l'administrateur.
Les serveurs témoins n'écoutent que sur la boucle locale.
"""
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from outils import BIN, LIB, charger
import bac_a_sable


def espaces_utilisateur_possibles():
    """bwrap peut-il reellement creer un espace de noms utilisateur ici ?

    Question d'ENVIRONNEMENT, pas de code. Ubuntu 24.04 restreint les espaces
    de noms utilisateur non privilegies par AppArmor, et un conteneur de CI en
    herite : bwrap echoue alors sur « setting up uid map: Permission denied ».

    Sans cette sonde, deux tests parfaitement valides apparaissent en rouge sur
    le runner distant. Un echec qui ne designe pas un defaut du projet apprend
    a ignorer la CI, ce qui coute plus cher que les deux tests concernes.

    La sonde est VOLONTAIREMENT etroite : elle ne repond non que si bwrap ne
    peut pas creer l'espace de noms du tout. Une regression du bac a sable
    continue donc d'echouer, elle n'est pas ignoree.
    """
    try:
        essai = subprocess.run(
            ["bwrap", "--unshare-user", "--ro-bind", "/", "/", "/bin/true"],
            capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    return essai.returncode == 0


USERNS = espaces_utilisateur_possibles()


@unittest.skipUnless(os.environ.get("CODEBYR_TEST_LINUX") == "1", "Intégration Linux explicite")
class ReseauReel(unittest.TestCase):
    def _lancer_banque(self, home, application):
        code = """import runpy
s = runpy.run_path('/codebyr-bin/codebyr-space')
espaces = {"banque": {"id":"banque", "nom":"Banque", "couleur":"#2FA36B",
 "blindage":"renforce", "audio":False,
 "reseau":{"mode":"liste-blanche", "domaines":[]}}}
raise SystemExit(s["cmd_launch"](espaces,"banque",%r))
""" % application
        argv = ["bwrap", "--unshare-pid", "--die-with-parent", "--ro-bind", "/usr", "/usr", "--ro-bind", "/etc", "/etc",
                "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
                "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
                "--symlink", "usr/bin", "/bin", "--ro-bind", BIN, "/codebyr-bin",
                "--bind", home, home,
                "--ro-bind", LIB, "/usr/share/codebyr",
                "--setenv", "PATH", "/codebyr-bin:/usr/bin:/bin",
                "--setenv", "HOME", home, "--unsetenv", "CODEBYR_ESPACE",
                "--setenv", "CODEBYR_LIB", "/usr/share/codebyr",
                "--", "/usr/bin/python3", "-B", "-c", code]
        if os.geteuid() == 0:
            import pwd
            utilisateur = pwd.getpwnam("cbyr-test-travail")
            os.chown(home, utilisateur.pw_uid, utilisateur.pw_gid)
            argv = ["setpriv", "--reuid", str(utilisateur.pw_uid), "--regid",
                    str(utilisateur.pw_gid), "--clear-groups", "--no-new-privs"] + argv
        try:
            resultat = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired as exc:
            self.fail("Délai dépassé : %r" % exc.stderr)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)

    @unittest.skipUnless(
        USERNS, "bwrap ne peut pas creer d'espace de noms utilisateur ici "
                "(restriction AppArmor du conteneur, pas un defaut du projet)")
    def test_lancement_complet_banque(self):
        sonde = ('import socket; s=socket.create_connection(("127.0.0.1",17890),timeout=3); '
                 's.sendall(bytes.fromhex("434f4e4e45435420696e7465726469742e746573743a34343320485454502f312e310d0a0d0a")); '
                 'assert b"403" in s.recv(4096)')
        with tempfile.TemporaryDirectory() as home:
            self._lancer_banque(home, ["/usr/bin/python3", "-c", sonde])

    @unittest.skipUnless(Path("/usr/bin/firefox-esr").exists(), "Firefox ESR requis")
    @unittest.skipUnless(
        USERNS, "bwrap ne peut pas creer d'espace de noms utilisateur ici "
                "(restriction AppArmor du conteneur, pas un defaut du projet)")
    def test_firefox_headless_dans_banque_blindee(self):
        with tempfile.TemporaryDirectory() as home:
            self._lancer_banque(home, ["/usr/bin/firefox-esr", "--headless", "--screenshot",
                                      home + "/capture.png", "about:blank"])
            image = Path(home) / ".local/share/codebyr/espaces/banque/home/capture.png"
            self.assertTrue(image.read_bytes().startswith(b"\x89PNG"))

    def test_seccomp_refuse_ptrace(self):
        code = '''import ctypes, errno
from filtre_syscalls import appliquer
appliquer()
lib = ctypes.CDLL(None, use_errno=True)
assert lib.ptrace(0, 0, 0, 0) == -1
assert ctypes.get_errno() == errno.EPERM
'''
        resultat = subprocess.run([sys.executable, "-B", "-c", code],
                                  env=dict(os.environ, PYTHONPATH=LIB),
                                  capture_output=True, text=True, timeout=10)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)

    def test_seccomp_ne_laisse_ouvrir_que_les_sockets_utiles(self):
        """1.20.0 : nf_tables, x_tables, AF_PACKET et les protocoles chargés
        à la demande ne se joignent plus depuis un Espace blindé ; TCP, UDP,
        ping, Unix et netlink des interfaces passent toujours."""
        code = '''import ctypes, errno, socket
from filtre_syscalls import appliquer
appliquer()
lib = ctypes.CDLL(None, use_errno=True)
def essai(famille, type_, protocole):
    fd = lib.socket(famille, type_, protocole)
    if fd >= 0:
        lib.close(fd)
        return "ok"
    return errno.errorcode.get(ctypes.get_errno(), "?")
cloexec = socket.SOCK_CLOEXEC
attendus = {
    (1, 1, 0): "ok", (1, 5, 0): "ok",                     # Unix, flux et paquets
    (2, 1 | cloexec, 0): "ok", (2, 1, 6): "ok",           # TCP
    (10, 2, 17): "ok", (2, 2, 0): "ok",                   # UDP
    (16, 3 | cloexec, 0): "ok",                           # netlink ROUTE
    (16, 3, 12): "ENOSYS",                                # netlink NETFILTER : nf_tables
    (16, 3, 16): "ENOSYS",                                # netlink GENERIC
    (17, 3, 0): "ENOSYS",                                 # AF_PACKET
    (2, 3, 255): "ENOSYS",                                # socket brute : x_tables
    (2, 1, 132): "ENOSYS",                                # SCTP
    (38, 5, 0): "ENOSYS", (40, 1, 0): "ENOSYS",           # AF_ALG, VSOCK
}
obtenus = {k: essai(*k) for k in attendus}
assert obtenus == attendus, obtenus
'''
        resultat = subprocess.run([sys.executable, "-B", "-c", code],
                                  env=dict(os.environ, PYTHONPATH=LIB),
                                  capture_output=True, text=True, timeout=10)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)

    def test_seccomp_refuse_io_uring(self):
        """io_uring offrait un second chemin vers tout ce que le filtre refuse.

        Les operations soumises dans l'anneau - ouvrir, lire, ecrire, se
        connecter - ne passent pas par les appels systeme correspondants :
        seccomp ne les voit jamais. Laisser io_uring ouvert vidait donc la
        liste de refus de son sens, en plus d'exposer une des surfaces
        noyau les plus touchees par des elevations de privileges.

        On verifie le REFUS A L'EXECUTION, pas la presence d'un nom dans une
        liste : un appel mal orthographie ne serait jamais resolu, et le
        filtre passerait pour actif sans rien bloquer.
        """
        code = '''import ctypes, errno
from filtre_syscalls import appliquer
appliquer()
lib = ctypes.CDLL(None, use_errno=True)
# io_uring_setup(entrees, params) - refuse avant toute allocation noyau.
assert lib.syscall(425, 1, 0) == -1
assert ctypes.get_errno() == errno.EPERM, ctypes.get_errno()
'''
        resultat = subprocess.run([sys.executable, "-B", "-c", code],
                                  env=dict(os.environ, PYTHONPATH=LIB),
                                  capture_output=True, text=True, timeout=10)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)

    def test_un_appel_ecarte_recoit_enosys_comme_un_appel_inconnu(self):
        """Liste d'autorisation (1.16.4) : hors des autorisés, ENOSYS.

        acct(NULL) sans privilège recevrait EPERM du noyau ; ici, le filtre
        répond avant lui. C'est ce qui distingue « refusé par le filtre » de
        « refusé par le noyau ».
        """
        code = '''import ctypes, errno
from filtre_syscalls import appliquer
appliquer(mesure=False)
lib = ctypes.CDLL(None, use_errno=True)
assert lib.syscall(163, 0) == -1 and ctypes.get_errno() == errno.ENOSYS, ctypes.get_errno()  # acct
mode = ctypes.c_int(0)
assert lib.syscall(239, ctypes.byref(mode), 0, 0, 0, 0) == -1  # get_mempolicy
assert ctypes.get_errno() == errno.ENOSYS, ctypes.get_errno()
# Les refus gardent EPERM : ce sont des interdits, pas des absences.
assert lib.ptrace(0, 0, 0, 0) == -1 and ctypes.get_errno() == errno.EPERM
# personality, jamais vu mais gardé : la lecture du modèle d'exécution passe.
assert lib.syscall(135, 0xffffffff) >= 0, ctypes.get_errno()
'''
        resultat = subprocess.run([sys.executable, "-B", "-c", code],
                                  env=dict(os.environ, PYTHONPATH=LIB),
                                  capture_output=True, text=True, timeout=10)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)

    def test_un_vrai_programme_tourne_sous_la_liste_d_autorisation(self):
        # Fils d'exécution, chiffrement, base de données, sous-processus,
        # réseau local : si la liste oubliait un appel courant, c'est ici que
        # ça casserait — pas chez un utilisateur.
        code = '''import hashlib, os, socket, sqlite3, ssl, subprocess, sys, tempfile, threading
from filtre_syscalls import appliquer
appliquer(mesure=False)
res = []
t = threading.Thread(target=lambda: res.append(hashlib.sha256(b"x" * 10**6).hexdigest()))
t.start(); t.join()
ssl.create_default_context()
with tempfile.TemporaryDirectory() as d:
    db = sqlite3.connect(os.path.join(d, "e.db")); db.execute("create table t(x)"); db.commit()
a, b = socket.socketpair(); a.sendall(b"ok"); assert b.recv(2) == b"ok"
sortie = subprocess.run([sys.executable, "-c", "print(40 + 2)"], capture_output=True, text=True)
assert sortie.stdout.strip() == "42", sortie
assert subprocess.run(["sh", "-c", "ls / > /dev/null && date > /dev/null"]).returncode == 0
print("tout a tourné")
'''
        resultat = subprocess.run([sys.executable, "-B", "-c", code],
                                  env=dict(os.environ, PYTHONPATH=LIB),
                                  capture_output=True, text=True, timeout=60)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertIn("tout a tourné", resultat.stdout)

    def test_le_mode_mesure_journalise_sans_rien_desserrer_ni_casser(self):
        """Le mode mesure laisse passer les candidats, et garde les refus.

        Il sert à regarder des applications réelles : s'il refusait un
        candidat, il casserait ce qu'on mesure ; s'il laissait passer un refus,
        activer la mesure affaiblirait le Blindage.
        """
        code = '''import ctypes, errno
from filtre_syscalls import appliquer
appliquer(mesure=True)
lib = ctypes.CDLL(None, use_errno=True)
# get_mempolicy (candidat) : permis, journalisé.
mode = ctypes.c_int(0)
assert lib.syscall(239, ctypes.byref(mode), 0, 0, 0, 0) == 0, ctypes.get_errno()
# personality(0xffffffff) (candidat) : la lecture du modèle d'exécution.
assert lib.syscall(135, 0xffffffff) >= 0, ctypes.get_errno()
# ptrace et io_uring : toujours refusés.
assert lib.ptrace(0, 0, 0, 0) == -1 and ctypes.get_errno() == errno.EPERM
assert lib.syscall(425, 1, 0) == -1 and ctypes.get_errno() == errno.EPERM
'''
        resultat = subprocess.run([sys.executable, "-B", "-c", code],
                                  env=dict(os.environ, PYTHONPATH=LIB),
                                  capture_output=True, text=True, timeout=10)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)

    def test_namespace_sans_sortie_directe_et_bouclage_refuse_par_le_filtre(self):
        """L'Espace n'a que le filtre ; le filtre ne le mène pas à cette machine.

        Le témoin écoute sur la boucle locale et figure dans la liste
        blanche. Jusqu'en 1.11, ce test attendait que le filtre l'atteigne.
        Depuis 1.12.0, c'est précisément ce qu'il doit refuser : un domaine
        autorisé qui mène à la machine ou au réseau local ne doit jamais
        devenir un passage. L'ancien test contredisait ce correctif, et la CI
        est restée rouge du 13 au 27 septembre sans que personne ne le lise.

        Le chemin positif — un site public autorisé est bien relayé — est
        vérifié sans réseau dans test_filtre_reseau.py.
        """
        proxy = charger("codebyr-net-proxy")
        with tempfile.TemporaryDirectory() as tmp, socket.socket() as temoin:
            temoin.bind(("127.0.0.1", 0))
            temoin.listen(1)
            port = temoin.getsockname()[1]
            chemin = str(Path(tmp) / "proxy")
            with socket.socket(socket.AF_UNIX) as serveur:
                serveur.bind(chemin)
                serveur.listen(8)
                filtre = subprocess.Popen([sys.executable, "-B", str(Path(BIN) / "codebyr-net-proxy"),
                                           "--fd", str(serveur.fileno()), "127.0.0.1"],
                                          pass_fds=(serveur.fileno(),))
                try:
                    sonde = '''import socket
try:
 s=socket.create_connection(("127.0.0.1", %d),timeout=1)
except OSError: pass
else: raise AssertionError("Connexion directe à l'hôte possible")
with socket.create_connection(("127.0.0.1",17890),timeout=3) as s:
 s.sendall(b"CONNECT interdit.test:443 HTTP/1.1\\r\\n\\r\\n")
 assert b"403" in s.recv(4096)
with socket.create_connection(("127.0.0.1",17890),timeout=3) as s:
 s.sendall(b"CONNECT 127.0.0.1:%d HTTP/1.1\\r\\n\\r\\n")
 data=b""
 while True:
  morceau=s.recv(4096)
  if not morceau: break
  data+=morceau
 assert b"403" in data, data[:80]
 assert "réseau local".encode() in data, "refus sans l'explication du réseau local"
''' % (port, port)
                    cmd = ["/usr/bin/python3", "/usr/share/codebyr/relais_reseau.py",
                           "/run/codebyr-proxy", "17890", "--", "/usr/bin/python3", "-c", sonde]
                    argv = bac_a_sable.wrap_bwrap(tmp, cmd, dict(os.environ),
                                                 renforce=True, audio=False, filtre=chemin)
                    position = argv.index("--")
                    argv[position:position] = ["--ro-bind", LIB, "/usr/share/codebyr"]
                    resultat = subprocess.run(argv, capture_output=True, text=True, timeout=15)
                    self.assertEqual(resultat.returncode, 0, resultat.stderr)
                finally:
                    filtre.terminate()
                    filtre.wait(timeout=5)
            # Ni la sonde ni le filtre n'ont joint le témoin : une connexion
            # établie attendrait ici, dans la file d'écoute.
            temoin.settimeout(0.3)
            with self.assertRaises(socket.timeout, msg="le témoin a été joint"):
                temoin.accept()[0].close()
        self.assertFalse(proxy.autorise("interdit.test", ["127.0.0.1"]))

    def test_jetable_sans_interface_externe(self):
        with tempfile.TemporaryDirectory() as home:
            argv = bac_a_sable.wrap_bwrap(home, ["/usr/bin/python3", "-c",
                'import socket; assert [n for _,n in socket.if_nameindex()] == ["lo"]'],
                dict(os.environ), renforce=True, hors_ligne=True)
            position = argv.index("--")
            argv[position:position] = ["--ro-bind", LIB, "/usr/share/codebyr"]
            resultat = subprocess.run(argv, capture_output=True, text=True, timeout=10)
            self.assertEqual(resultat.returncode, 0, resultat.stderr)


@unittest.skipUnless(os.environ.get("CODEBYR_TEST_LINUX") == "1" and
                     hasattr(os, "geteuid") and os.geteuid() == 0,
                     "Prototype UID : administrateur Linux")
class UIDReels(unittest.TestCase):
    def test_un_uid_ne_lit_pas_son_voisin_meme_sans_bwrap(self):
        import pwd
        a = pwd.getpwnam("cbyr-test-travail")
        b = pwd.getpwnam("cbyr-test-navigation")
        self.assertNotEqual(a.pw_uid, b.pw_uid)
        with tempfile.NamedTemporaryFile(dir=a.pw_dir) as secret:
            os.fchown(secret.fileno(), a.pw_uid, a.pw_gid)
            prefixe = ["setpriv", "--reuid", str(b.pw_uid), "--regid", str(b.pw_gid),
                       "--clear-groups", "--no-new-privs"]
            resultat = subprocess.run(prefixe + ["cat", secret.name], capture_output=True)
            self.assertNotEqual(resultat.returncode, 0)
            self.assertIn(b"Permission denied", resultat.stderr)
