# Signer le bouclier anti-hameçonnage

## Pourquoi il faut le faire, et quand

Le bouclier est une extension Firefox. **Firefox refuse de charger une extension
non signée** par Mozilla. Codebyr a longtemps contourné ce refus en posant
`xpinstall.signatures.required=false` dans les profils concernés — autrement dit
en désactivant la vérification des signatures d'extensions pour y installer une
protection. Ce contournement a été **supprimé** : aujourd'hui, sans `.xpi` signé,
`codebyr-space` n'installe rien et le dit.

Conséquence à retenir : **un `.xpi` signé est scellé.** Modifier son code
(`content.js`, `rendu.js`, `background.js`, `alerte.html`, `alerte.js`) dans le dépôt ne change strictement rien sur les machines tant que l'extension
n'a pas été re-signée. C'est contre-intuitif, et c'est la raison d'être du test
`tests/test_bouclier.py::XpiSigne` : il compare le code du dépôt à celui du
`.xpi` livré et passe au rouge dès qu'ils divergent.

**À faire donc à chaque modification de ce code, de `manifest.json` ou
des textes de l'alerte (`_locales/`).**

## Les langues de l'alerte (depuis la 1.4)

Les textes de l'alerte sont dans `_locales/<langue>/messages.json`, le format
des extensions : Firefox prend la langue de son interface, sinon l'anglais
(`default_locale`), comme le reste de Codebyr. **Le français
(`_locales/fr`) est la source**, écrite à la main ; les autres langues sont
produites depuis `po/<langue>.po` par `python3 packaging/traductions.py
extraire`. Un traducteur n'a donc qu'un fichier à tenir — mais une langue
ajoutée ou corrigée ne part qu'avec une nouvelle signature : la commande le
rappelle quand elle réécrit un `messages.json`.

## Une seule fois : les identifiants

1. Ouvrir <https://addons.mozilla.org/fr/developers/addon/api/key/>
   La page demande d'abord une connexion à un **compte Firefox** (le même que
   pour la synchronisation, si vous en avez un) : c'est normal, elle renvoie
   ensuite sur le formulaire. Sans le préfixe de langue (`/fr/` ou `/en-US/`),
   l'adresse ne répond pas.
2. Cliquer sur **« Generate new credentials »**. Deux valeurs apparaissent :
   - **JWT issuer** — de la forme `user:12345678:123`
   - **JWT secret** — une longue chaîne, **affichée une seule fois**
3. Les déposer dans un fichier **hors du dépôt**, `~/.codebyr-amo` :

   ```sh
   AMO_KEY='user:12345678:123'
   AMO_SECRET='le-long-secret'
   ```

   Ce secret permet de publier des extensions sous votre identité : il ne va ni
   dans le dépôt, ni dans un message, ni dans l'historique du shell.
4. Vérifier que `web-ext` est là : `web-ext --version`. Sinon :
   `npm install -g web-ext`.

## À chaque signature

```sh
sh live-build/scripts/sign-extension.sh
```

Le script fait tout : il vérifie que le numéro de version n'a pas déjà été
signé (Mozilla refuse un doublon), n'envoie que `manifest.json`, le code
et `_locales/` — surtout pas le sous-dossier `signed/`, qui embarquerait
l'ancien `.xpi` dans le nouveau —, récupère le paquet signé, l'installe dans
`…/antiphishing/signed/` en remplaçant le précédent, puis vérifie que le code,
le manifeste et les textes du `.xpi` sont bien ceux du dépôt.

Avant de signer, un contrôle sans compte ni envoi :
`web-ext lint --source-dir <copie de manifest.json, du code et de _locales>`.
Une version signée ne se resoumet pas : mieux vaut qu'elle soit juste du
premier coup.

Puis, pour confirmer :

```sh
python -m unittest discover -s tests    # les 2 tests du bouclier passent au vert
```

La signature se fait en canal **unlisted** (distribution privée) : pas de revue
humaine, pas de publication sur le catalogue Mozilla, une signature automatique
en une à deux minutes.

## Si Mozilla refuse

| Message | Cause | Solution |
|---|---|---|
| `Version already exists` | Ce numéro a déjà été signé | Monter `"version"` dans `manifest.json` (1.1 → 1.2) |
| `401 Unauthorized` | Identifiants invalides ou expirés | Régénérer les identifiants sur la page AMO |
| `Upload failed` | Identifiants faux, ou AMO indisponible | Vérifier `~/.codebyr-amo`, puis réessayer |

## Comment le bouclier arrive dans Firefox

C'est **Firefox qui l'installe**, par une politique d'entreprise livrée avec le
paquet : `/usr/lib/firefox-esr/distribution/policies.json`, qui désigne le
`.xpi` signé par son nom. `sign-extension.sh` met ce nom à jour à chaque
signature, et `tests/test_bouclier.py` vérifie que les deux concordent.

Pourquoi pas une copie déposée dans le profil, comme avant la 1.16.3 : une
extension Manifest V3 n'y reçoit pas d'office le droit de lire les pages.
Firefox ne l'accorde qu'à une installation par son circuit ordinaire — celui
qu'emprunte la politique. Le bouclier déposé restait chargé, signé, actif, et
ne s'exécutait sur aucune page (de la 1.6.0 à la 1.16.2). Deux autres faits
mesurés sur Firefox 140 ESR :

- ce Firefox lit la politique dans son dossier `distribution`, et dans
  `/etc/firefox/policies/` — **pas** dans `/etc/firefox-esr/policies/`. Un
  administrateur qui pose la sienne dans `/etc/firefox/policies/` remplace
  celle de Codebyr, et doit alors y reprendre le bouclier ;
- Firefox refuse de réinstaller par la politique une version déjà présente :
  c'est pourquoi `codebyr-space` retire les copies déposées autrefois.

## Comment les domaines arrivent dans une extension scellée

Le bouclier a besoin des domaines bancaires **de chaque utilisateur**, mais une
extension signée ne peut pas être modifiée. Le découplage se fait par le
**stockage managé** de Firefox : `codebyr-space` écrit
`~/.mozilla/managed-storage/antiphishing@codebyr.io.json` dans le dossier
personnel de l'Espace, et `content.js` lit les domaines au démarrage via
`browser.storage.managed.get("domaines")`. Le code reste donc **statique**, donc
signable, et les données restent propres à chaque utilisateur.

C'est ce qui rend la signature possible ; ne revenez pas à une injection de
domaines dans le code sans mesurer que cela rendrait l'extension insignable.
