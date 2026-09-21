# ── Frontend / React-Vite Dockerfile ─────────────────────────────────────────
# Multi-stage build:
#   1. builder  — installs npm deps and produces the Vite production build
#   2. runtime  — serves the static bundle with nginx

# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first (cache layer)
COPY package.json package-lock.json ./
RUN npm ci --frozen-lockfile

# Copy source and build
COPY . .

# VITE_API_BASE_URL must be set at build time because Vite embeds it into the
# JS bundle.  Pass it as a build argument so the value comes from docker-compose
# or CI rather than being hardcoded here.
ARG VITE_API_BASE_URL=http://localhost:8000/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

# ── Stage 2: runtime (nginx) ──────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# Remove the default nginx config; replace with one that handles React Router
# (history-mode SPA routing).
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the Vite build output
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
