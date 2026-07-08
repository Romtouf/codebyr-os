# Signer le bouclier anti-hameçonnage (point de sécurité)

## Le problème

Aujourd'hui, le bouclier est chargé dans les profils Firefox en **désactivant la
vérification des signatures** (`xpinstall.signatures.required=false`). C'est le seul
moyen d'installer une extension non signée — mais ça abaisse la sécurité de Firefox
dans ces profils (n'importe quelle autre extension non signée pourrait s'y charger).

**Objectif :** un bouclier **signé par Mozilla**, installé sans jamais toucher à ce
réglage.

## Pourquoi ce n'est pas qu'un `web-ext sign`

Le bouclier a besoin de connaître **les domaines bancaires de l'utilisateur**.
Aujourd'hui, `codebyr-space` les injecte dans le code de l'extension au moment de
l'installation (placeholder `/*__DOMAINES__*/`). Or **une extension signée est
scellée** : la modifier casse la signature.

Il faut donc découpler les données du code. La bonne méthode Firefox :
**`storage.managed`** (stockage managé).

## Le plan (2 étapes)

### Étape A — Refonte pour le stockage managé (à faire AVEC un test sur matériel)

1. `manifest.json` : ajouter la permission `"storage"` et déclarer un
   `browser_specific_settings.gecko.id` (déjà présent : `antiphishing@codebyr.io`).
2. `content.js` : au lieu du placeholder, lire les domaines au démarrage via
   `await browser.storage.managed.get("domaines")` (repli sur liste vide).
3. `codebyr-space._installer_bouclier` : au lieu d'injecter dans le code, écrire
   un manifeste natif de stockage managé par profil :
   `~/.mozilla/managed-storage/antiphishing@codebyr.io.json`
   contenant `{ "name": "antiphishing@codebyr.io", "type": "storage",
   "data": { "domaines": [ ... ] } }`.
4. Le code de l'extension devient **statique** → signable.

> ⚠️ Cette refonte touche un composant de sécurité qui **fonctionne aujourd'hui**.
> Elle doit être testée sur Firefox réel (le comportement de `storage.managed`
> ne se teste pas dans le chroot). Tant qu'elle n'est pas validée, on garde
> l'approche actuelle (non signée) en repli.

### Étape B — Signature Mozilla (nécessite TON compte)

1. Crée des identifiants API sur
   https://addons.mozilla.org/developers/addon/api/key/
2. `AMO_KEY=... AMO_SECRET=... live-build/scripts/sign-extension.sh`
   → produit un `.xpi` signé (canal *unlisted*, non public).
3. Place le `.xpi` signé dans
   `.../usr/share/codebyr/antiphishing/signed/antiphishing@codebyr.io.xpi`.
4. `codebyr-space` : si ce fichier existe, l'installer **tel quel** dans le
   profil (sans écrire `xpinstall.signatures.required=false`) ; sinon, repli
   sur l'approche actuelle.

## État

- [x] Manifeste prêt (id + version)
- [x] Script de signature (`sign-extension.sh`) + guide
- [ ] Refonte `storage.managed` (à coder + **tester sur matériel**)
- [ ] Signature Mozilla (nécessite le compte AMO de Romain)

Tant que ce n'est pas terminé, la limite est **documentée publiquement** dans
[SECURITY.md](../SECURITY.md) — la transparence tient lieu de garde-fou.
