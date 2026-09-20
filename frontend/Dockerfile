FROM node:24.7.0-alpine3.22 AS base

WORKDIR /app
COPY package*.json ./

FROM base AS development
RUN npm install \
    && chown -R node:node /app/node_modules
COPY --chown=node:node . .
USER node
EXPOSE 5173
CMD ["npm", "run", "dev"]

FROM base AS build
RUN npm install
COPY . .
RUN npm run build
