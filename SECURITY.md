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
- L'Espace Banque ne peut joindre **que** les domaines de la liste blanche de
  l'utilisateur.
- Le Blindage ajoute : espace de noms utilisateur, abandon de toutes les
  capabilities, session neuve (anti-injection TIOCSTI), plafonds
  mémoire/processus.

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

## Durcissement de la base

Debian stable, AppArmor actif, pare-feu nftables, Wayland, mises à jour de
sécurité automatiques (`unattended-upgrades`), surface applicative minimale
(`--apt-recommends false`).
