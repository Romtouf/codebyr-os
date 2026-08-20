# -*- coding: utf-8 -*-
"""Le bac à sable des Espaces — tests de NON-RÉGRESSION de sécurité.

Ces tests gardent des propriétés qui ont déjà été violées une fois. Chacun
correspond à une ligne de l'historique des correctifs de SECURITY.md : si l'un
d'eux repasse au rouge, c'est une régression de sécurité, pas un détail.
"""
import os
import unittest

from outils import BIN, LIB  # noqa: F401 — place le module partagé sur sys.path
import bac_a_sable   # noqa: E402


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
        return bac_a_sable.wrap_bwrap("/tmp/espace-home", ["firefox"], env, **kw)

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
        return bac_a_sable.wrap_bwrap("/tmp/espace-home", ["firefox"], env, **kw)

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


class SondeIsolation(unittest.TestCase):
    """« codebyr-space verifier-isolation » — le contrôle rejouable.

    La sonde s'exécute DANS un bac à sable et rapporte ce qu'elle atteint.
    Ici on ne teste pas le bac à sable (il faut Linux pour ça, c'est le rôle de
    la commande elle-même sur la machine) mais la lecture des mesures et les
    attentes : une sortie de bac à sable ne doit jamais pouvoir passer pour un
    succès.
    """

    CONFORME = {"bus_hote": False, "systemd_user": False, "bus_systeme": False,
                "x11": False, "son": True, "reseau": True, "home_isole": True}

    def test_lecture_des_mesures(self):
        mesures = bac_a_sable.analyser_sonde("bus_hote=non\nson=oui\nbruit\n")
        self.assertEqual(mesures, {"bus_hote": False, "son": True})

    def test_une_situation_conforme_passe(self):
        resultats = bac_a_sable.evaluer(self.CONFORME, self.CONFORME)
        self.assertTrue(all(ok for _l, _m, ok in resultats))

    def test_un_bus_hote_joignable_est_un_echec(self):
        fuite = dict(self.CONFORME, bus_hote=True)
        resultats = bac_a_sable.evaluer(fuite, self.CONFORME)
        echecs = [libelle for libelle, _m, ok in resultats if not ok]
        self.assertEqual(echecs, ["Bus de session de l'hôte joignable"])

    def test_une_mesure_manquante_est_un_echec(self):
        resultats = bac_a_sable.evaluer({"son": True}, self.CONFORME)
        self.assertFalse(all(ok for _l, _m, ok in resultats))

    def test_les_portes_de_sortie_sont_refusees_dans_TOUTES_les_situations(self):
        for titre, _options, attendu in bac_a_sable.SITUATIONS:
            for cle in ("bus_hote", "systemd_user", "bus_systeme", "x11"):
                self.assertFalse(attendu[cle],
                                 "« %s » tolère %s : ce sont les portes de "
                                 "sortie du bac à sable" % (titre, cle))

    def test_la_piece_jointe_est_sans_reseau_ni_micro(self):
        attendus = {t: a for t, _o, a in bac_a_sable.SITUATIONS}
        piece = attendus["Pièce jointe en Jetable"]
        self.assertFalse(piece["reseau"])
        self.assertFalse(piece["son"])

    def test_la_sonde_tente_vraiment_la_connexion(self):
        # Un socket peut exister sans être joignable — et inversement, tester la
        # seule présence du fichier donnerait un faux sentiment de sécurité.
        self.assertIn("s.connect(chemin)", bac_a_sable.SONDE)


if __name__ == "__main__":
    unittest.main()
