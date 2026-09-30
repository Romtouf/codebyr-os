# -*- coding: utf-8 -*-
"""Le Firefox d'un Espace : son profil, son filtre réseau, son bouclier.

Module partagé, chargé depuis /usr/share/codebyr (voir CODEBYR_LIB).

Sorti de codebyr-space en 1.17.0 (découpage, audit point 8), sans changement de
comportement. Tout ce qui est écrit ici l'est dans le dossier d'un Espace, que
l'Espace peut avoir piégé (liens, dossiers à la place de fichiers) : chaque
écriture passe par fichiers_surs, qui n'en suit aucun.
"""
import configparser
import json
import os
import re

import fichiers_surs

PROFIL_CODEBYR = "codebyr.default"
FORME_PROFIL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")

BOUCLIER_DIR = "/usr/share/codebyr/antiphishing"
BOUCLIER_ID = "antiphishing@codebyr.io"


def profil_par_defaut(texte):
    """Le dossier de profil que Firefox ouvrira, lu dans profiles.ini, ou None.

    Firefox est lancé avec MOZ_LEGACY_PROFILES=1 : il prend le profil marqué
    « Default=1 », ou le seul qui existe. Le fichier est dans le dossier de
    l'Espace, qui peut l'écrire : on n'en retient qu'un nom de dossier SIMPLE,
    relatif — ni « / », ni « .. » —, sans quoi un Espace ferait écrire le
    lanceur hors de chez lui.
    """
    lecteur = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        lecteur.read_string(texte)
    except configparser.Error:
        return None
    profils = [lecteur[s] for s in lecteur.sections() if s.startswith("Profile")]
    choisis = [p for p in profils if p.get("Default") == "1"] or \
              (profils if len(profils) == 1 else [])
    for p in choisis:
        chemin = p.get("Path", "")
        if p.get("IsRelative", "1") == "1" and FORME_PROFIL.fullmatch(chemin):
            return chemin
    return None


def profil_firefox(home):
    """Le dossier du profil que Firefox UTILISE dans cet Espace, prêt à écrire.

    Sans profiles.ini, on pose le nôtre, dès le premier lancement : c'est
    alors le profil de Codebyr qu'ouvrira Firefox. Avec un profiles.ini — que
    Firefox a pu écrire lui-même, s'il a été ouvert avant qu'une banque soit
    déclarée —, on s'installe dans le profil qu'il désigne. Écrire dans
    codebyr.default revenait à poser le bouclier dans un profil que personne
    n'ouvre : constaté le 29/09/2026 sur la VM, aucune alerte dans Navigation.
    Changer Firefox de profil, lui, ferait perdre marque-pages et historique.
    """
    ffbase = os.path.join(home, ".mozilla", "firefox")
    fichiers_surs.mkdir(ffbase)
    ini = os.path.join(ffbase, "profiles.ini")
    try:
        with fichiers_surs.ouvrir(ini, encoding="utf-8") as f:
            nom = profil_par_defaut(f.read()) or PROFIL_CODEBYR
    except FileNotFoundError:
        with fichiers_surs.ouvrir(ini, "w", encoding="utf-8") as f:
            f.write("[Profile0]\nName=codebyr\nIsRelative=1\nPath=%s\n"
                    "Default=1\n\n[General]\nStartWithLastProfile=1\nVersion=2\n"
                    % PROFIL_CODEBYR)
        nom = PROFIL_CODEBYR
    ffdir = os.path.join(ffbase, nom)
    fichiers_surs.mkdir(ffdir)
    return ffdir


def preparer_profil_firefox(home, port):
    """Pré-configure le profil Firefox de l'Espace pour passer par le filtre réseau."""
    ffdir = profil_firefox(home)
    prefs = [
        'user_pref("network.proxy.type", 1);',
        'user_pref("network.proxy.http", "127.0.0.1");',
        'user_pref("network.proxy.http_port", %d);' % port,
        'user_pref("network.proxy.ssl", "127.0.0.1");',
        'user_pref("network.proxy.ssl_port", %d);' % port,
        'user_pref("network.proxy.share_proxy_settings", true);',
        'user_pref("network.proxy.allow_hijacking_localhost", true);',
        'user_pref("network.trr.mode", 5);',
    ]
    ajouter_prefs(os.path.join(ffdir, "user.js"), prefs)


def domaines_proteges(espaces):
    """Domaines des banques protégées (liste blanche des Espaces à réseau restreint)."""
    out = []
    for e in espaces.values():
        r = e.get("reseau") or {}
        if r.get("mode") == "liste-blanche":
            for d in (r.get("domaines") or []):
                d = d.strip().removeprefix("*.")
                if d and d not in out:
                    out.append(d)
    return out


def ecrire_stockage_manage(home, doms):
    """Écrit le manifeste de STOCKAGE MANAGÉ Firefox : les domaines protégés sont
    fournis en DONNÉE (pas injectés dans le code), pour que l'extension reste
    statique et signable. Firefox lit ce fichier par utilisateur sous Linux."""
    msdir = os.path.join(home, ".mozilla", "managed-storage")
    fichiers_surs.mkdir(msdir)
    manifeste = {
        "name": BOUCLIER_ID,
        "description": "Domaines bancaires protégés par Codebyr.",
        "type": "storage",
        "data": {"domaines": doms},
    }
    with fichiers_surs.ouvrir(os.path.join(msdir, BOUCLIER_ID + ".json"), "w", encoding="utf-8") as f:
        json.dump(manifeste, f, ensure_ascii=False)


def ajouter_prefs(chemin, prefs):
    """Ajoute des « user_pref » à un user.js SANS le faire grossir sans fin.

    Ce fichier était réécrit en mode « ajout » à chaque lancement d'Espace : au
    bout de quelques centaines d'ouvertures, Firefox relisait la même
    préférence des centaines de fois. On dédoublonne, et on écrit une seule fois."""
    existantes = []
    try:
        with fichiers_surs.ouvrir(chemin, encoding="utf-8") as f:
            existantes = [l.rstrip("\n") for l in f if l.strip()]
    except OSError:
        pass
    def cle(ligne):
        resultat = re.match(r'\s*user_pref\("([^"\n]+)"\s*,', ligne)
        return resultat.group(1) if resultat else None
    gerees = {cle(p) for p in prefs} - {None}
    existantes = [l for l in existantes if cle(l) not in gerees]
    existantes.extend(dict.fromkeys(prefs))
    with fichiers_surs.ouvrir(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(existantes) + "\n")


def installer_bouclier(home, espaces):
    """Prépare le bouclier anti-hameçonnage pour le Firefox d'un Espace : il
    avertit si un site imite une banque protégée.

    Firefox installe l'extension signée lui-même, par la politique du paquet ;
    les domaines passent par le stockage managé, et le code de l'extension
    reste STATIQUE, donc signable par Mozilla. Il n'existe volontairement pas
    de repli « .xpi non signé » : il obligeait à poser
    xpinstall.signatures.required=false, c'est-à-dire à désactiver la
    vérification des signatures d'extensions — un affaiblissement réel du
    navigateur pour installer une protection."""
    installer_bouclier_pour(home, domaines_proteges(espaces))


def installer_bouclier_pour(home, doms):
    """Le bouclier, à partir de la seule liste des domaines protégés.

    Séparé pour pouvoir être posé DEPUIS un Espace à compte dédié : celui-ci
    ne peut pas lire le registre de l'utilisateur, on ne lui transmet que la
    liste dont il a besoin.
    """
    if not os.path.isdir(BOUCLIER_DIR):
        return
    # L'extension, c'est FIREFOX qui l'installe, par la politique que livre le
    # paquet (/usr/lib/firefox-esr/distribution/policies.json) : par son circuit
    # d'installation ordinaire, le seul qui accorde à une extension Manifest V3
    # le droit de lire les pages. Codebyr la déposait lui-même dans le profil ;
    # Firefox ne la découvrait pas toujours, et, découverte, ne lui accordait
    # pas toujours ce droit. Le bouclier restait chargé, et muet — depuis le
    # passage à Manifest V3 (1.6.0). Constaté le 29/09/2026 sur la VM.
    #
    # Reste à Codebyr ce que la politique ne sait pas faire : le profil, et la
    # liste des banques de CET utilisateur, fournie en donnée (l'extension reste
    # statique, donc signable). Écrite même vide : une banque retirée ne doit
    # pas rester protégée par une liste périmée.
    ffdir = profil_firefox(home)
    ecrire_stockage_manage(home, list(doms or []))
    retirer_copie_deposee(ffdir)
    # Firefox fait attendre l'accord de l'utilisateur avant d'activer une
    # extension déposée en silence dans le profil (3 : son réglage par défaut).
    # Codebyr posait 0 pour la sienne, et désarmait du même coup ce garde-fou
    # pour toutes les autres. On le rétablit.
    ajouter_prefs(os.path.join(ffdir, "user.js"), [
        'user_pref("extensions.autoDisableScopes", 3);',
        'user_pref("extensions.enabledScopes", 15);',
    ])
    if doms:
        print("Bouclier anti-hameçonnage : %d domaine(s) de banque protégé(s)." % len(doms))


def retirer_copie_deposee(ffdir):
    """Retire le bouclier que Codebyr déposait dans le profil (jusqu'en 1.16.3).

    Firefox refuse de réinstaller par la politique une version déjà présente :
    la copie déposée, souvent sans droit sur les pages, resterait donc à vie.
    On la retire ; Firefox la désinstalle au lancement suivant, et la politique
    la réinstalle au suivant, avec son droit (mesuré le 29/09/2026). Une copie
    que Firefox a installée LUI-MÊME par la politique n'est jamais touchée.
    """
    nom = BOUCLIER_ID + ".xpi"
    extdir = os.path.join(ffdir, "extensions")
    try:
        with fichiers_surs.ouvrir(os.path.join(ffdir, "extensions.json"), encoding="utf-8") as f:
            base = json.load(f)
        for a in base.get("addons") or []:
            if isinstance(a, dict) and a.get("id") == BOUCLIER_ID and \
                    (a.get("installTelemetryInfo") or {}).get("source") == "enterprise-policy":
                return
    except (OSError, ValueError):
        pass
    try:
        with fichiers_surs.dossier(extdir) as fd:
            os.unlink(nom, dir_fd=fd)
    except OSError:
        # Absente, ou un piège (lien, dossier) : rien à retirer, et rien qui
        # doive empêcher l'Espace de s'ouvrir.
        pass
