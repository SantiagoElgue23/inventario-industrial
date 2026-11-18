"""Administración de cuentas master por consola.

El rol master no puede otorgarse desde la web: solo quien tiene acceso al
servidor puede crear, promover o degradar cuentas master. Desde la raíz del
proyecto, después de ``alembic upgrade head``:

  python -m backend.app.auth_bootstrap listar
  python -m backend.app.auth_bootstrap crear-master <usuario>
  python -m backend.app.auth_bootstrap promover <usuario>
  python -m backend.app.auth_bootstrap degradar <usuario> --rol admin
  python -m backend.app.auth_bootstrap restablecer <usuario>
"""
import argparse
import getpass
import re

from sqlalchemy import delete, func, select

from . import models as m
from .auth import USERNAME_PATTERN, hash_password
from .database import SessionLocal


def ask_password(username: str) -> str:
    pwd = getpass.getpass(f"Contraseña nueva para {username} (mínimo 12 caracteres): ")
    if pwd != getpass.getpass("Repetir contraseña: "):
        raise SystemExit("Las contraseñas no coinciden; no se hicieron cambios")
    try:
        return hash_password(pwd)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def find(db, username: str) -> m.AppUser:
    account = db.scalar(select(m.AppUser).where(m.AppUser.username == username))
    if account is None:
        raise SystemExit(f"No existe la cuenta {username}")
    return account


def revoke(db, account: m.AppUser) -> None:
    db.execute(delete(m.AppSession).where(m.AppSession.user_id == account.id))


def main() -> None:
    parser = argparse.ArgumentParser(description="Cuentas master de Inventario Industrial")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("listar", help="Lista todas las cuentas y sus roles")
    sub.add_parser("crear-master", help="Crea una cuenta master nueva").add_argument("usuario")
    sub.add_parser("promover", help="Convierte una cuenta existente en master").add_argument("usuario")
    demote = sub.add_parser("degradar", help="Quita el rol master a una cuenta")
    demote.add_argument("usuario")
    demote.add_argument("--rol", choices=("admin", "user"), default="admin")
    sub.add_parser("restablecer", help="Restablece la contraseña de cualquier cuenta").add_argument("usuario")
    args = parser.parse_args()
    username = getattr(args, "usuario", "").strip().lower()

    with SessionLocal() as db:
        if args.command == "listar":
            for u in db.scalars(select(m.AppUser).order_by(m.AppUser.role, m.AppUser.username)):
                print(f"{u.username:<32} {u.role:<7} {'activa' if u.active else 'inactiva'}")
            return

        if args.command == "crear-master":
            if not re.fullmatch(USERNAME_PATTERN, username):
                raise SystemExit("Usuario inválido: 3 a 32 caracteres a-z, 0-9, punto, guion o guion bajo")
            if db.scalar(select(m.AppUser.id).where(m.AppUser.username == username)) is not None:
                raise SystemExit(f"La cuenta {username} ya existe; usá 'promover'")
            db.add(m.AppUser(username=username, role="master", password_hash=ask_password(username)))
        elif args.command == "promover":
            account = find(db, username)
            account.role = "master"
            revoke(db, account)
        elif args.command == "degradar":
            account = find(db, username)
            if account.role != "master":
                raise SystemExit(f"{username} no es master")
            masters = db.scalar(select(func.count()).select_from(m.AppUser).where(
                m.AppUser.role == "master", m.AppUser.active.is_(True)))
            if masters <= 1:
                raise SystemExit("No se puede degradar al último master activo")
            account.role = args.rol
            revoke(db, account)
        elif args.command == "restablecer":
            account = find(db, username)
            account.password_hash = ask_password(username)
            revoke(db, account)

        db.commit()
        print("Listo. Las sesiones abiertas de la cuenta afectada se cerraron.")


if __name__ == "__main__":
    main()
