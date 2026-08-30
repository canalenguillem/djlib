# Estado del proyecto

Resumen de lo construido hasta ahora, las decisiones que hay detrás y lo que
queda. Actualizado a 30 de agosto de 2026.

Para arrancarlo y para la referencia de la API, ver [README.md](README.md).

---

## Dónde está

En producción, en `https://djlib.enguillem.es`, sirviendo el build estático
desde nginx. Con datos reales dentro: 34 canciones, 26 fichas de artista y 53
relaciones entre artistas.

| | |
| --- | --- |
| Backend | 58 ficheros Python, ~5.500 líneas |
| Frontend | 37 ficheros, ~4.200 líneas |
| Tests | 126, en ~7 segundos |
| Migraciones | 4 |
| Endpoints | 42 |
| Commits | 15 |

## Lo que hace

Todo el MVP del briefing salvo el análisis de BPM.

**Tres vías de ingesta**, las tres desembocando en el mismo pipeline de
descarga:

1. **Enlace de YouTube** pegado a mano.
2. **Título y/o artista**: muestra los candidatos de YouTube con miniatura,
   canal y duración, y eliges. Solo con el artista, muestra diez para explorar
   su catálogo.
3. **Reconocimiento de audio**: grabas 11 segundos de lo que suena, AudD lo
   identifica y ofrece las versiones de YouTube para elegir.

**Biblioteca**: listado con búsqueda, filtrado combinado por etiquetas
(mood / estilo / momento de la noche), reproductor, descarga del mp3 y borrado.

**Artistas**: ficha creada automáticamente al descargar, con país, años de
actividad, biografía de Wikipedia y relaciones entre artistas de MusicBrainz.
Editable a mano.

**Crates**: selecciones con nombre y orden propio, montadas guardando un filtro
de golpe o añadiendo canciones a mano, y reordenables arrastrando o con flechas.

**Usuarios**: login con JWT, roles admin y user, alta y gestión desde el panel.

## Arquitectura

Tres servicios en Docker, con **un único puerto publicado**: el del frontend.
El backend y MariaDB no son alcanzables desde fuera de la red de compose; el
navegador llega a la API por el proxy `/api` del frontend, así que no hay
peticiones entre orígenes y CORS sobra.

```
navegador ──► frontend (nginx o Vite) ──┬──► /api  ──► backend (FastAPI) ──► db (MariaDB)
                                        └──► estáticos                       volumen music_data
```

Dos modos, mismo proyecto y mismos volúmenes:

```bash
docker compose -f docker-compose.prod.yml up -d --build   # producción
docker compose up -d                                      # desarrollo
```

En producción el código del backend **viene de la imagen**, así que cualquier
cambio necesita `up -d --build backend`.

## Modelo de datos

```
users ──< refresh_tokens
users ──< tracks

tracks >──< tags        (track_tags)      etiquetas de mood, estilo y momento
tracks >──< artists     (track_artists)   con posición: principal primero
artists ──< artist_relations              "miembro de", "colaboración"...
```

Las relaciones entre artistas guardan el **nombre** del otro aunque no esté en
la biblioteca; cuando más adelante aparece, la relación pasa a ser un enlace
navegable en los dos sentidos.

## Decisiones que conviene recordar

**Deduplicación en dos niveles.** Por id de vídeo, y como red secundaria por
una clave normalizada de artista + título que ignora acentos, mayúsculas y el
ruido típico de YouTube. "Blur - Song 2 (Official Video)" y "blur song 2" son
la misma canción.

**Los mp3 se guardan con el id del vídeo como nombre**, no con el título: sin
acentos, sin caracteres raros y sin dos canciones peleándose por el mismo
nombre. El nombre bonito se aplica al descargar desde el navegador.

**Las descargas viven dentro del proceso del backend**, sin cola externa. Es
suficiente para un uso personal, pero un reinicio las deja a medias: al
arrancar se marcan como error, se ven en el listado y hay botón de reintentar.

**Un solo worker de uvicorn** en producción, a propósito: las descargas se
ejecutan en el proceso y el limitador del login vive en memoria, así que
repartir las peticiones entre varios rompería ambas cosas.

**Solo se parte el artista por "feat."**, nunca por `&` ni por comas: "Simon &
Garfunkel" o "Earth, Wind & Fire" son un único artista y equivocarse ahí ensucia
más de lo que ayuda.

**Editar una ficha de artista a mano la marca como `manual`** y el enriquecido
automático deja de pisarla, salvo que se fuerce desde la propia ficha.

**El orden de un crate se manda entero**, no por movimientos sueltos: dos
reordenaciones seguidas no pueden dejarlo a medias, y el frontend puede pintar
el cambio al instante y deshacerlo si el servidor lo rechaza.

**El catálogo de etiquetas es cerrado**, con slug único por categoría: "80s" y
"Ochentas" chocan en vez de convivir. El filtrado combina en AND.

## Problemas encontrados en uso real

Estos salieron usando la aplicación de verdad, no en las pruebas. Se dejan
anotados porque explican por qué el código es como es.

**El primer resultado de YouTube suele ser un mix de una hora.** Buscar "Bad
Bunny Nueva Yirky" devolvía un mix de 42 minutos y el tope de una hora lo
dejaba pasar. Ahora se miran cinco candidatos y se elige por duración — y, mejor
aún, se te enseñan para que elijas tú. Un filtro automático evita el mix pero
con una consulta imprecisa acaba bajando otra canción que tampoco es; viendo la
lista se nota enseguida que hay que afinar el título.

**yt-dlp escribe un JSON por línea en las búsquedas**, no una lista. Se leía
solo el primero, así que el filtro por duración no hacía nada. El test no lo
detectó porque el fixture no reproducía la salida real: la lección es que los
dobles tienen que imitar la forma exacta de lo que sustituyen.

**El buscador de MusicBrainz devuelve 503 constantemente.** El lookup directo
por identificador sí es fiable, así que cuando el buscador falla el
identificador se resuelve por **Wikidata** (que guarda el mismo id en su
propiedad P434) y los datos se leen del lookup directo.

**AudD recomienda fragmentos de 2 a 12 segundos.** Con 13 y ruido ambiente real
devolvía error al generar la huella, aunque con audio limpio aguante más. La
grabación bajó a 11.

**El navegador cancela el eco por defecto.** `getUserMedia({audio: true})`
activa cancelación de eco, supresión de ruido y control de ganancia, pensados
para videollamadas. El cancelador elimina justo el sonido que sale por los
altavoces del propio equipo y **tarda unos segundos en adaptarse**: la primera
grabación salía bien y a partir de la segunda quedaba en silencio. Ahora se pide
la señal cruda.

**"No se ha reconocido" tapaba tres problemas distintos.** Ahora se separan: no
ha entrado sonido (el vúmetro lo avisa en directo y la grabación ni se envía,
para no gastar cuota de AudD), no reconocida (el audio está bien pero AudD no la
tiene: pasa con remezclas y edits de DJ), y ha fallado (cuota, clave, AudD
caído).

**Vite 6 bloquea los Host que no conoce.** Entrar por nombre de dominio daba
`403 Blocked request` hasta declararlo en `VITE_ALLOWED_HOSTS`. En producción no
aplica, porque ahí sirve nginx.

**Los tests salían a internet.** Los de biblioteca no sustituían el enriquecido
de artistas, así que cada uno consultaba MusicBrainz de verdad. Eso, más
recrear el esquema de la base de datos en cada test, tenía la suite en 250
segundos. Ahora son 6.

## Pruebas

126 tests de backend, con yt-dlp, MusicBrainz/Wikipedia y AudD sustituidos por
dobles. Corren contra una base MariaDB aparte, no contra SQLite, para probar el
mismo motor que producción.

```bash
docker compose exec backend pytest
```

Además, cada entrega se ha verificado en un navegador real contra el servidor:
login, descargas de verdad desde YouTube, reproducción, y el reconocimiento con
el micrófono simulado de Chromium alimentado con audio real.

## Qué queda

| | |
| --- | --- |
| **Editar título y artista desde la fila** | La API lo soporta (`PATCH /tracks/{id}`), la interfaz no. Serviría para corregir metadatos sucios de YouTube. |
| **Análisis de BPM** | Fase 2 explícita del briefing. |

## Copias de seguridad

`scripts/backup.sh` guarda el volcado de MariaDB, los mp3 y el `.env`, y **se
verifica sola** restaurando el volcado en una base de datos desechable. Corre
por cron todos los días a las 4:30. `scripts/restore.sh` hace el camino
inverso, pidiendo confirmación porque sobrescribe.

Se probó restaurando la copia completa en una pila Docker aislada, levantada
vacía: las siete tablas quedaron con los mismos recuentos que producción, los
mp3 coincidían byte a byte (283.216.662 en ambas) y `ffprobe` confirmó que eran
audio válido y no ficheros truncados.

## Riesgos conocidos

**yt-dlp se romperá.** YouTube cambia a menudo. El arreglo casi siempre es
`docker compose build --no-cache backend`. Si llega a pedir verificación
anti-bot, hay que exportar cookies del navegador y apuntar `YTDLP_COOKIES_FILE`.

**La cuota de AudD.** 300 peticiones gratis; después, 5 $ por cada 1.000. Al
agotarse, el reconocimiento deja de funcionar pero el resto de la biblioteca
sigue igual, y el mensaje lo dice claro.

**AudD no conoce las remezclas.** Indexa lanzamientos comerciales: los edits y
las sesiones de DJ no suelen estar, por muy limpia que sea la grabación.

**El espacio en disco.** Los mp3 crecen sin límite y nada lo vigila, y ahora
cada copia de seguridad multiplica ese tamaño por las que se conserven (siete
por defecto). Con 34 canciones son 269 MB por copia.

**Las copias están en la misma máquina.** Protegen de un borrado accidental o
de un `down -v`, no de que el disco muera. Apuntar `BACKUP_DIR` a un NAS o a un
disco externo cierra ese hueco.
