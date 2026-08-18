# Web image: builds the dashboard and serves the static output.
# Build from this directory:  docker build -t invoicepilot-web services/web
FROM node:22-slim AS builder

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . ./
RUN npm run build

FROM caddy:2-alpine
COPY --from=builder /app/dist /usr/share/caddy
COPY Caddyfile /etc/caddy/Caddyfile
# Where /api goes — read by Caddyfile. The default is the host's uvicorn,
# which is the local workflow; compose.prod.yml overrides it with the api
# container.
ENV API_UPSTREAM=host.docker.internal:8000
EXPOSE 80
