# -*- coding: utf-8 -*-
"""Les notifications d'un Espace arrivent à l'écran — sans lui donner le bus.

── LE PROBLÈME ─────────────────────────────────────────────────────────────
Depuis la 1.1.0, chaque Espace a un bus de session PRIVÉ (dbus-run-session).
C'est ce qui a fermé la faille la plus grave du projet : le bus de l'hôte y
était monté, et avec lui systemd --user, dont StartTransientUnit exécute
n'importe quoi HORS du bac à sable.

Contrepartie : plus personne, dans un Espace, ne fournit
« org.freedesktop.Notifications ». Une application qui prévient d'un
téléchargement terminé ou d'une erreur parle dans le vide.

── POURQUOI PAS xdg-dbus-proxy ─────────────────────────────────────────────
La réponse habituelle — « faire comme Flatpak » — demande de remplacer le bus
de l'Espace par un proxy filtrant. Or une application ne parle qu'à UN bus :
donner le proxy revient à retirer le bus privé. Les applications mono-instance
(Fichiers, l'Éditeur de texte) retrouveraient alors celle du bureau et y
ouvriraient leur fenêtre — l'isolation ET le liseré tomberaient. On échangerait
une notification contre une perte de cloisonnement.

── CE QUE FAIT CE RELAIS ───────────────────────────────────────────────────
Le bus privé n'est pas touché. Un petit service prend le nom
« org.freedesktop.Notifications » DANS l'Espace, sur ce bus privé, et transmet
le texte à l'hôte par une socket Unix dédiée à cet Espace. L'hôte affiche.

Ce que ce passage garantit, et qu'un proxy ne garantirait pas :

  · l'EN-TÊTE est imposé par l'hôte — une notification venue de Jetable
    s'affiche « Espace Jetable », jamais « Banque » ni « Codebyr ». Sans cela,
    une page piégée pourrait afficher une fausse alerte de sécurité crédible ;
  · le TEXTE est nettoyé (ni balises, ni caractères de contrôle) et borné ;
  · le DÉBIT est limité : on ne noie pas l'écran de l'utilisateur ;
  · les BOUTONS D'ACTION sont refusés : ils rappelleraient l'application, donc
    ouvriraient un canal de retour vers l'Espace.

Rien d'autre ne traverse : la socket ne transporte que deux chaînes de texte.
"""
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time

SOCKET_ESPACE = "/run/codebyr-notif"

# Bornes du texte affiché. Un titre plus long est coupé : une notification
# n'est pas un canal de transfert, et un pavé chasse le reste de l'écran.
MAX_RESUME = 120
MAX_CORPS = 300

# Débit : au-delà, on laisse tomber en silence (et on le note dans le journal).
PAR_FENETRE = 5
FENETRE_S = 15

_CONTROLE = re.compile(r"[\x00-\x1f\x7f]")


def nettoyer(texte, limite):
    """Texte affichable : sans balises, sans caractères de contrôle, borné.

    Les chevrons partent entièrement : le serveur de notifications de GNOME
    interprète un sous-ensemble de HTML, et une application hostile s'en
    servirait pour maquiller son message (gras, lien, faux bouton).
    """
    texte = _CONTROLE.sub(" ", str(texte or ""))
    texte = texte.replace("<", "").replace(">", "")
    texte = " ".join(texte.split())
    if len(texte) > limite:
        texte = texte[:limite - 1].rstrip() + "…"
    return texte


class Limiteur:
    """Compte les notifications sur une fenêtre glissante."""

    def __init__(self, maximum=PAR_FENETRE, fenetre=FENETRE_S, horloge=time.monotonic):
        self._max = maximum
        self._fenetre = fenetre
        self._horloge = horloge
        self._vues = []

    def autorise(self):
        maintenant = self._horloge()
        self._vues = [t for t in self._vues if maintenant - t < self._fenetre]
        if len(self._vues) >= self._max:
            return False
        self._vues.append(maintenant)
        return True


def afficher(nom_espace, resume, corps):
    """Affiche sur le bureau de l'hôte, sous l'identité de l'ESPACE."""
    subprocess.Popen(
        ["notify-send", "--app-name=Espace %s" % nom_espace,
         "--icon=dialog-information", resume, corps],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def traiter(brut, nom_espace, montrer=afficher, limiteur=None):
    """Une demande reçue : nettoyée, bornée, affichée. Renvoie True si affichée.

    Fonction pure d'accès disque et de réseau (l'affichage est injectable) :
    c'est elle qui décide ce qu'un Espace peut faire apparaître à l'écran.
    """
    try:
        demande = json.loads(brut.decode("utf-8", "replace"))
        if not isinstance(demande, dict):
            return False
    except ValueError:
        return False
    resume = nettoyer(demande.get("resume"), MAX_RESUME)
    corps = nettoyer(demande.get("corps"), MAX_CORPS)
    if not resume and not corps:
        return False
    if limiteur is not None and not limiteur.autorise():
        return False
    montrer(nom_espace, resume or corps, corps if resume else "")
    return True


def servir(srv, nom_espace, montrer=afficher, journal=None):
    """Boucle de l'hôte : lit une demande par connexion, l'affiche, répond."""
    limiteur = Limiteur()
    refuses = [0]

    def une(client):
        with client:
            try:
                client.settimeout(5)
                brut = client.recv(8192)
                if traiter(brut, nom_espace, montrer, limiteur):
                    client.sendall(b"ok\n")
                else:
                    refuses[0] += 1
                    if journal and refuses[0] in (1, 10, 100):
                        journal("Espace %s : %d notification(s) écartée(s)"
                                % (nom_espace, refuses[0]))
                    client.sendall(b"non\n")
            except OSError:
                pass

    while True:
        try:
            client, _ = srv.accept()
        except OSError:
            return
        threading.Thread(target=une, args=(client,), daemon=True).start()


# ── Côté Espace : le service qui prend le nom sur le bus PRIVÉ ──────────────

INTROSPECTION = """
<node>
  <interface name='org.freedesktop.Notifications'>
    <method name='Notify'>
      <arg type='s' name='app_name' direction='in'/>
      <arg type='u' name='replaces_id' direction='in'/>
      <arg type='s' name='app_icon' direction='in'/>
      <arg type='s' name='summary' direction='in'/>
      <arg type='s' name='body' direction='in'/>
      <arg type='as' name='actions' direction='in'/>
      <arg type='a{sv}' name='hints' direction='in'/>
      <arg type='i' name='expire_timeout' direction='in'/>
      <arg type='u' name='id' direction='out'/>
    </method>
    <method name='CloseNotification'>
      <arg type='u' name='id' direction='in'/>
    </method>
    <method name='GetCapabilities'>
      <arg type='as' name='capabilities' direction='out'/>
    </method>
    <method name='GetServerInformation'>
      <arg type='s' name='name' direction='out'/>
      <arg type='s' name='vendor' direction='out'/>
      <arg type='s' name='version' direction='out'/>
      <arg type='s' name='spec_version' direction='out'/>
    </method>
  </interface>
</node>
"""


def envoyer(resume, corps, chemin=SOCKET_ESPACE):
    """Transmet à l'hôte. Échec silencieux : une notification n'est pas critique."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect(chemin)
            s.sendall(json.dumps({"resume": resume, "corps": corps}).encode("utf-8"))
            s.recv(16)
        return True
    except OSError:
        return False


def service():
    """Prend « org.freedesktop.Notifications » sur le bus privé de l'Espace.

    Démarré à la demande par le bus lui-même (fichier .service), à la première
    notification : rien ne tourne tant qu'aucune application n'en envoie.
    """
    # Hors d'un Espace, ce service n'a rien à faire : sur le bureau, c'est GNOME
    # Shell qui fournit ce nom. Refuser ici évite qu'une activation accidentelle
    # ne le remplace par un relais qui ne mène nulle part.
    if not os.environ.get("CODEBYR_ESPACE"):
        sys.stderr.write("relais_notifications : hors d'un Espace, rien à faire.\n")
        return 1
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib

    compteur = [0]

    def appel(_co, _exp, _obj, _iface, methode, params, invocation):
        if methode == "Notify":
            # app_name, app_icon, actions et hints sont IGNORÉS : l'en-tête est
            # imposé par l'hôte, et une action rouvrirait un canal de retour.
            _, _, _, resume, corps, _, _, _ = params.unpack()
            envoyer(resume, corps)
            compteur[0] += 1
            invocation.return_value(GLib.Variant("(u)", (compteur[0],)))
        elif methode == "CloseNotification":
            invocation.return_value(None)
        elif methode == "GetCapabilities":
            invocation.return_value(GLib.Variant("(as)", (["body"],)))
        elif methode == "GetServerInformation":
            invocation.return_value(
                GLib.Variant("(ssss)", ("Codebyr", "Codebyr OS", "1", "1.2")))
        else:
            invocation.return_error_literal(
                Gio.DBusError.quark(), Gio.DBusError.UNKNOWN_METHOD, methode)

    noeud = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION)
    boucle = GLib.MainLoop()

    def pris(connexion, _nom):
        connexion.register_object("/org/freedesktop/Notifications",
                                  noeud.interfaces[0], appel)

    Gio.bus_own_name(Gio.BusType.SESSION, "org.freedesktop.Notifications",
                     Gio.BusNameOwnerFlags.NONE, pris, None,
                     lambda *a: boucle.quit())
    boucle.run()
    return 0


if __name__ == "__main__":
    sys.exit(service() if "--service" in sys.argv else 2)
