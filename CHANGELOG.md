# Journal des versions — Codebyr OS

Ce que chaque version apporte, en clair. Les correctifs de **sécurité** sont
détaillés dans [SECURITY.md](SECURITY.md), qui indique aussi ce qui était
vulnérable et comment.

Les mises à jour arrivent toutes seules par `apt` sur les machines installées.
Après une mise à jour, **déconnectez-vous et reconnectez-vous** : l'extension
GNOME (menu du Sceau, liserés colorés) ne se recharge pas à chaud.

---

## 1.19.1 — non publiée

**Deux failles fermées, relevées par une analyse externe du code** (détail
dans [SECURITY.md](SECURITY.md)) :

- **Une notification ne peut plus se faire passer pour un autre Espace.** Un
  titre déguisé en option (`--app-name=Espace Banque`) remplaçait l'en-tête
  imposé par Codebyr : une page web ouverte en Jetable, à qui l'on avait
  permis les notifications, pouvait signer une fausse alerte de la Banque ;
- **le compte invité ne touche plus au réseau de la machine**, ni au micro ou
  à la caméra hors de sa session. Il était membre de groupes qui lui
  permettaient, par exemple, de changer le DNS du Wi-Fi du propriétaire. Les
  machines installées sont corrigées à la mise à jour, et
  `sudo codebyr-space verifier-poste` le contrôle.

Et, sans effet visible : la vérification automatique du code couvre désormais
aussi les programmes qui tournent en administrateur (le service des comptes
d'Espaces, le premier processus d'un Espace, le filtre réseau, la
configuration du démarrage par l'installeur), et une fonction morte de
l'extension GNOME, qui identifiait un Espace d'une façon falsifiable, est
retirée.

---

## 1.19.0 — 1er octobre 2026

**Un démarrage sans couture.** Du logo du fabricant à l'écran de connexion,
plus de menu ni de texte technique :

- le menu de GRUB ne s'affiche plus 5 secondes à chaque démarrage. Il reste
  à portée : **tapotez F4** (Fn + F4 sur la plupart des portables) dès le logo
  du fabricant, pour démarrer un noyau précédent ou le mode de dépannage.
  Quand un autre système est installé, Windows par exemple, le menu reste
  visible pour choisir. Un délai réglé par vous dans `/etc/default/grub`
  n'est jamais remplacé ;
- les messages « Loading Linux … » et « Loading initial ramdisk … » ne
  s'écrivent plus en blanc sur noir avant le logo de Codebyr ; le menu, quand
  il s'ouvre, n'a plus le bleu de Debian ;
- le noyau n'affiche plus à l'écran ses erreurs ordinaires — sur une machine
  virtuelle VMware, il en écrivait une avant chaque démarrage. Elles restent
  dans le journal ;
- sous la phrase de passe du disque, plus de « cryptsetup: luks-…: set up
  successfully ». Une phrase de passe fausse affiche « Phrase de passe
  incorrecte. Réessayez. », dans la langue du système.

Le temps gagné : les 5 secondes du menu, moins une, gardée pour F4.

---

## 1.18.2 — 1er octobre 2026

**L'écran de démarrage parle la langue du système.** Sur un disque chiffré,
« Phrase de passe du disque » devient « Disk passphrase » quand Codebyr est
installé en anglais (ou dans une autre langue que le français). C'est la
langue du système qui compte, celle choisie à l'installation, et non celle
d'un compte : la question vient avant toute session. Un écran de démarrage
choisi par vous n'est jamais remplacé.

**Dans l'ISO 1.18.2**, publiée le même jour (reproductible, comme la 1.16.8) :

- une entrée « Live session (English) » au menu de démarrage : la session
  d'essai s'ouvre en anglais, clavier américain par défaut ;
- le diaporama de l'installeur suit la langue de la session ; il ne dit plus
  « bac à sable matériel », ce qui était inexact : les Espaces reposent sur le
  noyau Linux, pas sur du matériel ni des machines virtuelles.

---

## 1.18.1 — 1er octobre 2026

**Le bouclier anti-hameçonnage parle anglais.** Son alerte rouge (« site
suspect ») suit la langue de Firefox : en anglais pour toute langue autre que
le français, comme le reste de Codebyr. Bouclier 1.4, signé par Mozilla.

---

## 1.18.0 — 1er octobre 2026

**Codebyr parle anglais.** Tout ce que Codebyr affiche sur une machine
installée existe désormais aussi en anglais : la fenêtre « Bienvenue », le
menu du Sceau et ses fenêtres, Configuration Codebyr, l'Assistant de sécurité,
les notifications et messages des Espaces, la page de l'Espace Banque qui
refuse un site, les menus du clic droit dans Fichiers, le vérificateur
d'ISO. Pour l'essayer : Paramètres → Système → Région et langue → English,
puis se reconnecter.

- Le français reste la langue de Codebyr. Une session dans une autre langue
  que le français ou l'anglais reçoit l'anglais, plutôt que le français.
- Les noms des Espaces livrés suivent la langue (Personal, Work, Bank…) ;
  ceux que vous avez donnés restent tels quels.
- Restent en français pour l'instant : la page d'alerte du bouclier
  anti-hameçonnage, l'écran de démarrage et l'installeur. Ils viendront avec
  la prochaine ISO.
- Pour contribuer une langue : `po/en.po` sert de modèle (voir
  CONTRIBUTING.md).

**Aussi :**

- La vue d'ensemble (touche Super) ne pose plus l'icône d'une application à
  cheval sur le bas de chaque fenêtre : elle en recouvrait le contenu.
- « Autres applications… » ne propose plus les outils de Codebyr eux-mêmes
  (Assistant, Bienvenue) : les ouvrir dans un Espace n'a pas de sens.
- Une fenêtre du menu du Sceau qui ne peut pas s'ouvrir le dit, au lieu de
  ne rien faire.
- Configuration Codebyr : la liste des applications installées suit la
  langue de la session ; elle était toujours en français.
- La fenêtre « Bienvenue » montre l'Espace Navigation de sa vraie couleur
  (l'ambre de la charte depuis la 1.12.2).

---

## 1.17.2 — 1er octobre 2026

**Correctif de sécurité : un compte de la machine pouvait devenir
administrateur à la mise à jour suivante** (depuis la 1.10.0). Pour remplir le
dossier « Modèles » de chaque compte, la mise à jour suivait, en
administrateur, le chemin que les réglages du compte déclaraient — et lui
remettait ce qu'elle y trouvait. Un compte ordinaire, ou l'invité pendant sa
session, pouvait y désigner un dossier du système et se le voir remettre. Ce
travail se fait désormais sous l'identité du compte lui-même : il ne peut plus
atteindre que ce qui était déjà à lui. Détails dans [SECURITY.md](SECURITY.md).

**Codebyr se reconnaît dès le premier écran.**

- L'image des comptes, sur l'écran de connexion et de verrouillage, est le
  Sceau de Codebyr, et non plus la spirale de Debian. Les comptes existants la
  reçoivent aussi — sauf ceux qui ont choisi leur propre image.
- Au démarrage, le logo et « codebyr OS » restent au centre de l'écran : ils
  glissaient vers la gauche quand l'écran changeait de définition en cours de
  route. (Pour une machine déjà installée, la mise à jour régénère l'image de
  démarrage : quelques secondes de plus, une seule fois.)
- L'ouverture de session arrive sur le bureau, et non plus sur la vue
  d'ensemble de GNOME, dont le dock venait se poser sur le bouton « Suivant »
  de la fenêtre « Bienvenue ». La touche Super l'ouvre comme avant.
- Dans l'installeur, la barre latérale montre le Sceau et le nom en entier :
  le mot « codebyr » y était écrit dans la couleur du fond, et il ne restait
  que « OS ». (Visible à partir de la prochaine ISO.)

---

## 1.17.1 — 1er octobre 2026

**Retirer « Compte séparé » à un Espace fait bien revenir ses fichiers.**
« Configuration Codebyr » le promettait, mais ce n'était vrai que pour un
Espace qui avait d'abord vécu sous votre compte. Depuis la 1.16.1, chaque
Espace naît sous son propre compte : retirer le réglage l'ouvrait VIDE. Ses
fichiers n'étaient pas perdus — ils réapparaissaient en remettant le réglage —
mais rien ne le laissait voir. Désormais, ils reviennent. (Pour un Espace déjà
utilisé, cela vaut à partir de sa prochaine ouverture sous son compte.)

Le terminal annonce enfin l'application qu'il ouvre (« Ouverture de
« gnome-text-editor » »), et non l'outil qui l'enveloppe.

**Le découpage de `codebyr-space` se termine, sans rien changer à l'usage.**

- Ce que le bureau demande à un Espace à compte séparé — déménager ses
  données, les rapatrier, préparer son dossier — : `ordres_espace.py`.
- Ce que l'Espace fait chez lui, sous son propre compte — recevoir ses
  données, se restaurer, s'effacer, s'exporter — : `cote_espace.py`.
- `_lancer`, la fonction qui ouvre un Espace (400 lignes d'un seul tenant),
  enchaîne désormais des étapes nommées, dont l'ordre est vérifié par un test.
- Une fonction que plus rien n'appelait est retirée ; ses tests portent sur
  celle qui copie vraiment les fichiers.

---

## 1.17.0 — 30 septembre 2026

**Rien ne change à l'usage : c'est le cœur du système qui se range.**
`codebyr-space`, le programme qui ouvre les Espaces, dépassait 3 000 lignes :
trop pour qu'une seconde personne puisse le relire et le maintenir. Il est
découpé en modules, un par sujet, chacun avec ses tests (audit, point 8).

- Le Firefox d'un Espace — son profil, son filtre réseau, son bouclier
  anti-hameçonnage — vit désormais dans `navigateur.py`.
- Reconnaître et lancer un programme ajouté au menu d'un Espace :
  `programmes.py`.
- Où vivent les données des Espaces : `chemins.py`. Ce chemin était écrit six
  fois dans trois programmes ; il l'est désormais une seule.
- Les applications Flatpak d'un Espace — où elles s'installent, avec quel
  environnement : `flatpak_espace.py`.
- Ce qu'on accepte de sortir d'une archive d'Espace (sauvegarde, déménagement
  vers un compte séparé et retour) : `archives.py`.
- Les boîtes d'envoi, par lesquelles un fichier passe d'un Espace à un autre :
  `envois.py` ; le journal système commun à tous : `journal.py`.

---

## 1.16.8 — 30 septembre 2026

**Le noyau démarre avec deux protections de plus** (`slab_nomerge`,
`page_alloc.shuffle=1`), qui rendent plus difficile l'exploitation d'une faille
de la mémoire du noyau. Elles s'appliquent au prochain redémarrage, pour un
coût de quelques mégaoctets de mémoire. Les autres protections recommandées
étaient déjà actives dans le noyau de Debian 13.

---

## 1.16.7 — 30 septembre 2026

**Correctif de sécurité : deux fichiers de Codebyr étaient modifiables par
tous les comptes de la machine.** Depuis la 1.13.0, le lanceur de l'écran de
bienvenue (`/etc/xdg/autostart/codebyr-bienvenue.desktop`) et son icône étaient
installés sans protection. N'importe quel compte — l'invité, qui n'a pas de mot
de passe, compris — pouvait y inscrire une commande, exécutée à l'ouverture de
session de chacun. La mise à jour remet ces fichiers à leur contenu d'origine
et les protège ; aucune action n'est nécessaire.

---

## 1.16.6 — 30 septembre 2026

**« Ajouter une application » fonctionne sous compte séparé.** C'était le
dernier geste refusé dans ce mode, qui est celui de tous les Espaces. Téléchargez
le programme avec le navigateur de l'Espace — ou envoyez-le-lui —, puis, dans
« Configuration Codebyr », choisissez-le dans la liste des programmes que
l'Espace a trouvés chez lui : il apparaît dans son menu.

**Un nom plus propre est proposé pour le menu.** « LocalSend-1.18.2-linux-x86-64.AppImage »
proposait « Localsend- » ; c'est maintenant « LocalSend », sans la version ni
la plateforme. Le nom reste modifiable avant l'ajout.

**Les AppImage s'ouvrent dans les Espaces.** C'est la forme la plus courante
d'un programme téléchargé, et elle ne pouvait pas s'y lancer : elle a besoin,
pour se monter, d'un outil que la protection des Espaces interdit à juste
titre. Codebyr lui demande désormais de se décompresser et de se lancer sans
lui.

---

## 1.16.5 — 29 septembre 2026

**Les images ont de nouveau un aperçu dans Fichiers.** Photos, captures et
dessins s'affichaient tous avec la même icône générique, dans les Espaces
comme sur le bureau : l'outil qui fabrique ces aperçus n'était pas installé.
Il l'est désormais, par la mise à jour comme dans l'image d'installation. Les
aperçus que Fichiers avait notés en échec faute de cet outil — il ne
réessayait plus jamais — sont oubliés une fois, à la prochaine ouverture de
chaque Espace.

---

## 1.16.4 — 29 septembre 2026

**Le Blindage n'autorise plus que ce qu'il connaît.** Dans un Espace blindé,
un filtre refusait jusqu'ici une liste d'opérations dangereuses, et laissait
passer tout le reste — y compris les opérations qu'une future version de Linux
inventera, que personne n'aura examinées. C'est désormais l'inverse : seules
les opérations connues et utiles passent, tout le reste est refusé. La liste a
été établie en observant ce que les applications réelles des Espaces
demandent, avant de rien interdire.

---

## 1.16.3 — 29 septembre 2026

**Le bouclier anti-hameçonnage voit les adresses déguisées.** Une adresse
comme « mаbanque.fr », écrite avec un « а » de l'alphabet cyrillique, s'affiche
exactement comme celle de votre banque, et le bouclier ne la reconnaissait pas.
Il la lit désormais comme vous la voyez, accents et lettres d'autres alphabets
compris, et son avertissement indique comment l'adresse s'écrit réellement.

**Le bouclier fonctionne de nouveau — il ne fonctionnait plus depuis la
1.6.0.** En l'éprouvant dans un vrai Firefox, nous avons découvert qu'il était
bien chargé, mais muet : depuis son passage au nouveau format d'extension de
Firefox (août 2026), le droit de lire les pages n'est plus accordé d'office à
une extension déposée dans le profil, comme le faisait Codebyr. Personne ne le
lui accordait, et rien ne le signalait. C'est désormais Firefox qui installe le
bouclier lui-même, par une règle livrée avec Codebyr : il reçoit ce droit sans
que vous ayez rien à faire. Au premier ou au deuxième lancement de chaque
navigateur après la mise à jour, l'ancienne copie est remplacée.

Au passage, le bouclier s'installe aussi dans les Espaces dont le navigateur
avait été ouvert avant que vous déclariez votre banque (il était déposé dans un
profil que Firefox n'ouvrait pas), et Firefox retrouve son garde-fou contre les
extensions glissées en silence dans un profil, que Codebyr désactivait pour y
déposer la sienne.

---

## 1.16.2 — 29 septembre 2026

**Correctif de sécurité important.** Le service qui prépare les Espaces tourne
avec tous les droits. Pour présenter l'affichage et le son du bureau à un
Espace, il prenait ce qu'il trouvait à leur place dans le dossier de votre
session, sans vérifier que c'était bien eux. Un programme lancé sous votre
compte, ou un autre utilisateur de la machine, pouvait y mettre un raccourci
vers un fichier du système et se le faire ouvrir en écriture : c'est devenir
administrateur sans mot de passe. Jusqu'en 1.16.0, le compte invité le pouvait
aussi. Le service ne suit plus aucun raccourci : il vérifie ce qu'il ouvre et
travaille sur ce qu'il a vérifié. Le défaut existait depuis la 1.15.0.

**Un Espace au nom long, ou commençant par un chiffre, s'ouvre.** « 2025
Projets » ou « Mes impôts & factures 2026 » se créaient, puis refusaient de
s'ouvrir sans rien dire : sous compte séparé, le défaut depuis la 1.16.1,
l'identifiant d'un Espace doit commencer par une lettre et tenir en vingt
caractères. Les nouveaux Espaces reçoivent un identifiant qui convient ; un
Espace déjà créé ainsi dit pourquoi il ne s'ouvre pas, et peut être supprimé
puis recréé.

---

## 1.16.1 — 28 septembre 2026

**Chaque Espace a désormais son propre compte.** Le réglage « Compte séparé,
par Espace », livré en 1.15.0 et complété en 1.16.0, devient celui de tous les
Espaces — ceux qui sont livrés comme ceux que vous créez. Ses fichiers lui
appartiennent : ce qui s'échapperait d'un Espace ne retrouverait que lui, ni
les autres, ni votre dossier personnel.

À la première ouverture de chaque Espace après la mise à jour, ses données
**déménagent** vers son compte ; rien n'est effacé, et elles reviennent si vous
désactivez le réglage pour cet Espace dans « Configuration Codebyr ». Ce que
cela change pour vous :

- les applications Flatpak que vous aviez installées **dans** un Espace sont à
  réinstaller, dans l'Espace — la fenêtre de configuration le signale ;
- « Ajouter une application » (un programme téléchargé, une AppImage) n'est
  pas encore possible sous ce mode ; c'est dit à l'écran. Désactiver le compte
  séparé pour l'Espace concerné le permet ;
- une application Flatpak ne reçoit pas le fichier choisi dans « Ouvrir un
  fichier » (limite déjà décrite en 1.16.0).

Le terminal d'un Espace s'ouvre sous ce mode. Il « moulinait » sans jamais
apparaître : le compte d'un Espace n'a volontairement aucun shell de connexion,
et c'est ce shell qu'un terminal lance. Le bac à sable voit désormais un vrai
shell pour ce compte, et lui seul ; hors du bac à sable, le compte ne peut
toujours ouvrir aucune session.

**L'invité n'a jamais de compte séparé.** Sa session s'efface à la
déconnexion — son dossier personnel, et rien d'autre. Un Espace à compte
séparé vit ailleurs : il aurait survécu, et l'invité suivant aurait retrouvé le
navigateur et les fichiers du précédent. C'était déjà vrai d'un invité qui
cochait le réglage ; ce n'est plus possible.

**Personnel et Travail sont blindés à leur tour**, comme Banque, Navigation et
Jetable : filtre d'appels système, aucun privilège, session neuve, plafonds —
larges, comme pour Navigation, pour ne pas couper une journée de travail. Une
application Flatpak y reste possible, sous compte séparé ; elle y a le bac à
sable de Flatpak, pas le Blindage, et c'est dit à son ouverture. Les outils de
débogage qui observent un autre programme (`gdb`, `strace`) n'y fonctionnent
plus. Et, comme pour tout Espace blindé, le presse-papiers est vidé quand vous
passez de Personnel ou Travail au bureau (hors Espace) ; d'un Espace à un
autre, il l'était déjà.

**Une application Flatpak qui sortirait de son Espace ne s'y ouvre plus.**
Dans un Espace ordinaire, une application Flatpak ne passe pas par le bac à
sable de Codebyr : elle a le sien, et ce sont ses propres permissions qui
décident de ce qu'elle atteint. Certaines la font sortir de l'Espace tout
entier — parler au bus du bureau, y lancer des programmes, voir tous vos
fichiers. Elle portait pourtant le liseré de l'Espace, qui annonçait une
isolation qu'elle n'avait pas.

Elle est maintenant refusée, avec l'explication et les deux façons de faire :
l'ouvrir hors des Espaces, ou activer « Compte séparé » pour cet Espace, où le
compte de l'Espace borne ce qu'elle peut faire. Cela ne concerne que les
Espaces sans compte séparé — désormais l'exception : ceux de l'invité, et ceux
pour lesquels vous le désactivez. Les applications ordinaires ne sont pas
concernées, et la plupart des applications Flatpak non plus.

Au passage : une application choisie par « Autres applications… » était prise
pour une installation de toute la machine, même installée dans l'Espace.

**Le Jetable n'a plus de micro.** C'est là que s'ouvrent les liens douteux :
une page piégée n'a pas à pouvoir écouter la pièce. Le son part avec lui — les
deux passent par le même canal. Réglable dans « Configuration Codebyr ».

**Verr. Maj fonctionne comme sous Windows.** Il agit désormais comme Maj sur
toutes les touches, et pas seulement sur les lettres : Verr. Maj + `&` donne
`1`, + `;` donne `.`. C'est le geste habituel pour taper des chiffres quand on
vient de Windows. Il s'applique à votre session et à l'écran de connexion dès
la mise à jour. Sur une nouvelle installation, il vaut aussi pour la phrase de
passe du disque au démarrage ; sur une machine déjà installée, cette saisie-là
ne change pas, pour que votre phrase de passe se tape toujours comme le jour où
vous l'avez choisie.

**Plus de message d'erreur au démarrage, et l'espace d'échange fonctionne
enfin.** Sur un disque chiffré, deux messages « cryptsetup: ERROR » s'affichaient
à chaque démarrage, même après la bonne phrase de passe — de quoi croire qu'elle
avait été refusée. Ils concernaient l'espace d'échange, que l'installeur chiffre
à part et prévoyait d'ouvrir avec un fichier de clé qu'il ne crée pas dans la
configuration de Codebyr. Il ne s'ouvrait donc jamais : **aucune machine
chiffrée n'avait d'espace d'échange** depuis la 1.13.0 — et chaque démarrage
l'attendait 90 secondes en vain, car le programme qui ouvre ces volumes une fois
le système lancé (`systemd-cryptsetup`, séparé de systemd par Debian 13) manquait
à l'image.

Il est désormais chiffré avec une clé tirée au hasard à chaque démarrage : rien
à taper, et son contenu devient illisible dès l'extinction. Les machines déjà
installées sont réparées par la mise à jour. Le prix : pas de mise en veille
prolongée (hibernation), qui ne fonctionnait pas davantage.

**Votre système garde son nom, et le bon.** Deux défauts dans le fichier qui
porte l'identité du système (`/etc/os-release`) :

- ses adresses d'aide et de signalement menaient à `codebyr.io`, un domaine
  qui n'existe pas — et que n'importe qui aurait pu acheter pour recevoir vos
  demandes. Elles mènent désormais au site du projet et à son dépôt. Même
  correction dans l'installeur, qui n'affiche plus non plus de lien de dons :
  le projet n'en collecte pas ;
- ce fichier appartient à Debian, qui le réécrit à chaque version mineure
  (13.5 → 13.6…) : à la prochaine, votre machine se serait présentée comme
  « Debian GNU/Linux 13 ». Codebyr le reprend désormais par le mécanisme prévu
  pour cela, et sa version suit les mises à jour — une machine installée depuis
  l'ISO 1.13 s'annonçait « 1.13 » pour toujours.

**Sous le capot.**

- **Une version ne peut plus partir avec des tests en échec.** Du 13 au 27
  septembre, l'intégration continue était en échec, et quatre versions sont
  parties quand même : un test contredisait un correctif de sécurité, et
  personne ne l'a vu. La publication vérifie désormais que le code publié est
  commité, poussé, et validé.
- **Le dépôt des mises à jour porte une date de péremption.** Sans elle, un
  serveur compromis pouvait servir indéfiniment un ancien dépôt, correctement
  signé, et priver les machines de leurs correctifs sans que rien le signale.
- **Un paquet d'essai ne peut plus partir par erreur** chez tout le monde.
- **Un serveur de mises à jour injoignable ne bloque plus rien.** Un réglage
  qui ne servait qu'à construire l'image faisait attendre `apt` jusqu'à 40
  minutes devant un dépôt injoignable — c'est ainsi qu'une installation a
  échoué pendant une panne de courant chez le mainteneur. Il est retiré de
  l'image et des machines installées : `apt` retrouve ses délais ordinaires,
  et passe son chemin en quelques secondes, comme pour n'importe quel dépôt.
- `acl` et `libnotify-bin` deviennent des dépendances : sans le premier, un
  Espace à compte séparé pouvait ne plus s'ouvrir ; sans le second, un refus
  d'ouvrir un Espace avait lieu sans un mot.
- Le service des comptes d'Espaces ignore, hors de son mode d'essai, les
  variables qui lui feraient charger un module ou lancer un programme venus
  d'ailleurs.

**Le Sceau de la barre du haut se voit enfin.** L'icône était terne et trop
petite : un petit anneau gris sur un panneau noir où tout le reste est blanc.

Elle est désormais **dessinée** plutôt que chargée depuis un fichier, et prend
la couleur du texte de la barre — claire sur un thème sombre, sombre sur un
thème clair, sans réglage. Son trait a été épaissi pour la taille réelle d'une
icône de barre.

Trois tentatives avaient échoué en août, dont deux en rendant l'icône
invisible. La cause est maintenant connue : le dessin était fait de traits, là
où la recoloration de GNOME agit sur le remplissage.

## 1.16.0 — 15 septembre 2026

**Les applications Flatpak s'ouvrent dans un Espace à compte séparé.** C'était
la première des deux limites annoncées en 1.15.0 ; elle est levée.

Chaque Espace sous compte séparé a désormais **son propre bus de session**, et
donc ses propres « portails » — ces services par lesquels une application
demande d'ouvrir un fichier ou d'imprimer. Celui du bureau n'y entre toujours
pas, et n'y entrera pas : c'est lui qui donnait, en 1.1.0, un chemin hors du
bac à sable.

Ce que vous verrez :

- **installer une application dans un Espace** fonctionne comme avant, depuis
  « Configuration Codebyr ». La différence est invisible et elle compte : c'est
  l'Espace qui télécharge, chez lui, sous son propre compte. Votre compte n'y
  écrit rien ;
- **l'application s'ouvre** avec le liseré de son Espace, et tourne sous le
  compte de celui-ci ;
- **sa fenêtre « Ouvrir un fichier » ne montre que les fichiers de l'Espace** —
  ni les vôtres, ni ceux des autres Espaces.

C'est aussi un gain d'isolation pour qui utilisait déjà des applications
Flatpak : jusqu'ici, elles parlaient au bus de session du bureau, et ce qu'elles
faisaient ouvrir par ce biais s'ouvrait sous **votre** compte.

**Ce qui ne fonctionne pas, et pourquoi.** Une application Flatpak ne reçoit pas
le fichier choisi dans « Ouvrir un fichier ». Ce passage se fait par un service
qui monte un système de fichiers au moyen d'un programme à privilèges, ce qu'un
Espace interdit à tout ce qui tourne en lui — la protection même qui empêche un
programme échappé d'atteindre les outils d'administration. Nous gardons la
protection et disons la limite, plutôt que de l'affaiblir pour une commodité.
Le détail est dans [SECURITY.md](SECURITY.md).

Les applications déjà installées dans un Espace avant l'activation du compte
séparé sont **à réinstaller** dans l'Espace : leur installation vit dans un
dossier de votre compte, auquel celui de l'Espace n'a pas accès. La fenêtre de
configuration le dit.

**La carte graphique fonctionne aussi.** C'était la seconde limite annoncée en
1.15.0 ; elle est levée dans la même version. Un Espace qui y a droit reçoit
l'accès à la carte le temps qu'il est ouvert, et le perd à sa fermeture —
exactement comme votre session le reçoit à l'ouverture et le perd à la
déconnexion. L'affichage d'un Espace n'est donc plus dessiné par le processeur.
Banque et Jetable, qui n'ont pas accès à la carte par choix, n'y touchent
toujours pas.

**Sous le capot** : le dossier d'exécution d'un Espace a pris sa place
canonique, `/run/user/<son numéro de compte>`. Sans cela, aucune application
Flatpak ne démarrait — son bac à sable interne butait sur un chemin de notre
invention.

## 1.15.0 — 14 septembre 2026

**Chaque Espace peut désormais avoir son propre compte sur la machine.** C'est
le changement le plus profond depuis la première version. Il s'active Espace par
Espace, dans « Configuration Codebyr » → *Compte séparé, par Espace*.

Jusqu'ici, tous vos Espaces tournaient sous votre compte. Le bac à sable les
séparait par ce qu'ils *voient* ; rien ne les séparait par ce qu'ils ont le
*droit* de toucher. Un programme qui s'échappait du bac à sable retrouvait vos
documents et ceux de tous les autres Espaces. Avec un compte séparé, cette
frontière devient une règle du système, que le noyau vérifie à chaque ouverture
de fichier : ce qui s'échappe de Jetable ne peut plus lire Banque, ni votre
dossier personnel.

Ce que vous verrez, si vous activez le réglage :

- **à la première ouverture, les fichiers de l'Espace déménagent** vers son
  compte. Rien n'est effacé ; si vous décochez la case, ils reviennent, avec ce
  que vous avez fait entre-temps ;
- **tout le reste continue** : envoyer un fichier à un Espace, en faire sortir
  un, examiner une pièce jointe, sauvegarder, restaurer, effacer. Les fichiers
  passent par des boîtes que l'Espace et vous êtes seuls à partager ;
- **l'Espace jetable garde sa promesse** : son dossier vit en mémoire vive et
  disparaît à la fermeture, sans jamais toucher le disque ;
- **la mémoire est plafonnée pour l'Espace entier**, et non plus fenêtre par
  fenêtre.

Le réglage est **désactivé par défaut** : rien ne change tant que vous ne
l'activez pas, et rien ne tourne en arrière-plan tant qu'aucun Espace ne le
demande. Deux limites sont annoncées dans la fenêtre de configuration : une
application **Flatpak** installée dans un Espace ne s'ouvre pas sous compte
séparé, et l'accélération graphique n'y est pas encore disponible (l'affichage
se fait en rendu logiciel).

**Sur l'image d'installation**, cette version est la première à embarquer le
service des comptes d'Espaces, activé dès le premier démarrage. Le système s'y
annonce aussi sous son vrai numéro — `/etc/os-release`, `lsb_release` et
l'installeur affichaient « Codebyr OS 1.0 » quelle que soit la version gravée.

## 1.14.0 — 13 septembre 2026

**Les notifications reviennent dans les Espaces.** Une application qui prévient
d'un téléchargement terminé ou d'une erreur parlait dans le vide depuis la
1.1.0 : pour fermer une faille, les Espaces avaient perdu l'accès au service de
notifications du bureau.

Elles s'affichent désormais, sous le nom de leur Espace — « Espace Jetable »,
« Espace Banque ». Une application ne peut pas choisir cet en-tête : une page
piégée ouverte en Jetable ne peut donc pas afficher une fausse alerte signée
« Banque ». Le texte est nettoyé, borné, et le nombre de notifications est
limité pour qu'aucune application ne puisse noyer l'écran.

L'isolation n'a pas bougé d'un pouce : le bus de session de l'hôte n'entre
toujours pas dans un Espace.

## 1.13.0 — 13 septembre 2026

**Le disque est chiffré par défaut à l'installation.** La case « Chiffrer le
système » est désormais cochée d'avance : un ordinateur perdu ou volé ne livre
plus vos Espaces ni leurs sauvegardes. Vous choisissez une phrase de passe
pendant l'installation ; elle est demandée à chaque démarrage. Vous pouvez
encore décocher la case, mais le choix sûr est celui qu'on fait sans rien
toucher.

**La phrase de passe se tape avec votre clavier.** Elle est demandée par
l'écran de démarrage, clavier français chargé, et non plus par le chargeur de
démarrage, qui lisait tout en QWERTY : une phrase de passe choisie sur un
clavier AZERTY pouvait ne plus ouvrir le disque.

⚠️ **Retenez bien cette phrase de passe.** Sans elle, personne — pas même
Codebyr — ne peut rouvrir le disque.

**Le démarrage sécurisé est vérifié.** La chaîne complète — micrologiciel,
chargeur de démarrage, noyau — a été éprouvée sur une machine dont le démarrage
sécurisé est activé, comme la plupart des PC vendus aujourd'hui. Le noyau s'y
verrouille alors de lui-même : plus rien ne peut le modifier en marche.

**Corrections trouvées en éprouvant cette version.** L'écran de démarrage
n'affichait pas la demande de phrase de passe : on voyait une machine figée.
Les fenêtres de Codebyr apparaissaient avec une icône générique dans le dock.
Les machines virtuelles n'avaient ni presse-papiers partagé ni redimensionnement
de l'écran, alors que c'est ainsi que l'on essaie un système avant de
l'installer.

Ceci ne concerne que les **nouvelles** installations : un disque déjà installé
n'est pas modifié par la mise à jour.

## 1.12.2 — 13 septembre 2026

**L'Espace Navigation change légèrement de couleur.** Son Ambre était trop
claire pour se voir sur les fenêtres et le menu en thème clair. Elle devient un
peu plus soutenue : visible sur les deux thèmes, et mieux distinguée du rouge
de Jetable pour les personnes daltoniennes.

**Le nom de l'Espace se lit, sans dépendre des couleurs.** Chaque fenêtre porte
de nouveau une étiquette avec le nom de son Espace, en haut à gauche : elle
avait disparu depuis la 1.0.4. Quand une fenêtre est agrandie, l'étiquette
s'efface pour ne cacher aucun bouton, et le nom de l'Espace de la fenêtre
active s'affiche dans la barre du haut, à côté du Sceau. C'est le repère utile
à qui distingue mal le bleu de Personnel du violet de Travail — et il ne peut
pas être imité par une application.

## 1.12.1 — 13 septembre 2026

**Le filtre réseau est confiné par AppArmor.** C'est le seul programme qui
parle à Internet pour le compte d'un Espace restreint, et il tourne hors du bac
à sable. S'il était un jour trompé par une requête malveillante, il ne pourrait
plus lire vos documents, lancer un programme ni écrire ailleurs que dans la
liste des sites bloqués : AppArmor le lui interdit, quoi qu'il arrive.

Il démarre aussi en mode isolé : aucun module Python extérieur au système ne
peut s'y glisser avant lui.

Rien ne change dans votre usage.

## 1.12.0 — 13 septembre 2026

**Navigation est désormais blindée.** C'est l'Espace où l'on passe ses
journées sur le web — donc le plus exposé — et il ne l'était pas : ni filtre
d'appels système, ni abandon des privilèges. Il reçoit
maintenant le même Blindage que Banque et Jetable, avec des plafonds de
mémoire adaptés à un navigateur, pour qu'une session chargée ne soit jamais
fermée d'autorité.

**Le filtre réseau ne peut plus servir de passage vers votre réseau local.**
Il vérifiait le nom d'un site, pas l'adresse où ce nom mène. Un domaine
autorisé qu'on aurait fait pointer vers votre box, un NAS ou la machine
elle-même aurait ouvert à un Espace restreint ce que son cloisonnement doit
lui interdire. Une page explique désormais ce refus.

**Banque et Jetable n'ont plus accès direct à la carte graphique.** Ses
pilotes sont l'une des plus larges portes d'entrée du noyau. Ces deux Espaces
n'en ont besoin ni pour la vidéo ni pour la 3D ; l'affichage reste assuré.

**Le système ferme plusieurs accès au noyau** dont un usage ordinaire n'a
jamais besoin — et les ferme dès la mise à jour, sans attendre un redémarrage.

**Le menu du Sceau vérifie ce qu'il lit** dans la liste des Espaces avant de
s'en servir pour lancer une commande ou colorer une fenêtre.

**Ce que cela peut changer pour vous.** Une application Flatpak ajoutée à
l'Espace Navigation sera refusée, comme elle l'est déjà dans Banque : ses
permissions ne garantissent pas le Blindage. Si vous aviez désactivé le
Blindage de Navigation vous-même, votre choix est conservé. Les vidéos lues
dans Jetable sollicitent davantage le processeur.

`codebyr-space verifier-isolation` contrôle aussi la carte graphique et
l'Espace Navigation.

## 1.11.2 — 12 septembre 2026

**Les notifications portent le nom de Codebyr.** Elles s'affichaient sous
l'en-tête « notify-send », c'est-à-dire le nom de l'utilitaire qui les envoie —
y compris lorsqu'elles annoncent un refus de sécurité.

## 1.11.1 — 12 septembre 2026

**« Revenir à un instantané » ne fonctionnait plus du tout.** La restauration
refusait toute archive contenant un lien — et tout dossier personnel en
contient, ne serait-ce que par le profil du navigateur. On pouvait donc
sauvegarder un Espace, jamais le restaurer, et l'interface annonçait
« restauration impossible ».

Les liens internes sont désormais acceptés. Ce qu'il fallait refuser n'était
pas le lien, mais le lien qui **sort** de l'Espace : un lien vers un chemin
absolu ou remontant par `..` est toujours rejeté, comme les fichiers spéciaux.

**Les deux vérifications disent maintenant où les lancer.** Utilisées depuis un
Espace au lieu du bureau, elles donnaient des résultats faux — et
`verifier-isolation` concluait « au moins un contrôle a échoué, ne publiez pas
cette version » alors que tout allait bien.

La sonde s'exécutait dans un compartiment imbriqué et mesurait les restrictions
de l'Espace courant, pas celles qu'on voulait vérifier. Elles refusent
désormais, en expliquant pourquoi et quoi faire.

## 1.11.0 — 12 septembre 2026

**Lot de sécurité important.** Plusieurs frontières ont été renforcées à la
source. Rien ne change dans votre usage quotidien ; ce qui change, c'est ce
qu'un programme hostile peut atteindre.

**Le réseau d'un Espace est enfin cloisonné pour de bon.** La liste blanche ne
s'appliquait qu'au navigateur : tout autre programme lancé dans l'Espace
passait à côté. Chaque Espace restreint a désormais son propre réseau, sans
interface vers l'extérieur, et ne joint rien d'autre que son filtre.

**Le Blindage filtre les appels système.** Un programme ne peut plus inspecter
ni modifier la mémoire d'un autre, charger un module noyau, ni emprunter les
chemins habituels d'évasion.

**Une application ne peut plus se faire passer pour un autre Espace.** Elle
annonçait elle-même sa « classe de fenêtre » : il suffisait de se déclarer
« Banque » pour en obtenir la couleur — sur un système dont toute la lecture
repose sur cette couleur. La filiation est maintenant vérifiée.

**Plus d'ouverture d'Espace sans isolation.** Sans bubblewrap, rien ne se lance
du tout, au lieu de continuer en mode réduit.

**Fichiers, transferts et restauration** ne suivent plus les liens et ne
peuvent plus atteindre un fichier hors de l'Espace. Une restauration conserve
les anciennes données à côté, sous `avant-restauration-*` — pensez à les
supprimer quand vous n'en voulez plus, elles occupent de la place.

**Ce que cela peut changer pour vous.** Une application sans prise en charge de
proxy perdra son accès réseau dans un Espace restreint : il n'y a plus de repli
vers un accès direct. Les applications Flatpak sont refusées dans les Espaces
blindés, jetables ou à réseau restreint, leurs permissions n'étant pas
équivalentes. Après la mise à jour, **fermez et rouvrez vos Espaces**.

Les limites et ce qui reste à faire sont détaillés dans
[docs/securite-2026-09-12.md](docs/securite-2026-09-12.md).

## 1.10.1 — 24 août 2026

**« Nouveau document » existe enfin dans Fichiers.** Le menu ne proposait que
« Nouveau dossier » : créer un simple fichier texte obligeait à ouvrir un
terminal et taper `touch`.

GNOME n'affiche cette entrée que si votre dossier **Modèles** contient quelque
chose, et il était vide. Trois modèles y sont désormais déposés — texte,
feuille de calcul, Markdown — dans votre dossier personnel comme dans chaque
Espace.

Si vous avez déjà un modèle du même nom, il n'est pas touché.

Dans les Espaces, il fallait en outre **déclarer** où se trouve ce dossier :
ce chemin n'a aucune valeur par défaut, et le programme qui l'écrit d'habitude
ne tourne pas dans un compartiment isolé. Le dossier existait, personne ne le
regardait.

## 1.9.2 — 24 août 2026

**« Envoyer vers l'Espace » ne fonctionnait pas depuis un Espace.** Le fichier
n'arrivait jamais, alors que la commande annonçait « Copié ».

La cause est le cloisonnement lui-même : à l'intérieur d'un Espace, les autres
Espaces sont volontairement inatteignables. Le fichier partait donc dans un
dossier sans issue du bac à sable.

Chaque Espace dispose désormais d'une **boîte d'envoi**, et c'est le système
qui distribue. Le message le dit maintenant honnêtement : « Déposé pour
Travail — remis à la prochaine ouverture de cet Espace. » La remise a lieu dès
que vous ouvrez l'Espace destinataire, ce qui est de toute façon le moment où
vous allez y chercher le fichier.

Aucun Espace n'écrit chez un autre : chacun ne voit que sa propre boîte.

Depuis le bureau, l'envoi reste immédiat — rien ne change.

## 1.9.0 — 24 août 2026

**Un fichier venu d'un autre Espace s'ouvre sous cloche, tout seul.**

C'est le moment où la provenance cesse d'informer et se met à protéger. Vous
ouvrez, depuis Travail, un document téléchargé dans Navigation : il s'ouvre
isolé et **sans réseau**, et disparaît à la fermeture — au lieu de s'exécuter
au milieu de vos documents professionnels. Rien à décider, rien à cliquer : une
notification vous dit simplement ce qui vient de se passer.

Cela ne concerne que l'ouverture **depuis un Espace**, car c'est là qu'on sait
où l'on est. Et seulement les types de documents par lesquels arrivent les
pièges : PDF, documents bureautiques, archives, pages web.

**Le doute profite à l'ouverture.** Un fichier sans origine connue, ou déjà
chez lui, s'ouvre normalement. Refuser d'ouvrir des documents ordinaires ferait
désactiver la fonction en une semaine — et une protection désactivée ne protège
personne.

**Vos choix sont respectés.** Si vous avez déjà désigné une application pour un
type de fichier, Codebyr ne la remplace pas.

**Et une fois le document examiné ?** Clic droit → **« Ce fichier
m'appartient »**. Il s'ouvrira désormais normalement dans cet Espace. Sans ce
geste, une facture parfaitement légitime repartirait sous cloche à chaque
ouverture, sans qu'on puisse jamais l'annoter ni l'enregistrer.

Adopter ne déclare pas un fichier sain — personne ne peut le savoir. C'est
l'examen sous cloche qui permet de juger ; l'adoption enregistre que vous avez
jugé. Et elle ne vaut que pour cet Espace : envoyé ailleurs, le document
redevient étranger.

## 1.7.0 — 24 août 2026

**Un fichier garde désormais la trace de l'Espace d'où il vient.**

Les Espaces cloisonnent les applications. Ils ne cloisonnaient pas les
fichiers : un document téléchargé dans Navigation, envoyé dans Travail puis
ouvert, s'y exécutait au milieu de vos documents professionnels. Le
cloisonnement avait parfaitement tenu — c'est vous qui aviez transporté le
fichier de l'autre côté, d'un geste tout à fait normal.

Le gestionnaire de fichiers gagne une colonne **« Espace d'origine »** : un
document venu de Navigation se repère au milieu de vos dossiers de Travail,
comme une fenêtre se repère à son liseré. Rien de nouveau à apprendre — la même
idée, appliquée aux fichiers.

Cela vaut aussi pour ce que vous **téléchargez** : un fichier reçu dans un
Espace en porte l'origine sans qu'on ait rien eu à faire, et la garde en le
quittant.

Deux commandes l'accompagnent :

- `codebyr-space provenance <fichier>` — d'où vient ce fichier, et l'ouvrir
  ici ferait-il franchir une frontière ;
- `codebyr-space contagion <espace>` — combien de fichiers venus d'ailleurs
  se trouvent dans cet Espace.

**Ce que cela ne fait pas.** La marque ne survit ni à une clé USB en FAT, ni à
une pièce jointe, ni à la plupart des partages réseau : elle se perd là où elle
servirait le plus. Windows et macOS ont la même limite, et cela reste l'une de
leurs protections les plus efficaces. C'est un indice, pas une frontière — un
fichier sans marque ne déclenche donc rien.

## 1.6.0 — 23 août 2026

**Le bouclier anti-hameçonnage passe en Manifest V3.** Firefox accepte encore
l'ancien format, mais Mozilla finira par refuser de le signer — et ce jour-là,
le bouclier ne serait plus livrable du tout. C'était le seul chantier du projet
avec une échéance imposée de l'extérieur ; il est fait avant, pas après.

Rien ne change pour vous : mêmes protections, même fonctionnement. L'extension
ne collecte aucune donnée, ce qui est désormais déclaré explicitement dans son
manifeste — une exigence que Mozilla imposera bientôt à toutes les extensions.

## 1.5.5 — 23 août 2026

**`codebyr-space verifier-poste` : la machine vérifie elle-même ce qu'on lui a
promis.** Six contrôles, chacun correspondant à un défaut réellement survenu
ici — jamais à une hypothèse : le clic droit Jetable est-il vraiment
chargeable, le compte invité refuse-t-il tout mot de passe, les dossiers
personnels sont-ils privés, le trousseau connaît-il la clé qui signe
aujourd'hui, les mises à jour sont-elles réellement armées, le bac à sable
est-il opérationnel.

Ces défauts ont un point commun qui les rend redoutables : **ils ne se voient
pas à l'usage.** Un poste dont le trousseau a périmé, ou dont le compte invité
a repris un mot de passe, se comporte exactement comme un poste sain. Il ne
s'en plaint jamais. Même principe que `verifier-isolation` : on n'interroge pas
le système, on l'observe.

**« Envoyer vers l'Espace… » au clic droit.** Annoncé dans l'architecture depuis
le début et jamais réalisé : faire passer un document d'un Espace à l'autre
demandait d'exporter un instantané ou de passer par le presse-papiers. Le
fichier est **copié** dans le dossier « Partagé » de l'Espace choisi —
l'original ne bouge pas, et l'Espace de destination reste ce qu'il est.

À ne pas confondre avec « Ouvrir en Jetable », qui est le geste de la méfiance.
Celui-ci est l'inverse : on classe un document dont on ne se méfie pas.

Un fichier du même nom n'est **jamais écrasé** : il devient « rapport (2).pdf ».
Écraser en silence serait le pire comportement possible ici — on ne saurait
même pas avoir perdu quelque chose, le geste ayant l'air d'avoir réussi.

**Pour les développeurs.** La publication refuse désormais un paquet plus ancien
que le code qu'il est censé contenir : même piège que l'ISO périmée, un artefact
daté qu'on republie en croyant publier son travail.

Une tentative de refonte de l'icône du Sceau a été **abandonnée** après trois
essais infructueux, et l'icône d'origine restaurée. Ce qui a été essayé, et la
raison de chaque échec, est consigné dans `docs/chantiers.md`.

## 1.4.1 — 20 août 2026

**Le clic droit « Ouvrir en Jetable » manquait vraiment à l'appel.** La 1.4.0
livrait bien l'extension, mais le greffon qui la charge (`python3-nautilus`)
n'était qu'une *recommandation* : sur un poste où le paquet avait été installé
à la main, il n'était pas là, et le menu contextuel restait parfaitement normal
— sans le moindre message d'erreur. C'est désormais une dépendance ferme.

Une fonctionnalité qui repose sur une recommandation n'est pas livrée, elle est
espérée. Rien à faire de votre côté : la mise à jour installe ce qui manque.

## 1.4.0 — 20 août 2026

**« Ouvrir en Jetable » arrive dans le clic droit.** Le geste naturel — clic
droit sur une pièce jointe douteuse — était promis depuis le début sans jamais
exister : il fallait passer par le menu du Sceau ou la ligne de commande,
c'est-à-dire ne jamais s'en servir au moment où l'on en a besoin. Le fichier
s'ouvre dans un Espace éphémère, **blindé et sans réseau** : le piège
s'exécute dans le vide et disparaît à la fermeture.

## 1.3.1 — 20 août 2026

**Correctif de mise à jour, important.** L'ajout d'une sous-clé de signature a
rendu le dépôt invérifiable par les machines déjà installées : leur trousseau,
gravé lors de l'installation, ne connaissait pas cette nouvelle clé. `apt`
refusait la signature — proprement, mais totalement. Trois corrections :

- la clé publique publiée contient désormais la sous-clé, dans ses trois
  exemplaires (celui qu'on importe, celui que grave l'ISO, celui qu'embarque
  le paquet) — un test les compare pour qu'ils ne divergent plus ;
- le paquet **rafraîchit lui-même le trousseau** à l'installation, de sorte
  qu'une future rotation de clé ne demandera plus rien à personne ;
- pendant la transition, le dépôt est signé par **deux** clés à la fois : les
  machines anciennes valident par l'ancienne, les neuves par la nouvelle.

## 1.3.0 — 20 août 2026

**Le presse-papiers ne se contourne plus par le bureau.** Il était vidé quand
on passait d'un Espace à un autre — mais pas quand on passait par le bureau.
Copier dans Banque, cliquer sur le bureau, ouvrir n'importe quelle
application : le secret était encore là. La frontière ne se franchissait pas,
elle se contournait. Elle se ferme désormais aussi à la sortie d'un Espace
sensible ; les Espaces ordinaires gardent leur souplesse.

**Le bouclier anti-hameçonnage veille aussi dans l'Espace Banque.** Il en était
exclu au motif que la liste blanche y suffit — mais cette liste, c'est vous qui
la saisissez. Le jour où un site imitateur y entre par erreur, plus rien ne
criait.

**L'adresse que vous saisissez est vérifiée.** Ajouter le site de sa banque
passe par un contrôle sérieux : les adresses IP sont refusées, les caractères
interdits aussi, et `mabanque.fr@piege.fr` est lu comme votre navigateur le
lira — `piege.fr`. L'interface vous prévient quand une saisie est refusée, au
lieu de ne rien faire.

**Le filtre réseau accepte SOCKS5.** Jusqu'ici il ne protégeait que le
navigateur ; les autres applications d'un Espace passaient à côté.

**Quand une application n'est pas vraiment cloisonnée, on vous le dit.** Une
application Flatpak installée pour toute la machine partage ses données entre
tous les Espaces — le liseré coloré laissait croire l'inverse.

**L'empreinte de la clé de signature est publiée sur le site**, en plus du
dépôt : deux sources indépendantes à comparer.

**L'Espace Banque non configuré s'explique enfin.** Il n'ouvrait aucun site —
ce qui est voulu — mais sans rien dire de compréhensible : en HTTPS, le
navigateur affiche sa propre page d'erreur et notre explication n'arrivait
jamais à l'écran. Une notification apparaît maintenant au lancement, et la page
de blocage est une vraie page qui dit quoi faire.

Pour les développeurs : `build.sh` ne peut plus annoncer une construction
réussie sans avoir rien reconstruit (les jalons d'une construction précédente
faisaient tout sauter, au risque de publier une ISO périmée).

## 1.2.0 — 20 août 2026

**Vos réglages ne bloquent plus les mises à jour de sécurité.** Jusqu'ici, dès
que vous touchiez un réglage, votre copie de la configuration devenait un
instantané figé : aucune valeur par défaut livrée ensuite ne pouvait plus vous
atteindre. Autrement dit, plus vous configuriez votre système, moins les
durcissements vous parvenaient. Les deux configurations se superposent
désormais : vos choix gagnent, les nouveautés arrivent quand même.

**Son et micro réglables par Espace.** Le serveur de son donne aussi accès au
microphone. Vous pouvez le couper Espace par Espace dans « Configuration
Codebyr » — c'est déjà le cas pour Banque.

**Une commande pour vérifier l'isolation.** `codebyr-space verifier-isolation`
lance une sonde dans un vrai bac à sable et vous dit, preuve à l'appui, ce
qu'un Espace peut réellement atteindre. Utile après chaque mise à jour, et
indispensable pour qui veut vérifier plutôt que croire.

**Quand une application ne démarre pas, vous le savez.** Avant, il ne se
passait rien à l'écran. Le menu du Sceau vous prévient désormais, et
`journalctl -t codebyr` donne le détail.

Corrections : adresses IPv6 dans le filtre réseau, marqueurs de processus
laissés par une application tuée brutalement (ils pouvaient faire afficher le
mauvais liseré), aide de `codebyr-space --help` qui ne documentait que 3 actions
sur 13.

## 1.1.0 — 19 août 2026

**Correctif de sécurité important.** Une application malveillante lancée dans
un Espace pouvait, par le bus de communication du bureau, s'exécuter **hors**
de son compartiment et lire les données de tous les autres Espaces. Le chemin
est fermé. Détails complets dans [SECURITY.md](SECURITY.md).

**Le compte Invité n'a plus de mot de passe public.** Il était `invite` sur
toutes les machines Codebyr. Désormais aucun mot de passe ne fonctionne pour ce
compte (ni SSH, ni `su`, ni `sudo`) : seule sa session graphique locale
s'ouvre, d'un clic et sans rien saisir.

**Votre dossier personnel est privé sur le système installé.** La protection
n'existait que sur la version « live ». Un compte Invité pouvait donc lire vos
fichiers sur une machine installée.

**L'Espace Banque échoue fermé.** Sans site déclaré, il n'ouvrait plus rien du
tout — auparavant il avait un accès complet à Internet alors que l'interface
annonçait une restriction. Déclarez votre banque dans « Configuration Codebyr »
au premier usage.

**Le bouclier anti-hameçonnage crie moins fort et plus juste.** Il ne se
déclenche plus sur un simple bout de nom présent n'importe où dans l'adresse
(`revolut.zendesk.com` était signalé comme frauduleux), et vous pouvez déclarer
un site légitime une fois pour toutes.

## 1.0.7 — 2 août 2026

Bouclier anti-hameçonnage signé par Mozilla.

## 1.0.5 — 2 août 2026

Presse-papiers cloisonné entre Espaces, mode invité, liseré pointillé pour le
Jetable.

## 1.0.2 — 1er août 2026

Canal de mise à jour `apt` et corrections de sécurité.

## 1.0.1 — 1er août 2026

Correctifs issus d'une revue de sécurité externe.

## 1.0 — 9 juillet 2026

Première version installable : Espaces isolés, liserés colorés, Jetable,
installeur graphique.
