# Sift web UI image (Dev B). Multi-stage: build the Vite app with Node, then
# serve the static bundle with nginx, which also reverse-proxies the API surface
# to the `api` container (see nginx.conf). Build context = ./web.

# ---- build stage -----------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app

# Install deps against the lockfile first for a cacheable layer.
COPY package.json package-lock.json ./
RUN npm ci

# Build the static bundle into /app/dist.
COPY . .
RUN npm run build

# ---- runtime stage ---------------------------------------------------------
FROM nginx:1.27-alpine

# SPA fallback + reverse proxy to the api service.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Static assets produced by the build stage.
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
