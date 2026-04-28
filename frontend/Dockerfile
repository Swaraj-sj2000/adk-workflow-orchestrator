# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Build argument for API URL - can be passed via gcloud builds submit or docker build
ARG VITE_API_URL=https://orchestrator-backend-yo2mex5f2a-ew.a.run.app
ENV VITE_API_URL=$VITE_API_URL

# Show what API URL is being used
RUN echo "Building with VITE_API_URL: $VITE_API_URL"

# Build the app
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 8080 (Cloud Run expects 8080)
EXPOSE 8080

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
