
import os
from pathlib import Path
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


# Localizar la raíz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Cargar las variables de entorno
load_dotenv(PROJECT_ROOT / ".env")

# Obtener la conexión a PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "No se encontró DATABASE_URL. "
        "Creá el archivo .env en la raíz del proyecto "
        "utilizando .env.example como plantilla."
    )

# Configurar argumentos de conexión
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    connect_args = {"connect_timeout": 5}

# Crear motor de conexión
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
