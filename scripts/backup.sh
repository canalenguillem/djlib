#!/usr/bin/env bash
# Copia de seguridad de DJ Library: base de datos, mp3 y configuracion.
#
#   ./scripts/backup.sh              copia y la verifica
#   ./scripts/backup.sh --no-verify  copia sin verificar (mas rapida)
#   ./scripts/backup.sh --quiet      sin salida salvo errores (para cron)
#
# Las copias van a BACKUP_DIR (por defecto ./backups) en carpetas con fecha, y
# se conservan las BACKUP_KEEP mas recientes.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

VERIFICAR=1
SILENCIOSO=0
for arg in "$@"; do
  case "$arg" in
    --no-verify) VERIFICAR=0 ;;
    --quiet) SILENCIOSO=1 ;;
    *) echo "Opcion desconocida: $arg" >&2; exit 2 ;;
  esac
done

log() { [ "$SILENCIOSO" -eq 1 ] || echo "$@"; }
fallo() { echo "[backup] ERROR: $*" >&2; exit 1; }

[ -f .env ] || fallo "no se encuentra .env en $RAIZ"
# El entorno manda sobre .env: asi se puede lanzar puntualmente
# BACKUP_KEEP=1 o BACKUP_DIR=/mnt/nas ./scripts/backup.sh sin editar nada.
while IFS= read -r linea; do
  case "$linea" in ''|'#'*) continue ;; esac
  clave="${linea%%=*}"
  [ -n "${!clave:-}" ] || export "$clave=${linea#*=}"
done < .env

DESTINO="${BACKUP_DIR:-$RAIZ/backups}"
CONSERVAR="${BACKUP_KEEP:-7}"
SELLO="$(date +%Y-%m-%d_%H%M%S)"
CARPETA="$DESTINO/$SELLO"

docker compose ps --status running --services 2>/dev/null | grep -qx db \
  || fallo "el servicio db no esta en marcha"

mkdir -p "$CARPETA"
# La copia lleva secretos (.env) y musica: solo para el usuario.
chmod 700 "$DESTINO" "$CARPETA"

log "[backup] $SELLO -> $CARPETA"

# --- Base de datos ---
# --single-transaction hace el volcado consistente sin bloquear las tablas, de
# modo que la aplicacion puede seguir funcionando mientras se copia.
log "[backup] volcando la base de datos..."
docker compose exec -T db mariadb-dump \
  -u root -p"$MARIADB_ROOT_PASSWORD" \
  --single-transaction --routines --triggers --events \
  --databases "$MARIADB_DATABASE" \
  | gzip > "$CARPETA/db.sql.gz"

[ -s "$CARPETA/db.sql.gz" ] || fallo "el volcado de la base de datos esta vacio"

# --- Musica ---
# Se empaqueta desde el contenedor, que es quien tiene montado el volumen.
log "[backup] empaquetando los mp3..."
docker compose exec -T backend tar czf - -C /data music > "$CARPETA/music.tar.gz"

# --- Configuracion ---
# Sin .env no se puede restaurar en una maquina nueva: la contrasena de la base
# de datos tiene que coincidir. Va cifrado por permisos de fichero, nada mas.
cp .env "$CARPETA/env.backup"
chmod 600 "$CARPETA/env.backup"

# --- Manifiesto ---
CANCIONES=$(docker compose exec -T db mariadb -u root -p"$MARIADB_ROOT_PASSWORD" \
  -N -B -e "SELECT COUNT(*) FROM \`$MARIADB_DATABASE\`.tracks" 2>/dev/null || echo "?")
ARTISTAS=$(docker compose exec -T db mariadb -u root -p"$MARIADB_ROOT_PASSWORD" \
  -N -B -e "SELECT COUNT(*) FROM \`$MARIADB_DATABASE\`.artists" 2>/dev/null || echo "?")
FICHEROS=$(tar tzf "$CARPETA/music.tar.gz" | grep -c '\.mp3$' || true)

cat > "$CARPETA/MANIFEST.txt" <<MANIFEST
DJ Library - copia de seguridad
fecha:      $(date --iso-8601=seconds)
maquina:    $(hostname)
base:       $MARIADB_DATABASE
canciones:  $CANCIONES (registros en tracks)
mp3:        $FICHEROS ficheros
artistas:   $ARTISTAS
tamanos:    db $(du -h "$CARPETA/db.sql.gz" | cut -f1) | musica $(du -h "$CARPETA/music.tar.gz" | cut -f1)

Restaurar con:  ./scripts/restore.sh $SELLO
MANIFEST

log "[backup] $CANCIONES canciones, $FICHEROS mp3, $ARTISTAS artistas"
log "[backup] $(du -sh "$CARPETA" | cut -f1) en total"

# --- Verificacion ---
# Una copia que no se ha probado no es una copia. Se restaura el volcado en una
# base de datos desechable y se comprueba que los datos estan.
if [ "$VERIFICAR" -eq 1 ]; then
  log "[backup] verificando la copia..."
  PRUEBA="${MARIADB_DATABASE}_verify"
  docker compose exec -T db mariadb -u root -p"$MARIADB_ROOT_PASSWORD" \
    -e "DROP DATABASE IF EXISTS \`$PRUEBA\`; CREATE DATABASE \`$PRUEBA\`;"

  # El volcado trae "CREATE DATABASE" y "USE" de la base original: se cambian
  # al vuelo para que entre en la de prueba sin tocar la de verdad.
  gunzip -c "$CARPETA/db.sql.gz" \
    | sed "s/\`$MARIADB_DATABASE\`/\`$PRUEBA\`/g" \
    | docker compose exec -T db mariadb -u root -p"$MARIADB_ROOT_PASSWORD"

  RESTAURADAS=$(docker compose exec -T db mariadb -u root -p"$MARIADB_ROOT_PASSWORD" \
    -N -B -e "SELECT COUNT(*) FROM \`$PRUEBA\`.tracks")
  docker compose exec -T db mariadb -u root -p"$MARIADB_ROOT_PASSWORD" \
    -e "DROP DATABASE \`$PRUEBA\`;"

  RESTAURADAS=$(echo "$RESTAURADAS" | tr -d '[:space:]')
  [ "$RESTAURADAS" = "$CANCIONES" ] \
    || fallo "la copia no restaura bien: $RESTAURADAS canciones frente a $CANCIONES"

  # Y que el tar no este corrupto
  tar tzf "$CARPETA/music.tar.gz" > /dev/null || fallo "el archivo de musica esta corrupto"

  echo "verificada: restaura $RESTAURADAS canciones" >> "$CARPETA/MANIFEST.txt"
  log "[backup] verificada: el volcado restaura $RESTAURADAS canciones y el tar es legible"
fi

# --- Rotacion ---
mapfile -t ANTIGUAS < <(find "$DESTINO" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' \
  | sort -r | tail -n +$((CONSERVAR + 1)))
for vieja in "${ANTIGUAS[@]:-}"; do
  [ -n "$vieja" ] || continue
  log "[backup] borrando copia antigua: $vieja"
  rm -rf "${DESTINO:?}/$vieja"
done

log "[backup] listo"
