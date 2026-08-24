# Journal des versions — Codebyr OS

Ce que chaque version apporte, en clair. Les correctifs de **sécurité** sont
détaillés dans [SECURITY.md](SECURITY.md), qui indique aussi ce qui était
vulnérable et comment.

Les mises à jour arrivent toutes seules par `apt` sur les machines installées.
Après une mise à jour, **déconnectez-vous et reconnectez-vous** : l'extension
GNOME (menu du Sceau, liserés colorés) ne se recharge pas à chaud.

---

## 1.9.2 — en préparation

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

## 1.9.0 — en préparation

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

## 1.7.0 — en préparation

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

## 1.6.0 — en préparation

**Le bouclier anti-hameçonnage passe en Manifest V3.** Firefox accepte encore
l'ancien format, mais Mozilla finira par refuser de le signer — et ce jour-là,
le bouclier ne serait plus livrable du tout. C'était le seul chantier du projet
avec une échéance imposée de l'extérieur ; il est fait avant, pas après.

Rien ne change pour vous : mêmes protections, même fonctionnement. L'extension
ne collecte aucune donnée, ce qui est désormais déclaré explicitement dans son
manifeste — une exigence que Mozilla imposera bientôt à toutes les extensions.

## 1.5.5 — en préparation

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
