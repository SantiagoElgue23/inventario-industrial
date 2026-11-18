"""Punto de entrada de la API de Inventario Industrial."""
import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import AUTH_ROUTER, current_user, finalize_response
from .routers import assets, catalog, locations, products, projects, stock, system, works

app = FastAPI(
    title="Inventario Industrial API",
    version="0.4.0",
    description=(
        "API de inventario: catálogo general, activos individuales, "
        "ubicaciones, movimientos, proyectos y trabajos."
    ),
)

origins = [
    value.strip()
    for value in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if value.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)
app.middleware("http")(finalize_response)

app.include_router(AUTH_ROUTER)
app.include_router(system.public_router)
# Todas las rutas de negocio exigen sesión; los permisos por rol se declaran en cada endpoint.
for module in (system, catalog, products, assets, locations, stock, projects, works):
    app.include_router(module.router, dependencies=[Depends(current_user)])
