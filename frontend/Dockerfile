# --- Base con dependencias instaladas ---------------------------------------
FROM node:22-alpine AS base
WORKDIR /app
# npm ci instala exactamente las versiones del lockfile: builds reproducibles.
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# --- Desarrollo: dev server de Vite con hot reload --------------------------
FROM base AS dev
EXPOSE 5173
CMD ["npm", "run", "dev"]

# --- Produccion: build estatico servido por nginx (para el despliegue) ------
FROM base AS build
# Vite congela las variables VITE_* en el build, no las lee al arrancar.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
