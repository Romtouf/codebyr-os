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

1. `python -m py_compile` sur tout script Python modifié.
2. Les changements Calamares/branding se testent **dans le chroot** avant tout
   rebuild (voir les scripts d'inspection dans `live-build/scripts/`).
3. Test complet : ISO en machine virtuelle (QEMU/VirtualBox), puis idéalement sur
   machine réelle — la détection matérielle (KVM notamment) ne se valide qu'en réel.
4. Pour l'installeur : dérouler une installation complète jusqu'au redémarrage
   sur le système installé.

## Proposer un changement

1. Issue d'abord pour les changements de fond (nouvelle fonctionnalité,
   changement du modèle de sécurité).
2. Pull request avec : quoi/pourquoi, comment ça a été testé (voir protocole).
3. Les changements touchant à l'isolation ou au réseau doivent expliquer leur
   impact sécurité.

## Où aider en priorité

- Tests sur du matériel varié (UEFI/BIOS, GPU divers, Wi-Fi capricieux)
- Traductions des outils Codebyr (l'infrastructure gettext reste à poser)
- CI de build (GitHub Actions) et ISO reproductibles
- Phase 6 : prototype micro-VM KVM pour les Espaces sensibles
