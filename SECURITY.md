# Politique de sécurité

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
- Le **navigateur** de l'Espace Banque ne peut joindre que les domaines de la
  liste blanche de l'utilisateur (proxy local — voir « Limites connues » :
  c'est un garde-fou au niveau du navigateur, pas encore une règle réseau
  imposée à tout l'Espace). **Liste vide = tout est bloqué** : un Espace à
  réseau restreint échoue fermé, jamais ouvert.
- Le **mode invité** est un vrai compte Unix distinct, sans droits
  d'administration, dont la session est effacée à la déconnexion. Le dossier
  personnel de l'utilisateur principal est en `0700` — sur l'image live **comme
  sur le système installé** (`codebyr-durcir-poste`). Le compte invité n'a aucun
  mot de passe utilisable (`*` dans `/etc/shadow`) : ni SSH, ni `su`, ni `sudo`
  ne peuvent s'en servir ; seule sa session graphique locale est autorisée, sans
  mot de passe.
- Le Blindage ajoute : espace de noms utilisateur, abandon de toutes les
  capabilities, session neuve (anti-injection TIOCSTI), plafonds
  mémoire/processus.
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
  par défaut. Partout ailleurs, le son fonctionne, donc le micro est joignable.
- **Un seul compte Unix pour tous les Espaces.** Leurs données vivent sous
  `~/.local/share/codebyr/espaces/`. Le bac à sable empêche une application
  *lancée dans un Espace* d'en sortir, mais toute application lancée
  normalement (hors Espace), ou tout code qui s'échapperait du bac à sable, lit
  l'ensemble. La séparation par UID dédié est la suite logique ; elle n'est pas
  encore faite.

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
projet. Sa protection, sa hiérarchie cible (clé maîtresse hors ligne +
sous-clés), la procédure de renouvellement et la conduite à tenir en cas de fuite
sont décrites dans [docs/chaine-de-signature.md](docs/chaine-de-signature.md) —
qui indique aussi, sans détour, ce qui n'est **pas encore** en place.

## Durcissement de la base

Debian stable, AppArmor actif, pare-feu nftables (`policy drop` en entrée),
Wayland, mises à jour de sécurité automatiques (`unattended-upgrades`),
`sysctl` durcis (kptr_restrict, ptrace_scope, protections liens/fifo…),
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
- **Filtre réseau bancaire** : appliqué au niveau du profil navigateur ; un code
  hostile déjà exécuté *dans* l'Espace pourrait le contourner. Il protège du web
  et de l'hameçonnage, pas d'un binaire malveillant lancé dans l'Espace.
- **Compositeur Wayland et audio (PipeWire) partagés** entre Espaces. Comme le
  presse-papiers Wayland dépend du compositeur, il est techniquement commun à
  tous les Espaces : la protection Codebyr (vidage au changement d'Espace,
  transfert explicite) est **temporelle** — elle réduit la fenêtre de fuite,
  elle n'apporte pas l'étanchéité d'une VM. Soupape :
  `~/.config/codebyr/presse-papiers-libre` désactive le vidage automatique.
- **Applications Flatpak** : proviennent de Flathub — confiance déléguée à
  Flathub et à l'éditeur de chaque application.
- **Sites bancaires réels et liste blanche** : beaucoup de banques chargent des
  ressources depuis des domaines tiers (CDN, prestataire 3-D Secure, captcha).
  Une liste blanche saisie à la main peut donc casser une authentification
  forte. Ajoutez le domaine signalé dans la page de blocage, ou utilisez un
  autre Espace le temps de l'opération — mais ne désactivez pas la protection.

## Historique des correctifs de sécurité

| Version | Correctif |
|---|---|
| 1.1.0 | **Sortie de bac à sable par le bus de session.** Le socket `$XDG_RUNTIME_DIR/bus` de l'hôte était monté (en lecture seule) dans chaque Espace. Un `--ro-bind` ne protège pas un socket : le noyau ne refuse l'écriture sur un montage read-only que pour les fichiers, répertoires et liens. Du code hostile dans un Espace pouvait donc parler au bus de session complet, appeler `systemd --user` (`StartTransientUnit`) et exécuter du code **hors** du bac à sable, sous l'identité de l'utilisateur — puis lire les données de tous les autres Espaces. Le socket n'est plus exposé ; chaque Espace n'a que son bus privé (`dbus-run-session`). |
| 1.1.0 | **Dossier personnel lisible par le compte invité sur le système installé.** Le `chmod 700` n'existait que dans l'image live, sur un compte supprimé à l'installation. Désormais appliqué à l'installation **et** rattrapé par `apt` sur les postes existants (`codebyr-durcir-poste`). |
| 1.1.0 | **Mot de passe du compte invité, public et identique partout** (`invite`/`invite`). Remplacé par un compte sans mot de passe utilisable (`*`), dont seule la session graphique locale est autorisée. |
| 1.1.0 | **Espace à réseau restreint sans domaine = réseau libre.** Le filtre ne démarrait pas si la liste blanche était vide : l'Espace Banque avait alors un accès complet à Internet alors que l'interface annonçait une restriction. Il échoue désormais fermé. |
