# Codebyr OS — Référence des couleurs

La charte complète (avec usages, interdits et spécimens) est dans
[charte-graphique.html](charte-graphique.html). Ceci est la référence rapide.

## Couleur signature

| Nom | Thème clair | Thème sombre | Usage |
|---|---|---|---|
| **Sentinelle** | `#0B87A0` (texte) / `#10A5C2` (graphique) | `#43C7DF` / `#2FB9D4` | Marque, accents, éléments interactifs |

## Neutres

| Rôle | Clair | Sombre |
|---|---|---|
| Fond | `#F4F7F8` | `#0B1419` |
| Surface | `#FFFFFF` | `#111D24` |
| Encre (texte) | `#12222C` | `#E7EEF1` |
| Encre secondaire | `#4A5D68` | `#93A6B0` |
| Trait / bordure | `#DBE4E8` | `#223540` |

Les neutres ont un léger biais cyan : jamais de gris pur.

## Couleurs des Espaces (langage fonctionnel)

Ces couleurs ne sont **jamais décoratives** : elles indiquent toujours
l'appartenance d'une fenêtre ou d'un contenu à un Espace.

| Espace | Nom | Hex | Sens |
|---|---|---|---|
| Personnel | Azur | `#4E8FEF` | Vie quotidienne |
| Travail | Améthyste | `#8F6CF0` | Professionnel |
| Banque | Émeraude | `#2FA36B` | Financier, isolement maximal |
| Navigation | Ambre | `#E09A32` | Web ordinaire |
| Jetable | Braise | `#E25551` | Éphémère, autodétruit |
| Système | Ardoise | `#6E7E89` | Réservé au système, non attribuable |

Règles :
- Une couleur d'Espace n'est jamais utilisée comme accent d'interface générique.
- Le liseré de fenêtre fait 3 px, la pastille de barre de titre 10 px.
- Jetable est toujours accompagné d'un trait **pointillé** (couleur seule ≠ suffisant,
  accessibilité daltonisme).
