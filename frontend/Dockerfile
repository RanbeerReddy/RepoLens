# Stage 1: Build React application
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

# Nginx configuration for SPA routing and API proxy
RUN echo 'server { \
    listen 80; \
    server_name localhost; \
    root /usr/share/nginx/html; \
    index index.html; \
    \
    location / { \
        try_files $$uri $$uri/ /index.html; \
    } \
    \
    location /api/ { \
        proxy_pass http://backend:8080/api/; \
        proxy_set_header Host $$host; \
        proxy_set_header X-Real-IP $$remote_addr; \
    } \
    \
    location /health { \
        proxy_pass http://backend:8080/health; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
