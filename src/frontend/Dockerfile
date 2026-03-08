# === Dev: Vite hot-reload (non-root) ===
FROM node:20-slim AS dev

# Create non-root user
RUN groupadd -r viteuser && useradd -r -g viteuser -u 1002 viteuser

WORKDIR /app

# Copy package files as root, install as root (npm requires write to cache)
COPY --chown=viteuser:viteuser package*.json ./
RUN npm ci --prefer-offline --no-audit

# Copy source code
COPY --chown=viteuser:viteuser . .

# Switch to non-root user
USER viteuser

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# === Build: compile to static assets ===
FROM node:20-slim AS build

WORKDIR /app

# Copy package files and install dependencies
COPY package*.json ./
RUN npm ci --prefer-offline --no-audit --production=false

# Copy source and build
COPY . .
RUN npm run build

# === Prod: nginx serves static files (non-root) ===
FROM nginxinc/nginx-unprivileged:alpine AS prod

# Copy compiled assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration if it exists (default otherwise)
COPY nginx.conf /etc/nginx/conf.d/default.conf 2>/dev/null || true

EXPOSE 8080

# Healthcheck for production nginx
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8080/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
