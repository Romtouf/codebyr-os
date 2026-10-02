# Le canal d'essai

Codebyr se met à jour tout seul, en administrateur, sans personne devant
l'écran. Une version publiée arrive donc sur **toutes** les machines en
quelques heures. D'où deux canaux, depuis la 1.20.1 :

| Canal | Adresse | Pour qui | Rythme |
|---|---|---|---|
| **stable** | `https://apt.codebyr.dev` | tout le monde (le réglage de l'installation) | une version par semaine au plus — un correctif de sécurité part sans attendre |
| **essai** | `https://apt.codebyr.dev/essai` | les testeurs volontaires | dès qu'une version d'essai est prête |

Le canal d'essai contient les versions stables, **plus** la dernière version
d'essai (`1.20.1~essai2`, par exemple). Elle est construite depuis du code
poussé et validé par la CI, et signée par la même clé que le reste. Pour apt,
`1.20.1~essai2` est plus ancienne que `1.20.1` : à la publication stable, un
testeur reçoit la version définitive comme tout le monde.

Comme le canal stable, le canal d'essai ne peut fournir que `codebyr-tools` :
l'épinglage d'apt (`/etc/apt/preferences.d/codebyr.pref`) vaut pour tout le
serveur `apt.codebyr.dev`.

## Rejoindre le canal d'essai

Dans un terminal :

```sh
sudo tee /etc/apt/sources.list.d/codebyr-essai.sources >/dev/null <<'FIN'
Types: deb
URIs: https://apt.codebyr.dev/essai
Suites: ./
Signed-By: /usr/share/keyrings/codebyr-archive-keyring.gpg
FIN
sudo apt update
```

Les versions d'essai arrivent ensuite par les mises à jour automatiques. Pour
en avoir une tout de suite : `sudo apt upgrade`.

Merci de signaler ce qui ne va pas sur
<https://github.com/Romtouf/codebyr-os/issues>, avec la sortie de
`codebyr-space verifier-poste` et la version (`apt policy codebyr-tools`).

## Le quitter

```sh
sudo rm /etc/apt/sources.list.d/codebyr-essai.sources
sudo apt update
```

La machine garde sa version d'essai jusqu'à la version stable suivante, qui la
remplace d'elle-même.

## Publier une version d'essai (mainteneur)

1. Le code est commité, poussé, et la CI est verte.
2. Construire le paquet d'essai de la version en préparation :
   `./build-deb.sh 1.20.1~essai1` (le numéro de VERSION, suivi de `~essaiN`).
3. Dans le WSL : `./publish-apt.sh --essai`. Le script fait les mêmes
   vérifications que pour le stable (code commité, paquet plus récent que le
   code, CI verte, signature) et ne prend que le paquet d'essai le plus récent
   de cette version.
4. Envoyer depuis Git Bash, avec la commande que le script affiche.

Le dépôt d'essai se périme comme le stable (90 jours) : à republier, ou à
re-signer par `./publish-apt.sh --essai --resigner`.
