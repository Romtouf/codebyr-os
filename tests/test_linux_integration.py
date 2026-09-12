"""Intégration réelle : CODEBYR_TEST_LINUX=1 python3 -m unittest discover -s tests.

Les deux comptes du prototype doivent avoir été créés par l'administrateur.
Les serveurs témoins n'écoutent que sur la boucle locale.
"""
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from outils import BIN, LIB, charger
import bac_a_sable


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

    def test_lancement_complet_banque(self):
        sonde = ('import socket; s=socket.create_connection(("127.0.0.1",17890),timeout=3); '
                 's.sendall(bytes.fromhex("434f4e4e45435420696e7465726469742e746573743a34343320485454502f312e310d0a0d0a")); '
                 'assert b"403" in s.recv(4096)')
        with tempfile.TemporaryDirectory() as home:
            self._lancer_banque(home, ["/usr/bin/python3", "-c", sonde])

    @unittest.skipUnless(Path("/usr/bin/firefox-esr").exists(), "Firefox ESR requis")
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

    def test_namespace_refuse_direct_et_autorise_uniquement_proxy(self):
        proxy = charger("codebyr-net-proxy")
        with tempfile.TemporaryDirectory() as tmp, socket.socket() as temoin:
            temoin.bind(("127.0.0.1", 0))
            temoin.listen(1)
            port = temoin.getsockname()[1]

            def repondre():
                connexion, _ = temoin.accept()
                with connexion:
                    connexion.sendall(b"TEMOIN")

            threading.Thread(target=repondre, daemon=True).start()
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
 data=s.recv(4096)
 assert b"200" in data
 if b"TEMOIN" not in data: data += s.recv(4096)
 assert b"TEMOIN" in data
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
