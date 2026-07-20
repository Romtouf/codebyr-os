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
  client/        →  sources.list + clé + unattended, à embarquer dans l'ISO
```

Le tout est signé avec la **même clé de release** que les ISO
(`E6FB6616EC58E15F40DA876CB1E8C803CE596E68`, trousseau `/root/.gnupg-codebyr`
du WSL de build).

## Publier une nouvelle version

1. **Incrémenter la version** dans [`../VERSION`](../VERSION) (ex. `1.0.2`).
2. **Construire le paquet** (dans le WSL de build) :
   ```bash
   CODEBYR_REPO=/mnt/c/Users/pcrom/codebyros bash packaging/build-deb.sh
   ```
3. **Générer et signer le dépôt** :
   ```bash
   GNUPGHOME=/root/.gnupg-codebyr bash packaging/publish-apt.sh
   ```
4. **Déployer** `packaging/apt-repo/` vers le serveur (voir ci-dessous).

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

## Activer le canal dans l'ISO (une fois le dépôt EN LIGNE)

> ⚠️ **Ordre impératif.** N'activez ceci qu'après avoir confirmé que
> `https://apt.codebyr.dev/InRelease` répond. Un dépôt injoignable ferait
> échouer `apt update` sur toutes les machines.

```bash
cp packaging/client/1000-canal-maj.hook.chroot live-build/config/hooks/normal/
mkdir -p live-build/config/includes.chroot_after_packages/usr/share/keyrings
cp codebyr-signing-key.asc \
   live-build/config/includes.chroot_after_packages/usr/share/keyrings/codebyr.asc
mkdir -p live-build/config/includes.chroot_after_packages/etc/apt/sources.list.d \
         live-build/config/includes.chroot_after_packages/etc/apt/apt.conf.d
cp packaging/client/codebyr.sources \
   live-build/config/includes.chroot_after_packages/etc/apt/sources.list.d/
cp packaging/client/51codebyr-unattended \
   live-build/config/includes.chroot_after_packages/etc/apt/apt.conf.d/
```

Les ISO suivantes auront alors le canal actif dès l'installation.

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
