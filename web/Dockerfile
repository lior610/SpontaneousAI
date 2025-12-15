FROM node:18-alpine

WORKDIR /app

# Install dependencies first (better caching)
COPY package.json package-lock.json*./
RUN npm install

# Copy source code
COPY . .

# Default command
CMD ["npm", "run", "dev"]