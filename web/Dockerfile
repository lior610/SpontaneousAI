# ==========================================
# 1. Base Stage
# ==========================================
FROM node:18-alpine AS base
WORKDIR /app
COPY web/package.json web/package-lock.json* ./
RUN npm install

# ==========================================
# 2. Development Stage
# ==========================================
FROM base AS development
COPY web/ .
CMD ["npm", "run", "dev"]

# ==========================================
# 3. Build Stage
# ==========================================
FROM base AS build
COPY web/ .
COPY .env /app/.env
RUN npm run build

# ==========================================
# 4. Production Stage
# ==========================================
FROM nginx:alpine AS production
# Copy the built assets from the build stage
COPY --from=build /app/dist /usr/share/nginx/html
# Copy the custom nginx configuration
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]