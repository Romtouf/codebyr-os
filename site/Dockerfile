# Codebyr OS — site vitrine (os.codebyr.dev)
# Image statique : nginx alpine + les fichiers du site. Aucune étape de build.
FROM nginx:1.27-alpine

# Configuration nginx (compression, cache, en-têtes de sécurité).
# NB : ce fichier ne doit PAS figurer dans .dockerignore, sinon il est
# exclu du contexte de build et ce COPY échoue.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Les fichiers du site, copiés explicitement : rien d'autre ne se retrouve
# servi (ni Dockerfile, ni compose, ni README).
WORKDIR /usr/share/nginx/html
RUN rm -rf ./*
COPY index.html styles.css fonts.css app.js ./
COPY fonts/ ./fonts/
COPY captures/ ./captures/

EXPOSE 80
