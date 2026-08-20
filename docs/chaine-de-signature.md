# Chaîne de signature — Codebyr OS

Ce document décrit ce que les clés du projet engagent, comment elles doivent
être protégées, et quoi faire si l'une d'elles fuit.

## Pourquoi c'est le point le plus sensible du projet

Le dépôt APT `apt.codebyr.dev` est configuré sur chaque machine Codebyr avec
`unattended-upgrades`. Autrement dit : **ce qui est signé par la clé du projet
s'installe tout seul, en root, chez tous les utilisateurs.** Une clé de
signature compromise ne vaut pas un incident de sécurité — elle vaut la prise de
contrôle du parc.

Le serveur, lui, est secondaire : `apt` refuse un dépôt dont la signature ne
correspond pas au trousseau embarqué. Un serveur piraté sans la clé ne peut rien
livrer. **La clé est l'actif à protéger, pas la machine qui la sert.**

## État actuel (à corriger)

| | Situation | Risque |
|---|---|---|
| Nombre de clés | **Une seule**, `E6FB6616EC58E15F40DA876CB1E8C803CE596E68` | Elle signe les ISO *et* le dépôt APT : une fuite compromet tout d'un coup |
| Emplacement | `/root/.gnupg-codebyr` du WSL de build, sur un poste Windows de développement | Poste de travail quotidien, exposé au web et au courriel |
| Phrase de passe | ~~Aucune~~ → **posée le 20/08/2026** | Un vol de fichiers ne suffit plus à signer à la place du projet |
| Expiration | Aucune | Une clé volée reste valable indéfiniment |
| Révocation | Pas de certificat prégénéré | Sans lui, impossible de révoquer une clé dont on a perdu l'accès |

`publish-apt.sh` refuse désormais de signer avec une clé sans phrase de passe et
ne contient plus de phrase de passe en clair. La suite ci-dessous est la
migration à faire **avant** toute diffusion large.

## Cible : une clé maîtresse hors ligne, des sous-clés en service

```
  Clé maîtresse (certification uniquement, [C])
  └─ hors ligne : clé USB chiffrée + copie papier, JAMAIS sur le poste de build
     ├─ sous-clé [S] « releases »   → signe SHA256SUMS des ISO
     └─ sous-clé [S] « apt »        → signe InRelease / Release.gpg du dépôt
```

Ce que cela change concrètement : une sous-clé volée se révoque et se remplace
depuis la clé maîtresse **sans changer l'empreinte publiée**, donc sans avoir à
faire réimporter une nouvelle clé à tous les utilisateurs. C'est précisément ce
qu'on ne peut pas faire aujourd'hui.

### Mise en place

```bash
export GNUPGHOME=/root/.gnupg-codebyr

# 1) Deux sous-clés de signature, valables 1 an, sur la clé existante.
gpg --quick-add-key E6FB6616EC58E15F40DA876CB1E8C803CE596E68 ed25519 sign 1y   # releases
gpg --quick-add-key E6FB6616EC58E15F40DA876CB1E8C803CE596E68 ed25519 sign 1y   # apt
gpg --list-secret-keys --with-subkey-fingerprints   # noter les deux empreintes

# 2) Certificat de révocation — À FAIRE MAINTENANT, pas le jour de l'incident.
gpg --output revocation-codebyr.asc --gen-revoke \
    E6FB6616EC58E15F40DA876CB1E8C803CE596E68
#    → à stocker HORS de ce dépôt et hors du poste de build
#      (clé USB chiffrée, coffre, impression papier). Ce fichier permet à
#      quiconque le détient de révoquer la clé : il se protège comme la clé.

# 3) Sauvegarder la clé maîtresse, puis la RETIRER du poste de build.
gpg --export-secret-keys --armor \
    E6FB6616EC58E15F40DA876CB1E8C803CE596E68 > maitresse-SECRETE.asc   # → support hors ligne
gpg --export-secret-subkeys --armor \
    E6FB6616EC58E15F40DA876CB1E8C803CE596E68 > sous-cles.asc
gpg --delete-secret-keys E6FB6616EC58E15F40DA876CB1E8C803CE596E68
gpg --import sous-cles.asc          # le poste de build ne garde QUE les sous-clés

# 4) Phrase de passe (indispensable).
gpg --edit-key E6FB6616EC58E15F40DA876CB1E8C803CE596E68 passwd
```

> `.gitignore` exclut `*-SECRETE.asc`, `*secret*.asc` et `*.gpg` — mais ne
> comptez pas dessus : ces fichiers n'ont rien à faire dans l'arborescence du
> dépôt, même ignorés.

### Utilisation ensuite

```bash
# Dépôt APT — le « ! » impose CETTE sous-clé (sinon gpg choisit tout seul).
CODEBYR_APT_KEY='<empreinte-sous-cle-apt>!' bash packaging/publish-apt.sh

# ISO
CODEBYR_SIGNER='<empreinte-sous-cle-releases>!' bash live-build/scripts/sign-release.sh
```

L'empreinte publiée aux utilisateurs (README, SECURITY.md, `codebyr-verifier`,
site) reste celle de la **clé maîtresse** : elle ne change pas quand une
sous-clé est renouvelée.

## Poser ou changer la phrase de passe (piège WSL)

```sh
export GPG_TTY=$(tty)          # SANS cette ligne, rien ne se passe
export GNUPGHOME=/root/.gnupg-codebyr
gpg --edit-key E6FB6616EC58E15F40DA876CB1E8C803CE596E68
gpg> passwd
gpg> save
```

Deux pièges qui font perdre du temps :

- **Sans `GPG_TTY`, `passwd` échoue en silence.** L'agent ne sait pas sur quel
  terminal afficher la demande, et rend la main sans un mot ni une erreur. La
  ligne est désormais dans le `.bashrc` du WSL de construction.
- **« Key not changed so no update needed » n'est PAS un échec.** Depuis
  GnuPG 2, `passwd` modifie la protection de la clé privée par l'agent,
  immédiatement ; la partie publique du trousseau, elle, ne change pas. Ce
  message est donc normal et attendu.

Pour vérifier sans se fier à une impression :

```sh
gpg-connect-agent 'keyinfo --list' /bye | grep '^S KEYINFO'
# S KEYINFO <keygrip> D - - <cache> <protection> <fpr> ...
#                           $7      $8 → P protégée, C en clair
```

Attention à la colonne : `$7` est le **cache**, `$8` la **protection**. Tester
en signant ne prouve rien si l'agent a la phrase en mémoire — il ne la
redemandera pas.

## Renouvellement annuel

Les sous-clés expirent au bout d'un an — volontairement, pour forcer le geste.
Un mois avant (`publish-apt.sh` prévient), sortir la clé maîtresse du support
hors ligne et prolonger :

```bash
gpg --edit-key E6FB…6E68
> key 1        # sélectionner la sous-clé
> expire       # 1y
> save
gpg --export-secret-subkeys --armor E6FB…6E68 > sous-cles.asc   # → poste de build
```

Rien à republier côté utilisateur : l'ancre de confiance est inchangée.

## En cas de compromission

1. **Couper la diffusion** : retirer `apt-repo/` du serveur (mieux vaut un
   `apt update` en échec qu'un paquet hostile installé en root).
2. Révoquer la sous-clé concernée depuis la clé maîtresse, publier le trousseau
   à jour, republier le dépôt signé avec une sous-clé neuve.
3. Si c'est la **clé maîtresse** qui a fuité : importer le certificat de
   révocation prégénéré, publier la clé révoquée, créer une nouvelle clé, et
   **annoncer publiquement** la rotation (README, site, canaux du projet) avec
   la nouvelle empreinte. Les utilisateurs devront réimporter la clé à la main :
   c'est le scénario coûteux, celui que la hiérarchie ci-dessus permet d'éviter.
4. Publier un avis dans `SECURITY.md` : ce qui a fuité, quand, quelles versions
   sont suspectes, comment vérifier.

## Ce qui reste à faire

- [ ] Sous-clés dédiées `releases` et `apt`, clé maîtresse hors ligne
- [x] Phrase de passe sur la clé de signature *(posée le 20/08/2026 ; `publish-apt.sh` le confirme au démarrage)*
- [ ] Certificat de révocation généré et stocké hors ligne
- [ ] Expiration à 1 an sur les sous-clés
- [ ] Empreinte publiée en plusieurs endroits indépendants (dépôt, site, réseaux)
      pour qu'une substitution soit détectable
