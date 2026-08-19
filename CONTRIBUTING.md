# Contribuer à Codebyr OS

Merci de votre intérêt ! Ce document couvre l'essentiel pour construire, modifier
et tester Codebyr OS.

## Environnement de build

Il faut un système Debian/Ubuntu avec les droits root. Sous Windows, WSL2 avec une
distro Debian fonctionne très bien (c'est l'environnement de développement
d'origine) — voir `live-build/scripts/provision-wsl.sh`.

```bash
sudo apt install live-build rsync librsvg2-bin
export CODEBYR_REPO=/chemin/vers/ce/depot
sudo -E bash live-build/scripts/build.sh        # → dist/*.iso (30-60 min)
```

Points importants :
- **Jamais de build sur un montage Windows/9p** : le script recopie tout vers
  `/var/tmp/codebyr-build` (ext4) automatiquement.
- Le cache de paquets (`cache/`) survit aux rebuilds : les itérations suivantes
  sont bien plus rapides.
- `--apt-recommends false` est actif : **tout paquet requis doit être listé
  explicitement** dans `config/package-lists/`. C'est la source n°1 de bugs
  subtils (binaire manquant à l'exécution) — en cas de doute, vérifiez avec
  `live-build/scripts/inspect-iso.sh`.

## Architecture du code

| Composant | Rôle |
|---|---|
| `usr/bin/codebyr-space` | Cœur : cycle de vie des Espaces, bwrap, réseau, blindage |
| `usr/bin/codebyr-jetable` | Ouverture jetable de liens et fichiers |
| `usr/bin/codebyr-net-proxy` | Filtre réseau à liste blanche (HTTP/CONNECT) |
| `usr/bin/codebyr-config` | Réglages (GTK4/Adwaita) : domaines bancaires, blindage |
| `usr/bin/codebyr-assistant` | Assistant de sécurité (GTK4, 100 % local) |
| `usr/bin/codebyr-bienvenue` | Tour de bienvenue + lancement de l'installation |
| `usr/bin/codebyr-durcir-poste` | Durcissements du poste **installé** (dossiers personnels en 0700, compte invité sans mot de passe utilisable). Appelé par le hook de build, par Calamares et par le `postinst` du paquet |
| `tests/` | Suite de tests (bibliothèque standard, sans dépendance), dont les gardes de non-régression de sécurité |
| `usr/share/gnome-shell/extensions/codebyr@codebyr.io/` | Menu du Sceau, liserés colorés |
| `etc/codebyr/espaces.json` | Registre système des Espaces (copie utilisateur dans `~/.config/codebyr/`) |
| `config/hooks/normal/0*.hook.chroot` | Branding, durcissement, live, invité, débrand, locales, permissions, installeur |

Conventions :
- **Interface et messages en français**, code commenté en français.
- Python : bibliothèque standard uniquement (pas de dépendance pip) ; GTK4 via
  PyGObject pour les interfaces.
- Les scripts `usr/bin/codebyr-*` reçoivent automatiquement le bit exécutable au
  build (hook `0700-permissions`).

## Protocole de test (important)

L'expérience du projet en une règle : **ne jamais expédier un fichier qui n'a pas
été testé dans son état final exact.**

### 1. Automatisé (à lancer avant chaque commit)

```bash
python -m unittest discover -s tests -v
```

Sans dépendance : bibliothèque standard uniquement, comme le reste du projet.
La même suite tourne en CI (`.github/workflows/ci.yml`) sur chaque push et
chaque pull request, avec en plus `py_compile`, `ruff` (erreurs réelles
seulement), `bash -n`, `shellcheck` et la construction du `.deb`.

Les tests de `tests/test_bac_a_sable.py` sont des **gardes de non-régression de
sécurité** : chacun correspond à une ligne de l'historique des correctifs de
SECURITY.md. Un test rouge là-dedans n'est pas un détail de style — c'est une
faille qui revient. Ne les neutralisez jamais pour faire passer la CI.

### 2. Manuel (ce que la CI ne peut pas voir)

1. Les changements Calamares/branding se testent **dans le chroot** avant tout
   rebuild (voir les scripts d'inspection dans `live-build/scripts/`).
2. Test complet : ISO en machine virtuelle (QEMU/VirtualBox), puis idéalement sur
   machine réelle — la détection matérielle (KVM notamment) ne se valide qu'en réel.
3. Pour l'installeur : dérouler une installation complète jusqu'au redémarrage
   sur le système installé.
4. **Après toute modification touchant les comptes ou PAM**, vérifier sur le
   système installé :
   - `ls -ld /home/*` → l'utilisateur principal doit être en `drwx------` ;
   - se connecter en **Invité** depuis l'écran de connexion : aucun mot de passe
     ne doit être demandé ;
   - `sudo -u invite cat /home/<vous>/…` → doit être refusé ;
   - se déconnecter de la session invité, s'y reconnecter : elle doit être vierge.
5. **Après toute modification du bac à sable**, vérifier depuis un terminal
   ouvert DANS un Espace (menu du Sceau → Espace → Terminal) :

   ```sh
   ls $XDG_RUNTIME_DIR                     # aucun fichier « bus »
   systemctl --user status                 # doit ÉCHOUER
   busctl --user list | grep -c org.gnome.Shell   # doit afficher 0
   ```

   > ⚠️ Ne testez **pas** avec « `busctl --user` doit échouer » : c'est faux.
   > `busctl --user` se connecte au bus indiqué par l'environnement, donc au
   > bus **privé** de l'Espace — il RÉPOND, et c'est normal. Il liste même des
   > services « activatable », qui viennent des fichiers de
   > `/usr/share/dbus-1/` visibles en lecture seule. Ce qu'on veut prouver,
   > c'est que le bus de la **session hôte** est hors d'atteinte : d'où
   > `systemctl --user` (la porte de sortie historique) et l'absence de
   > `org.gnome.Shell`.

## Proposer un changement

1. Issue d'abord pour les changements de fond (nouvelle fonctionnalité,
   changement du modèle de sécurité).
2. Pull request avec : quoi/pourquoi, comment ça a été testé (voir protocole).
3. Les changements touchant à l'isolation ou au réseau doivent expliquer leur
   impact sécurité.

## Continuité du projet (à lire si vous dépendez de Codebyr OS)

Codebyr OS est aujourd'hui maintenu par **une seule personne**, et le dépôt APT
installe des paquets en root sur les machines des utilisateurs. Dire les choses
franchement vaut mieux que de laisser chacun le découvrir :

- **Si la maintenance s'arrête**, les machines installées continuent de
  fonctionner et reçoivent toujours les mises à jour de sécurité **Debian**
  (c'est la base du système). Seuls les correctifs des outils Codebyr
  s'arrêtent. Rien ne casse du jour au lendemain.
- **Le dépôt APT peut être neutralisé proprement** en supprimant
  `/etc/apt/sources.list.d/codebyr.sources` : le système redevient un Debian
  ordinaire, avec les Espaces figés dans leur version installée.
- **Tout est reconstructible** depuis ce dépôt : l'ISO (`live-build/scripts/build.sh`)
  et le paquet (`packaging/build-deb.sh`) ne dépendent d'aucun service privé.
  Seules les **clés de signature** ne sont pas dans le dépôt (par construction) :
  un fork devra publier sa propre clé et sa propre empreinte
  (voir [docs/chaine-de-signature.md](docs/chaine-de-signature.md)).
- **Ce qu'il faudrait pour réduire ce risque** : un second mainteneur avec accès
  au dépôt et à l'hébergement, et une clé de signature détenue par deux
  personnes. Les candidatures sont les bienvenues — c'est le besoin n°1 du
  projet, avant toute nouvelle fonctionnalité.

## Dette technique connue (assumée, écrite noir sur blanc)

- **Extension Firefox en Manifest V2.** Firefox la supporte encore, mais AMO
  pousse vers MV3 ; la migration devra être faite avant que MV2 ne soit refusé
  à la signature. Le bouclier étant un simple content script sans arrière-plan,
  la conversion devrait rester mécanique.
- **Registre des Espaces lu par quatre programmes** (trois en Python, un en
  GJS) : impossible de partager du code entre Python et GJS, et les outils
  Python restent volontairement autonomes. La règle (« la copie utilisateur
  prime ») est donc vérifiée par un test (`tests/test_registre_coherence.py`)
  plutôt que garantie par le langage.
- **Un seul compte Unix pour tous les Espaces** — voir SECURITY.md.
- **Les ISO ne sont pas reproductibles** (horodatage, état du miroir Debian).

## Où aider en priorité

- Tests sur du matériel varié (UEFI/BIOS, GPU divers, Wi-Fi capricieux)
- Traductions des outils Codebyr (l'infrastructure gettext reste à poser)
- **Un UID Unix par Espace** — la seule façon de rendre la séparation vraie même
  après une sortie de bac à sable (voir SECURITY.md, « Limites connues »)
- ISO reproductibles, et construction de l'ISO en CI (la CI actuelle vérifie le
  code et le paquet, pas l'image)
