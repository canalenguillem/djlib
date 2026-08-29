#!/bin/sh
# Espera a la base de datos, aplica migraciones y siembra el admin inicial.
set -e

echo "[entrypoint] Esperando a MariaDB en ${DB_HOST:-db}:${DB_PORT:-3306}..."
for i in $(seq 1 60); do
  if python -c "
import os, socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect((os.environ.get('DB_HOST', 'db'), int(os.environ.get('DB_PORT', '3306'))))
except OSError:
    sys.exit(1)
" 2>/dev/null; then
    echo "[entrypoint] MariaDB disponible."
    break
  fi
  sleep 2
done

echo "[entrypoint] Aplicando migraciones (alembic upgrade head)..."
alembic upgrade head

echo "[entrypoint] Sembrando usuario admin inicial..."
python -m app.cli.seed

echo "[entrypoint] Arrancando: $@"
exec "$@"
