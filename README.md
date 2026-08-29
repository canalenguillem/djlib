# DJ Library — Fase 1: autenticacion

Modulo de autenticacion y gestion de usuarios de DJ Library (FastAPI + MariaDB +
Vite/React/TypeScript, todo en Docker). Los modulos de tracks, artistas, tags,
reconocimiento de audio y descarga con yt-dlp llegaran en fases posteriores.

## Puesta en marcha

### 1. Variables de entorno

```bash
cp .env.example .env
```

Rellena en `.env` como minimo:

| Variable | Como obtenerla |
| --- | --- |
| `JWT_SECRET_KEY` | `openssl rand -hex 32` |
| `MARIADB_ROOT_PASSWORD` | inventala (no se usa desde la app) |
| `MARIADB_PASSWORD` | inventala; es la del usuario de la aplicacion |
| `SEED_ADMIN_PASSWORD` | la contrasena inicial de `enguillem` (min. 10 caracteres) |

**Solo se publica un puerto en el host: el del frontend** (`FRONTEND_HOST_PORT`,
5175 por defecto). El backend y MariaDB viven dentro de la red de compose; el
navegador llega a la API por el proxy del frontend (`/api` -> `backend:8000`),
asi que no hay peticiones entre origenes y `CORS_ORIGINS` puede quedarse vacio.
Si 5175 esta ocupado, cambia `FRONTEND_HOST_PORT` y nada mas.

### 2. Arrancar

```bash
docker compose up -d --build
docker compose logs -f backend   # opcional: ver migraciones y seed
```

El backend, al arrancar, espera a MariaDB, aplica las migraciones de Alembic y
siembra el usuario admin. El seed es idempotente: si `enguillem` ya existe, no
toca nada.

- Frontend: http://localhost:5175 (o el `FRONTEND_HOST_PORT` que hayas puesto)
- API: http://localhost:5175/api — documentacion interactiva en
  http://localhost:5175/api/docs
- MariaDB: sin puerto publicado. Para una consulta puntual:
  `docker compose exec db mariadb -u<usuario> -p <base>`. Para conectar un
  cliente SQL externo, descomenta el bloque `ports` de `db` en el compose.

### 2b. Acceder desde otro dispositivo de la LAN

Funciona tal cual por IP: `http://<ip-del-servidor>:5175`. La API va por el
mismo origen (`/api`), asi que no hay nada mas que abrir.

Si entras por **nombre de host** (`http://debianllama.local:5175`), Vite lo
rechaza con `403 Blocked request` salvo que lo declares en `VITE_ALLOWED_HOSTS`
(lista separada por comas, o `*` para permitir cualquiera en una LAN de
confianza). Es una proteccion anti DNS-rebinding del dev server; las IPs y
`localhost` estan siempre permitidos.

### 3. Entrar

Usuario `enguillem` (o el `SEED_ADMIN_USERNAME` que hayas puesto) con la
contrasena de `SEED_ADMIN_PASSWORD`.

### Si pierdes la contrasena del admin

```bash
docker compose exec backend python -c "
from app.db.session import SessionLocal
from app.services import user_service
db = SessionLocal()
u = user_service.get_by_username(db, 'enguillem')
user_service.change_password(db, u, 'LaNuevaQueQuieras123')
db.commit()"
```

Cambiar la contrasena asi tambien revoca las sesiones abiertas de ese usuario.

## Tests

```bash
docker compose exec backend pytest
```

Corren contra una base de datos MariaDB aparte (`<MARIADB_DATABASE>_test`), que
crea el script `docker/mariadb/init/01-create-test-db.sh` la primera vez que se
inicializa el volumen. Si ya tenias el volumen creado de antes, la base de tests
no existira: recrealo con `docker compose down -v && docker compose up -d`.

## API

Desde el navegador todas cuelgan del prefijo `/api` (el proxy lo quita antes de
llegar al backend): `POST http://localhost:5175/api/auth/login`.

| Metodo | Ruta | Acceso | Descripcion |
| --- | --- | --- | --- |
| POST | `/auth/login` | publico | Devuelve access + refresh token |
| POST | `/auth/refresh` | publico | Rota el refresh token y devuelve un par nuevo |
| POST | `/auth/logout` | publico | Revoca el refresh token indicado |
| GET | `/auth/me` | autenticado | Datos del usuario actual |
| PATCH | `/auth/me/password` | autenticado | Cambia la propia contrasena |
| PATCH | `/auth/me/email` | autenticado | Anade/edita/borra el propio email |
| GET | `/users` | admin | Listado de usuarios |
| POST | `/users` | admin | Alta de usuario |
| PATCH | `/users/{id}` | admin | Activar/desactivar o cambiar rol |
| GET | `/health` | publico | Comprobacion de vida |

## Decisiones de seguridad

- **Contrasenas**: argon2id (`argon2-cffi`). El login verifica siempre un hash,
  exista el usuario o no, para no filtrar por tiempo que usernames hay dados de alta.
- **Access token**: JWT de 15 min (configurable) con `sub`, `role`, `iat` y `jti`.
- **Refresh token**: opaco y aleatorio, guardado **hasheado** en `refresh_tokens`.
  Rota en cada uso; reutilizar uno ya rotado revoca todas las sesiones del usuario.
- **Cambio de contrasena**: actualiza `password_changed_at`, lo que invalida los
  access tokens emitidos antes, y revoca los refresh tokens existentes. La sesion
  que hace el cambio recibe un par nuevo para no quedarse fuera.
- **Desactivar un usuario** cierra sus sesiones abiertas de inmediato.
- **Superficie expuesta**: solo el puerto del frontend. La API y la base de
  datos no son alcanzables desde fuera de la red de compose.
- **Rate limiting** en `/auth/login`: por IP y solo sobre intentos fallidos
  (un login correcto limpia el contador). Vive en memoria del proceso; para
  varias replicas habria que moverlo a Redis.
- Un admin no puede desactivarse ni cambiarse el rol a si mismo.

## Estructura

```
backend/    FastAPI, SQLAlchemy, Alembic, pytest
frontend/   Vite + React + TypeScript
docker/     scripts de inicializacion de MariaDB
```

## Notas para el despliegue (fase posterior)

- El `Dockerfile` del frontend ya tiene la fase `prod` (build estatico + nginx).
  Para usarla: `docker build --target prod ./frontend`, o un compose de
  produccion que apunte a ese target. Su `nginx.conf` replica el proxy `/api`
  del dev server, asi que el esquema de un solo puerto se mantiene igual.
- `TRUST_PROXY_HEADERS=true` (ya activo) hace que el rate limiting use la IP de
  `X-Forwarded-For`, que es la que anade el proxy del frontend.
- `CORS_ORIGINS` solo hace falta si algun dia sirves la API en un dominio
  distinto al del frontend.
