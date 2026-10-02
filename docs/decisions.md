# Fiches de décision — l'histoire des règles du code

Le code de Codebyr dit **la règle** et **sa raison**, au présent. Ce qui a été
constaté, quand, et comment on y est arrivé vit ici : un commentaire n'est pas
un journal (analyse externe du 01/10/2026, point 2.3). Les failles de sécurité,
elles, sont décrites dans [SECURITY.md](../SECURITY.md), et chaque version
dans le [CHANGELOG](../CHANGELOG.md).

Une règle du code qui paraît excessive a souvent son histoire ci-dessous :
lisez-la avant de la retirer.

---

## Le service des comptes d'Espaces (`usr/lib/codebyr/codebyr-uid`)

**Ne jamais ouvrir le dossier d'exécution du bureau** — mesuré le 14/09/2026 :
l'ouvrir rendait joignable le bus de session du bureau, donc `systemd --user`,
donc l'exécution hors du bac à sable.

**S'arrêter au repos** — constaté le 14/09/2026 sur la machine d'essai : le
service restait en mémoire jusqu'au redémarrage dès qu'un Espace avait été
ouvert une fois.

**Le premier processus annonce qu'il écoute** — constaté le 14/09/2026 : un
premier processus mort au lancement ne se voyait nulle part, la socket
d'ordres (créée par root) acceptant les connexions sans que personne y
réponde ; le bureau attendait indéfiniment.

**Tout ou rien à la préparation** — constaté le 14/09/2026 : le premier
processus refusait de démarrer alors que le socket Wayland était déjà monté
chez l'Espace et le droit déjà accordé ; rien n'était défait, et l'essai
suivant a monté un second socket par-dessus le premier.

**Retirer les montages empilés avant d'en poser un** — constaté le 14/09/2026 :
la fermeture n'en retirait qu'un, et le dossier survivait à l'Espace.

**Ne taire aucun démontage refusé** — constaté le 14/09/2026 : la fermeture se
disait réussie en laissant le montage en place.

**L'Espace écrit dans son dossier d'exécution sans prise sur les sockets
présentés** — mesuré le 15/09/2026 : un montage lié ne peut être ni supprimé,
ni renommé, ni remplacé par un lien, fût-ce par le propriétaire du dossier.

**La carte graphique par droit nominatif** — mesuré le 15/09/2026 : sans lui,
un Espace sous compte séparé dessine avec le processeur.

**N'attendre que les enfants directs du premier processus** — constaté le
15/09/2026, au journal : « abandonné par un service arrêté, mais encore
utilisé : conservé », la fenêtre venant d'être fermée. Les portails et
auxiliaires Flatpak démarrés par le bus survivent aux fenêtres.

**Refermer les Espaces abandonnés** — constaté le 15/09/2026 sur la machine
d'essai : un Espace fermé depuis longtemps gardait l'accès à
`/dev/dri/renderD128`, après un arrêt du service pendant qu'il était ouvert.

**Ouvrir les sockets du bureau sans suivre de lien, et travailler sur le
descripteur** — reproduit le 29/09/2026 : un lien `wayland-9` → `/etc/shadow`
dans le dossier d'exécution du bureau faisait de tout compte du bureau un root
(SECURITY.md, 1.16.2). `/proc/self/fd/N` mène au fichier ouvert sans relire son
nom : mesuré le même jour avec mount (util-linux 2.41) et setfacl (acl 2.3.2) ;
sans `--no-canonicalize`, mount atterrissait sur la cible d'un lien posé à la
destination.

**Reconnaître un montage par la table du noyau** — trouvé le 02/10/2026 par le
banc d'essai du service (`tests/uid_harnais.py`) : `os.path.ismount` ne voit
pas un montage lié venu du même système de fichiers ; sur un `/run` d'un seul
tenant, la fermeture laissait le montage et le droit sur le socket du bureau
(SECURITY.md, 1.20.1).

## Le lanceur des Espaces (`usr/bin/codebyr-space`) et ses modules

**Créer le dossier du journal des refus avant le filtre** — constaté le
14/09/2026 : pour un Espace à compte dédié, personne ne le créait ; les refus
de la Banque n'étaient notés nulle part, et Configuration ne pouvait plus
proposer d'autoriser le domaine manquant.

**Vérifier les associations de fichiers posées, pas l'absence d'erreur** —
constaté le 14/09/2026 : elles n'étaient pas posées et la préparation se disait
réussie ; ce sont elles qui ouvrent sous cloche un fichier venu d'ailleurs.

**Poser les droits des boîtes par le descripteur, jamais par une ACL par
défaut** — reproduit dans le WSL avec deux comptes sans privilège le
14/09/2026 : le masque d'une ACL suit le mode de création (« effective: --- »),
et le bureau ne pouvait rien relever, sans que rien ne le dise.

**Oublier une seule fois les échecs de vignettes** — constaté le 29/09/2026 sur
la VM : 45 échecs, tous antérieurs à l'arrivée de l'outil qui les fabrique.

**Flatpak et le dossier d'exécution** — mesuré le 15/09/2026 : Flatpak monte un
bac à sable sous le dossier d'exécution, et échoue s'il n'est pas à la place
attendue (`/run/user/<uid>`) ; sous un chemin de notre invention, il remontait
jusqu'à un dossier de root (« Failed to sync »). D'où, en 1.16.0, le dossier
d'exécution canonique de chaque Espace (`comptes.py`, `bac_a_sable.py`), et le
bus de l'Espace à sa place, sur lequel le portail démarre de lui-même
(`codebyr-espace-init`).

**La carte graphique : le nœud de rendu seul** — mesuré le 15/09/2026 : il
suffit à l'accélération matérielle, et c'est le seul que logind ouvre à une
application ordinaire.

**Démarrer dans le dossier de l'Espace** (`--chdir`) — 28/09/2026 : sous compte
séparé, un terminal s'ouvrait dans `/`, et `ls` montrait le système.

**Un shell dans le bac à sable** (`codebyr-espace-init`) — constaté le
28/09/2026, quand le compte séparé est devenu le défaut : tout terminal lançait
`nologin` et « moulinait » sans jamais s'afficher.

**La vérification d'isolation refuse de tourner depuis un Espace** — lancée
depuis Banque le 12/09/2026, elle a annoncé « aucun réseau » pour un Espace
ordinaire, puis « ne publiez pas cette version ».

**Ouvrir les dossiers intermédiaires en O_PATH** (`fichiers_surs.py`) —
constaté le 14/09/2026 : toute écriture dans le dossier d'un Espace à compte
dédié échouait, le compte ne pouvant lire `/var/lib/codebyr/espaces/<uid>`.

**Refermer toujours le bout transmis d'un ordre** (`ordres_espace.py`) — vu dans
le WSL le 14/09/2026 : le fil attendait à jamais un correspondant disparu. La
marque « compte séparé retiré » : relevé le 01/10/2026 en relisant le code (un
Espace rouvert vide après le retrait du réglage).

**Déposer dans SA boîte** (`envois.py`) — constaté le 24/08/2026 : « Envoyer »
copiait dans un dossier fantôme du bac à sable et annonçait « Copié ». Le
14/09/2026, un silence cachait qu'aucun envoi ne partait d'un Espace à compte
dédié.

**Les liens qui restent dans l'instantané** (`archives.py`) — constaté le
12/09/2026 sur une VM : « Revenir à un instantané » échouait toujours sur une
archive produite par Codebyr (le profil Firefox contient des liens).

**Les identifiants d'Espace** (`registre.py`) — constaté le 29/09/2026 :
« 2025 Projets » donnait un identifiant qu'un compte Unix refuse ; l'Espace se
créait, puis refusait de s'ouvrir sous compte séparé.

**Le profil de Firefox où poser le bouclier** (`navigateur.py`) — constaté le
29/09/2026 sur la VM : écrire dans `codebyr.default` posait le bouclier dans un
profil que personne n'ouvrait, et le bouclier, déposé à la main, était muet
depuis la 1.6.0 ; la copie déposée se retire, Firefox la réinstalle par la
politique avec son droit (mesuré le même jour).

**Le filtre d'appels système** (`filtre_syscalls.py`) — liste des appels
connus relevée le 29/09/2026 (libseccomp 2.6.0) ; écartés établis par deux
mesures sur la VM le même jour (Firefox et une vidéo, Fichiers et ses
vignettes, une application Flatpak, la console). Sockets restreintes le
02/10/2026 (SECURITY.md, 1.20.0).

**L'autotest du poste** (`autotest.py`) — le 20/08/2026, « Ouvrir en Jetable »
a été livré, testé, empaqueté — et ne fonctionnait pas : le greffon n'était
pas installé. Le même jour, l'ajout d'une sous-clé a rendu le trousseau apt de
tout le parc obsolète.

## Le bureau

**L'identité des fenêtres** (`codebyr-config`, `codebyr-bienvenue`,
`codebyr-assistant`) — constaté le 13/09/2026 sur une installation réelle :
sans `GLib.set_prgname`, l'icône générique (un losange gris) dans le dock, la
vue d'ensemble et Alt+Tab. Le cache d'icônes rafraîchi par le postinst : même
date, même losange, sur une machine où apt avait créé le cache avant l'icône.

**L'extension GNOME** — l'étiquette du nom, enfant du liseré, a cessé de
s'afficher pendant six semaines (constaté le 13/09/2026) ; l'étiquette posée
sur Fichiers en haut d'écran recouvrait son premier bouton (même jour) ; la
variante de l'icône du Sceau retenue à l'aperçu du 15/09/2026 ; « Autres
applications… » muette par une variable qui masquait `remplir` (vu le
01/10/2026) ; la session ouverte sur la vue d'ensemble, dont le dock et
l'icône sous les fenêtres recouvraient le bouton « Suivant » de Bienvenue (même
jour).

**La colonne « Provenance »** (`codebyr-provenance.py`) — une soirée perdue le
23/08/2026 sur des emblèmes d'icônes qui ne se chargeaient pas, sans message.

## Le démarrage

**L'écran de démarrage** (`codebyr.script`) — l'invite de phrase de passe
restait invisible sur la première installation chiffrée (13/09/2026) ; le logo
glissait au changement de définition (01/10/2026, sur la VM).

**GRUB** (`91-codebyr-demarrage.cfg`) — essayé sur la VM le 01/10/2026 : F4
ouvre le menu, Maj maintenue ne fait rien sous VMware, Échap mène au menu de
VMware ou à l'invite `grub>` ; `piix4_smbus … SMBus base address
uninitialized` s'affichait avant le logo malgré « quiet ».

**L'espace d'échange chiffré** (`codebyr-durcir-poste`) — constaté le
28/09/2026 sur une installation neuve de la 1.16.0.

## Le paquet

**Copier, et non déplacer, à la déviation** (`codebyr-tools.preinst`) —
constaté le 28/09/2026 : dpkg signalait « dangereux, utilisez --no-rename ».
La déviation de l'avatar éprouvée le 01/10/2026 sur une copie du système de
l'ISO 1.16.8.

**Le profil AppArmor du service** (`etc/apparmor.d/codebyr-uid`) — constaté
sur la machine d'essai le 14/09/2026 : sans la lecture de `/usr/share/codebyr`,
le service ne démarrait pas, AppArmor refusant en silence ; sans `capability
kill`, la fermeture échouait en silence (même jour) ; sans `/proc`, le
rangement des Espaces abandonnés échouait (15/09/2026).
