"""Un PID réutilisé ne doit ni recevoir une couleur ni être tué à tort."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from outils import RACINE, charger

space = charger("codebyr-space")
EXTENSION = Path(RACINE) / "live-build/config/includes.chroot_after_packages/usr/share/gnome-shell/extensions/codebyr@codebyr.io/extension.js"


@unittest.skipUnless(hasattr(os, "pidfd_open"), "pidfd Linux")
class IdentiteLinux(unittest.TestCase):
    def test_fermeture_refuse_un_pid_recycle(self):
        with tempfile.TemporaryDirectory() as temporaire:
            proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
            try:
                naissance = space._naissance_processus(proc.pid)
                self.assertTrue(naissance)
                Path(temporaire, "pid-%d" % proc.pid).write_text("travail")
                birth = Path(temporaire, "birth-%d" % proc.pid)
                birth.write_text("0")
                with patch.object(space, "_rundir", return_value=temporaire):
                    space.cmd_close({}, "travail")
                    self.assertIsNone(proc.poll(), "Le processus d'une autre naissance a été tué")
                    Path(temporaire, "pid-%d" % proc.pid).write_text("travail")
                    birth.write_text(naissance)
                    space.cmd_close({}, "travail")
                    self.assertNotEqual(proc.wait(timeout=5), 0)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                proc.wait(timeout=5)


@unittest.skipUnless(shutil.which("node"), "Node pour les décisions GJS")
class CouleurFiable(unittest.TestCase):
    def test_classe_annoncee_ne_remplace_pas_la_filiation(self):
        source = EXTENSION.read_text(encoding="utf-8")
        # Les décisions sont testées avec les mêmes fonctions que GNOME,
        # seules les lectures GLib de /proc et du registre sont simulées.
        noms = ("ppid", "naissanceCorrespond", "espaceParProcessus")
        fonctions = "\n".join(
            re.search(r"function " + n + r"\([\s\S]*?\n\}", source).group() for n in noms)
        programme = '''const assert = require('node:assert/strict');
const {TextDecoder} = require('node:util');
const fichiers = new Map();
const GLib = {file_get_contents: p => [fichiers.has(p), Buffer.from(fichiers.get(p) || '')]};
''' + fonctions + '''
const espaces = [{id:'navigation'}, {id:'banque'}];
const win = {get_pid:()=>42, get_wm_class:()=> 'codebyr-banque'};
fichiers.set('/run/codebyr/pid-42', 'navigation');
fichiers.set('/run/codebyr/birth-42', '123');
fichiers.set('/proc/42/stat', '42 (nom ) avec parenthese) ' + Array(19).fill('0').join(' ') + ' 123');
assert.equal(espaceParProcessus(win, espaces, '/run/codebyr').id, 'navigation');
fichiers.set('/run/codebyr/birth-42', '122');
assert.equal(espaceParProcessus(win, espaces, '/run/codebyr'), null);
'''
        resultat = subprocess.run(["node", "-e", programme], capture_output=True, text=True, timeout=10)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        # Aucune décision effective ne doit réintroduire la classe auto-déclarée.
        usages = re.findall(r"espacePourFenetre\(", source)
        self.assertEqual(len(usages), 1, json.dumps(usages))  # définition historique seule
