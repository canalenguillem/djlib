"""Pone una contrasena nueva a un usuario, para cuando se ha olvidado.

La contrasena se pide por teclado sin mostrarla, dos veces; nunca va en la
linea de comandos, que quedaria en el historial. Cierra ademas todas las
sesiones abiertas del usuario.

Uso (en el servidor):
    docker compose -f docker-compose.prod.yml exec backend \\
        python -m app.cli.reset_password enguillem
"""

import sys
from getpass import getpass

from app.db.session import SessionLocal
from app.services import user_service
from app.services.user_service import PasswordPolicyError


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Uso: python -m app.cli.reset_password <usuario>", file=sys.stderr)
        return 2
    username = argv[1]

    with SessionLocal() as db:
        user = user_service.get_by_username(db, username)
        if user is None:
            print(f"[reset] No existe el usuario '{username}'.", file=sys.stderr)
            return 1

        nueva = getpass(f"Contrasena nueva para '{username}': ")
        if getpass("Repitela: ") != nueva:
            print("[reset] No coinciden. No se cambia nada.", file=sys.stderr)
            return 1
        try:
            user_service.change_password(db, user, nueva)
        except PasswordPolicyError as exc:
            print(f"[reset] {exc}", file=sys.stderr)
            return 1
        # Si estaba desactivado, tampoco podria entrar
        if not user.is_active:
            user.is_active = True
            print("[reset] El usuario estaba desactivado: se ha reactivado.")
        db.commit()

    print(f"[reset] Contrasena de '{username}' cambiada. Se han cerrado sus sesiones abiertas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
