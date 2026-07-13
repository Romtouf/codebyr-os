# Polices auto-hébergées — attributions

Les fichiers `.woff2` de ce dossier sont redistribués sous la
**SIL Open Font License 1.1** (texte intégral : [OFL.txt](OFL.txt)).

| Police | Fichiers | Copyright / source amont |
|---|---|---|
| **Bricolage Grotesque** | `bricolage-grotesque-*.woff2` | Copyright 2022 The Bricolage Grotesque Project Authors — <https://github.com/ateliertriay/bricolage> |
| **Inter** | `inter-*.woff2` | Copyright 2016 The Inter Project Authors — <https://github.com/rsms/inter> |
| **JetBrains Mono** | `jetbrains-mono-*.woff2` | Copyright 2020 The JetBrains Mono Project Authors — <https://github.com/JetBrains/JetBrainsMono> |

Chaque police est distribuée sous OFL-1.1, identique pour les trois.

## Pourquoi auto-héberger

Le site d'un système d'exploitation qui promet la confidentialité ne peut pas
faire appeler Google par chaque visiteur. En auto-hébergeant :

- **aucune requête vers un tiers** — rien ne fuite, pas de traceur, pas de RGPD à gérer ;
- la **CSP est verrouillée** (`default-src 'self'`), aucune origine externe autorisée ;
- le site fonctionne **hors ligne** et reste stable si Google Fonts change ou tombe.

## Régénérer

Ce sont des **polices variables** : un seul fichier couvre toutes les graisses
(Bricolage 500–800, Inter 400–700, JetBrains Mono 400–600), pour les
sous-ensembles `latin` et `latin-ext`. Les déclarations `@font-face`
correspondantes sont dans [`../fonts.css`](../fonts.css).
