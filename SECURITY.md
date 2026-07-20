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
- Un Espace compromis n'accède pas aux fichiers des autres Espaces (dossiers
  personnels séparés, bus D-Bus privés, `/tmp` isolés).
- Le **navigateur** de l'Espace Banque ne peut joindre que les domaines de la
  liste blanche de l'utilisateur (proxy local — voir « Limites connues » :
  c'est un garde-fou au niveau du navigateur, pas encore une règle réseau
  imposée à tout l'Espace).
- Le Blindage ajoute : espace de noms utilisateur, abandon de toutes les
  capabilities, session neuve (anti-injection TIOCSTI), plafonds
  mémoire/processus.
- Le presse-papiers ne « suit » pas passivement d'un Espace à l'autre : dès que
  le focus passe à un Espace différent de celui qui l'a rempli, il est vidé.
  Un transfert reste possible mais **explicite** (menu « Transférer vers… »).

**Hors périmètre (assumé) :**
- Exploits noyau : l'isolation repose sur les namespaces Linux (bubblewrap),
  pas sur de la virtualisation matérielle. Un attaquant disposant d'un 0-day
  noyau peut s'échapper. Le palier micro-VM (KVM) est prévu en Phase 6.
- Attaquant physique, evil maid, matériel compromis.
- Le compositeur Wayland et le serveur audio sont partagés entre Espaces
  (fenêtres et son doivent bien s'afficher quelque part) : un Espace ne peut pas
  lire l'écran d'un autre via Wayland, mais ce canal n'a pas l'étanchéité d'une VM.

**Principe de communication** : Codebyr OS « réduit drastiquement les dégâts » —
jamais « rend invulnérable ». Toute contribution qui gonflerait la promesse
au-delà de ce que le code garantit sera refusée.

## Intégrité des versions

Chaque ISO est signée avec la clé GPG du projet. Le fichier `SHA256SUMS` (empreinte
de l'ISO) est accompagné de `SHA256SUMS.asc` (signature détachée). La clé publique
est dans le dépôt (`codebyr-signing-key.asc`), empreinte
`E6FB6616EC58E15F40DA876CB1E8C803CE596E68`. Procédure de vérification : voir le
README. N'utilisez jamais une ISO dont la signature n'est pas valide.

## Durcissement de la base

Debian stable, AppArmor actif, pare-feu nftables (`policy drop` en entrée),
Wayland, mises à jour de sécurité automatiques (`unattended-upgrades`),
`sysctl` durcis (kptr_restrict, ptrace_scope, protections liens/fifo…),
surface applicative minimale (`--apt-recommends false`).

## Limites connues (transparence)

- **Extensions Firefox non signées** : le bouclier anti-hameçonnage est chargé
  via `xpinstall.signatures.required=false` dans les profils concernés, ce qui
  abaisse la vérification des signatures d'extensions dans ces profils.
  Objectif : faire signer le bouclier par Mozilla (AMO, distribution privée).
- **Filtre réseau bancaire** : appliqué au niveau du profil navigateur ; un code
  hostile déjà exécuté *dans* l'Espace pourrait le contourner. Il protège du web
  et de l'hameçonnage, pas d'un binaire malveillant lancé dans l'Espace.
- **Compositeur Wayland et audio (PipeWire) partagés** entre Espaces. Comme le
  presse-papiers Wayland dépend du compositeur, il est techniquement commun à
  tous les Espaces : la protection Codebyr (vidage au changement d'Espace,
  transfert explicite) est **temporelle** — elle réduit la fenêtre de fuite,
  elle n'apporte pas l'étanchéité d'une VM. L'isolation forte du presse-papiers
  suppose des compositeurs imbriqués (piste micro-VM, Phase 6). Soupape :
  `~/.config/codebyr/presse-papiers-libre` désactive le vidage automatique.
- **Applications Flatpak** : proviennent de Flathub — confiance déléguée à
  Flathub et à l'éditeur de chaque application.
