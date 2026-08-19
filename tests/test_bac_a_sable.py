# -*- coding: utf-8 -*-
"""Le bac à sable des Espaces — tests de NON-RÉGRESSION de sécurité.

Ces tests gardent des propriétés qui ont déjà été violées une fois. Chacun
correspond à une ligne de l'historique des correctifs de SECURITY.md : si l'un
d'eux repasse au rouge, c'est une régression de sécurité, pas un détail.
"""
import os
import unittest

from outils import BIN, charger

espace = charger("codebyr-space")


class BusDeSession(unittest.TestCase):
    """Le bus de session de l'HÔTE ne doit jamais entrer dans un Espace.

    Historique : il y était monté en lecture seule. Or un « --ro-bind » ne
    protège pas un socket (le noyau ne refuse l'écriture sur un montage
    read-only que pour fichiers, répertoires et liens). Du code hostile dans un
    Espace pouvait donc joindre systemd --user et exécuter du code hors du bac
    à sable. C'est LE test à ne jamais laisser tomber.
    """

    def _argv(self, **kw):
        env = {"XDG_RUNTIME_DIR": "/run/user/1000"}
        return espace.wrap_bwrap("/tmp/espace-home", ["firefox"], env, **kw)

    def test_le_socket_du_bus_hote_est_absent(self):
        for options in ({}, {"renforce": True}, {"hors_ligne": True},
                        {"renforce": True, "hors_ligne": True}):
            argv = self._argv(**options)
            self.assertNotIn("/run/user/1000/bus", argv,
                             "le bus de session de l'hôte est exposé (%s)" % options)

    def test_la_variable_du_bus_hote_est_retiree(self):
        argv = self._argv()
        self.assertIn("--unsetenv", argv)
        self.assertIn("DBUS_SESSION_BUS_ADDRESS", argv)

    def test_le_bus_prive_enveloppe_la_commande(self):
        # dbus-run-session est ce qui REMPLACE le bus de l'hôte : sans lui,
        # retirer le socket priverait les applications de tout bus.
        with open(os.path.join(BIN, "codebyr-space"), encoding="utf-8") as f:
            source = f.read()
        self.assertIn("dbus-run-session", source)


class Cloisonnement(unittest.TestCase):

    def _argv(self, **kw):
        env = {"XDG_RUNTIME_DIR": "/run/user/1000"}
        return espace.wrap_bwrap("/tmp/espace-home", ["firefox"], env, **kw)

    def test_hors_ligne_coupe_vraiment_le_reseau(self):
        self.assertIn("--unshare-net", self._argv(hors_ligne=True))
        self.assertNotIn("--unshare-net", self._argv())

    def test_blindage_abandonne_les_privileges(self):
        argv = self._argv(renforce=True)
        self.assertIn("--cap-drop", argv)
        self.assertIn("ALL", argv)
        self.assertIn("--new-session", argv)

    def test_audio_desactive_retire_le_socket_pipewire(self):
        self.assertNotIn("/run/user/1000/pipewire-0", self._argv(audio=False))
        self.assertIn("/run/user/1000/pipewire-0", self._argv(audio=True))

    def test_pas_de_son_hors_ligne(self):
        # Une pièce jointe examinée sans réseau n'a pas non plus besoin du micro.
        self.assertNotIn("/run/user/1000/pipewire-0", self._argv(hors_ligne=True))

    def test_le_systeme_reste_en_lecture_seule(self):
        argv = self._argv()
        # On relit les montages sous forme de triplets (option, source, cible).
        montages = [(argv[i], argv[i + 1], argv[i + 2])
                    for i, a in enumerate(argv[:-2])
                    if a in ("--bind", "--ro-bind", "--ro-bind-try", "--dev-bind-try")]
        for option, source, _cible in montages:
            if source in ("/usr", "/etc", "/sys/devices", "/sys/dev/char"):
                self.assertTrue(option.startswith("--ro-bind"),
                                "%s doit être monté en lecture seule (%s)"
                                % (source, option))
        # Le seul montage inscriptible est le dossier personnel de l'Espace.
        inscriptibles = [m[1] for m in montages if m[0] == "--bind"]
        self.assertEqual(inscriptibles, ["/tmp/espace-home"])


if __name__ == "__main__":
    unittest.main()
