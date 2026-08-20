# Chantiers — Codebyr OS

État au **20 août 2026**, pendant la préparation de la 1.2.0.
Ce qui a été fermé est listé en fin de document — un suivi qui ne reflète pas
l'état réel ne sert à rien.

Ce document liste **tout** ce qui est identifié : les chantiers de fond, les
correctifs de confort, la dette technique, et ce qui est volontairement écarté.
Il vaut mieux une liste longue et honnête qu'une liste courte et rassurante —
et un chantier écrit ici n'est pas un engagement, c'est une décision à prendre.

## Comment lire

| Marque | Sens |
|---|---|
| 🔴 | Sécurité — touche au modèle de menaces |
| 🟠 | Produit — ce que l'utilisateur voit et ressent |
| 🔵 | Qualité, tests, chaîne de construction |
| ⚪ | Dette technique, limites connues |

**Effort** : `S` quelques heures · `M` quelques jours · `L` quelques semaines ·
`XL` un ou plusieurs mois.

---

## 1. Maintenant — terminer la 1.1.0

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| 🔵 | **Signer et publier l'ISO 1.1.0** — `sign-release.sh`, puis `gh release create v1.1.0` avec l'ISO, `SHA256SUMS` et `SHA256SUMS.asc` | La dernière release publique est la 1.0.7. Une installation neuve repart aujourd'hui d'une image qui contient la faille corrigée ce matin (elle la recevrait ensuite par apt, mais elle démarre vulnérable) | S |

---

## 2. Sécurité — architecture

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| 🔴 | **Un UID Unix par Espace** | Le chantier structurant. Aujourd'hui tous les Espaces tournent sous votre compte et leurs données vivent dans `~/.local/share/codebyr/espaces/`. Le bac à sable les sépare, mais toute évasion — ou toute application lancée hors Espace — lit l'ensemble. C'est la seule façon de rendre la séparation vraie au niveau du système. **Point dur** : faire accepter par le compositeur Wayland des applications tournant sous d'autres UID (piste : portails XDG + `systemd-run --uid`). À dimensionner avant de s'y engager | XL |
| 🔴 | **`xdg-dbus-proxy` pour les portails et les notifications** | Depuis la 1.1.0, un Espace n'a plus qu'un bus privé vide : plus de notifications, plus de portails XDG. Un proxy filtrant les rendrait **sans** rouvrir l'accès au bus de session. **Point dur identifié** (voir l'encadré ci-dessous) : le proxy remplace le bus privé, or c'est ce bus privé qui empêche aujourd'hui une application mono-instance de rejoindre celle de l'hôte. À traiter sur machine, pas à l'aveugle | M |
| 🔴 | **Filtre réseau au niveau de l'Espace, pas du navigateur** | La liste blanche de Banque s'applique au profil Firefox : un binaire hostile lancé dans l'Espace la contourne. Un vrai cloisonnement demande un namespace réseau par Espace (veth + nftables, ou slirp), appliqué à **tous** les processus | L |
| 🔴 | **Filtre seccomp dans le bac à sable** (`bwrap --seccomp`) | Aucun filtre d'appels système aujourd'hui : toute la surface du noyau est exposée depuis un Espace. C'est précisément la surface par laquelle une évasion passerait | M |
| 🔴 | **Presse-papiers** | La protection est **temporelle** (vidage au changement d'Espace), pas étanche : le compositeur Wayland est partagé. Une vraie séparation demande un mécanisme au niveau du compositeur | L |
| 🔴 | **Applications Flatpak système** | Une application Flatpak installée pour toute la machine est partagée entre Espaces et garde son propre bac à sable ; le liseré n'y est qu'indicatif. Soit on force l'installation par Espace, soit on le signale clairement dans l'interface (aujourd'hui c'est écrit… dans le terminal) | M |
| 🔴 | **Profils AppArmor pour les composants Codebyr** | Seuls les profils Debian de série sont actifs. `codebyr-space`, `codebyr-net-proxy` et l'extension n'ont pas de profil dédié | M |
| 🔴 | **Durcissement noyau au démarrage** | `GRUB_CMDLINE_LINUX` ne contient rien (`lockdown`, `init_on_alloc`, `slab_nomerge`…). `lockdown` n'a de sens qu'avec Secure Boot : à traiter ensemble | M |
| 🔴 | **Secure Boot de bout en bout** | `shim-signed` et `grub-efi-amd64-signed` sont dans l'image, mais le parcours complet n'a jamais été vérifié sur une machine avec Secure Boot **activé** | M |
| 🟠 | **LUKS pré-coché par défaut** | L'architecture annonce une case pré-cochée avec une formulation grand public ; en réalité c'est le parcours Calamares standard. Soit on le fait, soit on corrige la promesse (marqué `[visé]` aujourd'hui) | M |

### Le point dur de `xdg-dbus-proxy`

Le sujet paraît mécanique — « faire comme Flatpak » — et il ne l'est pas. Trois
faits qui se contredisent :

1. Une application ne parle qu'à **un seul** bus de session. Donner le proxy
   revient donc à retirer le bus privé (`dbus-run-session`).
2. Or c'est précisément ce bus privé qui empêche Fichiers ou l'Éditeur de texte
   — applications *mono-instance* — de repérer l'instance déjà lancée par
   l'hôte et d'y ouvrir simplement une fenêtre. Sans lui, l'isolation ET le
   liseré retombent.
3. En mode `--filter`, `xdg-dbus-proxy` refuse `RequestName` sauf `--own=NOM`.
   Une application GTK dont l'enregistrement échoue ne démarre pas du tout.

Flatpak s'en sort parce qu'il **connaît** le nom de bus de l'application : il
vaut son identifiant. Codebyr lance des commandes quelconques
(`firefox-esr`, un binaire téléchargé) : la correspondance n'existe pas
toujours.

Deux pistes, à départager **sur une machine réelle** :

- déduire le nom de bus du fichier `.desktop` quand il y en a un
  (`org.gnome.Nautilus.desktop` → `--own=org.gnome.Nautilus`), et se rabattre
  sur le bus privé sinon ;
- ou n'accorder le proxy qu'aux Espaces qui le demandent, pour les seules
  applications où le besoin est réel (envoi de fichiers, notifications).

Ce qu'il ne faut pas faire : livrer une implémentation non essayée. Le mode
d'échec n'est pas « les notifications manquent » — c'est « l'application ne
démarre plus », sur la fonction centrale du système.

---

## 3. Chaîne d'approvisionnement et clés

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| 🔴 | **Publier l'empreinte à plusieurs endroits indépendants** (dépôt, site, réseaux sociaux, éventuellement un keyserver) | Aujourd'hui elle n'est que dans le dépôt : quiconque contrôle le dépôt contrôle l'ancre de confiance | S |
| 🔵 | **ISO reproductibles** | Deux constructions de la même version donnent aujourd'hui deux images différentes (horodatage, état du miroir Debian). Personne ne peut vérifier indépendamment que l'ISO publiée correspond au code publié | L |
| 🔵 | **Automatiser la re-signature de l'extension en CI** | La signature AMO est manuelle. Un correctif du bouclier peut rester lettre morte — le test l'attrape désormais, mais il faut encore agir à la main | M |

---

## 4. Extension navigateur (bouclier anti-hameçonnage)

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| 🔴 | **Migration Manifest V2 → V3** | Firefox accepte encore MV2, mais AMO pousse vers MV3 et finira par refuser MV2 à la signature. Le bouclier étant un simple *content script* sans page d'arrière-plan, la conversion devrait rester mécanique — mais elle doit être faite **avant** le refus, pas après | M |
| 🟠 | **Homographes internationaux (punycode)** | La détection gère quelques substitutions (`0`→`o`, `rn`→`m`…), pas les caractères Unicode ressemblants (cyrillique, grec). C'est une technique d'hameçonnage courante | M |
| 🟠 | **Aucun bouclier dans l'Espace Banque** | Par conception (la liste blanche y suffit), mais si un domaine imitateur était ajouté à la liste blanche par erreur, rien ne le signalerait | S |
| ⚪ | **La liste « sites approuvés » est par Espace** | Approuver un site dans Navigation ne l'approuve pas dans Personnel : chaque Espace a son profil Firefox. Cohérent avec le modèle, mais à expliquer aux utilisateurs | — |

---

## 5. Produit et expérience

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| 🟠 | **Liste de banques préremplie** | L'utilisateur doit aujourd'hui saisir le domaine de sa banque à la main. Une liste « quelle est votre banque ? » rendrait le premier contact évident. ⚠️ Elle doit être construite à partir de données **vérifiées**, jamais devinées : un domaine faux dans une liste blanche casse l'authentification forte. *(Le reste est fait : notification au lancement + page de blocage explicite.)* | M |
| 🟠 | **« Ouvrir en Jetable » au clic droit dans Fichiers** | C'est le geste naturel, il était promis dans la documentation, il n'existe pas. Aujourd'hui il faut passer par le menu du Sceau ou la ligne de commande | M |
| 🟠 | **« Envoyer vers l'Espace… » dans Fichiers** | Annoncé dans l'architecture (marqué `[visé]`). Le transfert passe aujourd'hui par l'export/import d'instantané ou le presse-papiers explicite | M |
| 🟠 | **Notifications depuis les Espaces** | Perdues depuis la 1.1.0 (bus privé). Dépend du chantier `xdg-dbus-proxy` | — |
| 🟠 | **Thème GTK/libadwaita Codebyr** clair et sombre | Annoncé dans l'architecture (`[visé]`). Aujourd'hui : accent GNOME « teal », fonds d'écran et réglages par défaut | M |
| 🟠 | **Internationalisation (gettext)** | Toutes les chaînes des outils Codebyr sont en français, en dur. Le système propose ~150 locales, mais Codebyr lui-même reste monolingue — un frein direct à l'adoption hors francophonie | L |
| 🟠 | **Mode invité : point d'entrée plus clair** | Le menu du Sceau ouvre le sélecteur d'utilisateur GNOME ; l'utilisateur doit encore comprendre qu'il faut choisir « Invité » | S |

---

## 6. Qualité, tests, CI

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| 🔵 | **Tests pour `codebyr-config` et `codebyr-assistant`** | Ils dépendent de GTK, donc ne sont pas testés. Extraire la logique pure (registre, domaines, journal des refus) la rendrait testable | M |
| 🔵 | **Construction de l'ISO en CI** | Longue et exigeante (root, périphériques *loop*) : plutôt un déclenchement manuel ou nocturne qu'à chaque commit | L |

---

## 7. Projet et diffusion

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| 🟠 | **Des testeurs — priorité n°1 après la 1.1.0** | Le protocole est écrit, personne ne l'a déroulé. Tout le reste de cette liste relève de la supposition tant que cinq personnes n'ont pas installé le système sur leur propre matériel. Et la 1.1.0 est le premier état où une exposition publique ne peut pas se retourner contre vous | M |
| 🔵 | **Un second mainteneur** | Facteur bus = 1, sur un projet qui pousse du code en root chez ses utilisateurs. C'est écrit dans CONTRIBUTING ; ça ne se règle pas en l'écrivant | — |
| 🟠 | **Publier les posts de lancement** | LinkedIn est prêt ; LinuxFr, Show HN, Reddit et Mastodon sont rédigés | S |
| 🟠 | **La vidéo de démonstration** | Le storyboard existe, la vidéo non. À refaire avec les gestes **réels** (le storyboard montrait un clic droit qui n'existe pas — corrigé dans le texte) | M |
| 🔵 | **Liste de compatibilité matérielle** | À construire à partir des retours de testeurs (UEFI/BIOS, GPU, Wi-Fi) | — |

---

## 8. Dette technique et limites connues

| | Point | Détail | Effort |
|---|---|---|---|
| ⚪ | **`codebyr-space` fait ~1 000 lignes** | Découpage souhaitable, contraint par le choix « ce sont des commandes, pas une bibliothèque » | M |
| ⚪ | **Proxy : pas de SOCKS** | HTTP et CONNECT uniquement. Suffisant pour un navigateur, insuffisant pour d'autres applications | M |
| ⚪ | **Espace jetable en mémoire vive** | Le dossier éphémère vit dans `/tmp`, donc en RAM : rien de ce qu'on ouvre en Jetable n'atteint jamais le disque, ce qui est exactement la promesse. Le revers est qu'un téléchargement volumineux peut saturer la mémoire. **Arbitrage assumé** : le déplacer sur disque protégerait la RAM au prix de la propriété qui fait l'intérêt du Jetable. À revoir seulement si des testeurs rencontrent le problème | — |
| ⚪ | **`desktop_exec` ignore les *Actions* des fichiers `.desktop`** | Seule la ligne `Exec` principale est lue | S |
| ⚪ | **L'extension relit le registre à chaque fenêtre créée** | Sans conséquence perceptible, mais inutile | S |

---

## 9. Explicitement hors périmètre

À dire clairement, pour ne pas y revenir tous les six mois :

- **La virtualisation matérielle** (le modèle Qubes). C'est le choix fondateur de Codebyr : s'adapter au matériel existant plutôt que l'exiger. Un exploit noyau permet de sortir d'un Espace, et c'est assumé.
- **La protection contre un attaquant physique répété** (*evil maid*), au-delà du chiffrement LUKS.
- **Le matériel déjà compromis** (micrologiciel, chaîne d'approvisionnement matérielle).
- **L'architecture ARM** (Raspberry Pi, Apple Silicon) : x86-64 uniquement pour l'instant.

---

## Fait

### 1.2.0 (en préparation)

| | Chantier |
|---|---|
| 🔴 | **Les réglages du système atteignent enfin les utilisateurs qui personnalisent.** Le fichier utilisateur remplaçait celui du système : dès qu'on touchait un réglage, plus aucun défaut livré par apt ne pouvait plus l'atteindre — plus on configurait, moins on était protégé. Les deux se superposent désormais clé par clé, et l'écriture ne consigne que les différences |
| 🔴 | **Son et micro réglables par Espace**, dans « Configuration Codebyr » |
| 🔴 | **Signalement privé de vulnérabilité activé** — le canal que SECURITY.md documentait n'existait pas |
| 🔵 | **`codebyr-space verifier-isolation`** : une sonde s'exécute dans un vrai bac à sable et rapporte ce qu'un Espace atteint réellement, pour trois situations |
| 🔵 | **Le registre tient dans un module partagé** (`/usr/share/codebyr/registre.py`) au lieu de quatre implémentations — c'est ainsi qu'elles avaient divergé. L'extension GJS applique la même règle, vérifiée par les tests |
| 🔵 | **La CI vérifie la syntaxe JavaScript** (une erreur dans `extension.js` supprimait le menu et les liserés, sans message) **et refuse les bashismes** dans les scripts `#!/bin/sh` (invisibles pour `bash -n` comme pour `dash -n`, ils ne cassent qu'à la construction de l'ISO) |
| 🟠 | **Retour d'erreur au lancement** : le menu du Sceau prévient quand une application ne démarre pas |
| 🟠 | **Journal système** (`journalctl -t codebyr`) — sans jamais consigner le fichier ouvert ni l'adresse visitée |
| 🔵 | CHANGELOG public, modèles d'issues, Dependabot, actions GitHub à jour |
| 🔴 | **La chaîne de signature est durcie.** Phrase de passe posée, sous-clé de signature dédiée (expire dans un an), clé maîtresse et certificat de révocation sortis de la machine sur support amovible. Un vol du poste de construction ne donne plus que de quoi signer — révocable sans que personne ne réimporte l'empreinte publiée |
| 🔴 | **Phrase de passe sur la clé de signature** — posée le 20/08/2026. Au passage, le contrôle qui devait refuser de signer avec une clé nue lisait la mauvaise colonne de `keyinfo` : il ne pouvait pas se déclencher |
| 🔵 | **`build.sh` ne peut plus « réussir » sans rien reconstruire.** live-build note ses étapes dans `.build/`, que le `rsync` du script préservait : une reconstruction sautait tout, annonçait « Build completed successfully » en 90 secondes et ne produisait aucune ISO — ou pire, en aurait produit une contenant l'ancien chroot. Nettoyage automatique, et refus d'une ISO antérieure au début de la construction |
| 🟠 | **Espace Banque non configuré : l'utilisateur comprend enfin.** Notification au lancement, et vraie page d'explication au lieu d'un texte brut — le nom d'hôte y est échappé, il vient du site visité |
| ⚪ | Adresses IPv6 dans le filtre réseau ; marqueurs de processus orphelins (ils faisaient afficher le mauvais liseré) ; boucles `for` sur `find` qui cassaient sur un chemin contenant une espace |

### 1.1.0 (19 août 2026)

Sortie de bac à sable par le bus de session, dossier personnel lisible par le
compte invité sur le système installé, mot de passe invité public, Espace à
liste blanche vide qui laissait tout passer, faux positifs du bouclier, repli
« extension non signée », discours aligné sur le code, première CI et premiers
tests. Détail dans [SECURITY.md](../SECURITY.md).

---

## Si je ne devais garder que trois choses

1. **Des testeurs.** C'était le numéro deux, c'est devenu le numéro un : la
   chaîne de signature est durcie, la 1.2.0 est publiée et vérifiable. Les
   44 autres chantiers relèvent de la supposition tant que cinq personnes
   n'ont pas installé le système sur leur propre matériel.
2. **`xdg-dbus-proxy`** — pour rendre aux Espaces les notifications et les
   portails perdus en 1.1.0, sans rouvrir la faille. Le point dur est analysé
   plus haut : cela se tranche sur une machine.
3. **Un UID par Espace.** Le seul chantier qui rende la promesse d'isolation
   vraie même quand le bac à sable cède. Gros morceau, à dimensionner avant de
   s'y engager.
