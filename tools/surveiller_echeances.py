#!/usr/bin/env python3
"""Les échéances qui arrêteraient les mises à jour de tout le parc, en silence.

Un dépôt apt dont le Release a dépassé son Valid-Until est refusé par apt
(« Release file … is expired ») : plus aucune mise à jour n'arrive, et rien
ne le signale à l'écran. De même une sous-clé de signature expirée. Ce
programme lit les vraies échéances — celles servies en ligne et celles de la
clé publique du dépôt — et échoue quand l'une approche.

Lancé chaque semaine par .github/workflows/surveiller-echeances.yml, qui ouvre
alors un ticket. À la main : python3 tools/surveiller_echeances.py
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import os
import subprocess
import sys
import urllib.request

DEPOTS = {
    "dépôt stable": "https://apt.codebyr.dev/Release",
    "canal d'essai": "https://apt.codebyr.dev/essai/Release",
}
CLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                   "codebyr-signing-key.asc")
# Re-signer un dépôt prend cinq minutes : un mois de marge suffit. Une clé
# demande de ressortir la clé maîtresse de son support hors ligne : deux mois.
MARGE_DEPOT = 30
MARGE_CLE = 60
REMEDE_DEPOT = ("re-signer sans rien publier : publish-apt.sh --resigner "
                "(--essai --resigner pour le canal d'essai), puis l'envoi habituel")
REMEDE_CLE = ("prolonger ou remplacer la sous-clé avec la clé maîtresse "
              "(docs/chaine-de-signature.md)")


def valide_jusqu_a(release):
    """L'échéance d'un fichier Release, ou None s'il n'en porte pas."""
    for ligne in release.splitlines():
        if ligne.startswith("Valid-Until:"):
            return parsedate_to_datetime(ligne.split(":", 1)[1].strip())
    return None


def echeances_de_la_cle(colonnes):
    """(empreinte courte, rôle, échéance) de la clé et de chaque sous-clé de
    signature, lues dans la sortie de « gpg --show-keys --with-colons »."""
    resultat = []
    for ligne in colonnes.splitlines():
        champs = ligne.split(":")
        if champs[0] not in ("pub", "sub") or champs[1] in ("r", "e"):
            continue
        if champs[0] == "sub" and "s" not in champs[11]:
            continue
        if not champs[6]:
            continue
        role = "clé maîtresse" if champs[0] == "pub" else "sous-clé de signature"
        resultat.append((champs[4], role,
                         datetime.fromtimestamp(int(champs[6]), tz=timezone.utc)))
    return resultat


def alertes(echeances, maintenant):
    """Les échéances trop proches : [(libellé, jours restants, remède)]."""
    retour = []
    for libelle, quand, marge, remede in echeances:
        if quand is None:
            continue
        jours = (quand - maintenant).days
        if jours < marge:
            retour.append((libelle, jours, remede))
    return retour


def lire(url):
    with urllib.request.urlopen(url, timeout=30) as reponse:
        return reponse.read().decode("utf-8", "replace")


def main():
    maintenant = datetime.now(timezone.utc)
    echeances, erreurs = [], []
    for nom, url in DEPOTS.items():
        try:
            quand = valide_jusqu_a(lire(url))
        except OSError as e:
            erreurs.append("%s injoignable (%s) : %s" % (nom, url, e))
            continue
        if quand is None:
            erreurs.append("%s : aucun Valid-Until dans %s" % (nom, url))
            continue
        echeances.append((nom, quand, MARGE_DEPOT, REMEDE_DEPOT))
    colonnes = subprocess.run(["gpg", "--show-keys", "--with-colons", CLE],
                              capture_output=True, text=True, check=True).stdout
    for empreinte, role, quand in echeances_de_la_cle(colonnes):
        echeances.append(("%s %s" % (role, empreinte), quand, MARGE_CLE, REMEDE_CLE))

    for libelle, quand, _marge, _remede in echeances:
        print("%-40s %s (dans %d jours)" % (libelle, quand.date(), (quand - maintenant).days))
    trop_proches = alertes(echeances, maintenant)
    for libelle, jours, remede in trop_proches:
        print("ÉCHÉANCE PROCHE : %s dans %d jours — %s" % (libelle, jours, remede))
    for erreur in erreurs:
        print("ERREUR : " + erreur)
    return 1 if trop_proches or erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
