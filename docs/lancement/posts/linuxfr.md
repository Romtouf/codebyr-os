# Journal LinuxFr — à coller tel quel

**Titre : J'ai construit Codebyr OS — la compartimentation de Qubes, mais pour ma mère**

Bonjour 'nal,

Il y a quelques mois, je me suis posé une question simple : pourquoi la meilleure
idée de la sécurité desktop — la compartimentation façon Qubes OS — reste-t-elle
réservée aux experts avec 16 Go de RAM et une tolérance infinie à la friction ?

J'ai donc construit **Codebyr OS** : une distribution basée sur Debian stable qui
reprend cette idée, mais avec des mots humains et zéro configuration.

## Le concept : les Espaces

Au lieu de « VM », « domaines » et « templates », Codebyr propose des **Espaces** :
des compartiments isolés, chacun avec sa couleur. Personnel (bleu), Travail
(violet), Banque (vert), Navigation (orange), Jetable (rouge). Chaque fenêtre
porte un liseré à la couleur de son Espace : on sait toujours « où » on est.

Concrètement :

- **La pièce jointe douteuse** ? Clic droit → « Ouvrir en Jetable » : elle
  s'ouvre dans une bulle **sans réseau** (namespace réseau isolé) qui
  **s'autodétruit** à la fermeture. Le piège explose dans le vide. Un second
  geste, « Envoyer vers l'Espace… », déplace un document d'un compartiment à
  l'autre sans passer par le presse-papiers.
- **La banque** ? Le navigateur de l'Espace Banque ne peut joindre QUE les
  domaines de votre banque : l'Espace n'a aucune interface réseau à lui, tout
  passe par un filtre à liste blanche, lui-même confiné par AppArmor, qui
  refuse aussi les adresses du réseau local. Dans les autres Espaces, un
  bouclier anti-hameçonnage signé par Mozilla repère les sites sosies — y
  compris ceux écrits avec des lettres d'autres alphabets.
- **Le reste** : instantanés par Espace (« retour dans le temps »), mode invité
  auto-nettoyé, assistant de sécurité 100 % local, en français et en anglais
  (installeur en ~150 langues), installation 100 % hors-ligne possible.

Techniquement : l'isolation repose sur **bubblewrap** (namespaces noyau), et
**chaque Espace tourne sous son propre compte Unix** : ce qui s'échappe d'un
bac à sable ne lit toujours pas les fichiers des autres. Mode « Blindage » :
user namespace, cap-drop ALL, session neuve, plafonds mémoire/processus,
filtre d'appels système en liste d'autorisation, cloison Landlock. Bus D-Bus
privé par Espace.

## L'honnêteté d'abord

Ce n'est **pas** Qubes : pas de virtualisation matérielle, l'isolation repose
sur le noyau — un 0-day noyau peut donc s'échapper d'un namespace. C'est une
limite assumée. Le modèle de menace complet est dans le
SECURITY.md du dépôt : Codebyr réduit drastiquement les dégâts des menaces du
quotidien — hameçonnage, pièces jointes, sites frauduleux — il ne rend pas
invulnérable, et je refuse de prétendre le contraire.

## Où en est le projet

Version 1.20 (octobre 2026) : ISO live installable, testée sur machines
réelles (UEFI, hors-ligne, Wi-Fi, boutique Flatpak/Flathub incluse), mises à
jour par apt. Code sous GPL-3.0. **L'ISO est reproductible** : reconstruite
depuis le code publié, elle est identique octet pour octet. Les versions sont **signées
avec GPG** par une sous-clé dont la clé maîtresse vit hors ligne sur support
amovible — et la procédure de vérification du README fonctionne réellement, de
bout en bout, depuis un trousseau vierge.

Une commande résume l'esprit du projet :

```console
codebyr-space verifier-isolation
```

Elle lance une sonde **dans un vrai bac à sable** et rapporte ce qu'un Espace
atteint réellement — bus de session de l'hôte, `systemd --user`, socket X11,
réseau, dossier personnel — face à ce que chaque situation est censée
autoriser. Elle mesure au lieu d'affirmer. Sa jumelle, `verifier-poste`,
contrôle la machine installée de la même façon : compte invité sans mot de
passe utilisable, dossiers personnels en 0700, trousseau apt à jour, mises à
jour automatiques réellement armées. Chaque contrôle existe parce que la chose
en question a cassé ici une fois, en silence.

Deux points à peser avant d'essayer : **aucun audit professionnel** — une
analyse externe du code, en octobre 2026, a relevé quatre défauts, tous
corrigés —, et à en croire les compteurs de téléchargement, **je suis encore
le seul à l'utiliser**. C'est l'état honnête des choses, et c'est l'essentiel
de la raison de ce journal. L'historique des correctifs de sécurité — dont une
sortie de bac à sable fermée en 1.1.0 et deux élévations de privilèges que
j'ai trouvées en relisant le code — est dans SECURITY.md, pas enfoui dans les
commits.

→ **Le site (captures d'écran)** : https://os.codebyr.dev
→ **Dépôt + ISO signée** : https://github.com/Romtouf/codebyr-os

(Le site est auto-hébergé, ne charge aucune ressource tierce — polices
comprises — et n'a ni traceur ni CDN. La moindre des choses pour un projet
qui parle de vie privée.)

Je cherche des testeurs (surtout non techniques !), des retours francs, et des
contributeurs. Et je prends volontiers vos critiques sur le modèle de sécurité —
c'est comme ça qu'il s'améliorera.

Merci 'nal !

---

**Avant de poster** : mettre à jour le numéro de version, et relire l'état
de la section « Analyse externe » de SECURITY.md.
