# Captures d'écran — liste de plans

À prendre sur le HP Envy (système installé, session propre). Touche **Impr écran**
= capture interactive GNOME (zone/fenêtre/écran). Les fichiers atterrissent dans
`~/Images/Captures d'écran/`.

**Réglages avant de shooter** : fond d'écran Codebyr d'origine, fermer les fenêtres
inutiles, aucune donnée personnelle visible (pas de vrais domaines bancaires — utiliser
`mabanque.fr` comme exemple).

## Les 7 plans (nommer les fichiers exactement ainsi)

| Fichier | Contenu | Comment |
|---|---|---|
| `01-bureau.png` | Le bureau Codebyr propre (fond, barre du haut avec le Sceau) | plein écran |
| `02-menu-sceau.png` | Le menu du Sceau **ouvert**, les 5 Espaces + entrées visibles | plein écran (le menu ne se capture pas en mode fenêtre) |
| `03-liseres.png` | 2-3 fenêtres côte à côte avec des liserés de couleurs différentes (ex. Fichiers dans Personnel + Firefox dans Navigation) | plein écran |
| `04-jetable.png` | Un document ouvert **en Jetable** (liseré rouge bien visible) | plein écran |
| `05-configuration.png` | ⚙ Configuration Codebyr (domaines banque + blindage + applications du menu) | fenêtre |
| `06-installeur.png` | L'installeur Calamares, page « Emplacement » ou « Résumé » | *depuis la session live* — fenêtre |
| `07-bienvenue.png` | Le tour de bienvenue, page « Vos Espaces » (la légende des couleurs) | fenêtre (`codebyr-bienvenue --force` pour le rouvrir) |

## Transfert vers le dépôt

Une clé USB ou le réseau, puis placer les fichiers dans `docs/captures/` du dépôt.
Claude s'occupe ensuite de : compression (PNG → poids raisonnable), intégration
au README (galerie), commit + push.

## Conseil cadrage

Résolution native, pas de zoom. Pour `03-liseres.png`, choisir des fenêtres aux
contenus neutres (Fichiers vide, page d'accueil Firefox). Le but : qu'on comprenne
le code couleur en une seconde.
