# Signer le bouclier anti-hameçonnage

## Pourquoi il faut le faire, et quand

Le bouclier est une extension Firefox. **Firefox refuse de charger une extension
non signée** par Mozilla. Codebyr a longtemps contourné ce refus en posant
`xpinstall.signatures.required=false` dans les profils concernés — autrement dit
en désactivant la vérification des signatures d'extensions pour y installer une
protection. Ce contournement a été **supprimé** : aujourd'hui, sans `.xpi` signé,
`codebyr-space` n'installe rien et le dit.

Conséquence à retenir : **un `.xpi` signé est scellé.** Modifier `content.js`
dans le dépôt ne change strictement rien sur les machines tant que l'extension
n'a pas été re-signée. C'est contre-intuitif, et c'est la raison d'être du test
`tests/test_bouclier.py::XpiSigne` : il compare le code du dépôt à celui du
`.xpi` livré et passe au rouge dès qu'ils divergent.

**À faire donc à chaque modification de `content.js` ou de `manifest.json`.**

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
signé (Mozilla refuse un doublon), n'envoie que `manifest.json` et `content.js`
— surtout pas le sous-dossier `signed/`, qui embarquerait l'ancien `.xpi` dans
le nouveau —, récupère le paquet signé, l'installe dans
`…/antiphishing/signed/` en remplaçant le précédent, puis vérifie que le code
du `.xpi` est bien celui du dépôt.

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
