# Chantiers — Codebyr OS

État au **19 août 2026**, juste après la publication de la 1.1.0.

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
| 🔴 | **Phrase de passe sur la clé de signature** — procédure dans [chaine-de-signature.md](chaine-de-signature.md) | Devenu le premier risque du projet : le canal apt est vivant et atteint root sur toutes les machines ; la clé dort en clair sur un poste Windows de développement | S |
| 🔴 | **Activer le signalement privé de vulnérabilité** sur GitHub : `gh api -X PUT repos/Romtouf/codebyr-os/private-vulnerability-reporting` | SECURITY.md demande d'utiliser l'onglet « Security → Report a vulnerability »… qui est désactivé. Le canal de signalement documenté **n'existe pas** : un chercheur bien intentionné n'a aujourd'hui aucun moyen privé de vous joindre | S |
| 🔵 | **Cocher la Phase 5** dans le README (ISO signées ✅, CI ✅, site ✅ — restent les testeurs) | Le README annonce encore la diffusion comme non commencée | S |
| 🔵 | **Sortir le certificat de révocation de la machine** — il existe (`/root/.gnupg-codebyr/openpgp-revocs.d/`) mais il est sur le même disque que la clé qu'il sert à révoquer | Si le poste est perdu ou chiffré par un rançongiciel, vous perdez la clé **et** le moyen de la révoquer | S |

---

## 2. Sécurité — architecture

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| 🔴 | **Un UID Unix par Espace** | Le chantier structurant. Aujourd'hui tous les Espaces tournent sous votre compte et leurs données vivent dans `~/.local/share/codebyr/espaces/`. Le bac à sable les sépare, mais toute évasion — ou toute application lancée hors Espace — lit l'ensemble. C'est la seule façon de rendre la séparation vraie au niveau du système. **Point dur** : faire accepter par le compositeur Wayland des applications tournant sous d'autres UID (piste : portails XDG + `systemd-run --uid`). À dimensionner avant de s'y engager | XL |
| 🔴 | **`xdg-dbus-proxy` pour les portails et les notifications** | Depuis la 1.1.0, un Espace n'a plus qu'un bus privé vide : plus de notifications, plus de portails XDG (sélecteur de fichiers, capture d'écran). Un proxy filtrant rend ces services **sans** rouvrir l'accès au bus de session. C'est exactement ce que fait Flatpak. Gain de sécurité *et* de confort — le meilleur rapport des deux | M |
| 🔴 | **Filtre réseau au niveau de l'Espace, pas du navigateur** | La liste blanche de Banque s'applique au profil Firefox : un binaire hostile lancé dans l'Espace la contourne. Un vrai cloisonnement demande un namespace réseau par Espace (veth + nftables, ou slirp), appliqué à **tous** les processus | L |
| 🔴 | **Filtre seccomp dans le bac à sable** (`bwrap --seccomp`) | Aucun filtre d'appels système aujourd'hui : toute la surface du noyau est exposée depuis un Espace. C'est précisément la surface par laquelle une évasion passerait | M |
| 🔴 | **Micro et son** | Le socket PipeWire vaut accès au microphone. Seul Banque le refuse (`"audio": false`), et uniquement via le registre système — un utilisateur ayant une copie personnelle du registre ne l'a pas. Il faut un réglage visible dans « Configuration Codebyr », par Espace | S |
| 🔴 | **Presse-papiers** | La protection est **temporelle** (vidage au changement d'Espace), pas étanche : le compositeur Wayland est partagé. Une vraie séparation demande un mécanisme au niveau du compositeur | L |
| 🔴 | **Applications Flatpak système** | Une application Flatpak installée pour toute la machine est partagée entre Espaces et garde son propre bac à sable ; le liseré n'y est qu'indicatif. Soit on force l'installation par Espace, soit on le signale clairement dans l'interface (aujourd'hui c'est écrit… dans le terminal) | M |
| 🔴 | **Profils AppArmor pour les composants Codebyr** | Seuls les profils Debian de série sont actifs. `codebyr-space`, `codebyr-net-proxy` et l'extension n'ont pas de profil dédié | M |
| 🔴 | **Durcissement noyau au démarrage** | `GRUB_CMDLINE_LINUX` ne contient rien (`lockdown`, `init_on_alloc`, `slab_nomerge`…). `lockdown` n'a de sens qu'avec Secure Boot : à traiter ensemble | M |
| 🔴 | **Secure Boot de bout en bout** | `shim-signed` et `grub-efi-amd64-signed` sont dans l'image, mais le parcours complet n'a jamais été vérifié sur une machine avec Secure Boot **activé** | M |
| 🟠 | **LUKS pré-coché par défaut** | L'architecture annonce une case pré-cochée avec une formulation grand public ; en réalité c'est le parcours Calamares standard. Soit on le fait, soit on corrige la promesse (marqué `[visé]` aujourd'hui) | M |

---

## 3. Chaîne d'approvisionnement et clés

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| 🔴 | **Clé maîtresse hors ligne + sous-clés dédiées** (`releases`, `apt`) | Une sous-clé volée se révoque et se remplace **sans changer l'empreinte publiée**, donc sans faire réimporter une clé à tous les utilisateurs. Impossible aujourd'hui : une seule clé fait tout | M |
| 🔴 | **Expiration à 1 an sur les sous-clés** | La clé actuelle expire le 07/07/2028 (688 jours). Une clé volée reste valable jusque-là | S |
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
| 🟠 | **Assistant de première configuration pour Banque** | Depuis la 1.1.0, un Espace Banque non configuré **n'ouvre aucun site** (échec fermé, correct mais brutal). Un écran « quelle est votre banque ? » avec une liste des banques françaises transformerait la fonctionnalité phare en quelque chose d'utilisable. ⚠️ La liste doit être construite à partir de données **vérifiées**, jamais devinées : un domaine faux dans une liste blanche casse l'authentification forte | M |
| 🟠 | **« Ouvrir en Jetable » au clic droit dans Fichiers** | C'est le geste naturel, il était promis dans la documentation, il n'existe pas. Aujourd'hui il faut passer par le menu du Sceau ou la ligne de commande | M |
| 🟠 | **« Envoyer vers l'Espace… » dans Fichiers** | Annoncé dans l'architecture (marqué `[visé]`). Le transfert passe aujourd'hui par l'export/import d'instantané ou le presse-papiers explicite | M |
| 🟠 | **Notifications depuis les Espaces** | Perdues depuis la 1.1.0 (bus privé). Dépend du chantier `xdg-dbus-proxy` | — |
| 🟠 | **Retour d'erreur quand une application ne démarre pas** | L'extension lance `codebyr-space` sans lire sa sortie : si le lancement échoue, l'utilisateur ne voit **rien** | S |
| 🟠 | **Thème GTK/libadwaita Codebyr** clair et sombre | Annoncé dans l'architecture (`[visé]`). Aujourd'hui : accent GNOME « teal », fonds d'écran et réglages par défaut | M |
| 🟠 | **Internationalisation (gettext)** | Toutes les chaînes des outils Codebyr sont en français, en dur. Le système propose ~150 locales, mais Codebyr lui-même reste monolingue — un frein direct à l'adoption hors francophonie | L |
| 🟠 | **Mode invité : point d'entrée plus clair** | Le menu du Sceau ouvre le sélecteur d'utilisateur GNOME ; l'utilisateur doit encore comprendre qu'il faut choisir « Invité » | S |
| 🟠 | **Journal des actions Codebyr** | Aucune trace exploitable quand un utilisateur signale « ça n'a pas marché ». Un journal (`journalctl`, identifiant `codebyr`) rendrait le support possible | S |

---

## 6. Qualité, tests, CI

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| 🔵 | **`codebyr-space verifier-isolation`** : une commande qui lance une sonde **dans** un bac à sable et rapporte ce qui est joignable (bus de session, systemd, micro, réseau) | Les trois vérifications qu'on a faites à la main en VM deviendraient une commande, reproductible par n'importe quel testeur, et exécutable après chaque mise à jour | M |
| 🔵 | **Tests pour `codebyr-config` et `codebyr-assistant`** | Ils dépendent de GTK, donc ne sont pas testés. Extraire la logique pure (registre, domaines, journal des refus) la rendrait testable | M |
| 🔵 | **Construction de l'ISO en CI** | Longue et exigeante (root, périphériques *loop*) : plutôt un déclenchement manuel ou nocturne qu'à chaque commit | L |
| 🔵 | **Nettoyer les 6 avertissements `shellcheck`** (`SC2044`, boucles `for` sur `find`, dans `0500-debrand.hook.chroot`) | Signalés sans bloquer. Sans conséquence sur ces chemins, mais autant ne pas laisser de bruit | S |
| 🔵 | **Actions GitHub sur Node 20 déprécié** (`actions/checkout@v4`, `setup-python@v5`) | Avertissement à chaque run ; il faudra passer aux versions suivantes | S |
| 🔵 | **Dependabot** pour les actions GitHub (actuellement désactivé) | Sinon les versions d'actions vieillissent en silence | S |
| 🔵 | **CHANGELOG.md public** | L'historique vit dans les messages de commit et le tableau de SECURITY.md. Un utilisateur qui veut savoir ce qu'apporte une version n'a pas d'endroit évident | S |

---

## 7. Projet et diffusion

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| 🟠 | **Des testeurs — priorité n°1 après la 1.1.0** | Le protocole est écrit, personne ne l'a déroulé. Tout le reste de cette liste relève de la supposition tant que cinq personnes n'ont pas installé le système sur leur propre matériel. Et la 1.1.0 est le premier état où une exposition publique ne peut pas se retourner contre vous | M |
| 🔵 | **Un second mainteneur** | Facteur bus = 1, sur un projet qui pousse du code en root chez ses utilisateurs. C'est écrit dans CONTRIBUTING ; ça ne se règle pas en l'écrivant | — |
| 🟠 | **Publier les posts de lancement** | LinkedIn est prêt ; LinuxFr, Show HN, Reddit et Mastodon sont rédigés | S |
| 🟠 | **La vidéo de démonstration** | Le storyboard existe, la vidéo non. À refaire avec les gestes **réels** (le storyboard montrait un clic droit qui n'existe pas — corrigé dans le texte) | M |
| 🔵 | **Modèles d'issues et tri** | Aucun modèle aujourd'hui ; les premiers rapports arriveront en vrac | S |
| 🔵 | **Liste de compatibilité matérielle** | À construire à partir des retours de testeurs (UEFI/BIOS, GPU, Wi-Fi) | — |

---

## 8. Dette technique et limites connues

| | Point | Détail | Effort |
|---|---|---|---|
| ⚪ | **Registre des Espaces lu par 4 programmes** | Trois en Python, un en GJS. Impossible de partager du code entre les deux langages ; la cohérence est garantie par un test (`tests/test_registre_coherence.py`) plutôt que par le langage. Un démon `codebyr-spaced` serait la vraie réponse — mais il ajouterait un service privilégié à sécuriser | L |
| ⚪ | **`codebyr-space` fait ~1 000 lignes** | Découpage souhaitable, contraint par le choix « ce sont des commandes, pas une bibliothèque » | M |
| ⚪ | **Proxy : adresses IPv6 littérales** | `CONNECT [2001:db8::1]:443` conserve les crochets et la connexion échoue. Impact quasi nul (les navigateurs utilisent des noms), mais c'est faux | S |
| ⚪ | **Proxy : pas de SOCKS** | HTTP et CONNECT uniquement. Suffisant pour un navigateur, insuffisant pour d'autres applications | M |
| ⚪ | **Espace jetable dans `/tmp`** | Le dossier personnel éphémère vit dans `/tmp`, souvent en RAM. Un téléchargement volumineux dans un Jetable peut saturer la mémoire | S |
| ⚪ | **`desktop_exec` ignore les *Actions* des fichiers `.desktop`** | Seule la ligne `Exec` principale est lue | S |
| ⚪ | **Fichiers `pid-*` orphelins** | Si un processus meurt anormalement, son marqueur reste dans le répertoire d'exécution jusqu'à la prochaine fermeture d'Espace | S |
| ⚪ | **L'extension relit le registre à chaque fenêtre créée** | Sans conséquence perceptible, mais inutile | S |
| ⚪ | **Réglages système masqués par la copie utilisateur** | Dès qu'un utilisateur a un `~/.config/codebyr/espaces.json`, les nouveaux réglages livrés dans `/etc` (comme `"audio": false` sur Banque) ne s'appliquent plus à lui. Il faudrait fusionner les deux registres au lieu de choisir l'un ou l'autre | M |

---

## 9. Explicitement hors périmètre

À dire clairement, pour ne pas y revenir tous les six mois :

- **La virtualisation matérielle** (le modèle Qubes). C'est le choix fondateur de Codebyr : s'adapter au matériel existant plutôt que l'exiger. Un exploit noyau permet de sortir d'un Espace, et c'est assumé.
- **La protection contre un attaquant physique répété** (*evil maid*), au-delà du chiffrement LUKS.
- **Le matériel déjà compromis** (micrologiciel, chaîne d'approvisionnement matérielle).
- **L'architecture ARM** (Raspberry Pi, Apple Silicon) : x86-64 uniquement pour l'instant.

---

## Si je ne devais garder que trois choses

1. **Terminer la 1.1.0** — signer l'ISO, publier la release, poser une phrase de passe sur la clé, activer le signalement de vulnérabilité. Quelques heures, et le projet est propre.
2. **Des testeurs.** Tout le reste est supposition sans eux.
3. **`xdg-dbus-proxy`**, puis **un UID par Espace.** Le premier rend aux Espaces ce que la 1.1.0 leur a retiré ; le second est le seul qui rende la promesse d'isolation vraie même quand le bac à sable cède.
