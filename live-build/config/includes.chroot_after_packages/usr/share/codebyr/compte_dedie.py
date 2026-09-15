# -*- coding: utf-8 -*-
"""Côté bureau du chantier « un UID par Espace » : demander, tenir, exécuter.

Le service root (codebyr-uid) prépare le compte d'un Espace ; le premier
processus de l'Espace (codebyr-espace-init) exécute ce qu'on lui demande. Ce
module est ce que le LANCEUR sait de ces deux-là, et rien de plus.

── ACTIVATION ──────────────────────────────────────────────────────────────
Un Espace tourne sous son propre compte quand le registre le demande :

    {"id": "travail", ..., "compte": "dedie"}

Rien ne le demande par défaut. Tant que ce chantier n'est pas terminé, c'est un
réglage d'essai, et chaque geste qui n'est pas encore prêt est REFUSÉ avec une
explication, jamais tenté à moitié (voir GESTES_PAS_ENCORE_PRETS).

Ce qui fonctionne : ouvrir et fermer, déménagement des données et retour,
envoi de fichiers dans les deux sens par les boîtes de l'Espace, examen d'une
pièce jointe.

── ÉCHEC FERMÉ ─────────────────────────────────────────────────────────────
Un Espace qui demande un compte dédié et ne peut pas l'obtenir ne s'ouvre pas
sous le compte du bureau « en attendant ». Ce serait lui retirer, sans le dire,
la protection qu'on lui a promise — la même règle que « aucun lancement sans
bac à sable ».
"""
import json
import os
import socket

SOCKET_SERVICE = os.environ.get("CODEBYR_UID_SOCKET", "/run/codebyr-uid.sock")
TAILLE_MAX = 65536


class Indisponible(OSError):
    """Le compte dédié ne peut pas être obtenu : l'Espace ne s'ouvre pas."""


def demande(esp):
    return isinstance(esp, dict) and esp.get("compte") == "dedie"


def incompatibilites(esp, fichier=None, est_flatpak=False):
    """Ce qui ne peut pas encore se faire sous compte dédié. Liste de raisons.

    Décision pure : chaque refus dit à l'utilisateur ce qui manque, au lieu de
    l'essayer et d'échouer en silence dans le dossier d'un autre compte.
    """
    raisons = []
    if not demande(esp):
        return raisons
    if est_flatpak:
        raisons.append("les applications Flatpak ne sont pas encore prises en "
                       "charge dans un Espace à compte dédié")
    return raisons


# Gestes qui lisent ou écrivent le dossier d'un Espace à son ANCIEN
# emplacement, dans le dossier personnel du bureau. Sous compte dédié, ses
# données sont ailleurs, et le bureau ne peut pas les lire : les laisser faire
# afficherait « données effacées » ou « exporté » sur un dossier vide.
GESTES_PAS_ENCORE_PRETS = {
    "install": "y installer une application Flatpak",
    "add-app": "y ajouter une application",
}


def refus_de_geste(action, esp):
    """Le message de refus d'un geste pas encore prêt, ou None s'il peut se faire."""
    if not demande(esp) or action not in GESTES_PAS_ENCORE_PRETS:
        return None
    return ("L'Espace %s tourne sous son propre compte : Codebyr ne sait pas "
            "encore %s. Retirez « \"compte\": \"dedie\" » de son réglage pour "
            "retrouver ce geste." % (esp.get("nom", esp.get("id")),
                                     GESTES_PAS_ENCORE_PRETS[action]))


def _parler(chemin, demande_, garder=False, descripteurs=()):
    """Envoie une demande, lit la première réponse. Garde la connexion si demandé."""
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(30)
    try:
        client.connect(chemin)
        donnees = json.dumps(demande_).encode("utf-8")
        if descripteurs:
            # Joints au même message : le premier processus les reçoit avec la
            # demande, jamais séparément.
            envoye = socket.send_fds(client, [donnees], list(descripteurs))
            if envoye < len(donnees):
                client.sendall(donnees[envoye:])
        else:
            client.sendall(donnees)
        brut = b""
        while b"\n" not in brut:
            morceau = client.recv(TAILLE_MAX)
            if not morceau:
                break
            brut += morceau
        ligne, _, reste = brut.partition(b"\n")
        reponse = json.loads(ligne.decode("utf-8") or "{}")
    except (OSError, ValueError):
        client.close()
        raise
    if not garder:
        client.close()
        return reponse, None, b""
    return reponse, client, reste


class Session:
    """Un Espace ouvert sous son compte, TENU tant que cet objet vit.

    La connexion au service EST la tenue : la fermer — ou mourir — rend
    l'Espace, que le service referme quand plus personne ne le tient.
    """

    def __init__(self, esp_id, affichage, son, memoire, taches,
                 chemin=SOCKET_SERVICE, ephemere=False):
        try:
            reponse, self._client, _ = _parler(chemin, {
                "action": "ouvrir", "espace": esp_id, "affichage": affichage,
                "son": bool(son), "memoire": memoire, "taches": taches,
                "ephemere": bool(ephemere)},
                garder=True)
        except FileNotFoundError:
            raise Indisponible("le service des comptes d'Espaces n'est pas "
                               "installé sur cette machine")
        except (OSError, ValueError) as exc:
            raise Indisponible("le service des comptes d'Espaces ne répond "
                               "pas (%s)" % exc)
        if not reponse.get("ok"):
            if self._client:
                self._client.close()
            raise Indisponible("le service a refusé d'ouvrir cet Espace (%s)"
                               % reponse.get("erreur", "sans détail"))
        self._client.settimeout(None)
        self.compte = reponse["compte"]
        self.home = reponse["home"]
        try:
            self.runtime = reponse["runtime"]
        except KeyError:
            # Un service resté en 1.15.0 pendant que le lanceur est passé en
            # 1.16.0 : il répond « passerelle », que plus rien ne sait lire.
            # Le dire plutôt que de planter sur une clé manquante — l'Espace
            # ne s'ouvrira pas, et l'utilisateur saura quoi faire.
            if self._client:
                self._client.close()
            raise Indisponible(
                "le service des comptes date d'avant la mise à jour ; "
                "déconnectez-vous et reconnectez-vous")
        self.depot = reponse["depot"]
        self.ordres = reponse["ordres"]
        self.envois = reponse.get("envois")
        self.arrivees = reponse.get("arrivees")

    def rendre(self):
        if self._client is not None:
            self._client.close()
            self._client = None


def fermer(esp_id, chemin=SOCKET_SERVICE):
    """Referme un Espace d'un geste : toutes ses applications s'arrêtent."""
    try:
        reponse, _, _ = _parler(chemin, {"action": "fermer", "espace": esp_id})
    except FileNotFoundError:
        raise Indisponible("le service des comptes d'Espaces n'est pas installé")
    except (OSError, ValueError) as exc:
        raise Indisponible("le service des comptes d'Espaces ne répond pas (%s)" % exc)
    return bool(reponse.get("ok"))


def supprimer(esp_id, chemin=SOCKET_SERVICE):
    """Retire le compte d'un Espace supprimé, et ce que root lui avait préparé.

    À n'appeler qu'après avoir fait effacer ses données PAR l'Espace : root ne
    devrait trouver que des dossiers vides.
    """
    try:
        reponse, _, _ = _parler(chemin, {"action": "supprimer", "espace": esp_id})
    except FileNotFoundError:
        raise Indisponible("le service des comptes d'Espaces n'est pas installé")
    except (OSError, ValueError) as exc:
        raise Indisponible("le service des comptes d'Espaces ne répond pas (%s)" % exc)
    return bool(reponse.get("ok"))


def executer(ordres, argv, env, au_lancement=None, entree=None, sortie=None):
    """Fait exécuter argv DANS l'Espace, et attend sa fin. Renvoie le code.

    `au_lancement(pid)` est appelé dès que le processus existe : c'est là que
    le lanceur pose les marqueurs qui permettent à l'extension GNOME de colorer
    ses fenêtres, avant qu'elles n'apparaissent.

    `entree` / `sortie` : descripteurs donnés à la commande comme entrée ou
    sortie standard — le bout d'un tuyau, typiquement. L'appelant garde les
    siens et doit fermer, de son côté, le bout qu'il a transmis.

    Tant que cette fonction attend, la connexion tient l'application : si le
    lanceur meurt, le premier processus de l'Espace l'arrête.
    """
    demande_ = {"argv": argv, "env": env}
    descripteurs = []
    if entree is not None or sortie is not None:
        demande_["flux"] = []
        for nom, fd in (("entree", entree), ("sortie", sortie)):
            if fd is not None:
                demande_["flux"].append(nom)
                descripteurs.append(fd)
    try:
        reponse, client, reste = _parler(ordres, demande_, garder=True,
                                         descripteurs=descripteurs)
    except (OSError, ValueError) as exc:
        raise Indisponible("l'Espace ne répond pas (%s)" % exc)
    if not reponse.get("ok"):
        client.close()
        raise Indisponible("l'Espace a refusé la commande (%s)"
                           % reponse.get("erreur", "sans détail"))
    try:
        if au_lancement:
            au_lancement(reponse["pid"])
        client.settimeout(None)
        brut = reste
        while b"\n" not in brut:
            morceau = client.recv(TAILLE_MAX)
            if not morceau:
                # Connexion perdue sans code de sortie : le premier processus
                # de l'Espace s'est arrêté (Espace refermé d'un geste).
                return 143
            brut += morceau
        fin = json.loads(brut.partition(b"\n")[0].decode("utf-8"))
        return int(fin.get("fin", 1))
    finally:
        client.close()
