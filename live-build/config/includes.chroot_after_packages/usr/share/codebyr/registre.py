# -*- coding: utf-8 -*-
"""Registre des Espaces — lecture, fusion et écriture.

Module partagé par les outils Python de Codebyr (`codebyr-space`,
`codebyr-config`, `codebyr-assistant`). Ils l'importent depuis
/usr/share/codebyr ; la variable d'environnement CODEBYR_LIB permet de pointer
ailleurs (tests, développement).

── LE PROBLÈME QU'IL RÉSOUT ────────────────────────────────────────────────
Il y a deux fichiers :

  /etc/codebyr/espaces.json          les valeurs par défaut, livrées par le paquet
  ~/.config/codebyr/espaces.json     ce que l'utilisateur a personnalisé

Jusqu'ici, le second REMPLAÇAIT le premier : dès qu'un utilisateur avait touché
un réglage, sa copie devenait un instantané figé, et plus aucune valeur par
défaut ne pouvait plus jamais l'atteindre. Un durcissement livré par « apt » —
par exemple couper le micro dans l'Espace Banque — n'arrivait qu'aux personnes
n'ayant jamais rien configuré. Autrement dit : plus l'utilisateur s'impliquait,
moins il était protégé.

Désormais les deux fichiers se SUPERPOSENT, Espace par Espace et clé par clé :
la valeur de l'utilisateur gagne quand elle existe, la valeur par défaut
s'applique sinon. Les nouveaux réglages livrés par une mise à jour atteignent
donc tout le monde, sans écraser les choix de personne.

── CONSÉQUENCE POUR L'ÉCRITURE ─────────────────────────────────────────────
Le fichier utilisateur ne doit contenir QUE des différences. Écrire dedans la
vue fusionnée le retransformerait en instantané figé, et le problème
reviendrait par la porte de derrière. Les fonctions d'écriture ci-dessous
travaillent donc toujours sur la « couche » utilisateur seule.
"""
import json
import os

SYSTEME = "/etc/codebyr/espaces.json"
UTILISATEUR = os.path.expanduser("~/.config/codebyr/espaces.json")

def _vide():
    """Un registre vide, NEUF à chaque appel.

    Surtout pas une constante partagée : `dict(CONSTANTE)` est une copie de
    surface, et la liste « espaces » resterait commune à toutes les lectures.
    Ajouter un Espace alors que le fichier n'existe pas encore polluait
    silencieusement toutes les lectures suivantes du même processus."""
    return {"espaces": [], "apps": []}


def _lire(chemin):
    """Lit un registre. Un fichier absent ou illisible vaut « rien »."""
    try:
        with open(chemin, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _vide()
        data.setdefault("espaces", [])
        data.setdefault("apps", [])
        return data
    except (OSError, ValueError):
        return _vide()


def systeme():
    """Les valeurs par défaut livrées par le paquet."""
    return _lire(SYSTEME)


def couche():
    """La couche utilisateur seule (les personnalisations, sans les défauts)."""
    return _lire(UTILISATEUR)


def charger():
    """Vue fusionnée : défauts du système, recouverts par les choix de l'utilisateur.

    Chaque Espace fusionné porte en plus une clé « _systeme » (booléen) : elle
    dit s'il provient du paquet — donc s'il est supprimable ou non. Les clés
    commençant par « _ » sont calculées, jamais écrites sur disque.
    """
    sys_ = systeme()
    usr = couche()
    perso = {e.get("id"): e for e in usr.get("espaces", []) if isinstance(e, dict) and e.get("id")}

    fusion = []
    vus = set()
    for base in sys_.get("espaces", []):
        if not isinstance(base, dict) or not base.get("id"):
            continue
        eid = base["id"]
        espace = dict(base)
        espace.update(perso.get(eid, {}))   # l'utilisateur gagne, clé par clé
        espace["_systeme"] = True
        fusion.append(espace)
        vus.add(eid)

    for e in usr.get("espaces", []):        # Espaces créés par l'utilisateur
        if not isinstance(e, dict) or not e.get("id") or e["id"] in vus:
            continue
        espace = dict(e)
        espace["_systeme"] = False
        fusion.append(espace)
        vus.add(e["id"])

    # Liste d'applications commune : celle de l'utilisateur si elle existe.
    apps = usr.get("apps") or sys_.get("apps") or []
    return {"espaces": fusion, "apps": apps}


def espaces():
    """Vue fusionnée indexée par identifiant."""
    return {e["id"]: e for e in charger()["espaces"]}


def est_systeme(esp_id):
    """Cet Espace vient-il du paquet ? (donc : non supprimable)"""
    return any(e.get("id") == esp_id for e in systeme().get("espaces", []))


# ── Écriture : toujours sur la couche utilisateur ───────────────────────────

def ecrire_couche(data):
    """Écrit la couche utilisateur, en retirant les clés calculées."""
    propre = {
        "_commentaire": "Personnalisations Codebyr. Les valeurs absentes d'ici "
                        "viennent de /etc/codebyr/espaces.json et suivent les "
                        "mises à jour du système.",
        "espaces": [{k: v for k, v in e.items() if not k.startswith("_")}
                    for e in data.get("espaces", []) if isinstance(e, dict)],
    }
    if data.get("apps"):
        propre["apps"] = data["apps"]
    os.makedirs(os.path.dirname(UTILISATEUR), exist_ok=True)
    with open(UTILISATEUR, "w", encoding="utf-8") as f:
        json.dump(propre, f, ensure_ascii=False, indent=2)


def modifier_espace(esp_id, changements):
    """Enregistre une personnalisation pour un Espace (et elle seule).

    Les clés non citées restent gouvernées par les valeurs par défaut du
    système : c'est ce qui permet à une future mise à jour de les faire évoluer.
    """
    data = couche()
    for e in data["espaces"]:
        if isinstance(e, dict) and e.get("id") == esp_id:
            e.update(changements)
            break
    else:
        entree = {"id": esp_id}
        entree.update(changements)
        data["espaces"].append(entree)
    ecrire_couche(data)


def ajouter_espace(entree):
    """Ajoute un Espace créé par l'utilisateur."""
    data = couche()
    data["espaces"].append(entree)
    ecrire_couche(data)


def supprimer_espace(esp_id):
    """Retire un Espace de la couche utilisateur. Renvoie True s'il existait."""
    data = couche()
    avant = len(data["espaces"])
    data["espaces"] = [e for e in data["espaces"]
                       if not (isinstance(e, dict) and e.get("id") == esp_id)]
    if len(data["espaces"]) == avant:
        return False
    ecrire_couche(data)
    return True


def ecrire_apps_communes(apps):
    """Remplace la liste d'applications commune à tous les Espaces."""
    data = couche()
    data["apps"] = apps
    ecrire_couche(data)


def identifiant_libre(base):
    """Un identifiant d'Espace non utilisé, dérivé de « base »."""
    pris = set(espaces())
    esp_id = base
    n = 2
    while esp_id in pris:
        esp_id = "%s-%d" % (base, n)
        n += 1
    return esp_id
