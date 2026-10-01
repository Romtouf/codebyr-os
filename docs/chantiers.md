# Chantiers — Codebyr OS

Mise à jour de lecture : **1er octobre 2026**, version publiée **1.18.0**.

Ce document est la carte du projet : ce qui est fait, ce qui reste, et pourquoi.
Les estimations d'effort des lignes anciennes n'ont pas été refaites.

**Où en est le projet, en une phrase** : les chantiers structurants de sécurité
sont rendus et publiés ; ce qui reste tient surtout à la diffusion — des
testeurs, un second mainteneur, les posts de lancement.

**Ce que la relecture du 27 septembre 2026 a appris** : la CI était rouge
depuis le 13, et quatre versions sont parties quand même — un test contredisait
le correctif de sécurité de la 1.12.0, et l'échec de ruff en masquait un
autre. Les documents se contredisaient (la 1.16.1 annoncée publiée, le filtre
réseau décrit comme limité au navigateur, la Phase 6 décochée). Corrigé en
1.16.1, et surtout rendu impossible à refaire en silence : `publish-apt.sh`
exige une CI verte, `tests/test_coherence.py` confronte les documents entre
eux.

**Ce que l'audit technique du 29 septembre 2026 a appris** : une élévation de
privilèges réelle, présente depuis la 1.15.0 — le service root des comptes
suivait les liens posés dans le dossier d'exécution du bureau, et tout compte
du bureau pouvait se donner l'écriture sur `/etc/shadow`. Reproduite, corrigée
par descripteur épinglé, validée sur la VM et publiée en 1.16.2 le jour même.
Le même audit a mis au jour des Espaces créés qui ne s'ouvraient pas (nom long
ou commençant par un chiffre), un bouclier aveugle aux adresses déguisées par
d'autres alphabets, et trois documents périmés. En éprouvant ce bouclier dans un
vrai Firefox, la découverte la plus lourde : il était **muet partout depuis la
1.6.0** — chargé, mais privé du droit de lire les pages. Firefox l'installe
désormais lui-même, par une politique ; publié en 1.16.3 le même jour. Leçon :
une protection qu'aucun essai ne voit agir n'est pas une protection — le
bouclier n'avait été vérifié que chargé, jamais en train d'alerter. Deux des
propositions de l'audit ont été écartées ou reportées, raisons écrites : un
profil AppArmor pour `codebyr-space`, et la liste d'autorisation des appels
système sans mesure préalable.

Le chantier « un UID Unix par Espace » est clos depuis la 1.16.0 : un Espace
peut tourner sous son propre compte, avec ses applications Flatpak et la carte
graphique. **La décision qui restait est prise** (27/09/2026) : c'est le
réglage par défaut de chaque Espace dans la 1.16.1 — l'invité excepté, dont
les Espaces doivent s'effacer avec sa session. Personnel et Travail y sont
aussi blindés. Les deux se valident sur machine avant publication.

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
| ✅ | **Un UID Unix par Espace — fait en 1.15.0, par défaut en 1.16.1** | Le chantier structurant est rendu. Un Espace peut tourner sous son propre compte système : dossier à lui (0700) hors du dossier personnel, plafond mémoire sur l'Espace entier, Jetable en mémoire vive. Le **point dur redouté n'en était pas un** : mesuré avant d'être bâti, GNOME 48 affiche sans broncher une fenêtre d'un autre UID — il suffit de lui présenter la socket Wayland. Ce qui a coûté, c'est le reste : root ne lit jamais les données (le bureau emballe, l'Espace déballe, par un tuyau), déménagement ET retour des données, boîtes d'envoi dans les deux sens, pièce jointe, sauvegarde, restauration, suppression du compte. Passé au défaut en 1.16.1 (voir plus bas) | XL |
| ✅ | **Carte graphique sous compte séparé — fait en 1.16.0** | Seconde limite de la 1.15.0, levée. Le diagnostic tenait en une phrase : ce n'est pas un groupe qui donne accès à `/dev/dri`, c'est `logind`, qui pose un droit NOMINATIF pour l'utilisateur de la session et le retire à la déconnexion — un compte d'Espace n'a pas de session, donc aucun droit. Le service fait la même chose, le temps de l'Espace. **Deux mesures fausses avant la bonne** : le nom du moteur de rendu de GTK (« gl ») ne dit rien du matériel, il tourne aussi bien au-dessus de llvmpipe ; le signal qui tranche est le descripteur ouvert sur `/dev/dri/renderD*`. Et il a fallu activer la 3D dans la machine d'essai, dont la session était elle-même en rendu logiciel. Garde-fous : nœuds de rendu seulement, liens symboliques écartés, droit repris sur toutes les cartes à la fermeture | M |
| ✅ | **Applications Flatpak sous compte séparé — fait en 1.16.0** | Première des deux limites de la 1.15.0, levée. Chaque Espace a son bus de session, donc ses portails : la fenêtre « Ouvrir un fichier » s'affiche et ne montre que ses fichiers. L'installation se fait DANS l'Espace, par lui (`interne-flatpak`), dans un dossier que le bureau ne peut pas écrire. **Tout a été mesuré avant d'être bâti** : le blocage n'était ni les droits ni le compte, mais le CHEMIN — Flatpak suppose `/run/user/<uid>`, et la « passerelle » de la 1.15.0 a été remplacée par ce dossier canonique. Gain d'isolation au passage : une application Flatpak parlait jusqu'ici au bus du bureau, et ouvrait donc des programmes sous le compte de l'utilisateur. **Limite assumée** : le portail des documents ne monte pas son système FUSE sous `no-new-privs` (`fusermount3` est setuid), donc l'application ne reçoit pas le fichier choisi. Décidé le 15/09/2026 : garder la protection, dire la limite | L |
| ✅ | **Notifications des Espaces — fait en 1.14.0, sans `xdg-dbus-proxy`** | Le proxy est écarté pour la raison écrite ci-dessous : il faut retirer le bus privé, donc perdre l'isolation des applications mono-instance. Un relais rend les notifications sans y toucher — service sur le bus PRIVÉ, socket dédiée vers l'hôte, en-tête imposé (« Espace Jetable », jamais « Banque »), texte nettoyé et borné, débit limité, actions refusées. **Les fenêtres de fichiers, elles, n'étaient pas cassées** : GTK se rabat sur sa propre boîte de dialogue quand aucun portail ne répond — vérifié sur machine. Reste ouvert, si le besoin apparaît : les portails eux-mêmes (appareil photo, capture d'écran, ouverture d'une URI par l'hôte) | M |
| ✅ | **Filtre réseau au niveau de l'Espace — fait en 1.11.0** | Chaque Espace restreint a son propre espace de noms réseau, sans aucune interface vers l'extérieur : il ne joint que son filtre, par une socket Unix. Plus rien ne dépend du profil Firefox, et un binaire hostile lancé dans l'Espace ne trouve aucun réseau. Depuis 1.12.0, le filtre refuse aussi les adresses du réseau local (un domaine autorisé résolu en 127.0.0.1 ou vers la box) | L |
| ✅ | **Filtre d'appels système — liste d'autorisation, publiée en 1.16.4 le 29/09/2026** | Depuis la 1.11.0, 24 appels refusés sous Blindage (ptrace, bpf, kexec, keyctl, io_uring…), étendu à Navigation en 1.12.0, à Personnel et Travail en 1.16.1. Mais tout le reste passait, y compris l'appel qu'un futur noyau ajoutera. **Liste d'autorisation depuis la 1.16.4** : seuls les 379 appels connus de libseccomp 2.6.0 (`CONNUS`, liste figée) passent, moins les refus (EPERM) et 39 écartés ; tout autre appel reçoit ENOSYS, la réponse qui fait se rabattre la glibc sur l'appel plus ancien. **Mesuré avant d'être bâti**, deux fois sur la VM le 29/09/2026, par un mode mesure où les candidats restent permis mais journalisés (`tools/mesurer_seccomp.py`) : Firefox et une vidéo, Fichiers et ses vignettes, une application Flatpak, la console. Six candidats ont servi et restent permis — `quotactl` (Firefox), `mount` et `pivot_root` (bwrap imbriqué : Flatpak, vignettes ; toute la famille des montages avec eux), `name_to_handle_at` et `fanotify_*` (localsearch, la recherche de GNOME). Éprouvé dans le WSL et en CI : Firefox dans Banque blindée, node, Python, outils du shell, bwrap imbriqué. **Validé sur la VM** avant publication : tous les Espaces et leurs applications (Fichiers, Console, éditeur de texte, Calculatrice Flatpak, Firefox et une vidéo, Jetable), et la sonde d'isolation conforme dans les cinq situations — elle tourne elle-même sous la liste dans les Espaces blindés | M |
| ✅ | **Profils AppArmor — le filtre réseau (1.12.1) et le service des comptes (1.15.0) ; aucun pour `codebyr-space` ni l'extension, décidé le 29/09/2026** | `codebyr-net-proxy`, le seul programme qui parle au réseau pour un Espace peut-être compromis, tourne sous un profil strict. Le service des comptes d'Espaces, qui tourne en root, a le sien : il ne réduit pas son pouvoir — qui crée des comptes possède la machine — mais il borne les chemins qu'il écrit et les programmes qu'il lance, et un Espace sort du confinement à l'instant où il abandonne ses privilèges. **Les deux autres, examinés à la demande de l'audit du 29/09/2026, sont écartés.** L'extension vit DANS gnome-shell : AppArmor confine des processus, il faudrait confiner le bureau entier. `codebyr-space` doit lancer bwrap, flatpak et dbus-run-session hors confinement ; détourné, il relancerait bwrap avec ses propres arguments. Son profil ne contiendrait donc rien, et un outil oublié dans sa liste empêcherait un Espace de s'ouvrir, sans bruit. Ce qu'il reçoit d'un Espace se limite à 8 Ko de JSON (les notifications, lues par le module `json` de Python, affichées par `notify-send` sans shell) et aux fichiers envoyés (copiés par descripteur, sans suivre de lien). **Piste, si le besoin apparaît** : sortir la moitié hôte du relais de notifications dans son propre processus, confiné comme le filtre réseau — détourné, il ne pourrait plus que lancer `notify-send` | M |
| ✅ | **Durcissement noyau au démarrage — `lockdown` acquis ; `slab_nomerge` et `page_alloc.shuffle=1` publiés en 1.16.8 le 30/09/2026, validés sur la VM (`/proc/cmdline` après redémarrage ; GRUB régénéré d'office quand il ne porte pas les options)** | Mesuré le 30/09/2026 dans la configuration du noyau Debian 13 (6.12) : `init_on_alloc`, `randomize_kstack_offset` et `vsyscall=none` sont DÉJÀ actifs par défaut ; restaient `slab_nomerge` (coût : un peu de mémoire) et `page_alloc.shuffle=1`, livrés par le paquet (`/etc/default/grub.d/90-codebyr-noyau.cfg`, `update-grub` si besoin) et sur la ligne du live. `init_on_free=1` écarté pour son coût. Vérifié le 13/09/2026 : sous démarrage sécurisé, le noyau Debian se verrouille **tout seul** (`Kernel is locked down from EFI Secure Boot`), niveau `integrity` mesuré : plus rien ne peut modifier le noyau en marche (module non signé, `kexec`, écriture mémoire), même en administrateur. | S |
| ✅ | **Secure Boot de bout en bout — vérifié le 13/09/2026 (1.13.0)** | La chaîne complète fonctionne sur une machine au démarrage sécurisé activé, disque chiffré compris : le micrologiciel valide `shim`, qui valide GRUB, qui valide le noyau signé Debian (`Loaded X.509 cert 'Debian Secure Boot CA'`). Reste à confirmer sur du matériel réel, hors machine virtuelle | M |
| ✅ | **Applications Flatpak sorties de leur Espace — fermé en 1.16.1** | Dans un Espace ordinaire, une application Flatpak n'est pas dans notre bac à sable : ses permissions s'exercent sous le compte du bureau. `--socket=session-bus`, ou le droit de parler à `org.freedesktop.Flatpak`, systemd ou dconf, lui ouvraient l'exécution hors de tout bac à sable — sous le liseré de l'Espace. Elle est désormais refusée, avec les deux issues : l'ouvrir hors des Espaces, ou « Compte séparé ». Vérifié contre la sortie réelle de `flatpak info --show-permissions` | M |
| ✅ | **Personnel et Travail blindés — 1.16.1, validé sur la VM le 28/09/2026** | Les deux Espaces du quotidien étaient les seuls sans filtre d'appels système (`io_uring` y restait ouvert), sans abandon des capabilities ni session neuve. Blindés, avec les plafonds larges de Navigation (75 %, 4096 tâches). Conséquence réglée au passage : un Espace blindé refusait toute application Flatpak, et plus aucun Espace livré n'en aurait accepté — elles y sont admises sous compte séparé, avec un avertissement. **Éprouvé sur la VM** : Fichiers, Console, éditeur de texte ; presse-papiers vidé en quittant Travail pour le bureau ; sonde d'isolation conforme. **Reste à éprouver** : une application Flatpak sous compte séparé (LibreOffice, lui, n'est pas dans l'image) ; `ptrace` étant refusé, ni `gdb` ni `strace` dans ces Espaces. **À examiner** : dans Navigation, le son d'une vidéo saccade les ~5 premières secondes (VM ou bac à sable ? à comparer avec un Firefox hors Espace) | M |
| ✅ | **Compte séparé par défaut — décidé le 27/09/2026 (1.16.1), validé sur la VM le 28/09/2026** | Chaque Espace livré, et chaque Espace créé, a son compte d'office ; les données déménagent à la première ouverture et reviennent si l'on désactive le réglage. Éprouvé sur une VM installée en 1.16.0 puis mise à jour : déménagement de Personnel et Travail (fichiers présents), les cinq Espaces ouverts sous `cbyr-<uid>-<espace>`, filtre réseau de Banque, Jetable, et la session invitée sans compte séparé, effacée à la déconnexion. **L'invité en est exclu**, des deux côtés (lanceur et service) : sa remise à neuf n'efface que son dossier, et un Espace à compte séparé lui aurait survécu — défaut qui existait déjà pour un invité qui cochait le réglage. Ce que cela coûte, dit à l'utilisateur : « Ajouter une application » refusé (jusqu'à la 1.16.6, ligne suivante) ; applications Flatpak déjà installées dans un Espace à réinstaller ; une application Flatpak ne reçoit pas le fichier choisi dans « Ouvrir un fichier » | S |
| ✅ | **Terminal d'un Espace sous compte séparé — réparé en 1.16.1** | Découvert le 28/09/2026 sur la VM : la Console de Travail « moulinait » sans s'ouvrir. Le compte d'un Espace est créé avec `nologin` (voulu : aucune session possible), et un terminal lance le shell du compte. Comme Flatpak, le bac à sable voit sa propre liste des comptes, où seul ce compte a `/bin/bash` (`codebyr-espace-init` l'écrit dans `/run/user/<uid>`, `wrap_bwrap` la monte par-dessus `/etc/passwd`) ; hors du bac à sable, rien ne change. Au passage, les applications d'un Espace démarrent dans son dossier (`bwrap --chdir`) : le terminal s'ouvrait dans `/`. **Validé sur la VM le 28/09/2026** | S |
| ✅ | **Verr. Maj à la manière de Windows — 1.16.1, validé sur la VM le 28/09/2026** | Demandé par le mainteneur, jamais réalisé : aucune trace dans l'historique. Option XKB `caps:shiftlock` (Verr. Maj + `&` → `1`). Session et écran de connexion : défaut GNOME, désormais livré aussi par le paquet (il ne l'était pas : un nouveau défaut GNOME n'atteignait aucune machine installée). Console et phrase de passe du disque : posé à l'installation seulement — sur une machine installée, la phrase de passe doit continuer à se taper comme à sa création | S |
| ✅ | **« Ajouter une application » sous compte séparé — publié en 1.16.6 le 30/09/2026, validé sur la VM (LocalSend en AppImage, choisi dans la liste de Travail, lancé depuis le menu du Sceau)** | **Piège vu sur la VM** : le premier essai inscrivait au menu le chemin réel du dossier de l'Espace (`/var/lib/codebyr/espaces/…`), qui n'existe pas dans le bac à sable — le dossier y est monté au chemin du bureau. L'Espace répond désormais en chemins relatifs à son dossier, que le bureau place sous `~` ; le nom proposé perd la version et la plateforme (« LocalSend », pas « Localsend- »). C'était le dernier geste refusé sous ce mode, donc par défaut. Le bureau ne voit pas le dossier de l'Espace : c'est **l'Espace qui dresse la liste** de ses programmes (Téléchargements, Partagé… à deux niveaux, sans suivre de lien, reconnus à leurs premiers octets — ELF, AppImage, script), et qui vérifie et rend exécutable celui qu'on choisit ; le bureau n'inscrit au menu que ce qui revient bien formé. Rien ne traverse du bureau vers l'Espace. **Les AppImage**, jamais traitées jusqu'ici, sont lancées avec `--appimage-extract-and-run` : le Blindage interdit l'outil à privilèges (`fusermount3`) qui les monterait. Au passage, pour un Espace ordinaire, le programme choisi est rendu exécutable par descripteur, sans suivre de lien — un lien vers `~/.ssh/id_rsa` posé par l'Espace aurait sinon rendu la clé lisible par tous | M |
| ✅ | **Espace d'échange chiffré — réparé en 1.16.1** | Découvert le 28/09/2026 sur une installation neuve : deux erreurs « cryptsetup » à chaque démarrage, après une phrase de passe pourtant acceptée. Calamares chiffre l'espace d'échange à part et prévoit de l'ouvrir avec un fichier de clé, qu'il ne crée pas quand /boot est en clair ; il ajoute aussi « resume= » sur la ligne du noyau (modules `fstab` et `grubcfg`). Résultat : **aucune machine chiffrée n'avait d'espace d'échange depuis la 1.13.0**, et chaque démarrage l'attendait 90 secondes — `systemd-cryptsetup`, que Debian 13 a sorti de systemd, manquait à l'image : personne n'ouvrait `/etc/crypttab` après le démarrage (dépendance ajoutée). `codebyr-durcir-poste` le passe en clé aléatoire à chaque démarrage (repère PARTUUID, anciennes signatures LUKS effacées, reprise retirée), à l'installation comme par `apt` sur les machines existantes. Éprouvé sur un vrai disque LUKS de test, garde-fous compris, puis **validé sur la VM le 28/09/2026** : plus aucune erreur au démarrage, 9,1 Go d'espace d'échange actif. Hibernation abandonnée — elle ne fonctionnait pas | S |
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
| ✅ | **ISO reproductibles — faites le 30/09/2026 (1.16.8)** | Le même commit, construit sur le poste du mainteneur (WSL, sans UEFI, avec cache) et en CI (machine neuve, UEFI), donne la même ISO octet pour octet. Il a fallu : construire depuis le commit (`git archive` : le disque Windows présentait tout en 777, daté du poste) ; `SOURCE_DATE_EPOCH` = date du commit ; Debian figé la veille du commit (snapshot.debian.org, les lots en cours d'import apparaissent après coup) ; `--apt-indices false` ; plus de cache `bootstrap` ; plus de catalogue Flathub pré-chargé ; mot de passe du live à empreinte fixe ; cache clavier refait après la disposition (setupcon glissait dans l'initrd un fichier au nom aléatoire) ; debconf normalisé (shim-signed s'enregistre deux fois quand la machine qui construit démarre en UEFI) ; caches apt et swcatalog, date de `/proc`. **Conséquence rattrapée à l'essai sur la VM** : sans index apt, l'installeur échouait à retirer les paquets du live (« code d'erreur 100 » — un nom inconnu d'apt fait échouer toute la commande) ; `packages.conf` sépare désormais `remove` (ce que l'image contient) et `try_remove`. **Au passage** : la faille des fichiers en 777 du paquet (1.16.7). Vérifiable par tous : `construire-iso.yml` compare à une empreinte donnée | L |
| ✅ | **L'installation ne dépend plus du serveur du projet — 1.16.1, validé sur la VM le 28/09/2026** | Le 28/09/2026, le serveur éteint par une panne de courant, une installation a échoué : l'installeur lance `apt-get update`, et un réglage de CONSTRUCTION resté dans l'image (`99codebyr-resilient.conf`, 20 nouvelles tentatives de 2 minutes) le faisait attendre au-delà des 10 minutes de Calamares. Retiré de l'image (hook 1000) et des machines installées (`codebyr-durcir-poste`, s'il porte bien son en-tête) : `apt` retrouve ses délais ordinaires, comme pour tout dépôt tiers | S |
| ✅ | **Pas de publication sans CI verte — 1.16.1** | `publish-apt.sh` refuse du code non commité, un commit absent de GitHub, une CI rouge ou en cours. Échappatoire explicite : `CODEBYR_PUBLIER_SANS_CI=1` | S |
| ✅ | **Paquets d'essai écartés de la publication — 1.16.1** | `dist/` reçoit aussi les paquets d'essai ; une version en `~` plus récente que la version publiée serait partie chez tout le parc par `unattended-upgrades`. Écartés, et un paquet plus récent que `VERSION` fait échouer la publication | S |
| ✅ | **Date de péremption du dépôt APT — 1.16.1** | `Valid-Until` à 90 jours : un serveur compromis ne peut plus figer les mises à jour en silence. **Engagement** : republier ou `publish-apt.sh --resigner` avant l'échéance | S |
| ✅ | **Identité du système — 1.16.1** | `/etc/os-release` désignait `codebyr.io`, un domaine inexistant que n'importe qui pouvait acheter, et appartenait à `base-files` : la prochaine version mineure de Debian aurait rebaptisé chaque machine « Debian GNU/Linux 13 » (reproduit sur la 1.16.0). Désormais livrée par `codebyr-tools` et détournée de `base-files` (`dpkg-divert`), sa version suit les mises à jour. Cycle éprouvé : mise à jour, réinstallation de `base-files`, retrait, réinstallation | S |
| ✅ | **Dépendances fermes : `acl`, `libnotify-bin` — 1.16.1** | `setfacl` (service des comptes) n'était là que par ricochet ; `notify-send` dit pourquoi un Espace est refusé, et le refus était muet sans lui | S |

---

## 3. Extension navigateur (bouclier anti-hameçonnage)

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| ✅ | **Manifest V3 — converti ET signé par Mozilla** | Le manifeste est passé en MV3, validé par `web-ext lint`, et l'extension livrée dans l'image porte bien une signature Mozilla (COSE et RSA, vérifié le 15/09/2026 dans le XPI embarqué). C'est ce qui a permis de supprimer le repli « extension non signée + `xpinstall.signatures.required=false` », qui affaiblissait réellement le navigateur pour y installer une protection. **Reste** : automatiser la re-signature à chaque changement de `content.js`, aujourd'hui manuelle (voir docs/signer-le-bouclier.md) | S |
| ✅ | **Homographes internationaux (punycode) — publié en 1.16.3 (bouclier 1.3, signé par Mozilla), éprouvé dans Firefox sur la VM** | Le navigateur donne le nom d'hôte en punycode : « mаbanque.fr », avec un « а » cyrillique, arrivait comme `xn--mbanque-2fg.fr`, ne ressemblait plus à rien, et le bouclier se taisait. Il relit désormais chaque étiquette comme elle s'affiche (RFC 3492), retire les accents, ramène les sosies cyrilliques, grecs et arméniens à leur lettre latine, et applique ses trois signaux à cette silhouette ; l'alerte dit comment l'adresse s'écrit vraiment. Un banc d'essai exécute le vrai `content.js` sous node : l'ancien bouclier restait muet sur les cinq attaques, le nouveau les arrête, sans fausse alerte sur `münchen.de` ni `пример.рф`. **Trouvé en l'éprouvant sur la VM — le bouclier était muet partout depuis la 1.6.0** : chargé, signé, actif, mais sans le droit de lire les pages, qu'une extension Manifest V3 déposée dans le profil ne reçoit pas d'office (mesuré ensuite dans Firefox 140 ESR : Firefox ne découvre pas toujours la copie déposée, et ne lui accorde le droit qu'à une installation par son circuit ordinaire). Firefox l'installe désormais lui-même, par une politique livrée dans `/usr/lib/firefox-esr/distribution/policies.json` (`/etc/firefox-esr/policies` n'est pas lu par ce Firefox) ; les copies déposées sont retirées, et `autoDisableScopes`, que Codebyr mettait à 0, revient à 3. Au passage : le profil de Codebyr n'était posé qu'avec le bouclier ; un Firefox ouvert avant qu'une banque soit déclarée s'était créé le sien — les réglages vont désormais dans le profil que `profiles.ini` désigne (nom simple seulement : le fichier est écrit par l'Espace). **Volontairement** : une étiquette qui mêle les alphabets sans imiter une banque n'alerte pas — Firefox l'affiche déjà en punycode, et une alerte pleine page qu'on apprend à écarter est pire que rien | M |

---

## 4. Produit et expérience

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| ✅ | **Pas de vignettes d'images dans Fichiers — publié en 1.16.5 le 29/09/2026, validé sur la VM (les six fonds d'écran Codebyr, PNG et SVG ; 45 échecs mémorisés effacés)** | Vu sur la VM : chaque image s'affichait avec l'icône générique. Ce n'était pas le bac à sable : `gdk-pixbuf-thumbnailer` (paquet `libgdk-pixbuf2.0-bin`), qui fabrique les aperçus des PNG, JPEG, SVG, WebP…, n'est qu'une recommandation de Nautilus, et l'image est construite sans recommandations. Aucune image n'avait donc d'aperçu, nulle part dans Codebyr. Ajouté à l'image et aux dépendances du paquet ; éprouvé dans le WSL sur les fonds d'écran Codebyr (PNG et SVG). **Second piège, vu sur la VM** : les PNG sont revenus, pas les SVG — Fichiers avait noté en échec les 45 SVG et JXL tentés AVANT la mise à jour (les descriptions de ces formats désignaient l'outil absent), et ne réessaie jamais. `codebyr-space` fait oublier ces échecs une fois, par Espace et sur le bureau | S |
| 🟠 | **Liste de banques préremplie** | L'utilisateur doit aujourd'hui saisir le domaine de sa banque à la main. Une liste « quelle est votre banque ? » rendrait le premier contact évident. ⚠️ Elle doit être construite à partir de données **vérifiées**, jamais devinées : un domaine faux dans une liste blanche casse l'authentification forte. *(Le reste est fait : notification au lancement + page de blocage explicite.)* | M |
| ✅ | **Notifications depuis les Espaces — rendues en 1.14.0** | Perdues depuis la 1.1.0, quand le bus de l'hôte a été retiré des Espaces. Elles reviennent par le relais, et portent le nom de leur Espace. Validé sur machine : en-tête non usurpable, débit limité |
| ✅ | **Icône du Sceau — comprise et refaite en 1.16.1** | Trois tentatives avaient échoué le 23/08/2026, dont deux en la rendant invisible. **La cause n'a été comprise que le 15/09/2026** : le fichier SVG dessine le Sceau en TRAITS (`stroke`), alors que la recoloration symbolique de GNOME agit sur le REMPLISSAGE — la passer en `fill` remplissait les arcs au lieu de les colorer, d'où les taches et les disparitions. La couleur restait donc écrite en dur : un gris moyen, visible partout mais beau nulle part. Le Sceau est désormais **dessiné avec Cairo**, comme le liseré pointillé : il prend la couleur du texte de la barre, suit le thème par construction, et son épaisseur est choisie pour 16 points et non héritée d'un dessin d'affiche. **Ce qui a changé la méthode** : un aperçu des variantes côte à côte (`tools/apercu_icone_sceau.py`), à taille réelle et agrandies, sur fond sombre et clair — choisir en regardant plutôt qu'en imaginant, et une seule déconnexion au lieu de trois | S |
| ✅ | **Ambre (Espace Navigation) invisible sur fond clair — réglé le 13/09/2026** | `#E09A32` (2,28 sur fond clair) devient `#BF7600` : 3,47 sur fond clair, 3,95 sur fond sombre, 5,19 pour le texte de l'étiquette. Parmi les teintes ambrées, c'est la meilleure marge sur les trois à la fois, et à contraste égal la plus éloignée de Jetable pour un deutéranope (7,8 contre 6,3 pour `#BA7B1C`). Gardé par `tests/test_contraste.py` | S |
| 🟡 | **Personnel et Travail indiscernables pour les daltoniens — compensé par le nom écrit** | Azur `#4E8FEF` et Améthyste `#8F6CF0` : écart CIEDE2000 de **2,7** en deutéranopie, **6,7** en protanopie. **Compensé le 13/09/2026** (1.12.2) par un repère qui ne dépend pas de la couleur : l'étiquette du nom sur chaque fenêtre — invisible depuis la 1.0.4, rétablie — et le nom de l'Espace de la fenêtre active dans la barre du haut, à côté du Sceau. Validé sur la VM. **Reste possible** : distinguer aussi les deux teintes, pour la pastille du menu et le liseré seuls. Chiffré par `tests/test_contraste.py` | S |
| 🟡 | **Internationalisation (gettext) — l'anglais publié en 1.18.0 (01/10/2026) ; reste ce que porte l'ISO** | Toutes les chaînes des outils Codebyr étaient en français, en dur — un frein direct à l'adoption hors francophonie (audit, point 5). **Fait en 1.18.0, validé sur la VM dans les deux langues** : le texte du code reste la version française, `po/en.po` en est la traduction anglaise de référence (422 textes) ; une langue sans traduction reçoit l'anglais, pas le français ; compilation sans dépendance et reproductible (`packaging/traductions.py`, .mo pour Python, .json pour l'extension, que gettext ne sait pas servir avec cette règle). Traduits : Bienvenue, lanceurs, extension, Configuration, Assistant, moteur des Espaces et modules, page de blocage (donnée au filtre par codebyr-space : son profil AppArmor lui interdit de lire les traductions, et c'est voulu), menus de Fichiers, vérificateur, noms livrés des Espaces. Garde-fous : aucun texte sans traduction, aucune phrase en dur dans un fichier traduit, aucune variable qui masque `_`, `n_` ou `remplir` (deux pièges réels, en Python et en JavaScript). **Restent** (prochaine ISO) : la page d'alerte du bouclier (à refaire signer par Mozilla), l'écran de démarrage, le diaporama de l'installeur, une entrée « English » au menu de démarrage du live | L |
| ✅ | **Codebyr dès le premier écran — publié en 1.17.2 le 01/10/2026, validé sur la VM** | Quatre défauts vus sur la VM. Avatar des comptes : la spirale Debian (`/etc/skel/.face` de desktop-base), remplacée par le Sceau — déviation dpkg éprouvée sur une copie du système de l'ISO, comptes existants rattrapés sauf image choisie. Démarrage : logo, libellé, message de cryptsetup et invite glissaient vers la gauche quand l'écran changeait de définition ; tout est replacé, et le thème suit désormais les mises à jour (image de démarrage régénérée seulement quand il change). Session : ouverte sur le bureau, sans la vue d'ensemble dont le dock recouvrait « Bienvenue ». Installeur : logo carré lisible sur la barre sombre (prochaine ISO). **Trouvé en route** : une élévation de privilèges dans le remplissage du dossier « Modèles » (voir SECURITY.md) | S |
| 🟠 | **Démarrage sans couture** | GRUB affiche 5 secondes de menu texte à chaque démarrage : le cacher (Échap pour l'ouvrir), sauf si un autre système est installé. Aucun texte technique entre le logo du fabricant, celui de Codebyr et l'écran de connexion ; messages de déverrouillage en français ; temps de démarrage mesuré (`systemd-analyze`) avant de couper | S–M |
| 🟠 | **Les Espaces visibles partout** | L'appartenance à un Espace ne se voit que par le liseré de 3 px. La montrer aussi dans un dock permanent (pastille de couleur sous chaque application ouverte), Alt+Tab et la vue d'ensemble : c'est la signature de Codebyr, et un dock toujours visible aide qui vient de Windows. **Décision à prendre** : dock permanent ou non (Dash to Dock, empaqueté par Debian). Maquette avant le code | M–L |
| ⚪ | **Finitions visuelles** | Mode sombre par défaut ou non ; applications Codebyr harmonisées (en-têtes, icônes, marges) ; fond de l'écran de connexion aux couleurs de Codebyr. Pas de thème GTK sur mesure : les applications modernes l'ignorent en partie et chaque version de GNOME le casse | S |
| 🟠 | **Mode invité : point d'entrée plus clair** | Le menu du Sceau ouvre le sélecteur d'utilisateur GNOME ; l'utilisateur doit encore comprendre qu'il faut choisir « Invité » | S |

---

## 5. Qualité, tests, CI

| | Chantier | Pourquoi | Effort |
|---|---|---|---|
| ✅ | **CI réparée — 27/09/2026** | Rouge du 13 au 27 septembre, sans que rien n'arrête les publications. Quatre causes, dont une que l'échec de ruff masquait : un import inutile (ruff) ; un test d'intégration qui attendait du filtre réseau ce que le correctif 1.12.0 lui interdit — joindre la boucle locale ; les réglages `net.core.bpf_jit_*`, invisibles hors de l'espace de noms réseau initial (conteneur) ; un test dont le nettoyage échouait sur tout compte ordinaire. Le chemin positif du filtre est désormais vérifié sans réseau (`test_filtre_reseau.py`) | S |
| ✅ | **Construction de l'ISO en CI — réussie le 28/09/2026** | Ses deux essais du 20/08/2026 échouaient sur `E: repository 'http://security.debian.org trixie/updates' does not have a Release` : ils tournaient sur le `live-build` d'Ubuntu 24.04 (`3.0~a57`, une branche de 2012), et non sur le même qu'en local, contrairement à ce que cette carte affirmait. Le passage au conteneur `debian:trixie` (12/09) le réglait ; relancé le 28/09/2026, le workflow produit l'ISO en 11 minutes et vérifie ce qu'elle contient. **Le facteur bus de la construction tombe** : une ISO sort d'un checkout propre, sans le poste du mainteneur. Reproductible depuis la 1.16.8 (ligne « ISO reproductibles ») : le workflow compare l'image à une empreinte donnée | M |

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
| ✅ | **`codebyr-space` découpé — 3 168 → 2 076 lignes, 8 étapes, publié en 1.17.0 et 1.17.1 (30/09 et 01/10/2026), validé sur une VM neuve** | Neuf modules partagés, extraits à l'identique (par script pour les plus gros) : `navigateur.py`, `programmes.py`, `chemins.py` (la racine des données, écrite six fois dans trois programmes, ne l'est plus qu'une), `flatpak_espace.py`, `archives.py`, `envois.py`, `journal.py`, `ordres_espace.py` (ce que le bureau demande à un Espace à compte dédié) et `cote_espace.py` (ce que l'Espace fait chez lui). `_lancer` : 400 → 218 lignes, enchaînant des étapes nommées dont un test garde l'ordre. Code mort retiré (`nom_libre`). **Piège évité** : les ordres faisaient exécuter `os.path.realpath(__file__)` — recopié dans un module, ce nom aurait désigné le module, et plus aucun ordre ne serait passé ; codebyr-space s'inscrit désormais dans `ordres_espace.PROGRAMME`, gardé par un test. **Défaut trouvé en relisant** : retirer « Compte séparé » ouvrait VIDE un Espace né sous son compte (tous, depuis 1.16.1) — corrigé en 1.17.1, cycle complet validé sur la VM | M |
| ⚪ | **Commentaires-journaux** | Beaucoup de commentaires racontent la découverte d'un défaut (« Constaté le … »). Précieux pour le pourquoi, mais ils alourdissent le code et vieilliront mal : leur place serait le CHANGELOG ou une fiche de décision, le code n'en gardant que la règle | S |

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
2. **Voir chaque protection agir, pas seulement se charger.** Le bouclier
   anti-hameçonnage est resté muet de la 1.6.0 à la 1.16.2 : chargé, signé,
   actif — et jamais vérifié en train d'alerter. Chaque protection mérite un
   essai qui la montre à l'œuvre, sur la VM ou dans un vrai programme.
3. **Parler une autre langue que le français — fait pour l'essentiel en
   1.18.0.** Tout ce que Codebyr affiche sur une machine installée existe en
   anglais ; une autre langue reçoit l'anglais. Restent, avec la prochaine
   ISO : la page d'alerte du bouclier, l'écran de démarrage, l'installeur et
   une session live en anglais — ce qu'un testeur étranger voit en premier. (Le découpage de
   `codebyr-space`, qui était ici, est fait en 1.17.0 et 1.17.1 ; l'ISO à
   jour et reproductible est publiée, la 1.16.8, le 30/09/2026.)

   *(`xdg-dbus-proxy`, ancien numéro deux, a été tranché le 13/09/2026 : les
   notifications passent par un relais, voir plus haut.)*
