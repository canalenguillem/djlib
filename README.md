# DJ Library

Biblioteca musical autoalojada para uso como DJ: descarga canciones de YouTube,
las clasifica por mood, estilo y momento de la noche, y permite filtrarlas para
montar crates tematicos. FastAPI + MariaDB + Vite/React/TypeScript, en Docker.

**Implementado**: autenticacion y usuarios; ingesta por enlace y por titulo +
artista; biblioteca con busqueda, filtrado combinado por etiquetas, reproductor,
descarga del mp3 y borrado; catalogo de etiquetas.

**Pendiente**: reconocimiento de audio tipo Shazam (la configuracion ya esta
prevista, falta clave de AudD/ACRCloud), fichas de artista con datos de
MusicBrainz/Wikipedia, crates guardados con nombre y analisis de BPM.

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

## Como funciona la ingesta

Los tres caminos del briefing (enlace, busqueda manual y, mas adelante,
reconocimiento) desembocan en el mismo pipeline:

1. El endpoint valida, deduplica y crea la fila con `status=pending`. Responde
   al instante con 202: la descarga no bloquea la peticion.
2. Una tarea en segundo plano resuelve los metadatos con yt-dlp
   (`--dump-json --skip-download`, barato), vuelve a deduplicar ahora que conoce
   el id real del video, y descarga el audio a mp3 con ffmpeg.
3. El frontend hace polling cada 3 segundos mientras haya descargas en marcha.

**Deduplicacion** en dos niveles: por id del video (indice sobre
`source_video_id`) y, como red secundaria, por una clave normalizada de
artista + titulo que ignora acentos, mayusculas y el ruido tipico de YouTube,
de modo que "Blur - Song 2 (Official Video)" y "blur song 2" son la misma.

**Los mp3** se guardan en el volumen `music_data` con el id del video como
nombre de fichero (sin acentos ni colisiones); el nombre bonito
"Artista - Titulo.mp3" se aplica al descargar desde el navegador.

Como las descargas viven dentro del proceso del backend, un reinicio las deja a
medias: al arrancar se marcan como error, se ven en el listado y se reintentan
con un boton.

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

Biblioteca (todo requiere sesion):

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| GET | `/tracks` | Listado con `search`, `status`, `tag_id` (repetible) y paginacion |
| POST | `/tracks/from-url` | Alta desde un enlace |
| POST | `/tracks/search` | Alta por titulo + artista (`ytsearch1`) |
| GET | `/tracks/{id}` | Detalle, util para seguir el estado de la descarga |
| PATCH | `/tracks/{id}` | Corregir titulo y artista a mano |
| PUT | `/tracks/{id}/tags` | Fijar las etiquetas de una cancion |
| POST | `/tracks/{id}/retry` | Reintentar una descarga fallida |
| GET | `/tracks/{id}/file` | El mp3 (soporta Range para el reproductor) |
| DELETE | `/tracks/{id}` | Borra el registro y el fichero |
| GET | `/tags` | Catalogo, filtrable por `kind` |
| POST | `/tags` | Crear etiqueta (`mood`, `style` o `moment`) |
| PATCH | `/tags/{id}` | Renombrar |
| DELETE | `/tags/{id}` | Borrar (se quita de las canciones que la tuvieran) |

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

## Si YouTube empieza a bloquear las descargas

Es el riesgo conocido de yt-dlp. Dos palancas, por orden:

1. Actualizar yt-dlp: `docker compose build --no-cache backend`. La mayoria de
   los bloqueos se arreglan solo con esto.
2. Si pide verificacion ("Sign in to confirm you're not a bot"), exporta las
   cookies de tu navegador a un fichero, montalo en el contenedor y apunta
   `YTDLP_COOKIES_FILE` a su ruta.

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
