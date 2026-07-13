# Codebyr OS — site vitrine (os.codebyr.dev)
# Image statique : nginx alpine + les fichiers du site. Aucune étape de build.
FROM nginx:1.27-alpine

# Configuration nginx (compression, cache, en-têtes de sécurité)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Les fichiers du site (voir .dockerignore pour ce qui est exclu)
WORKDIR /usr/share/nginx/html
RUN rm -rf ./*
COPY . .

EXPOSE 80
