# Site de présentation — Codebyr OS

Site vitrine statique, sans dépendance de build. Destiné à **https://os.codebyr.dev**.

- `index.html` — structure et contenu ;
- `styles.css` — design (tokens fidèles à la charte : couleur *Sentinelle*, neutres à biais cyan, couleurs d'Espaces strictement fonctionnelles) ;
- `app.js` — bascule de thème (clair/sombre), révélations au défilement, divers ;
- `captures/` — captures d'écran du système (copie de `../captures_ecran/`, pour que le
  dossier `site/` reste autonome et déployable tel quel).

## Déploiement

Le dossier est purement statique : il se publie tel quel (GitHub Pages, Netlify,
Cloudflare Pages…) à la racine de `os.codebyr.dev`. Aucune étape de build.

## Aperçu local

Ouvrir directement `index.html` dans un navigateur, ou servir le dossier :

```bash
python3 -m http.server 8080 --directory site
# → http://localhost:8080
```

## Notes de conception

- **Thème clair et sombre** : suit la préférence système, bascule manuelle mémorisée (`localStorage`).
- **Polices** : Bricolage Grotesque (titres), Inter (texte), JetBrains Mono (étiquettes) via Google Fonts. Repli sur les polices système si hors ligne.
- **Honnêteté** : la section 03 reprend mot pour mot le modèle de menaces couvertes / non couvertes du dépôt — le site ne survend jamais les capacités.
- **Accessibilité** : contrastes conformes, `prefers-reduced-motion` respecté, focus visibles, couleurs d'Espaces toujours doublées d'un libellé (Jetable en pointillés).

Destiné à la **Phase 5 (Diffusion)** de la feuille de route.
