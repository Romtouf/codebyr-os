# Codebyr OS — Architecture technique

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
│  codebyr-shell — extension GNOME                    │
│  Sélecteur d'Espaces · liserés colorés · Jetable    │
├─────────────────────────────────────────────────────┤
│  codebyr-spaced — démon D-Bus (Python/systemd)      │
│  Cycle de vie des Espaces · politique d'isolation   │
├──────────────────────────┬──────────────────────────┤
│  Conteneurs (Incus/LXC)  │  Micro-VM (KVM/libvirt)  │
│  défaut, léger           │  Espaces sensibles       │
├──────────────────────────┴──────────────────────────┤
│  codebyr-core — Debian stable durcie                │
│  AppArmor · nftables · Wayland · MAJ auto · LUKS    │
└─────────────────────────────────────────────────────┘
```

## Composants

### codebyr-core — la base durcie

Debian stable avec un métapaquet de durcissement appliqué dès l'installation :

- **AppArmor** en mode enforce avec profils pour tous les services exposés.
- **nftables** : tout est fermé en entrée par défaut.
- **Mises à jour automatiques** (`unattended-upgrades`), redémarrage proposé,
  jamais imposé.
- **Chiffrement LUKS2** du disque proposé par défaut à l'installation
  (case pré-cochée, phrase simple : « Protéger mes données si l'ordinateur
  est perdu ou volé »).
- **Wayland uniquement** (isolation des entrées clavier/écran entre fenêtres —
  indispensable au modèle de sécurité).
- Noyau avec options de durcissement (`lockdown`, `yama`, mitigations actives).

### codebyr-spaced — l'orchestrateur d'Espaces

Démon système exposé sur D-Bus. Responsabilités :

- Créer / démarrer / arrêter / détruire les Espaces.
- Choisir le **niveau d'isolation** de chaque Espace selon la politique :

| Situation | Backend | Pourquoi |
|---|---|---|
| Machine sans VT-x ou < 6 Go RAM | Conteneur Incus + bubblewrap | Seule option viable, reste une vraie isolation de fichiers/réseau/processus |
| Machine avec VT-x et ≥ 8 Go | Conteneurs par défaut, **micro-VM KVM pour Banque et Jetable** | L'isolation forte là où le risque est maximal |
| Machine confortable (≥ 16 Go) | Micro-VM pour tous les Espaces non-Personnel | Se rapproche du modèle Qubes, sans changer l'UX |

- Le backend est **invisible** : l'utilisateur voit « Banque », jamais « VM ».
- Réseau par Espace : Banque n'accède qu'à une liste d'autorisation (résolue
  localement), Jetable passe par un réseau isolé, Personnel a le réseau normal.
- Presse-papiers inter-Espaces **explicite** (implémenté dans l'extension
  GNOME) : le presse-papiers est vidé dès que le focus change d'Espace ; pour
  transférer, l'utilisateur passe par « Transférer le presse-papiers vers… »
  avec confirmation colorée (le modèle Qubes, simplifié). Limite : compositeur
  Wayland partagé → protection temporelle, pas étanchéité de VM (voir
  SECURITY.md).
- Fichiers : chaque Espace a son volume. Le transfert passe par « Envoyer
  vers l'Espace… » dans Fichiers, jamais par un montage partagé silencieux.

### codebyr-shell — l'interface

Extension GNOME Shell + réglages GNOME personnalisés :

- **Liseré coloré** de 3 px + pastille dans la barre de titre de chaque fenêtre,
  aux couleurs de l'Espace propriétaire (le compositeur Wayland garantit que la
  fenêtre ne peut pas mentir sur sa couleur).
- **Sélecteur d'Espaces** dans la barre supérieure : voir les Espaces actifs,
  en ouvrir, en fermer, tout comprendre d'un coup d'œil.
- **« Ouvrir en Jetable »** dans les menus contextuels (liens, pièces jointes,
  clés USB) : l'action s'exécute dans un Espace éphémère détruit à la fermeture.
- Thème GTK/libadwaita « Codebyr » clair + sombre (voir la charte graphique).

### Applications

- **Flatpak d'abord** : boutique GNOME Logiciels configurée sur Flathub (filtré),
  portails XDG pour les permissions (fichiers, caméra, micro, écran) — le modèle
  de permissions que tout le monde connaît déjà sur smartphone.
- Les applications s'installent **dans un Espace** (par défaut : Personnel).
  Une application installée dans Travail n'existe pas dans Banque.

### codebyr-installer

Calamares avec branding Codebyr et un parcours raccourci : langue → disque
(chiffrement pré-coché) → utilisateur → installation. Le premier démarrage
lance un assistant de 3 écrans qui présente les Espaces avec les couleurs.

## Chaîne de construction

- **`live-build`** (outil officiel Debian) dans un conteneur Docker ou WSL2 —
  reproductible, scriptable, CI-friendly.
- Sortie : ISO hybride (live + installation) amd64.
- Le branding (Plymouth, GRUB, GDM, fonds d'écran, thème) est un paquet
  `codebyr-branding` installé dans l'image.

## Menaces couvertes / non couvertes (honnêteté du modèle)

**Couvert** : compromission d'un site ou d'une application qui tente d'accéder
aux données des autres Espaces ; pièce jointe piégée ; extension de navigateur
malveillante ; vol de l'ordinateur (chiffrement).

**Non couvert** (et on ne prétendra jamais le contraire) : compromission du
noyau partagé pour les Espaces en conteneur (d'où les micro-VM dès que
possible) ; attaquant physique avec accès répété ; matériel compromis.
