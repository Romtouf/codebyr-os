# Journal des versions — Codebyr OS

Ce que chaque version apporte, en clair. Les correctifs de **sécurité** sont
détaillés dans [SECURITY.md](SECURITY.md), qui indique aussi ce qui était
vulnérable et comment.

Les mises à jour arrivent toutes seules par `apt` sur les machines installées.
Après une mise à jour, **déconnectez-vous et reconnectez-vous** : l'extension
GNOME (menu du Sceau, liserés colorés) ne se recharge pas à chaud.

---

## 1.5.5 — en préparation

**Retour à l'icône du Sceau d'origine.** Trois tentatives d'amélioration l'ont
laissée invisible dans le panneau. La dernière reposait pourtant sur un
diagnostic vérifié — le bon code s'exécutait, sans erreur au journal — et
l'icône ne se dessinait toujours pas.

L'icône historique est restaurée telle quelle. Elle n'est pas belle, mais elle
se voit sur les deux panneaux, ce pour quoi son gris avait été choisi. Ce qui a
été essayé, et pourquoi chaque essai a échoué, est consigné dans
`docs/chantiers.md` — le sujet ne sera rouvert qu'avec les moyens de l'essayer
en direct.

## 1.5.4 — en préparation

**Le Sceau ne se dessinait plus du tout.** Ni couleur ni thème en cause : la
construction. En réorganisant le code pour permettre deux variantes, l'icône
naissait vide et recevait son fichier ensuite — et dans ce cas elle ne
s'affiche pas. Restait la pastille de survol, vide, à sa place.

Le fichier est de nouveau passé au constructeur, comme dans la version qui
fonctionnait, avec une taille explicite. Et le suivi du thème ne peut plus
interrompre la construction de l'indicateur : il échoue en silence plutôt que
de tout emporter avec lui.

## 1.5.3 — en préparation

**Le Sceau, enfin.** La 1.5.2 le choisissait d'après le réglage `color-scheme`,
qui vaut « default » sur Codebyr — le thème *clair* des applications. Or GNOME
affiche malgré tout un panneau noir : le Sceau sombre y restait invisible, et
il ne restait qu'une pastille vide à sa place.

L'extension **mesure** désormais la couleur réelle du panneau au lieu de la
déduire d'un réglage, et choisit sur sa luminance. Si la mesure échoue, elle
retient le Sceau clair — le panneau de GNOME est noir par défaut.

## 1.5.2 — en préparation

**Le Sceau redevient visible.** La 1.5.1 l'avait rendu invisible sur le thème
sombre : passé à la couleur de base d'Adwaita, il comptait sur la recoloration
symbolique de GNOME — qui ne s'applique pas à une icône chargée depuis un
fichier. Sur un panneau noir, contraste de 1,7.

Aucune couleur fixe ne pouvait convenir : le panneau GNOME vaut `#fafafb` en
thème clair et `#000000` en sombre. Le Sceau existe donc en deux variantes, et
l'extension choisit selon votre thème — en changeant avec lui, sans
reconnexion.

## 1.5.1 — en préparation

**L'icône du Sceau, pour de vrai cette fois.** La 1.5.0 annonçait une icône
corrigée et embarquait l'ancienne : le paquet avait été construit avant le
correctif, et rien ne pouvait le montrer — le numéro de version, lui, était le
bon.

La publication refuse désormais un paquet plus ancien que le code qu'il est
censé contenir. C'est le même piège que l'ISO périmée : un artefact daté que
l'on republie en croyant publier son travail.

## 1.5.0 — en préparation

**`codebyr-space verifier-poste` : la machine vérifie elle-même ce qu'on lui a
promis.** Six contrôles, chacun correspondant à un défaut réellement survenu
ici — jamais à une hypothèse : le clic droit Jetable est-il vraiment chargeable,
le compte invité refuse-t-il tout mot de passe, les dossiers personnels sont-ils
privés, le trousseau connaît-il la clé qui signe aujourd'hui, les mises à jour
sont-elles réellement armées, le bac à sable est-il opérationnel.

Ces défauts ont un point commun qui les rend redoutables : **ils ne se voient
pas à l'usage.** Un poste dont le trousseau a périmé, ou dont le compte invité
a repris un mot de passe, se comporte exactement comme un poste sain. Il ne
s'en plaint jamais.

Même principe que `verifier-isolation` : on n'interroge pas le système, on
l'observe.

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
