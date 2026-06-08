# ==========================================
# 1. Base Stage
# ==========================================
FROM node:18-alpine AS base
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install

# ==========================================
# 2. Development Stage
# ==========================================
FROM base AS development
COPY . .
CMD ["npm", "run", "dev"]

# ==========================================
# 3. Production Stage
# ==========================================
FROM base AS production
COPY . .
CMD ["npm", "start"]