FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy application code
COPY . .

EXPOSE 5173

# Start Vite dev server with host bound for container access
CMD ["npm", "run", "dev", "--", "--host"]