# Chantiers — Codebyr OS

État au **20 août 2026**, la 1.4.1 publiée (dépôt APT et ISO).
Ce qui a été fermé est listé en fin de document — un suivi qui ne reflète pas
l'état réel ne sert à rien.

**22 chantiers ouverts.** Ce document liste **tout** ce qui est identifié : les chantiers de fond, les
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

## 1. Sécurité — architecture

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| 🔴 | **Un UID Unix par Espace** | Le chantier structurant. Aujourd'hui tous les Espaces tournent sous votre compte et leurs données vivent dans `~/.local/share/codebyr/espaces/`. Le bac à sable les sépare, mais toute évasion — ou toute application lancée hors Espace — lit l'ensemble. C'est la seule façon de rendre la séparation vraie au niveau du système. **Point dur** : faire accepter par le compositeur Wayland des applications tournant sous d'autres UID (piste : portails XDG + `systemd-run --uid`). À dimensionner avant de s'y engager | XL |
| 🔴 | **`xdg-dbus-proxy` pour les portails et les notifications** | Depuis la 1.1.0, un Espace n'a plus qu'un bus privé vide : plus de notifications, plus de portails XDG. Un proxy filtrant les rendrait **sans** rouvrir l'accès au bus de session. **Point dur identifié** (voir l'encadré ci-dessous) : le proxy remplace le bus privé, or c'est ce bus privé qui empêche aujourd'hui une application mono-instance de rejoindre celle de l'hôte. À traiter sur machine, pas à l'aveugle | M |
| 🔴 | **Filtre réseau au niveau de l'Espace, pas du navigateur** | La liste blanche de Banque s'applique au profil Firefox : un binaire hostile lancé dans l'Espace la contourne. Un vrai cloisonnement demande un namespace réseau par Espace (veth + nftables, ou slirp), appliqué à **tous** les processus | L |
| 🔴 | **Filtre seccomp dans le bac à sable** (`bwrap --seccomp`) | Aucun filtre d'appels système aujourd'hui : toute la surface du noyau est exposée depuis un Espace. C'est précisément la surface par laquelle une évasion passerait | M |
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

## 2. Chaîne d'approvisionnement et clés

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| 🔵 | **ISO reproductibles** | Deux constructions de la même version donnent aujourd'hui deux images différentes (horodatage, état du miroir Debian). Personne ne peut vérifier indépendamment que l'ISO publiée correspond au code publié | L |

---

## 3. Extension navigateur (bouclier anti-hameçonnage)

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| 🔴 | **Manifest V3 — converti, reste à FAIRE SIGNER** | Le manifeste est passé en MV3 et validé par `web-ext lint` : 0 erreur. Seul avertissement restant, sans objet ici, sur Firefox pour Android — plateforme hors périmètre. `strict_min_version` aligné sur l'ESR 140.14 que Codebyr livre réellement, ce qui permet de déclarer `data_collection_permissions: none` — une clé qu'AMO exigera bientôt de toutes les extensions. **Le bouclier installé sur les machines reste celui du `.xpi` signé** : tant qu'il n'est pas régénéré via AMO, cette conversion n'a aucun effet, et `tests/test_bouclier.py` reste rouge pour le rappeler. `AMO_KEY=… AMO_SECRET=… bash live-build/scripts/sign-extension.sh` | S |
| 🟠 | **Homographes internationaux (punycode)** | La détection gère quelques substitutions (`0`→`o`, `rn`→`m`…), pas les caractères Unicode ressemblants (cyrillique, grec). C'est une technique d'hameçonnage courante | M |

---

## 4. Produit et expérience

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| 🟠 | **Liste de banques préremplie** | L'utilisateur doit aujourd'hui saisir le domaine de sa banque à la main. Une liste « quelle est votre banque ? » rendrait le premier contact évident. ⚠️ Elle doit être construite à partir de données **vérifiées**, jamais devinées : un domaine faux dans une liste blanche casse l'authentification forte. *(Le reste est fait : notification au lancement + page de blocage explicite.)* | M |
| 🟠 | **Notifications depuis les Espaces** | Perdues depuis la 1.1.0 (bus privé). Dépend du chantier `xdg-dbus-proxy` | — |
| 🟠 | **Icône du Sceau — trois tentatives, trois échecs, revenue à l'origine** | Signalée comme peu soignée et trop petite. Le gris `#5c5c5c` historique n'est beau nulle part, mais il est visible partout : c'est le compromis qu'impose un panneau valant `#fafafb` en clair et `#000000` en sombre. **Ce qui a été essayé et n'a pas marché**, le 23/08/2026 : (1) passage en `fill` avec la couleur de base d'Adwaita, en comptant sur la recoloration symbolique de GNOME — elle ne s'applique pas à une icône chargée depuis un fichier, l'icône est devenue invisible ; (2) choix entre deux variantes d'après `color-scheme` — ce réglage vaut `default` sur Codebyr alors que le panneau est noir, donc mauvais choix ; (3) mesure de la couleur réelle du panneau — juste sur le fond (dates et journal le confirmaient : le bon code tournait, sans erreur), et **l'icône ne se dessinait toujours pas**. La piste restante est la construction de `St.Icon`, jamais confirmée. **Ne pas rouvrir sans pouvoir essayer en direct** : chaque aller-retour coûte une publication complète, et trois de suite ont laissé le Sceau invisible sur la machine du mainteneur | S |
| 🟠 | **Ambre (Espace Navigation) invisible sur fond clair** | Mesuré : contraste **2,376** contre un seuil de 3,0 pour un élément non textuel. C'est la pastille de barre de titre qui en souffre, posée sur un bandeau presque blanc — or la couleur d'un Espace n'est jamais décorative, c'est le seul repère visuel du cloisonnement. Une Ambre à 42 % de clarté, `#BA7B1C`, conviendrait aux deux fonds (3,54 / 5,26). **Décision de conception, pas correction technique** : elle vous appartient. Le défaut est gardé chiffré par `tests/test_contraste.py` | S |
| 🟠 | **Internationalisation (gettext)** | Toutes les chaînes des outils Codebyr sont en français, en dur. Le système propose ~150 locales, mais Codebyr lui-même reste monolingue — un frein direct à l'adoption hors francophonie | L |
| 🟠 | **Mode invité : point d'entrée plus clair** | Le menu du Sceau ouvre le sélecteur d'utilisateur GNOME ; l'utilisateur doit encore comprendre qu'il faut choisir « Invité » | S |

---

## 5. Qualité, tests, CI

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| 🔵 | **Construction de l'ISO en CI — commencée, pas finie** | Le workflow existe (`construire-iso.yml`, déclenchement manuel, conteneur Debian trixie, vérification du contenu produit). Il échoue encore sur `E: repository 'http://security.debian.org trixie/updates' does not have a Release` — l'ancienne convention de nommage du dépôt de sécurité, abandonnée depuis Bullseye. Or le même `live-build` (1:20250505+deb13u1) génère bien `trixie-security` dans le WSL du mainteneur, et le dépôt ne contient aucune configuration figée. **L'écart reste à trouver** : comparer le `config/` engendré par `lb config` des deux côtés est la piste directe | M |

---

## 6. Projet et diffusion

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| 🟠 | **Des testeurs — la priorité, désormais seule sur sa ligne** | Le protocole est écrit, personne ne l'a déroulé. Tout le reste de cette liste relève de la supposition tant que cinq personnes n'ont pas installé le système sur leur propre matériel. Et la 1.1.0 est le premier état où une exposition publique ne peut pas se retourner contre vous | M |
| 🔵 | **Un second mainteneur** | Facteur bus = 1, sur un projet qui pousse du code en root chez ses utilisateurs. C'est écrit dans CONTRIBUTING ; ça ne se règle pas en l'écrivant | — |
| 🟠 | **Publier les posts de lancement** | LinkedIn est prêt ; LinuxFr, Show HN, Reddit et Mastodon sont rédigés | S |
| 🟠 | **La vidéo de démonstration** | Le storyboard existe, la vidéo non. À refaire avec les gestes **réels** (le storyboard montrait un clic droit qui n'existe pas — corrigé dans le texte) | M |
| 🔵 | **Liste de compatibilité matérielle** | À construire à partir des retours de testeurs (UEFI/BIOS, GPU, Wi-Fi) | — |

---

## 7. Dette technique et limites connues

| | Point | Détail | Effort |
|---|---|---|---|

---

## 8. Explicitement hors périmètre

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
| 🔵 | **Autotest du poste** (`codebyr-space verifier-poste`). Six contrôles, chacun rejouant un défaut réellement survenu ici. Tous partagent le trait qui les rend redoutables : **ils ne se voient pas à l'usage** — un poste dont le trousseau a périmé se comporte comme un poste sain. C'est ce qui rend vérifiable la moitié des chantiers qu'un mainteneur seul peut fermer — **vérifié sur machine le 23/08/2026** |
| 🟠 | **« Envoyer vers l'Espace… » au clic droit.** Annoncé dans l'architecture depuis le début, jamais réalisé. Copie dans le sas « Partagé » de l'Espace choisi, sans imposer le blindage ni couper le réseau — c'est le geste inverse du Jetable. Un fichier du même nom n'est jamais écrasé — **vérifié sur machine le 23/08/2026** |
| 🟠 | **« Ouvrir en Jetable » au clic droit** dans le gestionnaire de fichiers, via une extension nautilus-python. Promis dans la documentation depuis le début, il n'avait jamais existé — **vérifié sur machine le 20/08/2026** (Nautilus 48.3). Le premier essai n'affichait rien : `python3-nautilus` n'était qu'un *Recommends*, donc absent, et l'extension n'était pas chargée — sans le moindre message. Dépendance ferme depuis la 1.4.1 |
| 🔴 | **Le filtre réseau parle SOCKS5**, sur le même port que HTTP. Il ne protégeait que le navigateur : tout autre programme lancé dans l'Espace passait à côté sans que rien ne le signale |
| 🟠 | **Une application Flatpak non cloisonnée le dit à l'écran.** L'avertissement existait — dans le terminal, c'est-à-dire nulle part pour qui a cliqué dans un menu. L'utilisateur croyait son application isolée, et le liseré coloré le lui confirmait à tort |
| ⚪ | **`codebyr-space` : 1 173 → 919 lignes**, le bac à sable dans son propre module |
| 🔴 | **Transition de clé sans intervention des utilisateurs.** L'ajout d'une sous-clé avait rendu le dépôt invérifiable par tout le parc installé — échec propre, mais total. Double signature pendant la transition, trousseau rafraîchi par le paquet, trois exemplaires de la clé publique réalignés et comparés par un test |
| 🔴 | **Le presse-papiers ne se contourne plus par le bureau.** On ne vidait qu'en passant d'un Espace à un autre : copier dans Banque, cliquer sur le bureau, ouvrir n'importe quelle application — le secret était encore là. On vide désormais aussi en SORTANT d'un Espace sensible |
| 🔵 | **La re-signature du bouclier est automatisable en CI** (déclenchement manuel, montée de version, signature Mozilla, dépôt du .xpi) |
| 🔵 | **Détection des applications et résolution des `.desktop` extraites et testées.** Un `.desktop` peut contenir plusieurs `Exec` — ceux de ses « actions » — et la première ligne venue n'est pas forcément l'application |
| ⚪ | **Jetable : avertissement quand la mémoire manque**, plutôt qu'une saturation en cours de route |
| 🔴 | **La saisie d'un domaine bancaire est analysée et testée.** C'est la seule porte d'entrée de la liste blanche, et elle n'avait aucun test. Refuse désormais les adresses IP, l'Unicode non converti, les caractères interdits, et lit `mabanque.fr@piege.fr` comme le navigateur le lira : `piege.fr` |
| 🔴 | **Le bouclier veille aussi dans l'Espace Banque.** Il en était exclu au motif que la liste blanche suffit — mais cette liste est saisie à la main, et l'erreur humaine est justement la menace couverte |
| 🔴 | **L'empreinte de la clé est publiée sur deux hébergements indépendants** (dépôt et site). Une seule source, et sa compromission passe inaperçue |
| ⚪ | **L'extension ne relit plus les registres à chaque fenêtre** : cache invalidé par date de modification |
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
   chaîne de signature est durcie, la 1.4.1 est publiée et vérifiable. Les
   22 autres chantiers relèvent de la supposition tant que cinq personnes
   n'ont pas installé le système sur leur propre matériel.

   Chiffre à garder en tête : au 20 août 2026, les cinq ISO publiées totalisent
   **zéro téléchargement**. Ce n'est pas un détail de communication — c'est ce
   qui rend tout le reste de cette liste théorique.
2. **`xdg-dbus-proxy`** — pour rendre aux Espaces les notifications et les
   portails perdus en 1.1.0, sans rouvrir la faille. Le point dur est analysé
   plus haut : cela se tranche sur une machine.
3. **Un UID par Espace.** Le seul chantier qui rende la promesse d'isolation
   vraie même quand le bac à sable cède. Gros morceau, à dimensionner avant de
   s'y engager.
