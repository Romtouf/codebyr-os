# -*- coding: utf-8 -*-
"""La langue dans laquelle Codebyr parle à l'utilisateur.

Codebyr est écrit en français : le texte écrit dans le code EST la version
française. Les autres langues sont des traductions — po/<langue>.po dans le
dépôt, compilées à la construction du paquet en
/usr/share/locale/<langue>/LC_MESSAGES/codebyr.mo.

Dans le code, tout texte destiné à l'écran passe par _() :

    _("Ouvrir dans l'Espace « {nom} »").format(nom=espace["nom"])

Le texte est traduit AVANT d'être complété : une traduction déplace les mots
autour de « {nom} », que les chaînes f"…" figeraient. Un test refuse tout
texte affiché qui n'a pas sa traduction anglaise (tests/test_traduction.py).

── QUELLE LANGUE ───────────────────────────────────────────────────────────
Les langues préférées de la session sont lues comme gettext les lit (LANGUAGE,
puis LC_ALL, LC_MESSAGES, LANG), et parcourues dans l'ordre :
  · le français, ou aucune préférence (C, POSIX) → le texte du code ;
  · une langue traduite → sa traduction ;
  · une langue qui ne l'est pas → la suivante.
Si aucune ne convient : l'anglais, la langue de référence. Qui ne lit pas le
français lit plus souvent l'anglais ; gettext seul lui aurait montré le
texte du code, en français.
"""
import gettext
import os
import struct

DOMAINE = "codebyr"
DOSSIER = "/usr/share/locale"
REFERENCE = "en"


def langues_preferees(environ=None):
    """Les langues de la session, dans l'ordre (« fr_FR.UTF-8 » → « fr_FR »)."""
    environ = os.environ if environ is None else environ
    for variable in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        valeur = environ.get(variable, "")
        if valeur:
            break
    else:
        return []
    langues = []
    for morceau in valeur.split(":"):
        code = morceau.split(".")[0].split("@")[0]
        if code:
            langues.append(code)
    return langues


def choisir(langues, disponibles):
    """La langue de traduction à charger, ou None pour le texte du code."""
    for code in langues:
        if code in ("C", "POSIX"):
            return None
        base = code.split("_")[0]
        if base == "fr":
            return None
        for candidat in (code, base):
            if candidat in disponibles:
                return candidat
    return REFERENCE if langues else None


class _Disponibles:
    """Les langues compilées, vérifiées seulement quand choisir() le demande.

    Ce module est importé aussi par des processus confinés (le service des
    comptes sous AppArmor, les bacs à sable) : en français ou sans langue, ils
    ne touchent à aucun fichier de /usr/share/locale.
    """

    def __init__(self, dossier):
        self.dossier = dossier

    def __contains__(self, langue):
        return os.path.isfile(os.path.join(self.dossier, langue, "LC_MESSAGES", DOMAINE + ".mo"))


def charger(dossier=DOSSIER, environ=None):
    """La traduction de la session ; le texte du code si elle manque."""
    langue = choisir(langues_preferees(environ), _Disponibles(dossier))
    if langue is None:
        return gettext.NullTranslations()
    try:
        with open(os.path.join(dossier, langue, "LC_MESSAGES", DOMAINE + ".mo"), "rb") as f:
            return gettext.GNUTranslations(f)
    except (OSError, ValueError, struct.error):
        # Absent ou abîmé : le texte du code, jamais un programme qui ne s'ouvre pas.
        return gettext.NullTranslations()


_traduction = charger()


def langue():
    """Le code de la langue affichée (« fr » pour le texte du code)."""
    return _traduction.info().get("language", "fr") or "fr"


def _(texte):
    """Le texte dans la langue de la session."""
    return _traduction.gettext(texte)


def nom_livre(texte):
    """Un nom livré par /etc/codebyr/espaces.json (« Banque », « Calculatrice »),
    dans la langue de la session. Ces noms ne sont pas écrits dans le code :
    l'extraction les relève dans le registre (packaging/traductions.py). Les
    noms donnés par l'utilisateur n'arrivent jamais ici (voir registre.py)."""
    return _traduction.gettext(texte)


def n_(singulier, pluriel, nombre):
    """Le texte au singulier ou au pluriel, selon la langue de la session.

    Sans traduction, c'est la règle du français : « 0 fichier », « 1 fichier »,
    « 2 fichiers » — gettext seul aurait écrit « 0 fichiers ».
    """
    if isinstance(_traduction, gettext.GNUTranslations):
        return _traduction.ngettext(singulier, pluriel, nombre)
    return singulier if nombre <= 1 else pluriel


if __name__ == "__main__":
    # Pour les scripts shell (codebyr-verifier…) :
    #   python3 -B traduction.py 'Fichier introuvable : {fichier}' fichier="$f"
    # écrit le texte traduit, complété. Ils l'appellent par leur fonction
    # « traduire », que packaging/traductions.py sait relever.
    import sys
    # Le catalogue directement : _() ne reçoit que des textes écrits dans le
    # code, que l'extraction relève (ici, ils sont dans les scripts).
    texte = _traduction.gettext(sys.argv[1]) if len(sys.argv) > 1 else ""
    valeurs = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)
    try:
        texte = texte.format(**valeurs)
    except (KeyError, IndexError, ValueError):
        pass
    sys.stdout.write(texte)
