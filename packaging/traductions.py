#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Les traductions de Codebyr : extraire les textes, compiler les langues.

    python3 packaging/traductions.py extraire
        Relit le code et met po/<langue>.po à jour : un texte nouveau y entre
        sans traduction, un texte disparu en sort. Les traductions existantes
        sont gardées. À lancer après avoir écrit ou modifié un texte affiché ;
        tests/test_traduction.py le rappelle à qui l'oublie.

    python3 packaging/traductions.py compiler <dossier po> <racine du paquet>
        Appelé par build-deb.sh. Pour chaque langue :
          · usr/share/locale/<langue>/LC_MESSAGES/codebyr.mo, pour les
            programmes Python (gettext) ;
          · usr/share/gnome-shell/extensions/codebyr@codebyr.io/traductions/
            <langue>.json, pour l'extension GNOME, qui choisit sa langue comme
            les programmes (voir traduction.py) — gettext ne le saurait pas.

Le texte source est le français écrit dans le code : il n'a pas de fichier
fr.po. Aucune dépendance hors de Python : la construction de l'ISO et la CI
n'ont rien de plus à installer, et le résultat ne dépend que des sources
(octet pour octet : l'ISO est reproductible).
"""
import ast
import json
import os
import re
import struct
import sys

INCLUDES = os.path.join("live-build", "config", "includes.chroot_after_packages")
EXTENSION = "usr/share/gnome-shell/extensions/codebyr@codebyr.io"

ENTETE_COMMENTAIRE = """\
# Codebyr OS — traduction : {langue}.
#
# Le texte source est le français écrit dans le code. Ce fichier est mis à
# jour par « python3 packaging/traductions.py extraire » : n'y ajoutez ni n'y
# retirez d'entrée à la main, traduisez seulement les « msgstr ».
"""
ENTETE = {
    "Project-Id-Version": "Codebyr OS",
    "MIME-Version": "1.0",
    "Content-Type": "text/plain; charset=UTF-8",
    "Content-Transfer-Encoding": "8bit",
}
# Pluriels : deux formes, la règle de l'anglais. Une langue à trois formes ou
# plus demandera d'apprendre sa règle à l'extension GNOME (voir compiler()).
PLURIELS = {"en": "nplurals=2; plural=(n != 1);"}


# ── Où sont les textes ─────────────────────────────────────────────────────

def sources(racine):
    """Les fichiers dont les textes s'affichent, chemins relatifs à l'arbre."""
    base = os.path.join(racine, INCLUDES)
    trouves = []
    for dossier, motif in (("usr/bin", None), ("usr/lib/codebyr", None),
                           ("usr/share/codebyr", ".py"),
                           ("usr/share/nautilus-python/extensions", ".py"),
                           (EXTENSION, ".js")):
        chemin = os.path.join(base, dossier)
        if not os.path.isdir(chemin):
            continue
        for nom in sorted(os.listdir(chemin)):
            complet = os.path.join(chemin, nom)
            if not os.path.isfile(complet):
                continue
            if motif and not nom.endswith(motif):
                continue
            if motif is None and _langage(complet) is None:
                continue
            trouves.append(dossier + "/" + nom)
    return trouves


def _langage(chemin):
    """« python », « shell » ou None, d'après la première ligne d'un programme."""
    with open(chemin, "rb") as f:
        premiere = f.readline()
    if not premiere.startswith(b"#!"):
        return None
    if b"python3" in premiere:
        return "python"
    if premiere.strip() in (b"#!/bin/sh", b"#!/bin/bash", b"#!/usr/bin/env bash"):
        return "shell"
    return None


class TexteNonTraduisible(ValueError):
    """Un _() qui ne reçoit pas un texte écrit tel quel."""


def textes_python(code, nom):
    """[(msgid, msgid_pluriel ou None)] des appels _() et n_() du code."""
    trouves = []
    for noeud in ast.walk(ast.parse(code, nom)):
        if not (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
                and noeud.func.id in ("_", "n_")):
            continue
        attendus = 1 if noeud.func.id == "_" else 2
        args = noeud.args[:attendus]
        if len(args) < attendus or not all(
                isinstance(a, ast.Constant) and isinstance(a.value, str) for a in args):
            raise TexteNonTraduisible(
                "%s:%d : %s() doit recevoir un texte écrit tel quel (pas de f\"…\", "
                "ni de variable) — compléter APRÈS avec .format()"
                % (nom, noeud.lineno, noeud.func.id))
        trouves.append((noeud.lineno, args[0].value, args[1].value if attendus == 2 else None))
    return [(m, p) for _l, m, p in sorted(trouves, key=lambda t: t[0])]


_CHAINE_JS = r"""'((?:[^'\\\n]|\\.)*)'"""
_APPEL_JS = re.compile(r"(?<![\w.$])(_|n_)\(\s*(?:" + _CHAINE_JS + r")(?:\s*,\s*" + _CHAINE_JS + r")?")
# Sauf leur propre définition (« function _(texte) »).
_APPEL_JS_NU = re.compile(r"(?<![\w.$])(?<!function )(?:_|n_)\(\s*(?!')")
_ECHAPPEMENTS_JS = {"n": "\n", "t": "\t", "'": "'", '"': '"', "\\": "\\"}


def _js_vers_texte(brut):
    return re.sub(r"\\(.)", lambda m: _ECHAPPEMENTS_JS.get(m.group(1), m.group(1)), brut)


def sans_commentaires_js(code):
    """Le code sans ses commentaires, remplacés par des espaces (les numéros de
    ligne restent justes). Les chaînes sont respectées : dans « 'https://…' »,
    « // » n'ouvre pas un commentaire."""
    sortie, i, n, guillemet = [], 0, len(code), None
    while i < n:
        c = code[i]
        if guillemet:
            if c == "\\":
                sortie.append(code[i:i + 2])
                i += 2
                continue
            if c == guillemet:
                guillemet = None
            sortie.append(c)
            i += 1
        elif c in "'\"`":
            guillemet = c
            sortie.append(c)
            i += 1
        elif code.startswith("//", i):
            fin = code.find("\n", i)
            fin = n if fin < 0 else fin
            sortie.append(" " * (fin - i))
            i = fin
        elif code.startswith("/*", i):
            fin = code.find("*/", i + 2)
            fin = n if fin < 0 else fin + 2
            sortie.append(re.sub(r"[^\n]", " ", code[i:fin]))
            i = fin
        else:
            sortie.append(c)
            i += 1
    return "".join(sortie)


def textes_js(code, nom):
    """Les _('…') et n_('…', '…') de l'extension : guillemets simples seulement."""
    code = sans_commentaires_js(code)
    for appel in _APPEL_JS_NU.finditer(code):
        ligne = code.count("\n", 0, appel.start()) + 1
        raise TexteNonTraduisible(
            "%s:%d : _() doit recevoir un texte entre guillemets simples, écrit "
            "tel quel — compléter APRÈS avec remplir()" % (nom, ligne))
    trouves = []
    for appel in _APPEL_JS.finditer(code):
        msgid = _js_vers_texte(appel.group(2))
        pluriel = _js_vers_texte(appel.group(3)) if appel.group(1) == "n_" else None
        if appel.group(1) == "n_" and appel.group(3) is None:
            ligne = code.count("\n", 0, appel.start()) + 1
            raise TexteNonTraduisible("%s:%d : n_() attend deux textes" % (nom, ligne))
        trouves.append((msgid, pluriel))
    return trouves


# Les scripts shell traduisent par leur fonction « traduire 'Texte {marque}' »
# (voir usr/share/codebyr/traduction.py). Entre apostrophes, le shell écrit
# une apostrophe « '\'' ».
_APPEL_SHELL = re.compile(r"(?<![\w-])traduire\s+'((?:[^']|'\\'')*)'")
_APPEL_SHELL_NU = re.compile(r"(?<![\w-])traduire\s+(?!')")


def textes_shell(code, nom):
    """Les textes des appels « traduire '…' » d'un script shell (hors commentaires)."""
    trouves = []
    for numero, ligne in enumerate(code.splitlines(), 1):
        if ligne.lstrip().startswith("#"):
            continue
        if _APPEL_SHELL_NU.search(ligne):
            raise TexteNonTraduisible(
                "%s:%d : traduire doit recevoir un texte entre apostrophes, écrit tel "
                "quel — compléter avec des marques {nom} et nom=valeur" % (nom, numero))
        trouves += [(m.replace("'\\''", "'"), None) for m in _APPEL_SHELL.findall(ligne)]
    return trouves


def extraire_textes(racine):
    """{(msgid, pluriel): [fichiers]} dans l'ordre de première apparition."""
    textes = {}
    for relatif in sources(racine):
        with open(os.path.join(racine, INCLUDES, relatif), encoding="utf-8") as f:
            code = f.read()
        if relatif.endswith(".js"):
            trouves = textes_js(code, relatif)
        elif not relatif.endswith(".py") and _langage(os.path.join(racine, INCLUDES, relatif)) == "shell":
            trouves = textes_shell(code, relatif)
        else:
            trouves = textes_python(code, relatif)
        for cle in trouves:
            fichiers = textes.setdefault(cle, [])
            if relatif not in fichiers:
                fichiers.append(relatif)
    # Les noms livrés par le registre (« Banque », « Calculatrice »…) : ils ne
    # sont pas dans le code, mais traduits à la lecture (traduction.nom_livre,
    # et la fonction nomLivre de l'extension).
    for nom in noms_du_registre(racine):
        fichiers = textes.setdefault((nom, None), [])
        if REGISTRE not in fichiers:
            fichiers.append(REGISTRE)
    source_bouclier = BOUCLIER + "/fr/messages.json"
    for entree in messages_bouclier(racine).values():
        fichiers = textes.setdefault((_vers_marques(entree["message"]), None), [])
        if source_bouclier not in fichiers:
            fichiers.append(source_bouclier)
    return textes


REGISTRE = "etc/codebyr/espaces.json"

# ── Le bouclier anti-hameçonnage (extension Firefox) ─────────────────────────
# Ses textes suivent le format des extensions : _locales/<langue>/messages.json,
# lus par Firefox lui-même. Le français (_locales/fr) est la source, écrite à la
# main ; les autres langues en sont produites depuis po/<langue>.po par
# « extraire », pour qu'un traducteur n'ait qu'un seul fichier à tenir. Ils
# entrent dans le .xpi SIGNÉ : une langue ajoutée demande une nouvelle
# signature (live-build/scripts/sign-extension.sh).
BOUCLIER = "usr/share/codebyr/antiphishing/_locales"


def _vers_marques(message):
    """« $HOTE$ » (Firefox) → « {hote} » (les traductions de Codebyr)."""
    return re.sub(r"\$([A-Za-z0-9_@]+)\$", lambda m: "{" + m.group(1).lower() + "}", message)


def _vers_firefox(texte):
    return re.sub(r"\{(\w+)\}", lambda m: "$" + m.group(1).upper() + "$", texte)


def messages_bouclier(racine):
    """{clé: entrée} du fichier de langue français du bouclier, la source."""
    chemin = os.path.join(racine, INCLUDES, BOUCLIER, "fr", "messages.json")
    if not os.path.isfile(chemin):
        return {}
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def messages_traduits(racine, entrees):
    """Le messages.json d'une langue, depuis ses entrées .po (traduites seulement :
    Firefox prend l'anglais, la langue par défaut, pour ce qui manque)."""
    traduits = {e.msgid: e.msgstr[0] for e in entrees if e.traduite and e.pluriel is None}
    sortie = {}
    for cle, entree in messages_bouclier(racine).items():
        msgid = _vers_marques(entree["message"])
        if msgid not in traduits:
            continue
        sortie[cle] = {"message": _vers_firefox(traduits[msgid])}
        if "placeholders" in entree:
            sortie[cle]["placeholders"] = entree["placeholders"]
    return json.dumps(sortie, ensure_ascii=False, indent=2) + "\n"


def noms_du_registre(racine):
    """Les noms d'Espaces et d'applications que le registre livré contient."""
    chemin = os.path.join(racine, INCLUDES, REGISTRE)
    if not os.path.isfile(chemin):
        return []
    with open(chemin, encoding="utf-8") as f:
        data = json.load(f)
    noms = []
    for e in data.get("espaces", []):
        noms.append(e.get("nom"))
        noms += [a.get("nom") for a in e.get("apps") or []]
    noms += [a.get("nom") for a in data.get("apps", [])]
    return [n for n in noms if isinstance(n, str) and n]


# ── Le format .po ──────────────────────────────────────────────────────────

class Entree:
    def __init__(self, msgid, pluriel=None):
        self.msgid = msgid
        self.pluriel = pluriel
        self.msgstr = [""] if pluriel is None else ["", ""]
        self.references = []
        self.floue = False

    @property
    def cle(self):
        return (self.msgid, self.pluriel)

    @property
    def traduite(self):
        return not self.floue and all(self.msgstr)


def _echapper(texte):
    return (texte.replace("\\", "\\\\").replace('"', '\\"')
            .replace("\n", "\\n").replace("\t", "\\t"))


def _desechapper(brut):
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), brut)


def lire_po(chemin):
    """(commentaire d'en-tête, {champ: valeur}, [Entree]) d'un fichier .po."""
    with open(chemin, encoding="utf-8") as f:
        lignes = f.read().splitlines()
    commentaire, entete, entrees = [], {}, []
    courante, champ, en_tete = None, None, True
    refs, floue = [], False

    def finir():
        nonlocal courante
        if courante is None:
            return
        if courante.msgid == "" and courante.pluriel is None:
            for ligne in courante.msgstr[0].split("\n"):
                if ": " in ligne:
                    cle, valeur = ligne.split(": ", 1)
                    entete[cle] = valeur
        else:
            entrees.append(courante)
        courante = None

    for ligne in lignes:
        if ligne.startswith("#"):
            if en_tete and courante is None and not entrees and not entete:
                commentaire.append(ligne)
                continue
            if ligne.startswith("#:"):
                refs.extend(ligne[2:].split())
            elif ligne.startswith("#,") and "fuzzy" in ligne:
                floue = True
            continue
        if not ligne.strip():
            continue
        m = re.match(r'^(msgid_plural|msgid|msgstr(?:\[(\d+)\])?)\s+"(.*)"$', ligne)
        if m:
            mot, indice, valeur = m.group(1), m.group(2), _desechapper(m.group(3))
            if mot == "msgid":
                finir()
                en_tete = False
                courante = Entree(valeur)
                courante.references, courante.floue = refs, floue
                refs, floue = [], False
                champ = ("msgid", None)
            elif mot == "msgid_plural":
                courante.pluriel = valeur
                courante.msgstr = ["", ""]
                champ = ("pluriel", None)
            else:
                i = int(indice) if indice is not None else 0
                while len(courante.msgstr) <= i:
                    courante.msgstr.append("")
                courante.msgstr[i] = valeur
                champ = ("msgstr", i)
            continue
        m = re.match(r'^"(.*)"$', ligne)
        if m and courante is not None:
            suite = _desechapper(m.group(1))
            if champ[0] == "msgid":
                courante.msgid += suite
            elif champ[0] == "pluriel":
                courante.pluriel += suite
            else:
                courante.msgstr[champ[1]] += suite
            continue
        raise ValueError("%s : ligne illisible : %r" % (chemin, ligne))
    finir()
    return "\n".join(commentaire), entete, entrees


def ecrire_po(chemin, langue, entrees):
    morceaux = [ENTETE_COMMENTAIRE.format(langue=langue), 'msgid ""', 'msgstr ""']
    champs = dict(ENTETE, Language=langue)
    if langue in PLURIELS:
        champs["Plural-Forms"] = PLURIELS[langue]
    for cle in ("Project-Id-Version", "Language", "MIME-Version", "Content-Type",
                "Content-Transfer-Encoding", "Plural-Forms"):
        if cle in champs:
            morceaux.append('"%s: %s\\n"' % (cle, champs[cle]))
    for e in entrees:
        morceaux.append("")
        for ref in e.references:
            morceaux.append("#: " + ref)
        if e.floue:
            morceaux.append("#, fuzzy")
        morceaux.append('msgid "%s"' % _echapper(e.msgid))
        if e.pluriel is None:
            morceaux.append('msgstr "%s"' % _echapper(e.msgstr[0]))
        else:
            morceaux.append('msgid_plural "%s"' % _echapper(e.pluriel))
            for i, texte in enumerate(e.msgstr):
                morceaux.append('msgstr[%d] "%s"' % (i, _echapper(texte)))
    with open(chemin, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(morceaux) + "\n")


def po_a_jour(racine, langue):
    """Les entrées que po/<langue>.po devrait contenir, traductions gardées."""
    chemin = os.path.join(racine, "po", langue + ".po")
    anciennes = {}
    if os.path.exists(chemin):
        anciennes = {e.cle: e for e in lire_po(chemin)[2]}
    entrees = []
    for (msgid, pluriel), fichiers in extraire_textes(racine).items():
        e = anciennes.get((msgid, pluriel)) or Entree(msgid, pluriel)
        e.references = list(fichiers)
        entrees.append(e)
    return entrees


def langues(racine):
    dossier = os.path.join(racine, "po")
    if not os.path.isdir(dossier):
        return []
    return sorted(n[:-3] for n in os.listdir(dossier) if n.endswith(".po"))


# ── Compilation ────────────────────────────────────────────────────────────

def mo(entete, entrees):
    """Le contenu d'un .mo (format GNU, sans table de hachage, clés triées)."""
    paires = {"": "".join("%s: %s\n" % kv for kv in entete.items())}
    for e in entrees:
        if not e.traduite:
            continue
        if e.pluriel is None:
            paires[e.msgid] = e.msgstr[0]
        else:
            paires[e.msgid + "\0" + e.pluriel] = "\0".join(e.msgstr)
    cles = sorted(paires, key=lambda c: c.encode("utf-8"))
    originaux = [c.encode("utf-8") for c in cles]
    traductions = [paires[c].encode("utf-8") for c in cles]
    n = len(cles)
    debut_textes = 28 + 16 * n
    table_o, table_t, donnees = [], [], b""
    for texte in originaux:
        table_o.append((len(texte), debut_textes + len(donnees)))
        donnees += texte + b"\0"
    for texte in traductions:
        table_t.append((len(texte), debut_textes + len(donnees)))
        donnees += texte + b"\0"
    sortie = struct.pack("<7I", 0x950412de, 0, n, 28, 28 + 8 * n, 0, 28 + 16 * n)
    for longueur, position in table_o + table_t:
        sortie += struct.pack("<2I", longueur, position)
    return sortie + donnees


def json_extension(entete, entrees):
    """La traduction de l'extension GNOME : {textes, pluriels, regle}."""
    regle = entete.get("Plural-Forms", "")
    if "plural=(n != 1)" not in regle and any(e.pluriel for e in entrees):
        raise ValueError("Règle de pluriel inconnue de l'extension : %r" % regle)
    textes = {e.msgid: e.msgstr[0] for e in entrees if e.traduite and e.pluriel is None}
    pluriels = {e.msgid: e.msgstr for e in entrees if e.traduite and e.pluriel is not None}
    return json.dumps({"textes": textes, "pluriels": pluriels},
                      ensure_ascii=False, sort_keys=True, indent=0) + "\n"


def compiler(dossier_po, racine_paquet):
    for nom in sorted(os.listdir(dossier_po)):
        if not nom.endswith(".po"):
            continue
        langue = nom[:-3]
        _c, entete, entrees = lire_po(os.path.join(dossier_po, nom))
        cible = os.path.join(racine_paquet, "usr/share/locale", langue, "LC_MESSAGES")
        os.makedirs(cible, exist_ok=True)
        with open(os.path.join(cible, "codebyr.mo"), "wb") as f:
            f.write(mo(entete, entrees))
        cible = os.path.join(racine_paquet, EXTENSION, "traductions")
        os.makedirs(cible, exist_ok=True)
        with open(os.path.join(cible, langue + ".json"), "w", encoding="utf-8", newline="\n") as f:
            f.write(json_extension(entete, entrees))
        traduites = sum(1 for e in entrees if e.traduite)
        print("   %s : %d textes sur %d traduits" % (langue, traduites, len(entrees)))


def main(argv):
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if argv[:1] == ["extraire"]:
        for langue in langues(racine):
            entrees = po_a_jour(racine, langue)
            ecrire_po(os.path.join(racine, "po", langue + ".po"), langue, entrees)
            manquantes = sum(1 for e in entrees if not e.traduite)
            print("po/%s.po : %d textes, %d à traduire" % (langue, len(entrees), manquantes))
            if messages_bouclier(racine):
                dossier = os.path.join(racine, INCLUDES, BOUCLIER, langue)
                os.makedirs(dossier, exist_ok=True)
                chemin = os.path.join(dossier, "messages.json")
                ancien = open(chemin, encoding="utf-8").read() if os.path.exists(chemin) else None
                nouveau = messages_traduits(racine, entrees)
                if nouveau != ancien:
                    with open(chemin, "w", encoding="utf-8", newline="\n") as f:
                        f.write(nouveau)
                    print("%s/%s/messages.json mis à jour : le bouclier est à "
                          "refaire signer (live-build/scripts/sign-extension.sh)"
                          % (BOUCLIER, langue))
        return 0
    if argv[:1] == ["compiler"] and len(argv) == 3:
        compiler(argv[1], argv[2])
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
