# -*- coding: utf-8 -*-
"""codebyr-durcir-poste n'écrit jamais en root dans un dossier personnel.

Le script tourne en root à chaque mise à jour du paquet, donc sans personne
devant l'écran (unattended-upgrades). Jusqu'à la 1.17.1, il créait le dossier
des modèles de chaque compte au chemin que ses réglages déclaraient, puis le
lui remettait par « chown ». Un compte qui déclarait « $HOME/../../etc » se
voyait remettre /etc à la mise à jour suivante : tout le système, depuis
n'importe quel compte, l'invité compris. Constaté le 01/10/2026 en ajoutant
l'avatar.

Désormais, tout ce qui touche un dossier personnel est fait sous l'identité de
son propriétaire. Le test réel rejoue l'attaque — par un chemin détourné et par
un lien — dans un espace de montage privé : /home en mémoire, un faux
/etc/passwd, et pour victime un dossier de root sous ce /home. Même si le
correctif régressait, il ne toucherait rien de la machine qui fait le test.
"""
import os
import shutil
import subprocess
import tempfile
import unittest

from outils import BIN, LIB

SCRIPT = os.path.join(BIN, "codebyr-durcir-poste")


def _lire():
    with open(SCRIPT, encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n")


class LesReglesDuScript(unittest.TestCase):

    def setUp(self):
        texte = _lire()
        debut = texte.index('if [ "${1:-}" = "--sous-l-identite" ]; then')
        fin = texte.index("\nfi\n", debut)
        self.utilisateur = texte[debut:fin]
        self.root = texte[:debut] + texte[fin:]

    def test_root_n_ecrit_rien_sous_un_dossier_personnel(self):
        # Le dossier lui-même (chmod 700, stat) est un chemin de /etc/passwd ;
        # ce qu'il contient appartient au compte.
        code = [l for l in self.root.splitlines() if not l.lstrip().startswith("#")]
        fautives = [l for l in code if '$home/' in l]
        self.assertEqual(fautives, [])

    def test_les_travaux_refusent_de_tourner_en_root(self):
        self.assertIn('[ "$(id -u)" != "0" ] || exit 0', self.utilisateur)

    def test_ils_sont_lances_sans_aucun_privilege(self):
        appel = [l for l in self.root.splitlines() if "/usr/bin/setpriv --reuid" in l]
        self.assertEqual(len(appel), 1)
        for option in ("--reuid=", "--regid=", "--clear-groups", "--no-new-privs", "--reset-env"):
            self.assertIn(option, appel[0])

    def test_sans_setpriv_rien_n_est_fait(self):
        # Le repli ne doit jamais être « faire quand même, en root ».
        self.assertIn("[ -x /usr/bin/setpriv ] || return 0", self.root)

    def test_le_dossier_doit_appartenir_au_compte(self):
        self.assertIn("""[ "$(stat -c '%u' "$home" 2>/dev/null)" = "$uid" ] || continue""", self.root)

    def test_seul_l_avatar_de_debian_est_remplace(self):
        self.assertIn('cmp -s "$face" /etc/skel/.face.desktop-base || exit 0', self.utilisateur)
        self.assertIn('[ -L "$face" ]', self.utilisateur)


UIDS = (60001, 60002, 60003, 60004)

PREPARATION = r"""
set -e
T="$1"
mount -t tmpfs -o mode=755 tmpfs /home
mount --bind "$T/passwd" /etc/passwd
mount --bind "$T/skel" /etc/skel
mount --bind "$T/modeles" /usr/share/codebyr/modeles
# Rien d'autre de la machine : le script lit aussi ces deux fichiers.
for f in /etc/crypttab /etc/apt/apt.conf.d/99codebyr-resilient.conf; do
	if [ -e "$f" ]; then mount --bind "$T/vide" "$f"; fi
done

# Les victimes : deux dossiers de root, à la place de /etc.
mkdir -m 755 /home/racine /home/racine2
for u in 60001 60002 60003 60004; do
	mkdir -m 700 "/home/u$u"
done
# 60001 déclare ses modèles hors de chez lui.
mkdir "/home/u60001/.config"
printf 'XDG_TEMPLATES_DIR="$HOME/../racine"\n' > /home/u60001/.config/user-dirs.dirs
# 60002 fait de son dossier de modèles un lien vers la victime.
ln -s /home/racine2 "/home/u60002/Modèles"
# 60003 : un compte ordinaire, avec l'avatar de Debian.
cp /etc/skel/.face.desktop-base /home/u60003/.face
# 60004 : modèles en anglais, et sa propre photo.
mkdir "/home/u60004/.config"
printf 'XDG_TEMPLATES_DIR="$HOME/Templates"\n' > /home/u60004/.config/user-dirs.dirs
cp "$T/photo" /home/u60004/.face
for u in 60001 60002 60003 60004; do
	chown -hR "$u:$u" "/home/u$u"
done

sh "$T/codebyr-durcir-poste" > "$T/journal" 2>&1 || true

find /home -printf '%U %p\n'
cmp -s /home/u60003/.face /etc/skel/.face && echo "AVATAR-REMPLACE u60003"
cmp -s /home/u60004/.face "$T/photo" && echo "AVATAR-GARDE u60004"
true
"""


@unittest.skipUnless(os.environ.get("CODEBYR_TEST_LINUX") == "1" and hasattr(os, "geteuid")
                     and os.geteuid() == 0 and shutil.which("unshare") and shutil.which("setpriv"),
                     "Intégration Linux en root (espace de montage privé)")
class LAttaqueRejouee(unittest.TestCase):

    def setUp(self):
        import pwd
        for uid in UIDS:
            try:
                pwd.getpwuid(uid)
            except KeyError:
                continue
            self.skipTest("uid %d déjà pris sur cette machine" % uid)
        self.crees = []
        for dossier in ("/usr/share/codebyr", "/usr/share/codebyr/modeles"):
            if not os.path.isdir(dossier):
                os.mkdir(dossier)
                self.crees.append(dossier)
        self.t = tempfile.mkdtemp(prefix="codebyr-durcir-")
        os.chmod(self.t, 0o755)

    def tearDown(self):
        shutil.rmtree(self.t, ignore_errors=True)
        for dossier in reversed(self.crees):
            os.rmdir(dossier)

    def _preparer(self):
        t = self.t
        with open("/etc/passwd", encoding="utf-8") as f:
            lignes = [l for l in f.read().splitlines() if not l.startswith("invite:")]
        lignes += ["cbyr-t%d:x:%d:%d::/home/u%d:/bin/sh" % (u, u, u, u) for u in UIDS]
        with open(os.path.join(t, "passwd"), "w", encoding="utf-8") as f:
            f.write("\n".join(lignes) + "\n")
        os.mkdir(os.path.join(t, "skel"))
        with open(os.path.join(t, "skel", ".face.desktop-base"), "wb") as f:
            f.write(b"<svg>spirale</svg>\n")
        shutil.copy(os.path.join(LIB, "avatar.svg"), os.path.join(t, "skel", ".face"))
        shutil.copytree(os.path.join(LIB, "modeles"), os.path.join(t, "modeles"))
        with open(os.path.join(t, "photo"), "wb") as f:
            f.write(b"une photo choisie\n")
        open(os.path.join(t, "vide"), "w").close()
        with open(os.path.join(t, "codebyr-durcir-poste"), "w", encoding="utf-8") as f:
            f.write(_lire())
        for racine, dossiers, fichiers in os.walk(t):
            for nom in dossiers:
                os.chmod(os.path.join(racine, nom), 0o755)
            for nom in fichiers:
                os.chmod(os.path.join(racine, nom), 0o644)

    def test_ni_chemin_detourne_ni_lien_ne_mene_hors_de_chez_soi(self):
        self._preparer()
        resultat = subprocess.run(
            ["unshare", "--mount", "--propagation", "private", "sh", "-c", PREPARATION,
             "preparation", self.t],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        with open(os.path.join(self.t, "journal"), encoding="utf-8") as f:
            journal = f.read()
        proprietaires = {}
        for ligne in resultat.stdout.splitlines():
            if ligne[:1].isdigit():
                uid, chemin = ligne.split(" ", 1)
                proprietaires[chemin] = int(uid)
        modeles = sorted(os.listdir(os.path.join(LIB, "modeles")))
        self.assertTrue(modeles)

        # Les victimes : toujours à root, et vides.
        for victime in ("/home/racine", "/home/racine2"):
            self.assertEqual(proprietaires.get(victime), 0, journal)
            dedans = [c for c in proprietaires if c.startswith(victime + "/")]
            self.assertEqual(dedans, [], journal)

        # Les comptes ordinaires sont servis, et propriétaires de ce qu'ils
        # reçoivent.
        for uid, dossier in ((60003, "/home/u60003/Modèles"), (60004, "/home/u60004/Templates")):
            self.assertEqual(proprietaires.get(dossier), uid, journal)
            for nom in modeles:
                self.assertEqual(proprietaires.get(dossier + "/" + nom), uid, journal)

        self.assertIn("AVATAR-REMPLACE u60003", resultat.stdout, journal)
        self.assertIn("AVATAR-GARDE u60004", resultat.stdout, journal)
        self.assertEqual(proprietaires.get("/home/u60003/.face"), 60003)


if __name__ == "__main__":
    unittest.main()
