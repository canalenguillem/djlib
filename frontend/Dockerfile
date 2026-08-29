# --- Base con dependencias instaladas ---------------------------------------
FROM node:22-alpine AS base
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .

# --- Desarrollo: dev server de Vite con hot reload --------------------------
FROM base AS dev
EXPOSE 5173
CMD ["npm", "run", "dev"]

# --- Produccion: build estatico servido por nginx (para el despliegue) ------
FROM base AS build
RUN npm run build

FROM nginx:alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
