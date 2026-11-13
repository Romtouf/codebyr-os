# -*- coding: utf-8 -*-
"""Les banques proposées à la configuration de l'Espace Banque.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Choisir sa banque dans une liste évite de taper son adresse — et de s'y
tromper. Mais un domaine faux dans la liste blanche est pire que pas de liste :
la banque ne s'ouvre plus, ou l'utilisateur apprend à tout autoriser. La liste
ne contient donc que des domaines lus sur le site officiel de chaque banque
(docs/decisions.md, « Liste de banques »), et chaque domaine y couvre ses
sous-domaines (codebyr-config ajoute aussi « *.domaine »). Une banque absente
se saisit à la main, et la page de blocage nomme tout site qui manquerait.

Chaque domaine passe par la même analyse que la saisie à la main : une entrée
abîmée de banques.json est écartée, jamais ajoutée telle quelle.
"""
import json
import os

import registre

FICHIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "banques.json")


def charger(chemin=FICHIER):
    """[(nom, [domaines])], triée par nom ; vide si le fichier manque."""
    try:
        with open(chemin, encoding="utf-8") as f:
            donnees = json.load(f)
    except (OSError, ValueError):
        return []
    banques = []
    for banque in donnees.get("banques", []) if isinstance(donnees, dict) else []:
        if not isinstance(banque, dict) or not isinstance(banque.get("nom"), str):
            continue
        domaines = [registre.normaliser_domaine(d) for d in banque.get("domaines", [])
                    if isinstance(d, str)]
        domaines = [d for d in domaines if d]
        if domaines:
            banques.append((banque["nom"].strip(), domaines))
    return sorted(banques, key=lambda b: b[0].casefold())
