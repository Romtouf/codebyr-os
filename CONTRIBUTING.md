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

## Textes affichés et traductions

Le texte écrit dans le code est la version **française** ; les autres langues
sont des traductions, dans `po/<langue>.po` (anglais : `po/en.po`, la langue
de référence pour qui ne lit pas le français).

- Tout texte destiné à l'écran passe par `_()` (Python :
  `from traduction import _`), écrit tel quel. On le complète **après** :
  `_("Ouvrir « {nom} »").format(nom=nom)` — jamais `_(f"…")`, que l'outil
  refuse : une traduction a besoin de déplacer les mots autour de `{nom}`.
- Les pluriels : `n_("{n} fichier", "{n} fichiers", n)`.
- Après avoir écrit ou modifié un texte :
  `python3 packaging/traductions.py extraire`, puis traduire les `msgstr`
  vides de `po/en.po`. `tests/test_traduction.py` échoue tant qu'il en reste.
- Lanceurs (`.desktop`) : `Name=` en anglais, `Name[fr]=` en français — GNOME
  montre `Name=` aux langues sans traduction.
- Ajouter une langue : copier `po/en.po` en `po/<langue>.po`, y changer
  `Language:` et traduire. La construction du paquet la compile seule.

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

- **Registre des Espaces lu par deux programmes** : le module `registre.py`,
  partagé par les trois outils Python, et l'extension GNOME, en GJS. Ils ne
  peuvent pas partager de code. Le format fait foi en un seul endroit,
  [docs/registre.md](docs/registre.md), et `tests/test_registre_coherence.py`
  vérifie que les deux appliquent la même règle et que chaque clé livrée y est
  décrite.
- **Une fonction manque sous compte séparé**, le mode par défaut depuis
  1.16.1 : une application Flatpak n'y reçoit pas le fichier choisi dans
  « Ouvrir un fichier » — voir SECURITY.md.

## Où aider en priorité

> La liste complète et priorisée des chantiers — sécurité, produit, dette
> technique, et ce qui est volontairement hors périmètre — est dans
> [docs/chantiers.md](docs/chantiers.md).

- Tests sur du matériel varié (UEFI/BIOS, GPU divers, Wi-Fi capricieux)
- Traductions des outils Codebyr (l'infrastructure gettext reste à poser)
- **Reconstruire l'ISO d'une version** et comparer son empreinte à celle de la
  release (README, « Reconstruire l'ISO vous-même ») : depuis la 1.16.8, l'image
  est reproductible, et chaque vérification indépendante compte
