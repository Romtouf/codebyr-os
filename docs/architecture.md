# Codebyr OS — Architecture technique

> **Comment lire ce document.** Chaque composant porte un état explicite :
> **[implémenté]** = présent dans l'ISO et dans `codebyr-tools` aujourd'hui ;
> **[visé]** = décision d'architecture retenue, pas encore écrite. Un document
> d'architecture qui décrit la cible comme si elle existait déjà abîme la
> crédibilité de tout le reste — y compris des promesses qui, elles, sont
> tenues. Le code fait foi ; en cas de doute, `git grep` tranche.

## Principes directeurs

1. **La sécurité est le défaut, jamais une option.** L'utilisateur ne configure
   pas la sécurité, il la reçoit. Toute décision qui exige une expertise pour
   être sûre est une mauvaise décision.
2. **L'isolation s'adapte au matériel, pas l'inverse.** Qubes exige la machine ;
   Codebyr OS s'adapte à elle. Le même système offre le meilleur niveau
   d'isolation que le matériel permet.
3. **Le vocabulaire est humain.** Ni « VM », ni « domaine », ni « conteneur »
   dans l'interface. Des Espaces, des couleurs, des permissions.
4. **Compatible d'abord.** Une application Linux ordinaire fonctionne sans
   adaptation. Le compartimentage l'entoure, il ne la modifie pas.

## Vue en couches

```
┌─────────────────────────────────────────────────────┐
│  codebyr-shell — extension GNOME       [implémenté] │
│  Sélecteur d'Espaces · liserés colorés · Jetable    │
├─────────────────────────────────────────────────────┤
│  codebyr-space — outil en ligne de commande         │
│                                        [implémenté] │
│  Cycle de vie des Espaces · politique d'isolation   │
│  (appelé directement par l'extension, pas de démon) │
├─────────────────────────────────────────────────────┤
│  Compartimentage bubblewrap (espaces de noms noyau) │
│  dossier isolé · /tmp isolé · bus privé · Blindage  │
│                                        [implémenté] │
├─────────────────────────────────────────────────────┤
│  codebyr-core — Debian stable durcie   [implémenté] │
│  AppArmor · nftables · Wayland · MAJ auto · LUKS    │
└─────────────────────────────────────────────────────┘
```

## Composants

### codebyr-core — la base durcie

Debian stable durcie par les hooks de construction (`0200-hardening`) :

- **AppArmor** activé en mode enforce, avec les profils **fournis par Debian**
  (`apparmor-profiles`, `apparmor-profiles-extra`). *[visé]* : des profils
  écrits par Codebyr pour ses propres composants.
- **nftables** : tout est fermé en entrée par défaut.
- **Mises à jour automatiques** (`unattended-upgrades`), redémarrage proposé,
  jamais imposé.
- **Chiffrement LUKS2** du disque, proposé par l'installeur Calamares.
  *[visé]* : case pré-cochée par défaut avec la formulation grand public
  (aujourd'hui c'est le parcours Calamares standard).
- **Wayland uniquement** (isolation des entrées clavier/écran entre fenêtres —
  indispensable au modèle de sécurité).
- **`sysctl` durcis** : `kptr_restrict`, `dmesg_restrict`, `yama.ptrace_scope`,
  protections liens/fifos/regular. *[visé]* : options de ligne de commande
  noyau (`lockdown=`, `init_on_alloc=`…) — `GRUB_CMDLINE_LINUX` ne contient
  rien de tel aujourd'hui, et `lockdown` n'a de sens qu'avec Secure Boot.

### codebyr-space — l'orchestrateur d'Espaces  *[implémenté]*

**Pas de démon.** L'orchestration est un outil en ligne de commande
(`/usr/bin/codebyr-space`, Python, bibliothèque standard) que l'extension GNOME
appelle directement. C'est volontaire tant que le périmètre le permet : pas de
service privilégié à sécuriser, pas d'API D-Bus à durcir, un chemin d'exécution
lisible de bout en bout. *[visé]* : un démon `codebyr-spaced` deviendra
nécessaire le jour où il faudra un état partagé entre sessions ou des
opérations privilégiées (réseau par Espace au niveau système, par exemple).

Responsabilités :

- Créer / démarrer / arrêter / détruire les Espaces.
- Choisir le **niveau d'isolation** de chaque Espace selon la politique :

| Situation | Niveau | Pourquoi |
|---|---|---|
| Tout Espace | Bac à sable bubblewrap (dossier isolé, `/tmp` isolé, bus D-Bus privé) | Isolation réelle des fichiers, du réseau et des processus |
| Espaces sensibles (Banque, Jetable) | **Blindage** : espace de noms utilisateur, `--cap-drop ALL`, session neuve, plafonds mémoire/processus | L'isolation renforcée là où le risque est maximal |

- Le backend est **invisible** : l'utilisateur voit « Banque », jamais un détail technique.
- Réseau par Espace : le **navigateur** de Banque ne joint que la liste
  d'autorisation (proxy local, résolution locale) ; une pièce jointe ouverte en
  Jetable n'a **aucune** interface réseau ; Personnel a le réseau normal.
  Nuance importante, détaillée dans SECURITY.md : la liste blanche s'applique au
  navigateur, pas encore à tout l'Espace. Liste vide = **tout est bloqué**
  (échec fermé), jamais « tout est permis ».
- **Le bus de session de l'hôte n'entre jamais dans un Espace.** Chaque Espace
  reçoit un bus PRIVÉ (`dbus-run-session`). Exposer le socket du bus de l'hôte,
  même en lecture seule, revenait à offrir une sortie de bac à sable : un
  `--ro-bind` n'empêche pas d'écrire dans un socket (le noyau ne refuse
  l'écriture sur montage read-only que pour fichiers, répertoires et liens), et
  le bus de session donne accès à `systemd --user`, donc à l'exécution de code
  hors du bac à sable. Même raison pour laquelle Flatpak passe par
  `xdg-dbus-proxy`.
- **Son et micro** : le socket PipeWire est partagé (le son doit bien sortir
  quelque part) et vaut accès micro. Un Espace peut le refuser
  (`"audio": false` dans le registre) — c'est le cas de Banque.
- Presse-papiers inter-Espaces **explicite** (implémenté dans l'extension
  GNOME) : le presse-papiers est vidé dès que le focus change d'Espace ; pour
  transférer, l'utilisateur passe par « Transférer le presse-papiers vers… »
  avec confirmation colorée (le modèle Qubes, simplifié). Limite : compositeur
  Wayland partagé → protection temporelle, pas étanchéité de VM (voir
  SECURITY.md).
- Fichiers : chaque Espace a son propre dossier personnel, monté sur `~` dans
  son bac à sable — aucun montage partagé silencieux. *[visé]* : l'entrée
  « Envoyer vers l'Espace… » dans le gestionnaire de fichiers ; aujourd'hui le
  transfert passe par l'export/import d'instantané ou par le presse-papiers
  explicite.
- **Limite structurelle assumée** : tous les Espaces tournent sous le **même
  compte Unix**, et leurs données vivent sous
  `~/.local/share/codebyr/espaces/`. Le bac à sable les sépare, mais tout
  processus lancé HORS Espace (une application ouverte normalement) lit tout.
  *[visé]* : un UID dédié par Espace, seule façon de rendre la séparation vraie
  même après une sortie de bac à sable.

### codebyr-shell — l'interface

Extension GNOME Shell + réglages GNOME personnalisés :

- **Liseré coloré** de 3 px + pastille dans la barre de titre de chaque fenêtre,
  aux couleurs de l'Espace propriétaire (le compositeur Wayland garantit que la
  fenêtre ne peut pas mentir sur sa couleur).
- **Sélecteur d'Espaces** dans la barre supérieure : voir les Espaces actifs,
  en ouvrir, en fermer, tout comprendre d'un coup d'œil.
- **« Ouvrir en Jetable »** : depuis le menu du Sceau (lien saisi) et via
  `codebyr-jetable <lien|fichier>`. *[visé]* : l'entrée dans les menus
  contextuels du gestionnaire de fichiers (clic droit sur une pièce jointe ou
  une clé USB).
- *[visé]* : thème GTK/libadwaita « Codebyr » clair + sombre. Aujourd'hui,
  l'habillage se limite à l'accent GNOME « teal », aux fonds d'écran et aux
  réglages par défaut (`90_codebyr.gschema.override`).

### Applications

- **Flatpak d'abord** : boutique GNOME Logiciels configurée sur Flathub
  (non filtré à ce jour), portails XDG pour les permissions.
- Les applications s'installent **dans un Espace** : installation Flatpak dédiée
  (`FLATPAK_USER_DIR` propre à l'Espace) et données séparées. Une application
  installée dans Travail n'existe pas dans Banque.
- Nuance : une application Flatpak **système** (installée pour toute la machine)
  reste partagée entre Espaces et garde son propre bac à sable Flatpak ; le
  liseré n'y est qu'indicatif. `codebyr-space` le dit à l'écran au lancement.

### codebyr-installer

Calamares avec branding Codebyr : langue → disque (chiffrement LUKS proposé) →
utilisateur → installation, puis nettoyage des artefacts de la session live
(`codebyr-nettoyage-installation`) et durcissement du poste installé
(`codebyr-durcir-poste` : dossiers personnels en 0700, compte invité sans mot de
passe utilisable). Le premier démarrage lance le tour de bienvenue.

## Chaîne de construction

- **`live-build`** (outil officiel Debian) sous WSL2 ou Debian natif —
  scriptable. *[visé]* : construction en CI et build reproductible (les ISO ne
  le sont pas aujourd'hui : horodatage et miroir Debian du moment).
- Sortie : ISO hybride (live + installation) amd64.
- Le branding (Plymouth, GRUB, GDM, fonds d'écran) est posé par les **hooks**
  de construction, pas par un paquet `codebyr-branding` (celui-ci n'existe pas).
- Le userland Codebyr, lui, est un vrai paquet : `codebyr-tools`, publié dans le
  dépôt APT signé — c'est le seul chemin pour corriger les machines déjà
  installées sans regraver d'ISO.

## Menaces couvertes / non couvertes (honnêteté du modèle)

**Couvert** : un site ou une application qui, depuis un Espace, tente
d'atteindre les fichiers des autres Espaces ; pièce jointe piégée (ouverte
blindée et sans réseau) ; site d'hameçonnage imitant une banque déclarée ; vol
de l'ordinateur (chiffrement LUKS).

**Non couvert** (et on ne prétendra jamais le contraire) :

- compromission du noyau partagé — l'isolation repose sur ses espaces de noms,
  pas sur des VM matérielles ;
- code hostile déjà exécuté *dans* l'Espace Banque, qui peut contourner le
  filtre réseau du navigateur ;
- captation du micro depuis un Espace où le son est autorisé ;
- lecture des données de tous les Espaces par un processus lancé **hors**
  Espace : ils partagent le même compte Unix ;
- attaquant physique avec accès répété ; matériel compromis.

La liste complète, avec les contournements connus, est dans
[SECURITY.md](../SECURITY.md) — c'est le document qui fait foi.
