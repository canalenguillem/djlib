# DJ Library

Biblioteca musical autoalojada para uso como DJ: descarga canciones de YouTube,
las clasifica por mood, estilo y momento de la noche, y permite filtrarlas para
montar crates tematicos. FastAPI + MariaDB + Vite/React/TypeScript, en Docker.

**Implementado**: autenticacion y usuarios; ingesta por enlace, por titulo +
artista y por reconocimiento de audio; biblioteca con busqueda, filtrado
combinado por etiquetas, reproductor, descarga del mp3 y borrado; catalogo de
etiquetas; fichas de artista con datos de MusicBrainz y Wikipedia.

**Pendiente**: crates guardados con nombre y analisis de BPM.

Para el estado detallado, las decisiones tomadas y los problemas que fueron
apareciendo en uso real, ver [ESTADO.md](ESTADO.md).

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

## Produccion

En desarrollo, el frontend es el dev server de Vite: sirve el codigo sin
minificar, expone el HMR y permite leer ficheros del proyecto. Eso no debe
estar de cara a internet. Para el despliegue hay un compose aparte que sirve el
build estatico desde nginx:

```bash
docker compose -f docker-compose.prod.yml up -d --build   # pasar a produccion
docker compose up -d                                      # volver a desarrollo
```

Usa el **mismo proyecto y los mismos volumenes**, asi que cambiar de modo
conserva la base de datos y los mp3. Diferencias respecto a desarrollo:

- nginx sirve el build estatico y hace de proxy de `/api` al backend, igual que
  hacia Vite: un unico puerto publicado y sin CORS.
- El backend corre sin `--reload` y sin montar el codigo desde el disco: **viene
  de la imagen**. Cualquier cambio en el backend necesita
  `docker compose -f docker-compose.prod.yml up -d --build backend`.
- Un solo worker de uvicorn a proposito: las descargas se ejecutan dentro del
  proceso y el limitador del login vive en memoria, asi que repartir las
  peticiones entre varios procesos romperia ambas cosas.
- Los assets llevan hash en el nombre y se cachean un ano; `index.html` nunca se
  cachea, para que el navegador no se quede con un build viejo.

Apunta tu reverse proxy con TLS al puerto publicado (`FRONTEND_HOST_PORT`).

## Copias de seguridad

```bash
./scripts/backup.sh              # copia y la verifica
./scripts/backup.sh --no-verify  # mas rapida, sin verificar
./scripts/restore.sh             # lista las copias disponibles
./scripts/restore.sh ultima      # restaura la mas reciente
```

Cada copia guarda el volcado de MariaDB, los mp3 y el propio `.env` (sin el,
no se puede restaurar en una maquina nueva porque la contrasena de la base de
datos tiene que coincidir). Van a `BACKUP_DIR` (por defecto `backups/`, que
esta en `.gitignore`) en carpetas con fecha, y se conservan las `BACKUP_KEEP`
mas recientes. El entorno manda sobre `.env`, asi que se puede lanzar una copia
puntual a otro sitio con `BACKUP_DIR=/mnt/nas ./scripts/backup.sh`.

**La copia se verifica sola**: restaura el volcado en una base de datos
desechable, comprueba que salen las mismas canciones y que el archivo de musica
se puede leer. Una copia que no se ha probado no es una copia.

El volcado usa `--single-transaction`, asi que es consistente sin bloquear las
tablas: la aplicacion puede seguir funcionando durante la copia.

**Ojo**: `backups/` contiene tus secretos y tu musica. No lo sincronices con
nada publico.

### Automatizarlo

```cron
30 4 * * * /ruta/a/djWill/scripts/backup.sh --quiet >> $HOME/djlib-backup.log 2>&1
```

Con `--quiet` no escribe nada si todo va bien, asi que el log solo crece cuando
hay problemas.

### Restaurar en una maquina nueva

1. Clona el repositorio y copia el `env.backup` de la copia como `.env`.
2. `docker compose -f docker-compose.prod.yml up -d --build`
3. `./scripts/restore.sh <fecha>`
4. `docker compose -f docker-compose.prod.yml restart backend`

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
   el id real del video, y descarga el audio a mp3 con ffmpeg. Se descarga la
   URL ya resuelta, no la consulta: repetirla podria dar otro resultado.
3. El frontend hace polling cada 3 segundos mientras haya descargas en marcha.

**Buscar por titulo y artista no descarga nada: muestra los candidatos.**
`POST /tracks/search/preview` devuelve los resultados de YouTube con miniatura,
canal y duracion, marcando los que ya estan en la biblioteca y los que duran
demasiado para ser una cancion. El usuario elige, y la descarga va por la misma
puerta que un enlace pegado a mano.

Basta con rellenar uno de los dos campos:

- **Titulo y artista**: busqueda concreta, cinco candidatos
  (`SEARCH_CANDIDATES`).
- **Solo el artista**: se esta explorando su catalogo, no buscando algo
  concreto, asi que se piden diez (`SEARCH_ARTIST_CANDIDATES`). Util cuando
  sabes de quien es pero no recuerdas el titulo.
- **Solo el titulo**: tambien vale, cinco candidatos.

El motivo es concreto: buscar "Bad Bunny Nueva Yirky" devuelve como primer
resultado un mix de 42 minutos, y elegir automaticamente el primero llena la
biblioteca de recopilatorios. Con la duracion delante, eso se ve de un vistazo y
ademas se nota que hay que afinar la consulta.

La vista previa usa `--flat-playlist`, que tarda 1,6 s en lugar de los 9,6 s que
cuesta pedir los metadatos completos de los cinco videos.

Sigue existiendo `POST /tracks/search`, que elige solo: se queda con el primer
candidato con duracion de cancion (`MAX_SONG_DURATION_SECONDS`, 15 min) y avisa
si ninguno la tiene. Para un tema legitimamente largo, pega su URL: por ahi el
tope es `MAX_TRACK_DURATION_SECONDS` (una hora).

**Deduplicacion** en dos niveles: por id del video (indice sobre
`source_video_id`) y, como red secundaria, por una clave normalizada de
artista + titulo que ignora acentos, mayusculas y el ruido tipico de YouTube,
de modo que "Blur - Song 2 (Official Video)" y "blur song 2" son la misma.

### Importar musica propia

`POST /tracks/upload` acepta ficheros que ya tenga el usuario: compras de
Bandcamp o Beatport, descargas de un record pool. Se admiten mp3, m4a, aac,
wav, aiff, flac, ogg y opus, hasta 200 MB (un wav de cuatro minutos ronda los
40 MB).

Se guarda **sin recodificar**, asi que un wav o un aiff conservan toda su
calidad, que es justo el motivo de haberlos comprado. El titulo y el artista se
leen del propio fichero con ffprobe si el usuario no los indica, y ffprobe hace
ademas de validacion: si no ve una pista de audio, el fichero no entra por mucho
que la extension diga lo contrario.

### Calidad del audio

**El flujo se guarda tal cual viene, sin recodificar.** YouTube sirve como
mucho unos 130 kbps con perdida (AAC de 130k o opus de ~122-138k, segun el
video); no existe el 320 kbps por mucho que lo prometan las webs de descarga.
Recodificar esos 130k a un mp3 de 320 no anade informacion: anade una segunda
compresion con perdida y triplica el tamano. Medido en una descarga real:

| | codec | bitrate | tamano |
| --- | --- | --- | --- |
| mp3 recodificado (como se hacia antes) | mp3 | 262 kbps | 5,6 MB |
| flujo original (como se hace ahora) | aac | 128 kbps | 3,0 MB |

Se prefiere **m4a (AAC)** sobre opus, aunque opus sea mejor codec por bit,
porque rekordbox, Serato y Mixxx leen m4a de forma nativa y con opus dan
problemas. Se controla con `YTDLP_FORMAT`.

Para un set de club conviene comprar los temas (Beatport, Bandcamp, Traxsource):
ahi si hay WAV o FLAC del master. Esta herramienta sirve para descubrir,
preparar y pinchar en un bar.

**Los ficheros** se guardan en el volumen `music_data` con el id del video como
nombre (sin acentos ni colisiones) y la extension del flujo descargado; el
nombre bonito "Artista - Titulo.m4a" se aplica al descargar desde el navegador.

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
| POST | `/tracks/search/preview` | Candidatos de YouTube para elegir, sin descargar |
| POST | `/tracks/search` | Alta por titulo + artista eligiendo automaticamente |
| GET | `/tracks/{id}` | Detalle, util para seguir el estado de la descarga |
| PATCH | `/tracks/{id}` | Corregir titulo y artista a mano |
| PUT | `/tracks/{id}/tags` | Fijar las etiquetas de una cancion |
| POST | `/tracks/{id}/retry` | Reintentar una descarga fallida |
| GET | `/tracks/{id}/file` | El mp3 (soporta Range para el reproductor) |
| DELETE | `/tracks/{id}` | Borra el registro y el fichero |
| POST | `/tracks/upload` | Subir un fichero propio (multipart) |
| GET | `/crates/{id}/export` | El crate entero en un zip, numerado en orden |
| GET | `/crates` | Listado con numero de canciones y duracion total |
| POST | `/crates` | Crear, opcionalmente con canciones de golpe |
| GET | `/crates/{id}` | El crate con sus canciones en orden |
| PATCH | `/crates/{id}` | Renombrar o cambiar la descripcion |
| DELETE | `/crates/{id}` | Borrar el crate (no toca las canciones) |
| POST | `/crates/{id}/tracks` | Anadir una cancion al final |
| DELETE | `/crates/{id}/tracks/{track_id}` | Quitarla |
| PUT | `/crates/{id}/order` | Fijar el orden mandando la lista completa |
| GET | `/recognize/status` | Si el servidor tiene el reconocimiento configurado |
| POST | `/recognize` | Identifica un fragmento de audio y devuelve candidatos |
| POST | `/recognize/screenshot` | Extrae las canciones que se lean en una imagen |
| GET | `/tags` | Catalogo, filtrable por `kind` |
| POST | `/tags` | Crear etiqueta (`mood`, `style` o `moment`) |
| PATCH | `/tags/{id}` | Renombrar |
| DELETE | `/tags/{id}` | Borrar (se quita de las canciones que la tuvieran) |
| PUT | `/tracks/{id}/artists` | Corregir a mano quien toca la cancion |
| GET | `/artists` | Listado de fichas, con `search` |
| POST | `/artists` | Alta manual de artista |
| GET | `/artists/{id}` | Ficha con sus relaciones |
| GET | `/artists/{id}/tracks` | Sus canciones en la biblioteca |
| PATCH | `/artists/{id}` | Edicion manual (la marca como `manual`) |
| POST | `/artists/{id}/enrich` | Reconsultar las fuentes (`?force=true` si es manual) |
| DELETE | `/artists/{id}` | Borrar la ficha (no borra sus canciones) |

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

## Reconocimiento de audio

Grabas 11 segundos de lo que esta sonando y el sistema identifica la cancion,
busca sus versiones en YouTube y te deja elegir cual descargar. Es el flujo
pensado para usarse con el movil en la mano, en un bar.

Hace falta una clave de **AudD**: se saca en
[dashboard.audd.io/signup](https://dashboard.audd.io/signup), da 300 peticiones
gratis sin tarjeta y despues cuesta 5 $ por cada 1000. Se configura con
`RECOGNITION_PROVIDER=audd` y `RECOGNITION_API_KEY`. **Sin clave, la pantalla no
aparece en el menu**: el frontend consulta `GET /recognize/status` y se oculta
sola, en lugar de ofrecer algo que va a fallar.

Detalles que importan en la practica:

- **Requiere HTTPS.** El navegador solo da acceso al microfono en contextos
  seguros, asi que por `http://<ip>:5175` no funciona y la pantalla lo explica
  en vez de fallar sin mas. Por el subdominio con TLS, si.
- **La grabacion dura 11 segundos** porque AudD recomienda fragmentos de 2 a 12:
  con 13 y ruido ambiente real devolvia el error 300 ("problem with creating an
  audio fingerprint"), aunque con audio limpio aguante mas. Tampoco se puede
  cortar antes de 3 segundos, que no daria material suficiente.
- El fragmento se graba en **opus** donde se puede (unos 100 KB), que es lo que
  conviene subiendo desde datos moviles; Safari en iOS solo admite mp4 y
  tambien esta contemplado.
- Se pide el microfono **sin cancelacion de eco, sin supresion de ruido y sin
  control automatico de ganancia**. Son los valores por defecto del navegador,
  pensados para videollamadas, y aqui hacen dano: el cancelador de eco elimina
  el sonido que sale por los altavoces del propio equipo (la primera grabacion
  sale bien y a partir de la segunda queda en silencio), y la supresion de
  ruido trata la musica como ruido de fondo.
- Se distinguen **tres** situaciones que antes se veian igual: **no ha entrado
  sonido** (el vumetro lo avisa en directo y la grabacion ni se envia, para no
  gastar cuota), **no reconocida** (el audio esta bien pero AudD no la tiene) y
  **ha fallado** (cuota agotada, clave mal, AudD caido). Cada una dice que hacer.
- Cuando no se reconoce se puede **escuchar lo grabado**, que resuelve enseguida
  la duda de si el problema fue la captura o la cancion.
- AudD indexa lanzamientos comerciales: las remezclas, edits y sesiones de DJ a
  menudo no estan en su base de datos por muy limpia que sea la grabacion.
- Si no reconoce, hay un formulario para buscar a mano con lo que hayas
  pillado del tema, sin salir de la pantalla.
- Una sola llamada al servidor devuelve la identificacion **y** los candidatos
  de YouTube: en el movil, con datos y en mitad de un bar, ahorrar una vuelta
  se nota.

## Energia de 1 a 5

Cada cancion puede llevar una intensidad de 1 a 5, como las estrellas que usan
los DJ en rekordbox o Serato: 1 para el warm-up con la gente entrando, 3 para
mantener la pista, 5 para el pico de la noche. **No es una nota de calidad**, y
por eso en la interfaz son puntos y no estrellas: las estrellas se leen
inevitablemente como "esta cancion es mejor".

Sirve para montar la curva de una noche: `GET /tracks?energy_min=4` da los temas
de pico, y `?sort=energy_asc` ordena de menos a mas para construir la subida.
Las canciones sin energia asignada quedan siempre al final (MariaDB no admite
`NULLS LAST`, asi que se emula con una clave de orden previa).

## Crates

Un **crate** es una seleccion de canciones con nombre y orden propio: "warm-up
del sabado", "cierre 90s". Viene de las cajas de vinilos que los DJ llevaban al
bar.

La diferencia con un filtro es que **no cambia solo**. Un filtro se recalcula
cada vez y ordena por fecha; un crate es una seleccion congelada en el orden
que tu decides, y sigue igual aunque despues cambies las etiquetas de una
cancion o borres una etiqueta entera.

Se montan de dos formas: filtrando la biblioteca y guardando el resultado de
golpe, o creando uno vacio y buscando canciones desde la propia ficha del
crate. Se reordena arrastrando o con flechas (en el movil, flechas).

**Se puede descargar el crate entero en un zip**, con las canciones numeradas
en el orden del set (`01 - Artista - Titulo.ext`). Es el puente con la noche del
bolo: se descomprime en el USB y queda listo para rekordbox o un CDJ. El zip va
sin comprimir, porque el audio ya viene comprimido y deflate solo gastaria CPU
para no ahorrar nada.

Solo entran canciones ya descargadas: un crate con descargas a medias no sirve
para pinchar.

**El orden se manda entero, no por movimientos sueltos** (`PUT
/crates/{id}/order` con la lista completa). Asi dos reordenaciones seguidas no
pueden dejar el crate en un estado a medias, y el frontend puede pintar el
cambio al instante y deshacerlo si el servidor lo rechaza.

## Leer capturas de pantalla

Se puede subir una captura y extraer de ella las canciones que se lean. El caso
para el que esta pensado: dejar **Shazam identificando solo** durante la noche y
al dia siguiente subir la captura de la lista, en vez de teclear diez canciones
a mano. Cada una lleva su boton para buscarla en YouTube y elegir version, igual
que en el resto de la aplicacion.

Vale para cualquier captura donde se lean titulos, no solo para Shazam. En el
ordenador se puede **pegar con Ctrl+V** sin pasar por guardar la imagen.

Necesita una clave de OpenAI en `OPENAI_API_KEY` y un modelo con vision en
`OPENAI_MODEL`. **Sin clave, la seccion no aparece**: el frontend lo consulta en
`GET /recognize/status`, igual que hace con el microfono. Las dos cosas son
independientes: se puede tener una sin la otra.

## Fichas de artista

Al descargar una cancion se crea sola la ficha de su artista y se rellena
consultando dos fuentes:

- **MusicBrainz** aporta pais, anos de actividad, tipo (grupo o persona) y las
  relaciones entre artistas, que es lo interesante: "Robbie Williams fue
  miembro de Take That".
- **Wikipedia** aporta la biografia en prosa. Se llega a ella por el enlace a
  Wikidata que MusicBrainz ya guarda, que acierta mas que buscar por nombre.

El buscador de MusicBrainz devuelve 503 con frecuencia. Cuando pasa, el
identificador del artista se resuelve por **Wikidata** (que guarda el mismo id
en su propiedad P434) y los datos se leen del lookup directo de MusicBrainz,
que si es estable. Se respeta el limite de una peticion por segundo.

Las relaciones guardan el nombre del otro artista aunque no este en la
biblioteca; cuando mas adelante aparece, la relacion pasa a ser un enlace
navegable en los dos sentidos.

**Editar una ficha a mano la marca como `manual`** y el enriquecido automatico
deja de pisarla. Desde la ficha se puede forzar el rehacer si se quiere volver a
los datos externos.

Para las canciones que ya estaban antes de existir este modulo:

```bash
docker compose exec backend python -m app.cli.link_artists
```

Crea las fichas que falten y las enriquece. Es idempotente.

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
