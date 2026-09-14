# Chantiers — Codebyr OS

Mise à jour de lecture : **13 septembre 2026**, version publiée **1.13.0**.
Les tableaux ci-dessous sont l'historique des chantiers et comportent des
estimations anciennes. Le suivi du [lot de sécurité et du prototype UID](securite-2026-09-12.md)
fait foi pour les changements locaux de septembre ; ils ne sont pas publiés.

Le réseau par namespace et le filtre seccomp sont implémentés dans ce lot,
avec tests Linux, mais attendent la validation des applications graphiques.
Le manifeste source et le XPI embarqué sont tous deux en MV3 : les champs
fonctionnels sont désormais comparés par les tests. La re-signature MV3
n'est donc plus un chantier ouvert sur cette copie du dépôt.

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
| ✅ | **Un UID Unix par Espace — fait en 1.15.0, au choix de l'utilisateur** | Le chantier structurant est rendu. Un Espace peut tourner sous son propre compte système : dossier à lui (0700) hors du dossier personnel, plafond mémoire sur l'Espace entier, Jetable en mémoire vive. Le **point dur redouté n'en était pas un** : mesuré avant d'être bâti, GNOME 48 affiche sans broncher une fenêtre d'un autre UID — il suffit de lui présenter la socket Wayland. Ce qui a coûté, c'est le reste : root ne lit jamais les données (le bureau emballe, l'Espace déballe, par un tuyau), déménagement ET retour des données, boîtes d'envoi dans les deux sens, pièce jointe, sauvegarde, restauration, suppression du compte. **Restent** : les applications Flatpak et la carte graphique, annoncées dans la fenêtre de configuration, et le passage au défaut | XL |
| ✅ | **Notifications des Espaces — fait en 1.14.0, sans `xdg-dbus-proxy`** | Le proxy est écarté pour la raison écrite ci-dessous : il faut retirer le bus privé, donc perdre l'isolation des applications mono-instance. Un relais rend les notifications sans y toucher — service sur le bus PRIVÉ, socket dédiée vers l'hôte, en-tête imposé (« Espace Jetable », jamais « Banque »), texte nettoyé et borné, débit limité, actions refusées. **Les fenêtres de fichiers, elles, n'étaient pas cassées** : GTK se rabat sur sa propre boîte de dialogue quand aucun portail ne répond — vérifié sur machine. Reste ouvert, si le besoin apparaît : les portails eux-mêmes (appareil photo, capture d'écran, ouverture d'une URI par l'hôte) | M |
| ✅ | **Filtre réseau au niveau de l'Espace — fait en 1.11.0** | Chaque Espace restreint a son propre espace de noms réseau, sans aucune interface vers l'extérieur : il ne joint que son filtre, par une socket Unix. Plus rien ne dépend du profil Firefox, et un binaire hostile lancé dans l'Espace ne trouve aucun réseau. Depuis 1.12.0, le filtre refuse aussi les adresses du réseau local (un domaine autorisé résolu en 127.0.0.1 ou vers la box) | L |
| ✅ | **Filtre d'appels système — fait en 1.11.0, étendu en 1.12.0** | 24 appels refusés sous Blindage (ptrace, bpf, kexec, keyctl, io_uring…), posés par libseccomp avant l'exécution. Étendu à l'Espace Navigation en 1.12.0 : c'était le plus exposé et le seul navigateur sans Blindage. **Reste** : passer d'une liste de refus à une liste d'autorisation, pour qu'un appel ajouté par un futur noyau ne passe pas par défaut | M |
| 🟡 | **Profils AppArmor — le filtre réseau (1.12.1) et le service des comptes (1.15.0)** | `codebyr-net-proxy`, le seul programme qui parle au réseau pour un Espace peut-être compromis, tourne sous un profil strict. Le service des comptes d'Espaces, qui tourne en root, a le sien : il ne réduit pas son pouvoir — qui crée des comptes possède la machine — mais il borne les chemins qu'il écrit et les programmes qu'il lance, et un Espace sort du confinement à l'instant où il abandonne ses privilèges. **Restent** `codebyr-space` et l'extension GNOME, tous deux non confinés | M |
| 🟡 | **Durcissement noyau au démarrage — `lockdown` acquis** | Vérifié le 13/09/2026 : sous démarrage sécurisé, le noyau Debian se verrouille **tout seul** (`Kernel is locked down from EFI Secure Boot`), niveau `integrity` mesuré : plus rien ne peut modifier le noyau en marche (module non signé, `kexec`, écriture mémoire), même en administrateur. Restent les options de ligne de commande (`slab_nomerge`, `init_on_free`…), à peser une par une : chacune coûte en performance | S |
| ✅ | **Secure Boot de bout en bout — vérifié le 13/09/2026 (1.13.0)** | La chaîne complète fonctionne sur une machine au démarrage sécurisé activé, disque chiffré compris : le micrologiciel valide `shim`, qui valide GRUB, qui valide le noyau signé Debian (`Loaded X.509 cert 'Debian Secure Boot CA'`). Reste à confirmer sur du matériel réel, hors machine virtuelle | M |
| ✅ | **LUKS pré-coché par défaut — fait le 13/09/2026 (1.13.0)** | `preCheckEncryption: true`, et /boot séparé en clair pour que la phrase de passe soit demandée par l'initramfs (clavier AZERTY) et non par GRUB (QWERTY). Racine en LUKS2/argon2id. Validé par une installation complète : aucun fichier de clé sur /boot, phrase de passe acceptée au clavier français | S |

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

**Tranché le 13/09/2026 : aucune des deux pistes.** Le besoin mesuré sur
machine était plus étroit qu'annoncé — les fenêtres « Enregistrer sous » de
GTK fonctionnent déjà sans portail — et il ne restait que les notifications.
Elles n'exigent pas de remplacer le bus : un service les prend sur le bus
PRIVÉ de l'Espace et passe le texte à l'hôte par une socket. Le dilemme des
trois faits ci-dessus disparaît, et l'hôte gagne au passage ce qu'un proxy ne
donnerait pas : il impose l'en-tête, borne le texte et limite le débit.
Voir `usr/share/codebyr/relais_notifications.py`.

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
| ✅ | **Notifications depuis les Espaces — rendues en 1.14.0** | Perdues depuis la 1.1.0, quand le bus de l'hôte a été retiré des Espaces. Elles reviennent par le relais, et portent le nom de leur Espace. Validé sur machine : en-tête non usurpable, débit limité |
| 🟠 | **Icône du Sceau — trois tentatives, trois échecs, revenue à l'origine** | Signalée comme peu soignée et trop petite. Le gris `#5c5c5c` historique n'est beau nulle part, mais il est visible partout : c'est le compromis qu'impose un panneau valant `#fafafb` en clair et `#000000` en sombre. **Ce qui a été essayé et n'a pas marché**, le 23/08/2026 : (1) passage en `fill` avec la couleur de base d'Adwaita, en comptant sur la recoloration symbolique de GNOME — elle ne s'applique pas à une icône chargée depuis un fichier, l'icône est devenue invisible ; (2) choix entre deux variantes d'après `color-scheme` — ce réglage vaut `default` sur Codebyr alors que le panneau est noir, donc mauvais choix ; (3) mesure de la couleur réelle du panneau — juste sur le fond (dates et journal le confirmaient : le bon code tournait, sans erreur), et **l'icône ne se dessinait toujours pas**. La piste restante est la construction de `St.Icon`, jamais confirmée. **Ne pas rouvrir sans pouvoir essayer en direct** : chaque aller-retour coûte une publication complète, et trois de suite ont laissé le Sceau invisible sur la machine du mainteneur | S |
| ✅ | **Ambre (Espace Navigation) invisible sur fond clair — réglé le 13/09/2026** | `#E09A32` (2,28 sur fond clair) devient `#BF7600` : 3,47 sur fond clair, 3,95 sur fond sombre, 5,19 pour le texte de l'étiquette. Parmi les teintes ambrées, c'est la meilleure marge sur les trois à la fois, et à contraste égal la plus éloignée de Jetable pour un deutéranope (7,8 contre 6,3 pour `#BA7B1C`). Gardé par `tests/test_contraste.py` | S |
| 🟡 | **Personnel et Travail indiscernables pour les daltoniens — compensé par le nom écrit** | Azur `#4E8FEF` et Améthyste `#8F6CF0` : écart CIEDE2000 de **2,7** en deutéranopie, **6,7** en protanopie. **Compensé le 13/09/2026** (1.12.2) par un repère qui ne dépend pas de la couleur : l'étiquette du nom sur chaque fenêtre — invisible depuis la 1.0.4, rétablie — et le nom de l'Espace de la fenêtre active dans la barre du haut, à côté du Sceau. Validé sur la VM. **Reste possible** : distinguer aussi les deux teintes, pour la pastille du menu et le liseré seuls. Chiffré par `tests/test_contraste.py` | S |
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

### Historique des versions 1.2 et suivantes

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
3. ~~**Un UID par Espace.**~~ Fait en 1.15.0, au choix de l'utilisateur.
   Reste à le passer au défaut, ce qui suppose de régler les applications
   Flatpak et l'accès à la carte graphique.
