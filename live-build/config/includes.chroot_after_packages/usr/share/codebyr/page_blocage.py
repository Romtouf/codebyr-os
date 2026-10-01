# -*- coding: utf-8 -*-
"""Les textes de la page que le filtre réseau montre à la place d'un site refusé.

Le filtre (codebyr-net-proxy) ne lit aucun fichier hors de Python : son profil
AppArmor l'interdit, et c'est voulu — il est exposé à tout ce qu'un site lui
envoie. codebyr-space lui donne donc ces textes déjà traduits, au lancement,
dans la variable CODEBYR_PAGE_BLOCAGE. Le filtre en garde une copie
française, qui sert si rien ne lui parvient : les deux doivent rester
identiques, et un test le vérifie (tests/test_traduction.py).

« %s » y est le site refusé, que le filtre échappe avant de l'insérer. Le
reste peut contenir du balisage (<code>, <b>, <br>) : ces textes viennent du
paquet, jamais d'un site.
"""
import json

import traduction
from traduction import _

VARIABLE = "CODEBYR_PAGE_BLOCAGE"


def textes():
    return {
        "langue": traduction.langue(),
        "titre_onglet": _("Site bloqué — Codebyr"),
        "bandeau": _("Espace à réseau restreint"),
        "interne_titre": _("Ce site mène à votre réseau local"),
        "interne_detail": _("<code>%s</code> est autorisé, mais son adresse désigne cette "
                            "machine ou un appareil de votre réseau — box, imprimante, "
                            "NAS — et non un site Internet.<br><br>"
                            "Un Espace à réseau restreint n'y a jamais accès : c'est ce "
                            "qui empêche un nom de domaine détourné de servir de passage "
                            "vers vos autres appareils."),
        "banque_titre": _("Ce site n'est pas celui de votre banque"),
        "banque_detail": _("L'Espace Banque ne peut joindre que les adresses que vous "
                           "avez déclarées. <code>%s</code> n'en fait pas partie.<br><br>"
                           "Si votre banque a réellement besoin de ce site pour "
                           "fonctionner, ouvrez <b>Configuration Codebyr</b> : il vous "
                           "sera proposé dans la liste des sites bloqués."),
        "vide_titre": _("Aucun site n'est encore autorisé ici"),
        "vide_detail": _("Ouvrez <b>Configuration Codebyr</b> et ajoutez l'adresse de "
                         "votre banque. Elle sera alors la seule joignable dans cet "
                         "Espace — c'est ce qui rend un lien d'hameçonnage inoffensif "
                         "quand il s'ouvre ici par mégarde."),
    }


def environnement(environ):
    """L'environnement du filtre : celui du lanceur, plus ses textes."""
    return dict(environ, **{VARIABLE: json.dumps(textes(), ensure_ascii=False)})
