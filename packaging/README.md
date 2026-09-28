# Canal de mise à jour — Codebyr OS

Sans ce canal, les outils Codebyr (`codebyr-*`, l'extension GNOME, le bouclier)
ne vivent que dans l'ISO : une personne ayant installé la 1.0 ne recevrait
**jamais** un correctif de sécurité sans réinstaller. Ce dossier livre les
correctifs par `apt`, comme n'importe quel paquet Debian.

## Vue d'ensemble

```
  build-deb.sh   →  codebyr-tools_<version>_all.deb   (tous les outils Codebyr)
  publish-apt.sh →  apt-repo/  (dépôt APT signé GPG : Packages, InRelease, .deb)
  apt-server/    →  conteneur nginx servant apt-repo/ sur apt.codebyr.dev
  (ISO)          →  hook 1000 + clé + unattended : le canal est actif dès l'installation
```

Le tout est signé avec la **même clé de release** que les ISO
(`E6FB6616EC58E15F40DA876CB1E8C803CE596E68`, trousseau `/root/.gnupg-codebyr`
du WSL de build).

> ⚠️ **Ce dépôt installe des paquets en root sur toutes les machines Codebyr.**
> La clé qui le signe vaut donc le parc entier. `publish-apt.sh` refuse
> désormais de signer avec une clé sans phrase de passe et n'en contient plus
> en clair. La hiérarchie cible (clé maîtresse hors ligne + sous-clé dédiée au
> dépôt), le renouvellement et la conduite à tenir en cas de fuite sont dans
> [docs/chaine-de-signature.md](../docs/chaine-de-signature.md). À faire **avant**
> toute diffusion large.

## Publier une nouvelle version

0. **Passer les tests** : `python -m unittest discover -s tests`.
   Si le test du bouclier signale que `content.js` diffère du `.xpi` signé,
   re-signez l'extension **avant** de publier (`live-build/scripts/sign-extension.sh`) :
   sans cela, votre correctif du bouclier ne s'appliquera sur aucune machine.
1. **Incrémenter la version** dans [`../VERSION`](../VERSION) (ex. `1.1.0`), et
   dater son entrée dans le CHANGELOG — une version pas encore publiée y est
   marquée « non publiée », et le README annonce la dernière qui l'est
   (`tests/test_coherence.py` y veille).
2. **Commiter, pousser, attendre la CI verte.** `publish-apt.sh` le vérifie et
   refuse sinon : du code non commité, un commit absent de GitHub, une CI rouge
   ou en cours. Échappatoire explicite, en cas de panne de GitHub seulement :
   `CODEBYR_PUBLIER_SANS_CI=1`.
3. **Construire le paquet** (dans le WSL de build) :
   ```bash
   CODEBYR_REPO=/mnt/c/Users/pcrom/codebyros bash packaging/build-deb.sh
   ```
4. **Générer et signer le dépôt** :
   ```bash
   GNUPGHOME=/root/.gnupg-codebyr bash packaging/publish-apt.sh
   # avec la sous-clé dédiée, une fois la migration faite :
   # CODEBYR_APT_KEY='<empreinte-sous-cle>!' bash packaging/publish-apt.sh
   ```
   La phrase de passe est demandée par `gpg-agent` ; pour un enchaînement non
   interactif, `CODEBYR_PASSPHRASE_FILE=/chemin/hors/depot` (jamais dans le
   dépôt, jamais dans l'historique du shell).

   Les paquets d'**essai** (version en `~`, comme `1.17.0~essai1`) restant dans
   `dist/` sont écartés : `unattended-upgrades` les installerait sur tout le
   parc. Un paquet plus récent que `VERSION` fait échouer la publication.
5. **Déployer** `packaging/apt-repo/` vers le serveur (voir ci-dessous).

### La date de péremption du dépôt

Le `Release` signé porte un `Valid-Until` (90 jours par défaut,
`CODEBYR_VALIDITE_JOURS` pour changer, `0` pour désactiver). Sans lui, qui tient
le serveur pourrait servir indéfiniment un **ancien** dépôt, correctement
signé : le parc ne recevrait plus aucun correctif, sans que rien le signale.

L'engagement en retour : **republier ou re-signer avant l'échéance**, affichée à
la fin de chaque publication. Sans nouvelle version, re-signer suffit :

```bash
GNUPGHOME=/root/.gnupg-codebyr bash packaging/publish-apt.sh --resigner
```

puis le même envoi. Passé l'échéance, `apt update` affiche une erreur pour ce
dépôt sur toutes les machines et les outils Codebyr cessent de se mettre à jour
— les mises à jour de Debian, elles, continuent.

Les machines installées récupèrent alors la mise à jour automatiquement
(`unattended-upgrades`) ou par `sudo apt update && sudo apt upgrade`.

## Héberger le dépôt (une fois)

Sur le serveur, à côté du site :

```bash
cd ~/docker
# placer le dépôt et la config du conteneur
mkdir -p codebyr-apt && cd codebyr-apt
cp -r <repo>/packaging/apt-server/* .
rsync -a --delete <repo>/packaging/apt-repo/ ./apt-repo/
docker compose up -d
```

Puis, dans **Nginx Proxy Manager** : `apt.codebyr.dev` → `codebyr-apt:80`,
SSL Let's Encrypt + Force SSL. (DNS : enregistrement A `apt` → IP du serveur.)

Vérifier : `curl -fsSL https://apt.codebyr.dev/InRelease | head` doit afficher
un bloc signé.

## Le canal dans l'ISO

Actif dans toutes les images publiées. Les pièces vivent dans la configuration
de live-build — il n'y en a pas d'autre copie :

- `live-build/config/hooks/normal/1000-canal-maj.hook.chroot` installe
  `codebyr-tools` comme vrai paquet, vérifie l'identité du système, active la
  socket du service des comptes, puis écrit le trousseau et la source APT ;
- `includes.chroot_after_packages/usr/share/keyrings/codebyr.asc` : la clé
  publique que ce hook convertit en trousseau ;
- `includes.chroot_after_packages/etc/apt/apt.conf.d/51codebyr-unattended` :
  l'origine « Codebyr OS » autorisée pour les mises à jour automatiques.

*(Le dossier `packaging/client/`, qui en gardait une copie de l'époque où le
canal n'était pas encore actif, a été retiré le 27/09/2026 : sa version du hook
était périmée et donnait une consigne devenue fausse.)*

## Adoption des fichiers existants

Sur une machine en 1.0, les fichiers Codebyr ont été posés par live-build (ils
n'appartiennent à aucun paquet). Le premier `apt install codebyr-tools` les
**adopte** proprement (dpkg en prend possession), puis les met à jour comme
n'importe quel paquet. `/etc/codebyr/espaces.json` est une *conffile* : une
modification locale est préservée et signalée en cas de conflit.

## Testé

Pipeline validé de bout en bout dans le WSL de build : construction du `.deb`
(droits normalisés, aucun dossier world-writable), dépôt signé (`Good
signature`), et `apt update` + `apt-cache policy` reconnaissant
`codebyr-tools 1.0.1` comme candidat depuis un dépôt local signé.
