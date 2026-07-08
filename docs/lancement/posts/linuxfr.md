# Journal LinuxFr — à coller tel quel (adapter les liens vidéo/captures)

**Titre : J'ai construit Codebyr OS — la compartimentation de Qubes, mais pour ma mère**

Bonjour 'nal,

Il y a quelques mois, je me suis posé une question simple : pourquoi la meilleure
idée de la sécurité desktop — la compartimentation façon Qubes OS — reste-t-elle
réservée aux experts avec 32 Go de RAM et une tolérance infinie à la friction ?

J'ai donc construit **Codebyr OS** : une distribution basée sur Debian stable qui
reprend cette idée, mais avec des mots humains et zéro configuration.

## Le concept : les Espaces

Au lieu de « VM », « domaines » et « templates », Codebyr propose des **Espaces** :
des compartiments isolés, chacun avec sa couleur. Personnel (bleu), Travail
(violet), Banque (vert), Navigation (orange), Jetable (rouge). Chaque fenêtre
porte un liseré à la couleur de son Espace : on sait toujours « où » on est.

Concrètement :

- **La pièce jointe douteuse** ? Clic droit → « Ouvrir en Jetable » : elle s'ouvre
  dans une bulle **sans réseau** (namespace réseau isolé) qui **s'autodétruit** à
  la fermeture. Le piège explose dans le vide.
- **La banque** ? L'Espace Banque n'a le droit de joindre QUE les domaines de
  votre banque (liste blanche réseau), et un bouclier anti-hameçonnage surveille
  les sites sosies dans les autres Espaces.
- **Le reste** : instantanés par Espace (« retour dans le temps »), mode invité
  auto-nettoyé, assistant de sécurité 100 % local, ~150 langues (français par
  défaut), installeur graphique Calamares, installation 100 % hors-ligne possible.

Techniquement : l'isolation repose sur **bubblewrap** (namespaces noyau), avec un
mode « Blindage » (user namespace, cap-drop ALL, session neuve, plafonds
mémoire/processus). Bus D-Bus privé par Espace, dossiers personnels séparés.

## L'honnêteté d'abord

Ce n'est **pas** Qubes : pas de virtualisation matérielle (c'est prévu comme
palier suivant pour les machines avec KVM — la détection est déjà là). Un 0-day
noyau peut s'échapper d'un namespace. Le modèle de menace complet est dans le
SECURITY.md du dépôt : Codebyr réduit drastiquement les dégâts des menaces du
quotidien — hameçonnage, pièces jointes, sites frauduleux — il ne rend pas
invulnérable, et je refuse de prétendre le contraire.

## Où en est le projet

v1.0 : ISO live installable, testée sur machines réelles (UEFI, hors-ligne,
Wi-Fi, boutique Flatpak/Flathub incluse). Code sous GPL-3.0, tout est
constructible avec live-build en trois commandes.

→ **Dépôt + ISO** : https://github.com/Romtouf/codebyr-os
→ Vidéo de 30 secondes du Jetable en action : [LIEN VIDÉO]

Je cherche des testeurs (surtout non techniques !), des retours francs, et des
contributeurs. Et je prends volontiers vos critiques sur le modèle de sécurité —
c'est comme ça qu'il s'améliorera.

Merci 'nal !
