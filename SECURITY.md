# Politique de sécurité

## Lot de sécurité de septembre 2026

**Publié en 1.11.0** : défauts de liens dans les échanges et la préparation des
Espaces, repli sans bubblewrap et restauration destructive corrigés ; réseau
restreint imposé par un namespace sans interface externe et un relais vers le
proxy ; filtre seccomp ajouté au Blindage.

**Publié en 1.12.0** : cinq écarts entre ce que Codebyr promet et ce que le
code appliquait, relevés par une relecture du 12 septembre — détaillés dans
l'historique ci-dessous, et validés sur un bureau GNOME réel.

**Publié en 1.15.0 et 1.16.0** : un Espace peut tourner sous **son propre
compte Unix** — réglage « Compte séparé, par Espace ». Depuis la 1.16.0, ses
applications Flatpak et la carte graphique y fonctionnent. Ce qui n'était qu'un prototype en septembre est
maintenant livré et éprouvé sur machine.

**Publié en 1.16.1** : le compte séparé
devient le **défaut** de chaque Espace (l'invité excepté), Personnel et Travail
sont blindés à leur tour ; une application
Flatpak dont les permissions la feraient sortir d'un Espace ordinaire n'y
s'ouvre plus ; le Jetable perd le micro ; l'identité du système ne désigne plus
un domaine inexistant (`codebyr.io`) et ne peut plus être rendue à Debian par
une mise à jour de `base-files` ; le dépôt APT porte une date de péremption, et
une version ne peut plus être publiée sans CI verte. Détail dans l'historique
ci-dessous.

**Publié en 1.16.8** : deux options de durcissement du noyau au
démarrage (`slab_nomerge`, `page_alloc.shuffle=1`), livrées aussi aux machines
déjà installées.

**Publié en 1.16.7** : de 1.13.0 à 1.16.6, le lanceur de session de
l'écran de bienvenue était modifiable par tous les comptes de la machine —
l'invité compris — et exécuté à l'ouverture de session de chacun. Détail dans
l'historique ci-dessous.

**Publié en 1.16.6** : « Ajouter une application » sous compte séparé,
fait par l'Espace lui-même ; et un programme ajouté à un Espace ordinaire
n'est plus rendu exécutable en suivant un lien.

**Publié en 1.16.4** : le filtre d'appels système du Blindage devient une
liste d'autorisation — tout appel qu'il ne connaît pas est refusé.

**Publié en 1.16.3** : le bouclier anti-hameçonnage était muet sur toutes
les machines depuis la 1.6.0 (droit de lire les pages jamais accordé) ; il est
désormais installé par Firefox lui-même, et reconnaît aussi les adresses
déguisées par des lettres d'autres alphabets (homographes).

**Publié en 1.16.2** : le service root qui prépare les Espaces suivait les
liens symboliques posés dans le dossier d'exécution du bureau. Tout compte du
bureau pouvait s'en servir pour devenir root. Détail dans l'historique
ci-dessous.

Le modèle ci-dessous décrit aussi des versions antérieures ; ne pas déduire
la protection d'un poste de la seule présence de ce document.

## Signaler une vulnérabilité

**Ne signalez pas les vulnérabilités dans les issues publiques.**

Utilisez l'onglet **Security → Report a vulnerability** du dépôt GitHub
(signalement privé), en décrivant : le composant touché, un scénario
d'exploitation concret, et si possible une reproduction pas à pas.

Vous recevrez une réponse dès que possible (projet bénévole — visez quelques
jours, pas quelques heures). Une fois le correctif publié, le signalement est
crédité (sauf souhait contraire).

## Modèle de menace — ce que Codebyr OS protège (et ne protège pas)

**Objectif** : contenir les dégâts des menaces du quotidien — hameçonnage,
pièce jointe piégée, site frauduleux, téléchargement douteux — pour un
utilisateur non technique.

**Garanties visées :**
- Un fichier ouvert « en Jetable » s'exécute **sans réseau** (namespace réseau
  isolé) et dans un dossier personnel jetable : pas d'exfiltration, pas de
  persistance après fermeture.
- Une application compromise dans un Espace n'accède pas aux fichiers des
  autres Espaces : dossiers personnels séparés, `/tmp` isolés, et **bus de
  session privé** — le socket du bus de session de l'hôte n'est jamais monté
  dans le bac à sable (voir « Historique des correctifs »).
- L'Espace Banque — et tout Espace à réseau restreint — ne peut joindre que
  les domaines de la liste blanche de l'utilisateur. La règle vaut pour
  **tout l'Espace**, pas seulement pour son navigateur : depuis 1.11.0, il a
  son propre espace de noms réseau, sans aucune interface vers l'extérieur, et
  ne sort que par le filtre (HTTP, HTTPS et SOCKS5). Un programme qui tenterait
  de passer à côté ne trouve aucun réseau. Ce qui reste possible est dans
  « Limites connues ». **Liste vide = tout est bloqué** : un Espace à réseau
  restreint échoue fermé, jamais ouvert.
- Le **mode invité** est un vrai compte Unix distinct, sans droits
  d'administration, dont la session est effacée à la déconnexion. Le dossier
  personnel de l'utilisateur principal est en `0700` — sur l'image live **comme
  sur le système installé** (`codebyr-durcir-poste`). Le compte invité n'a aucun
  mot de passe utilisable (`*` dans `/etc/shadow`) : ni SSH, ni `su`, ni `sudo`
  ne peuvent s'en servir ; seule sa session graphique locale est autorisée, sans
  mot de passe.
- Le Blindage ajoute : espace de noms utilisateur, abandon de toutes les
  capabilities, session neuve (anti-injection TIOCSTI), filtre d'appels
  système, plafonds mémoire/processus. Actif par défaut sur Banque, Jetable
  et — à partir de 1.12.0 — Navigation ; sur Personnel et Travail à partir de
  1.16.1, avec des plafonds larges (75 % de la mémoire, 4096 tâches). Banque
  et Jetable n'ont pas non plus d'accès direct à la carte graphique
  (`"gpu": false`).
- **Le démarrage est vérifié** quand la machine a le démarrage sécurisé
  activé — le cas de la plupart des PC vendus aujourd'hui. Chaîne éprouvée le
  13/09/2026 : micrologiciel → `shim` → GRUB → noyau signé par Debian. Le noyau
  s'y verrouille alors de lui-même — niveau `integrity` : plus rien ne peut
  **modifier** le noyau en marche (module non signé, `kexec`, écriture directe
  en mémoire), même en administrateur. Le niveau `confidentiality`, qui
  interdirait aussi de le **lire**, n'est pas activé : il casserait des usages
  ordinaires comme la veille prolongée.
- **Le disque est chiffré par défaut** depuis 1.13.0 : la case est cochée
  d'avance à l'installation (LUKS2, argon2id). Un ordinateur perdu ou volé ne
  livre ni les Espaces, ni leurs instantanés, ni les domaines bancaires
  déclarés. `/boot` reste en clair, séparé : il ne contient que le noyau, et
  c'est ce qui permet de saisir la phrase de passe avec le clavier choisi à
  l'installation plutôt qu'avec celui de GRUB, toujours QWERTY. Aucun fichier
  de clé n'est déposé sur cette partition — vérifié sur une installation réelle.
  L'espace d'échange est chiffré à part, avec une clé tirée au hasard à chaque
  démarrage (1.16.1) : ce qu'il contient devient illisible à l'extinction.
  Jusqu'en 1.16.0, il restait inutilisé — l'installeur l'avait réglé pour un
  fichier de clé jamais créé, d'où deux erreurs « cryptsetup » à chaque
  démarrage.
- Un domaine autorisé dont l'adresse désigne la machine ou le réseau local
  (bouclage, plages privées, lien local) est refusé par le filtre réseau, qui
  se connecte à l'adresse qu'il a vérifiée et non à un nom résolu une seconde
  fois (1.12.0).
- Les **notifications** d'un Espace s'affichent sous le nom de cet Espace, que
  l'application ne choisit pas : une page piégée ouverte en Jetable ne peut pas
  signer une fausse alerte « Banque ». Leur texte est nettoyé (ni balises, ni
  caractères de contrôle) et borné, leur débit limité, et les boutons d'action
  refusés — ils rouvriraient un canal vers l'Espace. Le bus de session de
  l'hôte, lui, n'entre toujours pas : seule une socket transportant deux
  chaînes de texte relie l'Espace au bureau (1.14.0).
- Le presse-papiers ne « suit » pas passivement d'un Espace à l'autre : il est
  vidé dès que le focus passe à un Espace différent de celui qui l'a rempli —
  **et aussi dès qu'on quitte un Espace sensible** (Blindage ou réseau
  restreint) vers le bureau ou une application ordinaire. Sans cette seconde
  règle, la frontière ne se franchissait pas, elle se contournait : copier dans
  Banque, cliquer sur le bureau, et le secret restait collable partout. Un
  transfert délibéré reste possible (menu « Transférer vers… »).

**Hors périmètre (assumé) :**
- Exploits noyau : l'isolation repose sur les namespaces Linux (bubblewrap),
  pas sur de la virtualisation matérielle. Un attaquant disposant d'un 0-day
  noyau peut s'échapper. C'est une limite assumée du modèle.
- Attaquant physique, evil maid, matériel compromis.
- Le compositeur Wayland et le serveur audio sont partagés entre Espaces
  (fenêtres et son doivent bien s'afficher quelque part) : un Espace ne peut pas
  lire l'écran d'un autre via Wayland, mais ce canal n'a pas l'étanchéité d'une VM.
- **Micro** : le socket PipeWire partagé vaut accès au microphone. Un Espace
  peut le refuser (`"audio": false` dans le registre) — c'est le cas de Banque
  par défaut, et de Jetable depuis 1.16.1 : c'est là que s'ouvrent les liens
  douteux. Le son de sortie part avec lui, par le même canal. Partout ailleurs,
  le son fonctionne, donc le micro est joignable.
- **Un compte Unix par Espace — par défaut depuis 1.16.1, sauf exceptions.**
  Jusqu'à la 1.16.0, les données des Espaces vivaient par défaut sous
  `~/.local/share/codebyr/espaces/`, sous votre compte : le bac à sable
  empêchait une application *lancée dans un Espace* d'en sortir, mais toute
  application lancée normalement (hors Espace), ou tout code qui s'échapperait
  du bac à sable, lisait l'ensemble. Depuis la 1.16.1, chaque Espace a son
  compte d'office, et le noyau vérifie la frontière à chaque ouverture de
  fichier. La limite demeure là où ce réglage ne s'applique pas : un Espace
  pour lequel vous le désactivez, et les Espaces de l'**invité**, qui n'en ont
  jamais — sa session s'efface à la déconnexion, et un Espace à compte séparé,
  rangé hors de son dossier, survivrait à l'invité suivant.

**Principe de communication** : Codebyr OS « réduit drastiquement les dégâts » —
jamais « rend invulnérable ». Toute contribution qui gonflerait la promesse
au-delà de ce que le code garantit sera refusée.

## Intégrité des versions

Chaque ISO est signée avec la clé GPG du projet. Le fichier `SHA256SUMS` (empreinte
de l'ISO) est accompagné de `SHA256SUMS.asc` (signature détachée). La clé publique
est dans le dépôt (`codebyr-signing-key.asc`), empreinte
`E6FB6616EC58E15F40DA876CB1E8C803CE596E68`. Procédure de vérification : voir le
README. N'utilisez jamais une ISO dont la signature n'est pas valide.

La même clé signe le dépôt APT, qui installe des paquets **en root** sur les
machines Codebyr via `unattended-upgrades` : c'est l'actif le plus sensible du
projet. Depuis 1.16.1, ce dépôt porte une date de péremption (`Valid-Until`,
90 jours) : un serveur compromis ne peut plus servir indéfiniment un ancien
dépôt signé pour priver le parc de ses correctifs sans que rien le signale. Sa protection, sa hiérarchie cible (clé maîtresse hors ligne +
sous-clés), la procédure de renouvellement et la conduite à tenir en cas de fuite
sont décrites dans [docs/chaine-de-signature.md](docs/chaine-de-signature.md) —
qui indique aussi, sans détour, ce qui n'est **pas encore** en place.

## Durcissement de la base

**Un compte Unix par Espace (1.15.0, par défaut depuis 1.16.1).** Ce compte n'a
ni mot de passe utilisable ni shell de connexion (`nologin`) : il ne peut ouvrir
aucune session. Dans son bac à sable seulement, une copie de la liste des
comptes lui donne `/bin/bash`, pour que ses terminaux fonctionnent (1.16.1). Un
Espace tourne sous son propre compte système : son dossier lui appartient (0700),
hors du dossier personnel, et le compte du bureau ne peut pas le lire. Ce qui
s'échappe du bac à sable retrouve alors ce compte-là, et rien d'autre. Le
service qui prépare ces comptes tourne en root, sur activation de socket ; il
n'exécute aucune commande venant du client, ne prend aucun chemin de lui,
n'ouvre jamais le dossier d'exécution du bureau (donc jamais son bus de
session), et refuse toute demande venant d'un Espace — sans quoi « jetable »
ferait ouvrir « banque ». Ce que le bureau veut ouvrir est exécuté par un
premier processus lancé sous le compte de l'Espace, sans aucun privilège : root
ne voit jamais la commande. Les données ne passent jamais par root non plus :
le bureau emballe ce qu'il a le droit de lire, l'Espace déballe chez lui.

Debian stable, AppArmor actif — avec un profil propre au filtre réseau des
Espaces depuis 1.12.1, et au service des comptes d'Espaces depuis 1.15.0 —,
pare-feu nftables (`policy drop` en entrée),
Wayland, mises à jour de sécurité automatiques (`unattended-upgrades`),
`sysctl` durcis (kptr_restrict, ptrace_scope, protections liens/fifo…, et
depuis 1.12.0 : BPF non privilégié, kexec, userfaultfd, TIOCSTI, compteurs de
performance — livrés par le paquet, donc aussi aux machines déjà installées),
surface applicative minimale (`--apt-recommends false`).

## Limites connues (transparence)

- **Bouclier : signé, ou absent.** Le repli « extension non signée +
  `xpinstall.signatures.required=false` » a été supprimé : il affaiblissait
  réellement le navigateur (plus aucune vérification de signature d'extension
  dans ce profil) pour y installer une protection. Sans `.xpi` signé par
  Mozilla, `codebyr-space` n'installe rien et le dit. Corollaire à connaître :
  **modifier `content.js` n'a aucun effet tant que l'extension n'a pas été
  re-signée** (le `.xpi` signé est scellé) — un test de la CI le vérifie.
- **« Ce site est légitime » ne vaut que pour un Espace.** Lever une alerte du
  bouclier dans Navigation ne la lève pas dans Personnel : chaque Espace a son
  propre profil Firefox, donc sa propre liste de sites approuvés. C'est
  cohérent avec le cloisonnement — une décision prise dans un compartiment n'en
  sort pas — mais cela surprend : le même site peut déclencher l'avertissement
  une seconde fois ailleurs.
- **Détection d'imitation, pas de vérité absolue** : le bouclier compare des
  noms de domaine (même nom sous une autre extension, faute de frappe,
  homoglyphe, nom utilisé comme étiquette). Il peut se tromper dans les deux
  sens ; l'utilisateur peut lever définitivement une alerte sur un site donné.
  Ce n'est pas une liste noire d'hameçonnage, et ça ne remplace pas celle de
  Firefox.
- **Filtre réseau d'un Espace restreint : les domaines autorisés restent
  joignables.** Le filtre s'impose à tout l'Espace (voir plus haut), mais il
  juge des NOMS : un programme hostile déjà exécuté dans l'Espace peut joindre
  les domaines de la liste — sur n'importe quel port — puisqu'ils sont
  autorisés. Le réseau local et la machine elle-même lui restent fermés, même
  si un domaine autorisé y mène (1.12.0).
- **Compositeur Wayland et audio (PipeWire) partagés** entre Espaces. Comme le
  presse-papiers Wayland dépend du compositeur, il est techniquement commun à
  tous les Espaces : la protection Codebyr (vidage au changement d'Espace,
  transfert explicite) est **temporelle** — elle réduit la fenêtre de fuite,
  elle n'apporte pas l'étanchéité d'une VM. Soupape :
  `~/.config/codebyr/presse-papiers-libre` désactive le vidage automatique.
- **Applications Flatpak** : proviennent de Flathub — confiance déléguée à
  Flathub et à l'éditeur de chaque application. Dans un Espace **ordinaire**,
  une application Flatpak ne passe pas par le bac à sable de Codebyr : elle a
  le sien, et ce sont ses permissions qui s'exercent, sous votre compte.
  Depuis 1.16.1, celles qui la feraient sortir de l'Espace la font refuser :
  bus de session du bureau, services qui exécutent pour elle
  (`org.freedesktop.Flatpak`, systemd, dconf), système de fichiers entier,
  dossier d'exécution du bureau, et — pour une application installée pour
  toute la machine — les parties décisives de votre dossier personnel
  (données des Espaces, lanceurs, démarrage de session). Ses **autres**
  permissions restent les siennes : une application installée pour toute la
  machine peut, par exemple, lire votre dossier Téléchargements, et ses
  données sont communes à tous les Espaces (c'est dit à l'écran). Sous
  « Compte séparé », le compte de l'Espace borne tout cela. Un Espace **blindé**
  n'accepte une application Flatpak que sous compte séparé, et le dit : elle
  y a le bac à sable de Flatpak, pas le Blindage de l'Espace. Banque et
  Jetable les refusent toujours — leur promesse porte sur le réseau.
- **Sous compte séparé, « Ajouter une application » ne prend qu'un programme
  de l'Espace** (depuis 1.16.6) : celui que son navigateur a téléchargé, ou
  qu'on lui a envoyé. Le bureau ne voit pas le dossier de l'Espace ; c'est
  l'Espace qui dresse la liste de ses programmes et rend exécutable celui
  qu'on choisit. Une AppImage y est lancée décompressée, sans FUSE : le
  Blindage interdit l'outil à privilèges qui la monterait.
- **Compte séparé : un Espace abandonné est refermé.** Un Espace vit dans sa
  propre portée systemd : il survit donc à l'arrêt du service des comptes (mise
  à jour, `systemctl stop`). Jusqu'en 1.16.0, le lanceur qui le tenait s'en
  allait ensuite sans que personne le sache, et l'Espace restait ouvert
  indéfiniment — avec l'accès à l'affichage du bureau, et à la carte graphique
  depuis cette version. Constaté le 15/09/2026 sur une machine d'essai. Le
  service referme désormais, à son démarrage et à chaque réveil, tout Espace
  qu'aucun service ne suit plus et qui n'a plus aucune application ouverte. Un
  Espace abandonné mais dont l'utilisateur a encore des fenêtres à l'écran
  n'est pas tué : il est signalé au journal, et refermé dès la dernière.
- **Compte séparé : la carte graphique.** Depuis la 1.16.0, un Espace qui y a
  droit reçoit un accès NOMINATIF et TEMPORAIRE aux nœuds de rendu de
  `/dev/dri`, posé à son ouverture et repris à sa fermeture — le même mécanisme
  que `logind` applique à une session d'utilisateur. Seuls les nœuds de rendu
  sont accordés : ceux qui pilotent l'écran (modes, sorties) ne le sont jamais.
  Banque et Jetable, dont le réglage est à « non », n'y touchent pas, et une
  pièce jointe non plus. Cet accès n'est pas une surface nouvelle : un Espace
  ordinaire l'avait déjà, par les droits de votre propre session.
- **Compte séparé : ouvrir un fichier depuis une application Flatpak.** Depuis
  la 1.16.0, les applications Flatpak s'ouvrent sous compte séparé, avec leurs
  portails — la fenêtre « Ouvrir un fichier » s'affiche, et elle ne montre que
  les fichiers de l'Espace. Mais l'application ne **reçoit** pas le fichier
  choisi : le passage se fait normalement par le « portail des documents », qui
  monte un système de fichiers FUSE au moyen de `fusermount3`, un programme
  setuid. Or un Espace tourne sous `no-new-privs`, qui interdit précisément
  qu'un programme acquière des privilèges — la protection qui empêche ce qui
  s'échapperait du bac à sable d'atteindre `sudo`, `pkexec` ou leurs failles.
  Mesuré le 15/09/2026 : `Can't mount path /run/user/<uid>/doc`. Le choix est
  assumé — garder la protection, et dire la limite — plutôt que de l'affaiblir
  pour une commodité. Les applications qui déclarent un accès aux fichiers
  (`--filesystem`) ne s'en tirent pas mieux : le passage par ce portail ne se
  contourne pas côté application.
- **Compte séparé : le bureau reste au-dessus.** Il dit à l'Espace quoi
  exécuter — il pouvait déjà tout exécuter sous sa propre identité, donc cela ne
  lui donne rien de neuf. L'inverse n'est pas vrai : un Espace ne commande rien
  au bureau, et ne peut pas demander l'ouverture d'un autre Espace.
- **Sites bancaires réels et liste blanche** : beaucoup de banques chargent des
  ressources depuis des domaines tiers (CDN, prestataire 3-D Secure, captcha).
  Une liste blanche saisie à la main peut donc casser une authentification
  forte. Ajoutez le domaine signalé dans la page de blocage, ou utilisez un
  autre Espace le temps de l'opération — mais ne désactivez pas la protection.

## Historique des correctifs de sécurité

| Version | Correctif |
|---|---|
| 1.17.2 | **Élévation au rang de root par le remplissage du dossier « Modèles »** (présent depuis 1.10.0). `codebyr-durcir-poste` tourne en root à chaque mise à jour de `codebyr-tools`, donc sans personne devant l'écran (`unattended-upgrades`). Pour chaque compte de `/home`, il lisait `XDG_TEMPLATES_DIR` dans `~/.config/user-dirs.dirs`, créait ce dossier, y copiait les modèles, puis remettait le dossier au compte par `chown`. Ce fichier appartient au compte : y écrire `"$HOME/../../etc"` faisait remettre `/etc` au compte à la mise à jour suivante — donc tout le système. Un lien `~/Modèles` → `/etc` produisait le même effet (`chown` suit les liens). Atteignable depuis tout compte non administrateur, l'invité compris si une mise à jour tombait pendant sa session. Tout ce qui écrit dans un dossier personnel est désormais exécuté sous l'identité de son propriétaire (`setpriv`, les trois identifiants changés, `--no-new-privs`, environnement remis à zéro), et seulement si le dossier lui appartient : un chemin détourné ne mène plus qu'où le compte pouvait déjà écrire. Relevé le 01/10/2026 en relisant le script pour y ajouter l'avatar ; attaque reproduite (le dossier victime passait au compte attaquant), puis vérifiée fermée. Un test la rejoue, chemin détourné et lien, dans un espace de montage privé. Aucune exploitation connue. |
| 1.16.7 | **Lanceur de session modifiable par tous (depuis 1.13.0).** Le paquet `codebyr-tools` installait `/etc/xdg/autostart/codebyr-bienvenue.desktop` et `/usr/share/icons/hicolor/scalable/apps/io.codebyr.Bienvenue.svg` en `0777`. Le premier est lu à l'ouverture de CHAQUE session : n'importe quel compte de la machine — l'invité, sans mot de passe, ou le compte d'un Espace sorti de son bac à sable — pouvait y inscrire une commande exécutée ensuite sous le compte de chaque utilisateur qui se connecte. Cause : le paquet publié se construit depuis un disque Windows, où tout apparaît en `0777`, et `build-deb.sh` ne normalisait que des dossiers choisis ; `verifier_paquet.py` ne contrôlait les droits que sur sa propre liste de fichiers ; la CI, qui construit depuis un checkout git aux droits justes, ne pouvait pas le voir. Désormais tout le paquet part de `0644`/`0755` et seuls les programmes reçoivent le bit d'exécution ; le vérificateur lit les droits de TOUTES les entrées dans l'archive ; un test construit le paquet depuis une copie des sources toute en `0777`. La mise à jour réécrit les deux fichiers (ce ne sont pas des fichiers de configuration) : un contenu altéré est remplacé. Relevé le 30/09/2026 en préparant l'ISO reproductible ; aucune exploitation connue. |
| 1.16.6 | **« Ajouter une application » rendait exécutable en suivant les liens.** Pour un Espace ordinaire, le programme choisi dans le dossier de l'Espace était rendu exécutable (`chmod 0755`) par son nom, depuis le compte du bureau. Un Espace compromis pouvait y placer un lien vers `~/.ssh/id_rsa` : le choisir rendait la clé privée lisible par tous les comptes de la machine. Le fichier est désormais ouvert sans suivre de lien et modifié par son descripteur, et seulement s'il est un fichier ordinaire. Sous compte séparé, le geste — nouveau en 1.16.6 — est fait par l'Espace lui-même, sur ses propres fichiers. |
| 1.16.4 | **Filtre d'appels système en liste de refus.** Sous Blindage, 24 appels étaient refusés et tout le reste passait — y compris l'appel qu'un futur noyau ajoutera, que personne n'aura examiné. Le filtre n'autorise plus que les appels connus de libseccomp 2.6.0 (liste figée dans le code), moins les refus (EPERM) et 39 appels écartés ; tout autre appel reçoit ENOSYS. Établi en mesurant d'abord, sur la VM, ce que les applications réelles des Espaces appellent (Firefox, Fichiers, Flatpak, la console) : six candidats ont servi et restent permis. |
| 1.16.3 | **Bouclier anti-hameçonnage muet depuis la 1.6.0.** Passé en Manifest V3 le 23/08/2026, il demande à Firefox le droit de lire les pages ; pour une extension Manifest V3, Firefox ne l'accorde d'office qu'à une installation par son circuit ordinaire. Codebyr déposait l'extension dans le profil : Firefox ne la découvrait pas toujours et, découverte, ne lui accordait pas toujours ce droit. Elle restait chargée, signée, active — et ne s'exécutait sur aucune page. Constaté le 29/09/2026 en l'éprouvant sur la VM ; mesuré ensuite dans Firefox 140 ESR. L'extension est désormais installée par Firefox lui-même, par une politique livrée dans son dossier `distribution` ; les copies déposées sont retirées, et le réglage `extensions.autoDisableScopes` — que Codebyr mettait à 0, désarmant pour toutes les extensions le garde-fou de Firefox contre les dépôts silencieux — revient à sa valeur par défaut. |
| 1.16.3 | **Bouclier anti-hameçonnage aveugle aux homographes.** Le navigateur donne au script le nom d'hôte en punycode : « mаbanque.fr », écrit avec un « а » cyrillique, arrivait comme `xn--mbanque-2fg.fr` et ne ressemblait plus à la banque protégée — alors qu'à l'écran l'adresse est identique à la vraie. Le bouclier relit désormais chaque étiquette comme elle s'affiche (RFC 3492), retire les accents, ramène les sosies cyrilliques, grecs et arméniens à leur lettre latine, et compare cette silhouette. Un banc d'essai exécute le vrai `content.js` : l'ancien bouclier laissait passer les cinq attaques essayées. Extension re-signée par Mozilla (1.3). |
| 1.16.2 | **Élévation au rang de root par le service des comptes d'Espaces** (présent depuis 1.15.0). `codebyr-uid` tourne en root et présente à un Espace les sockets du bureau, pris dans `/run/user/<uid>`, un dossier qui appartient au demandeur. Il suivait les liens symboliques. Le demandeur y créait `wayland-9`, lien vers `/etc/shadow`, puis demandait un Espace avec cet affichage. Le service montait le fichier chez l'Espace, puis lui en accordait l'écriture par `setfacl`, qui suit les liens et tourne hors du profil AppArmor. Tout compte du bureau devenait root, l'invité compris jusqu'en 1.16.0, comme tout programme lancé sous le compte de l'utilisateur, sans mot de passe. Même classe de défaut : `chmod` de la socket d'ordres dans un dépôt où le bureau écrit (course), et la destination du montage, dans le dossier de l'Espace. Le service ouvre désormais chaque socket sans suivre de lien (`O_PATH`, `O_NOFOLLOW`) et vérifie le descripteur : un socket, au demandeur. `mount`, `setfacl` et `chmod` agissent sur ce descripteur (`/proc/self/fd/N`), jamais sur un nom échangeable entre-temps. La destination est créée sans suivre de lien et montée sans résolution de chemin (`--no-canonicalize`). Attaque reproduite puis vérifiée fermée le 29/09/2026 ; un test la rejoue. |
| 1.16.1 | **Applications Flatpak sorties de leur Espace.** Dans un Espace ordinaire, une application Flatpak n'est pas dans le bac à sable de Codebyr, et ses permissions s'exercent sous le compte du bureau. Une application déclarant `--socket=session-bus`, ou le droit de parler à `org.freedesktop.Flatpak` (`flatpak-spawn --host`), à systemd ou à dconf, pouvait donc exécuter du code hors de tout bac à sable — la même classe de sortie que celle fermée en 1.1.0 — en portant le liseré de l'Espace. Ces permissions, et l'accès au système de fichiers entier, au dossier d'exécution du bureau ou aux parties décisives du dossier personnel, font désormais refuser l'application, avant tout lancement. Vérifié contre la sortie réelle de `flatpak info --show-permissions`, surcharges comprises. |
| 1.16.1 | **Adresses d'aide vers un domaine inexistant.** `/etc/os-release`, l'installeur Calamares (aide, problèmes connus, notes de version, dons) et l'extension GNOME désignaient `codebyr.io`, qui n'existe pas : quiconque l'aurait acheté recevait les demandes d'aide — et de dons — des utilisateurs d'une distribution de sécurité. Adresses remplacées par `os.codebyr.dev` et le dépôt GitHub ; un test refuse désormais tout domaine `codebyr` autre que `codebyr.dev`. |
| 1.16.1 | **Un Espace de l'invité pouvait survivre à sa session.** La remise à neuf de l'invité n'efface que son dossier personnel ; un Espace à compte séparé vit hors de ce dossier. Un invité qui cochait « Compte séparé » laissait donc le navigateur, les cookies et les fichiers de ses Espaces à l'invité suivant. L'invité n'obtient plus jamais de compte séparé : ni le lanceur ne le demande, ni le service ne l'accorde. *Non traité* : d'éventuels restes laissés sur une machine par un invité en 1.15–1.16. |
| 1.16.1 | **Micro ouvert dans le Jetable.** L'Espace où s'ouvrent les liens douteux avait accès au socket PipeWire, donc au microphone. Coupé par défaut. |
| 1.13.0 | **Disque non chiffré par défaut.** Le chiffrement était proposé sans être coché : la protection dépendait de l'utilisateur qui pense à la cocher. Case cochée d'avance, LUKS2/argon2id, /boot séparé en clair (aucune donnée, aucun fichier de clé) pour que la phrase de passe se tape avec le clavier de l'installation — GRUB, qui la demandait auparavant, lit toujours en QWERTY et rendait un disque AZERTY impossible à ouvrir. |
| 1.12.1 | **Filtre réseau non confiné.** Le seul programme qui parle au réseau pour un Espace restreint tournait hors bac à sable, avec tous les droits de l'utilisateur. Il est désormais confiné par AppArmor (socket héritée, résolution, connexions sortantes, journal des refus — rien d'autre) et démarre en Python isolé, sans module du dossier personnel. |
| 1.12.0 | **Navigation, l'Espace le plus exposé au web, n'était pas blindé** : pas de filtre d'appels système (io_uring, qui contourne seccomp et reste une source majeure de failles noyau, y était accessible), pas d'abandon des capabilities ni de session neuve. Blindé par défaut, avec des plafonds adaptés à un navigateur (75 % de la mémoire, 4096 tâches) pour ne pas tuer une session chargée. |
| 1.12.0 | **Le filtre réseau pouvait servir de passage vers le réseau local.** Il jugeait le nom, jamais l'adresse résolue, et tourne sur l'hôte : un domaine autorisé pointant vers 127.0.0.1 ou la box ouvrait à un Espace restreint un réseau qu'il ne voit pas. Les adresses non publiques sont refusées, en HTTP, HTTPS et SOCKS5. |
| 1.12.0 | **Carte graphique offerte à tous les Espaces**, sans condition. Retirée de Banque et de Jetable, et de toute pièce jointe examinée. |
| 1.12.0 | **Menu du Sceau** : identifiant d'Espace non échappé dans une ligne de commande (arguments supplémentaires passés à `codebyr-space`, dont un `--` choisissant le programme lancé) et couleur non vérifiée dans les feuilles de style. Aucun chemin normal ne produisait ces valeurs ; le registre est désormais vérifié à la lecture comme à l'écriture. |
| 1.1.0 | **Sortie de bac à sable par le bus de session.** Le socket `$XDG_RUNTIME_DIR/bus` de l'hôte était monté (en lecture seule) dans chaque Espace. Un `--ro-bind` ne protège pas un socket : le noyau ne refuse l'écriture sur un montage read-only que pour les fichiers, répertoires et liens. Du code hostile dans un Espace pouvait donc parler au bus de session complet, appeler `systemd --user` (`StartTransientUnit`) et exécuter du code **hors** du bac à sable, sous l'identité de l'utilisateur — puis lire les données de tous les autres Espaces. Le socket n'est plus exposé ; chaque Espace n'a que son bus privé (`dbus-run-session`). |
| 1.1.0 | **Dossier personnel lisible par le compte invité sur le système installé.** Le `chmod 700` n'existait que dans l'image live, sur un compte supprimé à l'installation. Désormais appliqué à l'installation **et** rattrapé par `apt` sur les postes existants (`codebyr-durcir-poste`). |
| 1.1.0 | **Mot de passe du compte invité, public et identique partout** (`invite`/`invite`). Remplacé par un compte sans mot de passe utilisable (`*`), dont seule la session graphique locale est autorisée. |
| 1.1.0 | **Espace à réseau restreint sans domaine = réseau libre.** Le filtre ne démarrait pas si la liste blanche était vide : l'Espace Banque avait alors un accès complet à Internet alors que l'interface annonçait une restriction. Il échoue désormais fermé. |
