# Journal des versions — Codebyr OS

Ce que chaque version apporte, en clair. Les correctifs de **sécurité** sont
détaillés dans [SECURITY.md](SECURITY.md), qui indique aussi ce qui était
vulnérable et comment.

Les mises à jour arrivent toutes seules par `apt` sur les machines installées.
Après une mise à jour, **déconnectez-vous et reconnectez-vous** : l'extension
GNOME (menu du Sceau, liserés colorés) ne se recharge pas à chaud.

---

## 1.3.1 — en préparation

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

## 1.3.0 — en préparation

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
