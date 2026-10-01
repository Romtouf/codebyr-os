# -*- coding: utf-8 -*-
"""Un faux serveur de notifications : ce que notify-send envoie VRAIMENT.

Lancé par tests/test_notifications.py sous « dbus-run-session », sur un bus
de session jetable. Il prend le nom org.freedesktop.Notifications, fait
afficher une notification, et écrit sur sa sortie, en JSON, ce que le
serveur a reçu : en-tête, titre, corps, urgence.

    python3 notifications_harnais.py relais <titre> <corps>
        par relais_notifications.afficher, pour l'Espace Jetable ;
    python3 notifications_harnais.py sans-tirets <titre> <corps>
        par la ligne d'avant la 1.19.1 (sans « -- »), pour prouver que
        l'attaque était réelle — un test qui ne la reproduirait pas ne
        prouverait rien.
"""
import json
import subprocess
import sys

from gi.repository import Gio, GLib

import relais_notifications

INTERFACE = """
<node>
  <interface name="org.freedesktop.Notifications">
    <method name="Notify">
      <arg type="s" direction="in"/><arg type="u" direction="in"/>
      <arg type="s" direction="in"/><arg type="s" direction="in"/>
      <arg type="s" direction="in"/><arg type="as" direction="in"/>
      <arg type="a{sv}" direction="in"/><arg type="i" direction="in"/>
      <arg type="u" direction="out"/>
    </method>
    <method name="GetCapabilities"><arg type="as" direction="out"/></method>
    <method name="GetServerInformation">
      <arg type="s" direction="out"/><arg type="s" direction="out"/>
      <arg type="s" direction="out"/><arg type="s" direction="out"/>
    </method>
  </interface>
</node>
"""


def main():
    mode, resume, corps = sys.argv[1:4]
    recu = {}
    boucle = GLib.MainLoop()

    def appel(_connexion, _emetteur, _chemin, _interface, methode, params, invocation):
        if methode == "Notify":
            app, _id, _icone, titre, texte, actions, indices, _delai = params.unpack()
            recu.update(app=app, resume=titre, corps=texte, actions=actions,
                        urgence=indices.get("urgency"))
            invocation.return_value(GLib.Variant("(u)", (1,)))
            boucle.quit()
        elif methode == "GetCapabilities":
            invocation.return_value(GLib.Variant("(as)", (["body"],)))
        else:
            invocation.return_value(GLib.Variant("(ssss)", ("faux", "codebyr", "1", "1.2")))

    def nom_obtenu(_connexion, _nom):
        if mode == "relais":
            relais_notifications.afficher("Jetable", resume, corps)
        else:
            subprocess.Popen(["notify-send", "--app-name=Espace Jetable",
                              "--icon=dialog-information", resume, corps])

    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    noeud = Gio.DBusNodeInfo.new_for_xml(INTERFACE)
    bus.register_object("/org/freedesktop/Notifications", noeud.interfaces[0], appel, None, None)
    Gio.bus_own_name_on_connection(bus, "org.freedesktop.Notifications",
                                   Gio.BusNameOwnerFlags.NONE, nom_obtenu, None)
    GLib.timeout_add_seconds(15, boucle.quit)
    boucle.run()
    print(json.dumps(recu))


if __name__ == "__main__":
    main()
