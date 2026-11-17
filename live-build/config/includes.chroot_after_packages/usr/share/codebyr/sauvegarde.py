# -*- coding: utf-8 -*-
"""La sauvegarde chiffrée des Espaces, vers un support que l'on range ailleurs.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Les instantanés d'un Espace (« Créer un instantané ») restent sur le même
disque, en clair : ils rattrapent une fausse manœuvre, pas un disque perdu ni
une machine volée. Cette sauvegarde-ci sort de la machine — une clé USB, un
disque externe — et doit donc pouvoir tomber en d'autres mains sans rien
livrer : chaque Espace y est une archive chiffrée par une phrase de passe.

Le chiffrement est celui de GnuPG (OpenPGP, AES-256), présent sur toute
machine Codebyr et sur tout Linux : une sauvegarde se relit sans Codebyr, par
« gpg -d », et le dit elle-même (LISEZ-MOI.txt). Aucun format maison.

Rien n'est écrit en clair en chemin : l'archive est chiffrée à la volée, et
n'apparaît sous son nom qu'une fois complète. La phrase de passe ne passe ni
par la ligne de commande (visible de tous les comptes de la machine), ni par
l'environnement : par un tube, que seul gpg lit.
"""
import os
import shutil
import subprocess
import tempfile
import time

import provenance
from traduction import _

SUFFIXE = ".tar.gz.gpg"
REGLAGES = "reglages.json.gpg"
PREFIXE_DOSSIER = "Sauvegarde-Codebyr-"
LISEZ_MOI = "LISEZ-MOI.txt"

# Une sauvegarde se casse hors ligne, à loisir : sa phrase de passe est sa
# seule défense. Douze caractères sont un plancher, pas un conseil.
PHRASE_MINIMALE = 12

# Dérivation de la clé la plus lente que GnuPG propose : chaque essai d'une
# phrase coûte à l'attaquant, une seule fois à l'utilisateur.
_DERIVATION = ["--s2k-mode", "3", "--s2k-digest-algo", "SHA512", "--s2k-count", "65011712"]


class Echec(Exception):
    """Le chiffrement ou le déchiffrement n'a pas abouti."""


def phrase_acceptable(phrase):
    """(vrai, "") ou (faux, raison lisible)."""
    if len(phrase or "") < PHRASE_MINIMALE:
        return False, _("La phrase de passe doit compter au moins {n} caractères.").format(
            n=PHRASE_MINIMALE)
    if "\n" in phrase or "\r" in phrase:
        return False, _("La phrase de passe ne peut pas contenir de saut de ligne.")
    return True, ""


def nom_du_dossier(instant=None):
    return PREFIXE_DOSSIER + time.strftime("%Y%m%d-%H%M", instant or time.localtime())


def espace_du_fichier(chemin):
    """L'Espace qu'une archive de sauvegarde désigne par son nom, ou None."""
    nom = os.path.basename(chemin)
    if not nom.endswith(SUFFIXE):
        return None
    esp_id = nom[:-len(SUFFIXE)]
    return esp_id if provenance.identifiant_valide(esp_id) else None


def commande(operation, tube, sortie, dossier_gpg):
    """La ligne de commande de gpg. La phrase de passe n'y figure jamais :
    gpg la lit sur le descripteur « tube »."""
    base = ["gpg", "--batch", "--yes", "--quiet", "--no-tty", "--homedir", dossier_gpg,
            "--pinentry-mode", "loopback", "--passphrase-fd", str(tube),
            "--no-symkey-cache"]
    if operation == "chiffrer":
        return base + ["--symmetric", "--cipher-algo", "AES256"] + _DERIVATION + [
            "--compress-algo", "none", "--output", sortie]
    return base + ["--decrypt", "--output", sortie]


def _tube_de_phrase(phrase):
    lecture, ecriture = os.pipe()
    try:
        os.write(ecriture, phrase.encode("utf-8") + b"\n")
    finally:
        os.close(ecriture)
    return lecture


def _oublier(dossier_gpg):
    """Arrête l'agent que gpg a pu lancer pour ce dossier, puis l'efface."""
    try:
        subprocess.run(["gpgconf", "--homedir", dossier_gpg, "--kill", "all"],
                       capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        pass
    shutil.rmtree(dossier_gpg, ignore_errors=True)


class Chiffrement:
    """« with Chiffrement(chemin, phrase) as flux : » — ce qu'on écrit dans
    flux arrive chiffré dans chemin. Le fichier n'apparaît sous son nom que si
    tout s'est bien passé ; sinon il ne reste rien."""

    def __init__(self, chemin, phrase):
        self.chemin = chemin
        self._partiel = chemin + ".partielle"
        self._phrase = phrase

    def __enter__(self):
        self._gpg = tempfile.mkdtemp(prefix="codebyr-gpg-")
        tube = _tube_de_phrase(self._phrase)
        try:
            self._proc = subprocess.Popen(
                commande("chiffrer", tube, self._partiel, self._gpg),
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                pass_fds=(tube,))
        except OSError as exc:
            _oublier(self._gpg)
            raise Echec(str(exc))
        finally:
            os.close(tube)
        return self._proc.stdin

    def __exit__(self, type_exc, exc, _trace):
        try:
            try:
                self._proc.stdin.close()
            except OSError:
                pass
            with self._proc.stderr:
                erreurs = self._proc.stderr.read().decode("utf-8", "replace").strip()
            code = self._proc.wait()
        finally:
            _oublier(self._gpg)
        if type_exc is None and code == 0:
            os.replace(self._partiel, self.chemin)
            return False
        try:
            os.unlink(self._partiel)
        except OSError:
            pass
        # gpg qui s'arrête en route (support plein, retiré…) casse le tube sous
        # la plume de l'appelant : c'est le même échec, dit par gpg.
        if type_exc is None or (issubclass(type_exc, OSError) and code != 0):
            raise Echec(erreurs or "gpg : code %d" % code)
        return False


def dechiffrer(source, phrase, sortie):
    """Déchiffre « source » dans le fichier « sortie ». Lève Echec si la phrase
    de passe est fausse ou si l'archive a été altérée : il ne reste alors rien."""
    dossier_gpg = tempfile.mkdtemp(prefix="codebyr-gpg-")
    tube = _tube_de_phrase(phrase)
    try:
        r = subprocess.run(commande("dechiffrer", tube, sortie, dossier_gpg) + [source],
                           stdin=subprocess.DEVNULL, capture_output=True, pass_fds=(tube,))
    except OSError as exc:
        raise Echec(str(exc))
    finally:
        os.close(tube)
        _oublier(dossier_gpg)
    if r.returncode != 0:
        try:
            os.unlink(sortie)
        except OSError:
            pass
        raise Echec(_("phrase de passe incorrecte, ou sauvegarde abîmée"))


def lisez_moi(espaces):
    """Ce que la sauvegarde dit d'elle-même, en clair, à qui la retrouvera."""
    lignes = [
        _("Sauvegarde chiffrée de Codebyr OS"),
        "",
        _("Chaque fichier « .tar.gz.gpg » est un Espace, chiffré par votre phrase de passe."),
        _("Sans elle, rien ne peut être relu — pas même par Codebyr."),
        "",
        _("Restaurer : Configuration Codebyr → Sauvegarde chiffrée → Restaurer un Espace."),
        _("Sans Codebyr, sur n'importe quel Linux :"),
        "    gpg -d personnel.tar.gz.gpg | tar xz",
        "",
        _("Espaces sauvegardés :"),
    ]
    lignes += ["  - %s" % nom for nom in espaces]
    return "\n".join(lignes) + "\n"
