# Briefing: DJ Library — Biblioteca musical local para DJ

## Objetivo

Aplicación web autoalojada (self-hosted) que permite construir y mantener una biblioteca de mp3 para uso como DJ, con dos vías de ingesta:

1. **Por link de YouTube** → descarga el audio como mp3 y lo añade a la biblioteca.
2. **Por reconocimiento de audio** (tipo Shazam) → grabas un fragmento de una canción sonando, se identifica (artista + título), se busca en YouTube y se descarga.
3. **Por búsqueda manual (título + artista)** → el usuario ya sabe qué canción es (sin necesidad de grabarla ni reconocerla) y quiere añadirla directamente escribiendo el nombre; el sistema busca en YouTube y descarga igual que en los casos anteriores.

Además, la biblioteca no es solo almacenamiento: debe permitir **clasificar cada canción por mood, estilo y tipo de fiesta/momento** (p. ej. "warm-up chill", "hits 80s", "británica energética"), para poder montar sets o "crates" temáticos como hace un DJ real preparando una noche.

Se publicará en un subdominio propio, por lo que requiere autenticación y gestión de usuarios desde el primer día. **Plan de desarrollo:** empezar por el módulo de autenticación (funcional en local/Docker) antes de tocar nada más; el despliegue en el subdominio real se hace una vez el auth esté probado y sólido.

## Stack

- **Contenedores:** Docker + docker-compose (servicios separados: backend, frontend, db, y opcionalmente un reverse proxy tipo Traefik/nginx si se gestiona en este mismo compose).
- **Backend:** FastAPI (Python).
- **Frontend:** Vite + React + TypeScript.
- **Base de datos:** MariaDB.
- **Descarga/búsqueda:** `yt-dlp` + `ffmpeg` (postprocesado a mp3), ejecutados desde el backend.
- **Captura de audio:** desde el navegador (Web Audio API / MediaRecorder), pensado como uso principal en móvil (grabar mientras suena la canción en un bar/sala), no solo en escritorio.
- **Reconocimiento:** cliente HTTP desde el backend a AudD.io o ACRCloud (evaluar tier gratuito/precisión de cada uno).
- **Datos de artistas:** cliente HTTP desde el backend a MusicBrainz (relaciones entre artistas/bandas) y/o Wikipedia-Wikidata (biografía en prosa).
- **Auth:** JWT (access + refresh token) con hashing de contraseñas (bcrypt/argon2). Login en frontend, endpoints protegidos en backend.

## Autenticación y usuarios

- Sistema de login con usuario/contraseña (JWT).
- Usuario inicial (seed): `enguillem`, rol **admin**.
- Roles: `admin` y `user` (el MVP puede simplificarse a solo estos dos).
- Funcionalidades de cuenta:
  - Cambiar contraseña (propia).
  - Añadir/editar correo electrónico (propio).
  - Admin puede dar de alta nuevos usuarios (username, email, contraseña inicial o invitación).
  - Admin puede ver/gestionar el listado de usuarios (activar/desactivar, cambiar rol — opcional en MVP).
- Todas las rutas de gestión de biblioteca (descarga, reconocimiento, borrado) requieren sesión autenticada. Dar de alta usuarios y gestión de cuentas requiere rol admin.

## Alcance funcional (MVP)

### 1. Ingesta por URL
- Input desde el frontend: URL de YouTube.
- Backend descarga y extrae audio a mp3 con metadata (título, artista si se puede inferir).
- Deduplicación: no descargar dos veces la misma canción (comparar por ID de YouTube o título normalizado).
- Feedback de progreso en el frontend (estado: descargando / completado / error).

### 2. Ingesta por reconocimiento (uso principal: móvil)
- Frontend responsive/mobile-first para esta pantalla en concreto: es el flujo que se va a usar en vivo, con el móvil en la mano, en un bar o sala.
- Botón grande de "grabar" con indicador claro de que está grabando (visual, tipo barra de progreso o contador de segundos) — hay ruido ambiente y poca luz, la UI tiene que ser inequívoca a golpe de vista.
- Captura de 10-15s desde el micrófono del móvil (MediaRecorder API; requiere HTTPS, lo cual ya viene dado por el subdominio con TLS).
- El fragmento se sube al backend, que lo envía a AudD/ACRCloud.
- Con el resultado (artista + título), búsqueda automática en YouTube (`yt-dlp ytsearch1:"artista título"`) y descarga como en el punto 1.
- Manejar caso de "no reconocido" (mostrar error claro en el móvil, botón directo de "reintentar grabación", y opción de pasar a búsqueda manual con lo que el usuario ya intuye del tema).
- Tener en cuenta que la app se usará con conexión de datos móviles, no solo wifi: cuidar tamaños de subida/respuesta y mostrar estados de carga claros ante conexiones más lentas.

### 3. Ingesta manual por título/artista
- Formulario simple: título + artista (el usuario ya sabe qué es, sin grabar ni reconocer nada).
- Mismo flujo de búsqueda y descarga que en los puntos 1 y 2 (`yt-dlp ytsearch1:"artista título"`).
- Útil especialmente para el conocimiento musical propio del usuario (temas de los 60-80 que reconoce de oído), evitando pasar por el paso de reconocimiento cuando no hace falta.

### 4. Clasificación y crates
- Cada canción puede etiquetarse con: **mood** (ej. chill, eufórico, oscuro), **estilo/género** (ej. electrónica, hip hop, trap, pop español, britpop) y **tipo de momento/fiesta** (ej. warm-up, prime time, cierre).
- Etiquetas como catálogo editable (no texto libre sin control, para evitar duplicados tipo "80s" / "Ochentas").
- Posibilidad de asignar varias etiquetas por canción.
- Filtrado de la biblioteca combinando etiquetas (ej. "warm-up" + "británica" + "chill") para armar un crate rápido antes de un set.
- (Fase 2, no MVP estricto pero fácil de dejar preparado en el modelo de datos): guardar "crates" con nombre propio como listas de canciones reutilizables.

### 5. Gestión de biblioteca (frontend + backend)
- Listado de canciones con búsqueda/filtro (título, artista, fecha, mood/estilo/tipo de fiesta).
- Reproductor simple embebido para previsualizar antes de usar en el set (opcional en MVP, útil para verificar descargas).
- Borrar canciones de la biblioteca (archivo + registro en DB).
- Descarga del mp3 desde el frontend (para pasarlo a Mixxx/rekordbox u otro software de DJ).
- Metadata almacenada en MariaDB: título, artista, fuente (URL original), fecha de descarga, duración, usuario que la añadió, BPM (fase 2), y relación con etiquetas de mood/estilo/tipo de fiesta.

### 6. Biblioteca de artistas
- Ficha de artista independiente de las canciones: nombre, biografía corta, bandas/proyectos anteriores o relacionados (ej. Robbie Williams ↔ Take That), década/país de origen.
- Relación muchos-a-muchos entre tracks y artistas (una canción puede tener varios artistas; un artista puede tener varias canciones en la biblioteca).
- Origen de la biografía: al añadir un artista nuevo (manual o automáticamente al descargar una canción suya), consultar una fuente externa para rellenar la ficha:
  - **MusicBrainz** (API gratuita, datos estructurados: bandas, relaciones entre artistas, fechas) — mejor para relaciones tipo "miembro de".
  - **Wikipedia/Wikidata** (extracto del resumen) — mejor para biografía en prosa.
  - Combinar ambas si se quiere biografía + relaciones estructuradas; si no, empezar solo con Wikipedia por simplicidad.
- Edición manual de la ficha desde el frontend, por si la fuente automática falla o el usuario quiere completarla con su propio conocimiento (que es amplio).
- Vista de "artista" en el frontend: biografía + listado de sus canciones ya presentes en la biblioteca.
- Este módulo también ayuda al caso de "sé que esta canción suena ahora mismo en todas partes pero no sé quién la toca": tras identificarla (por reconocimiento o búsqueda), el sistema crea/vincula automáticamente la ficha del artista, así queda documentado para la próxima vez.

## Fuera de alcance en el MVP (posibles fases futuras)
- Análisis de BPM/key para mezcla (librosa, o integración con Mixxx/rekordbox).
- Normalización de volumen (loudness) automática.
- Reconocimiento continuo en background / streaming.
- Crates guardados como listas nombradas y reordenables tipo Serato/rekordbox (el MVP cubre el etiquetado y filtrado; guardar la combinación como "crate" con nombre es fase 2).
- Invitación de usuarios por email (en MVP basta con alta directa por el admin).

## Arquitectura de servicios (docker-compose)

- `frontend`: Vite/React/TS servido (build estático detrás de nginx, o dev server en desarrollo).
- `backend`: FastAPI, expone API REST (`/auth`, `/tracks`, `/recognize`, `/users`, `/tags`, `/artists`).
- `db`: MariaDB con volumen persistente.
- Volumen persistente separado para los mp3 descargados (no dentro del contenedor de backend, para no perderlos en rebuilds).
- Variables sensibles (JWT secret, claves AudD/ACRCloud, credenciales DB) vía `.env`, no hardcodeadas.
- Si se expone en subdominio: reverse proxy (Traefik o nginx) con TLS (Let's Encrypt), ya sea en este mismo compose o gestionado a nivel del homelab si ya existe uno.

## Consideraciones técnicas a resolver en el desarrollo
- Rate limits / bloqueos de yt-dlp por parte de YouTube (posible necesidad de cookies o rotación de user-agent).
- Tamaño y gestión del volumen de mp3 (backup, límites de espacio).
- CORS entre frontend y backend si no quedan detrás del mismo dominio/proxy.
- Normalización de nombres de archivo (caracteres especiales, mayúsculas/minúsculas) para evitar duplicados por formato.
- Manejo de errores en descarga (vídeos privados, geobloqueados, eliminados).
- Al exponerse públicamente en subdominio: rate limiting básico en endpoints de login, y política de contraseñas mínima.
- Permisos de micrófono en móvil: gestionar bien el flujo de solicitud de permiso (especialmente en iOS Safari, más restrictivo que Android) y el mensaje de error si el usuario lo deniega.

## Aviso a tener en cuenta (no bloqueante)
Descargar audio de YouTube incumple sus Términos de Servicio. Para uso personal el riesgo práctico es bajo, pero al publicarse en un subdominio (aunque sea de acceso privado/autenticado), conviene no indexarlo públicamente ni promocionarlo como servicio abierto.

## Entregable esperado de esta primera fase con Claude Code
- Estructura de proyecto Docker (docker-compose.yml, Dockerfiles para backend y frontend).
- Backend FastAPI con:
  - Modelos y migraciones para MariaDB (usuarios, tracks, artistas, tags/etiquetas y sus relaciones).
  - Auth JWT completa (login, cambio de contraseña, gestión de email, alta de usuarios por admin).
  - Endpoints de ingesta por URL, por reconocimiento y por búsqueda manual (título/artista).
  - Endpoints de gestión de etiquetas (mood, estilo, tipo de fiesta) y filtrado combinado.
  - Endpoints de artistas: alta automática al añadir canción, enriquecido desde MusicBrainz/Wikipedia, edición manual.
- Frontend Vite/React/TS con:
  - Pantalla de login.
  - Vista de biblioteca (listado, búsqueda, filtrado por etiquetas, borrado).
  - Formulario de añadir por URL y por título/artista.
  - Flujo de grabación/reconocimiento de audio.
  - Gestión de etiquetas por canción (asignar mood/estilo/tipo de fiesta).
  - Vista de ficha de artista (biografía + canciones en la biblioteca), con opción de editar manualmente.
  - Panel de admin básico (alta de usuarios).
- Seed inicial del usuario `enguillem` como admin.
