# Site de présentation — Codebyr OS

Site vitrine statique, sans dépendance de build. Destiné à **https://os.codebyr.dev**.

- `index.html` — structure et contenu ;
- `styles.css` — design (tokens fidèles à la charte : couleur *Sentinelle*, neutres à biais cyan, couleurs d'Espaces strictement fonctionnelles) ;
- `app.js` — bascule de thème (clair/sombre), révélations au défilement, divers ;
- `captures/` — captures d'écran du système (copie de `../captures_ecran/`, pour que le
  dossier `site/` reste autonome et déployable tel quel).

## Déploiement (Docker + Nginx Proxy Manager)

Le site est du statique pur, servi par un conteneur nginx minimal.
Il ne publie **aucun port** : Nginx Proxy Manager (NPM) lui parle directement
sur le réseau Docker, par son nom de conteneur — plus sûr qu'exposer un port.

### 1. Trouver le réseau de NPM

```bash
docker inspect $(docker ps -qf name=nginx-proxy) \
  --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}'
```

Reporter le nom obtenu dans `docker-compose.yml` (clé `networks.proxy.name`).

### 2. Démarrer le conteneur

```bash
cd ~/docker
git clone https://github.com/Romtouf/codebyr-os.git codebyr-os
cd codebyr-os/site
docker compose up -d --build
```

Mise à jour ultérieure : `git pull && docker compose up -d --build`.

> Variante Portainer : **Stacks → Add stack → Repository**,
> URL `https://github.com/Romtouf/codebyr-os`, chemin du compose `site/docker-compose.yml`.
> Portainer construit l'image et peut se re-déployer automatiquement via webhook.

### 3. Publier le domaine dans NPM

DNS : un enregistrement **A** `os.codebyr.dev` → IP publique du serveur
(ports 80 et 443 ouverts).

Dans NPM, **Proxy Hosts → Add Proxy Host** :

| Champ | Valeur |
|---|---|
| Domain Names | `os.codebyr.dev` |
| Scheme | `http` |
| Forward Hostname | `codebyr-os-site` *(le nom du conteneur)* |
| Forward Port | `80` |
| Block Common Exploits | ✅ |

Puis onglet **SSL** : *Request a new SSL Certificate* (Let's Encrypt),
**Force SSL** ✅, **HTTP/2** ✅, **HSTS Enabled** ✅.

### Sécurité

`nginx.conf` pose déjà les en-têtes : CSP, `X-Frame-Options: DENY`,
`X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`.
Le TLS, HTTP/2 et HSTS sont gérés par NPM en amont.

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
