#!/usr/bin/env bash
# Restaura una copia de seguridad de DJ Library.
#
#   ./scripts/restore.sh                 lista las copias disponibles
#   ./scripts/restore.sh 2026-08-30_1035 restaura esa copia
#   ./scripts/restore.sh ultima          restaura la mas reciente
#
# SOBRESCRIBE la base de datos y los mp3 actuales, asi que pide confirmacion.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

fallo() { echo "[restore] ERROR: $*" >&2; exit 1; }

[ -f .env ] || fallo "no se encuentra .env en $RAIZ"
# El entorno manda sobre .env: asi se puede lanzar puntualmente
# BACKUP_KEEP=1 o BACKUP_DIR=/mnt/nas ./scripts/backup.sh sin editar nada.
while IFS= read -r linea; do
  case "$linea" in ''|'#'*) continue ;; esac
  clave="${linea%%=*}"
  [ -n "${!clave:-}" ] || export "$clave=${linea#*=}"
done < .env
DESTINO="${BACKUP_DIR:-$RAIZ/backups}"

[ -d "$DESTINO" ] || fallo "no hay carpeta de copias en $DESTINO"

if [ $# -eq 0 ]; then
  echo "Copias disponibles en $DESTINO:"
  find "$DESTINO" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' | sort -r | while read -r c; do
    canciones=$(grep -m1 '^canciones:' "$DESTINO/$c/MANIFEST.txt" 2>/dev/null | cut -d: -f2- || echo " ?")
    printf "  %s  %6s %s\n" "$c" "$(du -sh "$DESTINO/$c" | cut -f1)" "$canciones"
  done
  echo
  echo "Restaurar con:  ./scripts/restore.sh <fecha>   (o 'ultima')"
  exit 0
fi

SELLO="$1"
if [ "$SELLO" = "ultima" ]; then
  SELLO=$(find "$DESTINO" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' | sort -r | head -1)
  [ -n "$SELLO" ] || fallo "no hay ninguna copia en $DESTINO"
fi
CARPETA="$DESTINO/$SELLO"

[ -d "$CARPETA" ] || fallo "no existe la copia $SELLO"
[ -f "$CARPETA/db.sql.gz" ] || fallo "falta db.sql.gz en la copia"
[ -f "$CARPETA/music.tar.gz" ] || fallo "falta music.tar.gz en la copia"

echo "----------------------------------------------------------------"
cat "$CARPETA/MANIFEST.txt"
echo "----------------------------------------------------------------"
echo
echo "Esto SOBRESCRIBE la base de datos '$MARIADB_DATABASE' y los mp3 actuales."
read -r -p "Escribe 'restaurar' para continuar: " respuesta
[ "$respuesta" = "restaurar" ] || { echo "Cancelado."; exit 1; }

docker compose ps --status running --services 2>/dev/null | grep -qx db \
  || fallo "el servicio db no esta en marcha"

# --- Base de datos ---
echo "[restore] restaurando la base de datos..."
gunzip -c "$CARPETA/db.sql.gz" \
  | docker compose exec -T db mariadb -u root -p"$MARIADB_ROOT_PASSWORD"

# --- Musica ---
# --overwrite para que los ficheros existentes se reemplacen; los que haya de
# mas y no esten en la copia se quedan (no se borra nada por si acaso).
echo "[restore] restaurando los mp3..."
docker compose exec -T backend tar xzf - -C /data --overwrite < "$CARPETA/music.tar.gz"

CANCIONES=$(docker compose exec -T db mariadb -u root -p"$MARIADB_ROOT_PASSWORD" \
  -N -B -e "SELECT COUNT(*) FROM \`$MARIADB_DATABASE\`.tracks" | tr -d '[:space:]')
FICHEROS=$(docker compose exec -T backend sh -c 'ls /data/music/*.mp3 2>/dev/null | wc -l' | tr -d '[:space:]')

echo "[restore] listo: $CANCIONES canciones en la base de datos, $FICHEROS mp3 en disco"
echo "[restore] reinicia el backend para que recargue todo:"
echo "          docker compose restart backend"
