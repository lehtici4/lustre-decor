FROM node:24.7.0-alpine3.22 AS build

WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Imagem oficial do projeto OWASP CRS: Nginx com o módulo ModSecurity 3 já
# compilado e o Core Rule Set instalado. Tag pinada (versão do CRS + variante
# + data do build), não a tag flutuante "nginx-alpine" — mesmo princípio já
# aplicado à imagem do Nginx puro (ver docs/security.md, A08).
# Referência no momento em que foi pinada: sha256:1503b5ab7b8f8799d1525cd2a1690dfcdd5cc251a705523aa5783dd20e038b1b
FROM owasp/modsecurity-crs:4.28.0-nginx-alpine-202608131208

# Pacotes do SO com correção já publicada no Alpine mas ainda não incorporada
# a esta imagem base (mesmo achado do Trivy que já apareceu na imagem do
# backend — ver docs/security.md, A03). Precisa de root; devolve para o
# usuário sem privilégios da imagem original logo em seguida.
USER root
RUN apk upgrade --no-cache
USER nginx

# Substitui só o template do vhost (mantém os templates de ModSecurity/CRS da
# imagem base intactos, incluindo "modsecurity on;" no nível http — ver
# /etc/nginx/templates/conf.d/modsecurity.conf.template na imagem original).
COPY --chown=nginx:nginx nginx/templates/conf.d/default.conf.template /etc/nginx/templates/conf.d/default.conf.template
COPY --chown=nginx:nginx nginx/proxy_params.conf /etc/nginx/proxy_params.conf
COPY --from=build --chown=nginx:nginx /app/dist /usr/share/nginx/html

EXPOSE 8080 8443
