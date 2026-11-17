# -*- coding: utf-8 -*-
"""Clés USB et disques externes : un document qui en vient s'ouvre sous cloche.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Une clé USB trouvée, prêtée ou reçue reste l'un des plus vieux moyens de faire
entrer un piège sur un poste. La marque de provenance ne l'attrape pas : elle
vit dans un attribut étendu, qu'une clé en FAT ou en exFAT ne sait pas garder
(voir provenance.py). Mais l'emplacement parle à sa place. GNOME monte tout
support externe sous /media/<compte>/ (ou /run/media/<compte>/) ; un document
ouvert depuis là vient, par construction, de l'extérieur du poste.

Il s'ouvre donc dans le Jetable, comme une pièce jointe : blindé, sans réseau,
détruit à la fermeture. Le Jetable reçoit une COPIE du fichier : la clé
elle-même ne lui est jamais montrée, et le service root qui crée les comptes
d'Espaces n'a rien à apprendre.

Une clé qui est la VÔTRE ne doit pas payer pour les autres. Sans issue, chaque
document de votre propre clé partirait sous cloche, sans pouvoir être modifié,
et la fonction serait coupée dans la semaine — c'est le geste « Ce fichier
m'appartient » appliqué à un support entier. La confiance se donne clé par clé,
d'un clic droit dans Fichiers, et se retire de la même façon.

LIMITES, à dire avant qu'on les découvre :
- une clé est reconnue à l'identifiant (UUID) de son système de fichiers.
  Ce n'est pas une preuve : qui connaît cet identifiant peut le donner à une
  autre clé. C'est une commodité, pas une frontière ;
- un fichier COPIÉ de la clé vers vos dossiers perd ce lien, comme une pièce
  jointe enregistrée : la copie est un geste délibéré, et Codebyr ne surveille
  pas vos copies.
"""
import os
import re
import tempfile

# Là où le bureau monte les supports externes (udisks2). Un disque interne que
# vous montez vous-même depuis Fichiers y atterrit aussi : il est traité comme
# une clé, et une seule confiance suffit à le rendre ordinaire.
RACINES = ("/media", "/run/media")

# Les clés de confiance du compte du bureau. Dans ~/.config/codebyr, que les
# applications Flatpak ne peuvent pas atteindre (voir permissions_flatpak).
# Lu au moment de l'appel : les tests le remplacent.
CONFIANCE = os.path.expanduser("~/.config/codebyr/supports-de-confiance")

MONTAGES = "/proc/self/mountinfo"
PAR_UUID = "/dev/disk/by-uuid"

# Forme d'un UUID de système de fichiers tel que udev le nomme : « 1234-ABCD »
# (FAT, exFAT), « 0f3e…-… » (ext4), « 01D9… » (NTFS). On refuse tout le reste
# plutôt que d'écrire dans un fichier de préférences une chaîne venue d'un
# support que n'importe qui a pu préparer.
FORME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{1,63}\Z")

INCONNU = "inconnu"
CONFIANT = "confiance"


# ── Décisions pures — testables sans support branché ───────────────────────

def _sous(chemin, racine):
    racine = racine.rstrip("/")
    return chemin == racine or chemin.startswith(racine + "/")


def est_amovible(chemin_reel, racines=RACINES):
    """Vrai si ce chemin, déjà résolu, se trouve SUR un support externe.

    Strictement sous la racine : « /media » lui-même, ou « /media/<compte> »,
    sont des dossiers du poste, pas le contenu d'une clé.
    """
    for racine in racines:
        if _sous(chemin_reel, racine) and chemin_reel.rstrip("/") != racine.rstrip("/"):
            return True
    return False


def _decoder(champ):
    """mountinfo écrit l'espace, la tabulation et la barre oblique inverse en
    octal (« \\040 ») : une clé nommée « MA CLE » y figure ainsi."""
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), champ)


def lire_montages(texte):
    """[(point de montage, source)] d'après le contenu de /proc/self/mountinfo.

    Une ligne : « 36 35 8:17 / /media/rom/CLE rw,… - vfat /dev/sdb1 rw,… ».
    Le nombre de champs optionnels varie ; seul le tiret seul les sépare de la
    suite, c'est donc lui qu'on cherche.
    """
    montages = []
    for ligne in (texte or "").splitlines():
        champs = ligne.split()
        try:
            tiret = champs.index("-")
        except ValueError:
            continue
        if tiret < 5 or len(champs) < tiret + 3:
            continue
        montages.append((_decoder(champs[4]), _decoder(champs[tiret + 2])))
    return montages


def montage_de(chemin_reel, montages):
    """Le montage le plus profond qui contient ce chemin, ou None.

    À profondeur égale, le DERNIER l'emporte : c'est celui qu'on voit quand
    deux montages s'empilent au même endroit.
    """
    choisi = None
    for point, source in montages:
        if _sous(chemin_reel, point) and (choisi is None or len(point) >= len(choisi[0])):
            choisi = (point, source)
    return choisi


def etat(est_externe, uuid, confiance):
    """None (pas un support externe), « confiance » ou « inconnu ».

    Une clé dont on ne sait pas lire l'identifiant reste inconnue : on ne peut
    pas se souvenir d'elle, donc pas lui faire confiance.
    """
    if not est_externe:
        return None
    if uuid and uuid in confiance:
        return CONFIANT
    return INCONNU


# ── Accès au système ────────────────────────────────────────────────────────

def montages_du_systeme():
    """Les montages vus par ce processus (liste vide si illisible)."""
    try:
        with open(MONTAGES, encoding="utf-8", errors="replace") as f:
            return lire_montages(f.read())
    except OSError:
        return []


def uuid_de(source, dossier=PAR_UUID):
    """L'identifiant du système de fichiers monté depuis ce périphérique, ou None."""
    if not source or not source.startswith("/dev/"):
        return None
    try:
        reel = os.path.realpath(source)
        for nom in sorted(os.listdir(dossier)):
            if os.path.realpath(os.path.join(dossier, nom)) == reel:
                return nom if FORME.match(nom) else None
    except OSError:
        return None
    return None


def decrire(chemin, montages=None, dossier_uuid=PAR_UUID, racines=RACINES):
    """Le support d'un fichier : None s'il est sur le poste, sinon
    {"point": point de montage, "uuid": identifiant ou None}."""
    try:
        reel = os.path.realpath(chemin)
    except (OSError, ValueError):
        return None
    if not est_amovible(reel, racines):
        return None
    if montages is None:
        montages = montages_du_systeme()
    trouve = montage_de(reel, montages)
    if trouve is None or not est_amovible(trouve[0], racines):
        # Le chemin est sous /media mais aucun montage externe ne le porte :
        # on le traite quand même comme externe, sans identifiant.
        return {"point": None, "uuid": None}
    return {"point": trouve[0], "uuid": uuid_de(trouve[1], dossier_uuid)}


def lire_confiance(fichier=None):
    """L'ensemble des identifiants de supports de confiance (vide si aucun)."""
    fichier = fichier or CONFIANCE
    try:
        with open(fichier, encoding="utf-8") as f:
            return {ligne.strip() for ligne in f if FORME.match(ligne.strip())}
    except (OSError, UnicodeError):
        return set()


def _ecrire_confiance(uuids, fichier):
    dossier = os.path.dirname(fichier)
    os.makedirs(dossier, mode=0o700, exist_ok=True)
    fd, temporaire = tempfile.mkstemp(dir=dossier, prefix=".supports-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for uuid in sorted(uuids):
                f.write(uuid + "\n")
        os.replace(temporaire, fichier)
    except BaseException:
        try:
            os.unlink(temporaire)
        except OSError:
            pass
        raise


def faire_confiance(uuid, fichier=None):
    """Ajoute une clé aux supports de confiance. Faux si l'identifiant est refusé."""
    if not uuid or not FORME.match(uuid):
        return False
    fichier = fichier or CONFIANCE
    uuids = lire_confiance(fichier)
    if uuid not in uuids:
        _ecrire_confiance(uuids | {uuid}, fichier)
    return True


def retirer_confiance(uuid, fichier=None):
    """Retire une clé des supports de confiance. Vrai si elle y figurait."""
    fichier = fichier or CONFIANCE
    uuids = lire_confiance(fichier)
    if uuid not in uuids:
        return False
    _ecrire_confiance(uuids - {uuid}, fichier)
    return True


def etat_de(chemin, fichier_confiance=None, montages=None, dossier_uuid=PAR_UUID,
            racines=RACINES):
    """None, « confiance » ou « inconnu » pour ce fichier — voir etat()."""
    support = decrire(chemin, montages, dossier_uuid, racines)
    if support is None:
        return None
    return etat(True, support["uuid"], lire_confiance(fichier_confiance))
