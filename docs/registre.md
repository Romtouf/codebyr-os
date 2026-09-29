# Le registre des Espaces — format de référence

**Ce document fait foi.** Le registre décrit les Espaces : leur nom, leur
couleur, leurs protections. Deux programmes le lisent, qui ne peuvent pas
partager de code :

- `usr/share/codebyr/registre.py`, le module partagé par les trois outils
  Python (`codebyr-space`, `codebyr-config`, `codebyr-assistant`) ;
- l'extension GNOME (`extension.js`, en GJS), qui colore les fenêtres et
  construit le menu du Sceau.

Tous deux renvoient ici. `tests/test_registre_coherence.py` vérifie qu'ils
appliquent la même règle de fusion, et que chaque clé livrée dans
`/etc/codebyr/espaces.json` est décrite ci-dessous.

## Deux fichiers, superposés

| Fichier | Qui l'écrit | Contenu |
|---|---|---|
| `/etc/codebyr/espaces.json` | le paquet (`apt`) | les valeurs par défaut |
| `~/.config/codebyr/espaces.json` | l'utilisateur, par `codebyr-config` ou `codebyr-space` | ses **différences**, et ses Espaces à lui |

La fusion se fait **Espace par Espace, clé par clé** : la valeur de
l'utilisateur gagne quand elle existe, la valeur livrée s'applique sinon. Un
durcissement livré par une mise à jour atteint donc tout le monde, sans écraser
les choix de personne.

- Un Espace absent de `/etc` est un Espace **créé par l'utilisateur** : lui
  seul est supprimable.
- La liste `apps` de l'utilisateur, si elle existe, **remplace** celle du
  système (elle ne se fusionne pas élément par élément).
- Le fichier de l'utilisateur ne doit contenir **que des différences**
  (`registre.reduire_couche`). Y écrire la vue fusionnée le figerait : plus
  aucun défaut livré ensuite ne l'atteindrait.
- Les clés qui commencent par `_` sont **calculées** et jamais écrites
  (`_systeme` : l'Espace vient-il du paquet ?) ; `_commentaire` est ignoré.

## Structure

Trois clés au premier niveau : `espaces`, la liste des Espaces ; `apps`, la
liste d'applications commune à tous ; `_commentaire`, ignorée.

```json
{
  "_commentaire": "texte libre, ignoré",
  "espaces": [ { "id": "banque", "nom": "Banque", "couleur": "#2FA36B", … } ],
  "apps": [ { "nom": "Navigateur", "cmd": "firefox-esr" } ]
}
```

## Un Espace

| Clé | Valeurs | Absente | Sens |
|---|---|---|---|
| `id` | `[a-z][a-z0-9-]{0,19}` | — obligatoire | Identifiant. Une lettre en tête, **20 caractères au plus** : le compte Unix de l'Espace s'appelle `cbyr-<uid>-<id>`, et `useradd` n'en accepte que 32. `comptes.FORME_ESPACE` fait foi ; `registre.identifiant_libre` ne fabrique rien d'autre. Un identifiant hors de cette forme (créé jusqu'en 1.16.1) est encore lu, mais ne peut pas tourner sous compte séparé : l'ouverture le dit, la suppression passe. |
| `nom` | texte | — obligatoire | Nom affiché. |
| `couleur` | `#RGB` ou `#RRGGBB` | gris `#888888` | Liseré des fenêtres, pastille du menu. Vérifiée à l'écriture (`codebyr-space create`) **et** à la lecture (extension) : elle finit dans des feuilles de style, où une valeur comme `red; background-image: url(…)` ajouterait ses propres règles. |
| `app` | identifiant `.desktop` | `org.gnome.Nautilus.desktop` | Application ouverte par défaut. |
| `apps` | liste de `{"nom", "cmd"}` | la liste commune `apps` | Applications proposées dans le menu de cet Espace. |
| `compte` | `"dedie"` | compte du bureau | L'Espace tourne sous **son propre compte Unix**. Défaut de tout Espace livré ou créé depuis la 1.16.1. Jamais pour l'invité, quoi que dise le registre : ses Espaces doivent s'effacer avec sa session. |
| `blindage` | `"renforce"` | aucun | Bac à sable utilisateur, capacités retirées, session neuve, filtre d'appels système (`filtre_syscalls.py`), plafonds de ressources. |
| `plafonds` | `{"memoire": "2G" \| "75%", "taches": 64…32768}` | 2G, 800 tâches | Plafonds de l'Espace blindé ou à compte séparé. Une valeur mal formée est remplacée par le défaut, jamais refusée (`comptes.plafonds_valides`). |
| `reseau` | `{"mode": "liste-blanche", "domaines": [...]}` ou `{"mode": "coupe"}` (`"hors-ligne"`, même sens) | réseau ordinaire | Liste blanche : l'Espace n'a aucune interface réseau, seulement le filtre `codebyr-net-proxy`, qui ne laisse passer que ces domaines. Coupé : aucun réseau. Les domaines passent par `registre.normaliser_domaine`, seule porte d'entrée. |
| `audio` | booléen | `true` | Socket PipeWire (son et micro). Coupé d'office sans réseau et pour une pièce jointe examinée. |
| `gpu` | booléen | `true` | Accès à la carte graphique — sous compte séparé, aux seuls nœuds de rendu. Coupé pour une pièce jointe examinée. |
| `ephemere` | booléen | `false` | Jetable : dossier en mémoire vive, rien n'est conservé. |

Une valeur **absente** et une valeur **fausse** ne disent pas la même chose
pour `audio` et `gpu` : seul `false` retire l'accès. C'est voulu — un Espace
créé avant l'existence du réglage garde ce qu'il avait.
