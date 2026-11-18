"""Autenticación: cuentas personales, sesiones opacas y control de permisos.

El navegador recibe una cookie HttpOnly; solo el hash del identificador se guarda
en la base. Cada ruta protegida declara sus requisitos con dependencias:

- ``current_user``: exige una sesión válida (y Origin propio en métodos que modifican).
- ``require_admin`` / ``require_archive``: roles ``master`` o ``admin``.
- ``require_master``: solo ``master``.
- ``ensure_can_set_values``: los importes solo los registra ``master``.

El rol ``master`` nunca se otorga desde la API: se administra por consola con
``python -m backend.app.auth_bootstrap``.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import models as m
from .database import get_db

COOKIE_NAME = "inv_session"
IDLE_SECONDS = 1800
ITERATIONS = 600_000
ROLES = ("master", "admin", "user")
USERNAME_PATTERN = r"^[a-z0-9._-]{3,32}$"
VALUE_FIELDS = frozenset({"unit_value", "estimated_value", "value_currency"})
SENSITIVE_KEYS = frozenset({
    "unit_value", "estimated_value", "valuation_by_currency", "valuation_complete",
    "material_cost", "loss_cost", "valuation_incomplete", "cost", "total_value",
})

_LOGIN_ATTEMPTS: dict[tuple[str, str], list[float]] = {}
_LOGIN_LOCK = threading.Lock()


# ============================================================
# CONTRASEÑAS, SESIONES Y LÍMITE DE INTENTOS
# ============================================================


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str, salt: bytes | None = None) -> str:
    if len(password) < 12 or len(password.encode()) > 1024:
        raise ValueError("La contraseña debe tener entre 12 y 1024 bytes")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, count, salt, expected = encoded.split("$")
        if algo != "pbkdf2_sha256" or not 100_000 <= int(count) <= 2_000_000:
            return False
        result = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(count))
        return hmac.compare_digest(result, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def session_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME, token, max_age=IDLE_SECONDS, httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax", path="/api",
    )


def limit_login(client_ip: str, username: str) -> tuple[str, str]:
    """Defensa básica local: 10 intentos por cuenta/IP cada 15 minutos.

    En producción se recomienda añadir también rate limiting en el proxy inverso.
    """
    key = (client_ip, username)
    now = time.monotonic()
    with _LOGIN_LOCK:
        attempts = [t for t in _LOGIN_ATTEMPTS.get(key, []) if now - t < 900]
        if len(attempts) >= 10:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Demasiados intentos. Reintentá más tarde")
        attempts.append(now)
        _LOGIN_ATTEMPTS[key] = attempts
    return key


def clear_login(key: tuple[str, str]) -> None:
    with _LOGIN_LOCK:
        _LOGIN_ATTEMPTS.pop(key, None)


def revoke_sessions(db: Session, user_id: int) -> None:
    db.execute(delete(m.AppSession).where(m.AppSession.user_id == user_id))


# ============================================================
# DEPENDENCIAS DE AUTORIZACIÓN
# ============================================================


@dataclass(frozen=True)
class CurrentUser:
    id: int
    username: str
    role: str


def valid_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return request.headers.get("sec-fetch-site") != "cross-site"
    try:
        request_origin = f"{request.url.scheme}://{request.headers['host']}"
        origin_parts, target_parts = urlsplit(origin), urlsplit(request_origin)
        if origin_parts.scheme == target_parts.scheme and origin_parts.netloc == target_parts.netloc:
            return True
    except (ValueError, KeyError):
        pass
    allowed = {v.strip() for v in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")}
    return origin in allowed


def verify_origin(request: Request) -> None:
    """Protección CSRF: las operaciones que modifican datos exigen un Origin propio."""
    if request.method not in ("GET", "HEAD", "OPTIONS") and not valid_origin(request):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Origen no permitido")


def current_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
    """Valida la sesión, renueva su vencimiento y deja el rol en ``request.state``."""
    verify_origin(request)
    token = request.cookies.get(COOKIE_NAME)
    if not token or len(token) > 256:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión requerida")
    db_session = db.scalar(select(m.AppSession).where(m.AppSession.token_hash == session_hash(token)))
    now = utcnow()
    expiry = db_session.expires_at if db_session else None
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if not db_session or expiry <= now or not db_session.user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión expirada")
    user = db_session.user
    if user.role not in ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Rol inválido")
    db_session.expires_at = now + timedelta(seconds=IDLE_SECONDS)
    db.commit()
    # Lo usa finalize_response para renovar la cookie y ocultar importes.
    request.state.session_token = token
    request.state.role = user.role
    return CurrentUser(id=user.id, username=user.username, role=user.role)


def require_roles(*roles: str, detail: str = "Tu cuenta no tiene permiso para esta acción"):
    def dependency(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail)
        return user
    return dependency


require_admin = require_roles("master", "admin", detail="La cuenta user no administra la estructura del inventario")
require_archive = require_roles("master", "admin", detail="La cuenta user no puede archivar o restaurar registros")
require_master = require_roles("master", detail="Solo master administra cuentas")


def ensure_can_set_values(user: CurrentUser, payload: BaseModel) -> None:
    """Solo master registra o modifica importes; se evalúan los campos enviados."""
    if user.role != "master" and VALUE_FIELDS & payload.model_fields_set:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo master puede registrar o modificar valores económicos")


# ============================================================
# POSPROCESO DE RESPUESTAS
# ============================================================


def redact_values(value):
    if isinstance(value, dict):
        return {key: redact_values(v) for key, v in value.items() if key not in SENSITIVE_KEYS}
    if isinstance(value, list):
        return [redact_values(item) for item in value]
    return value


async def finalize_response(request: Request, call_next):
    """Renueva la cookie de sesión y elimina los importes de las respuestas para ``user``."""
    response = await call_next(request)
    token = getattr(request.state, "session_token", None)
    if token is None:
        return response
    if getattr(request.state, "role", None) == "user" and response.headers.get("content-type", "").startswith("application/json"):
        data = b"".join([chunk async for chunk in response.body_iterator])
        try:
            body = json.dumps(redact_values(json.loads(data)), ensure_ascii=False).encode()
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = data
        headers = dict(response.headers)
        headers.pop("content-length", None)
        response = Response(content=body, status_code=response.status_code, headers=headers, media_type="application/json")
    response.headers["Cache-Control"] = "no-store"
    set_cookie(response, token)
    return response


# ============================================================
# ENDPOINTS DE SESIÓN
# ============================================================

AUTH_ROUTER = APIRouter(prefix="/api/auth", tags=["Autenticación"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=1024)


class AccountOut(BaseModel):
    username: str
    role: str


class OwnPasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=1024)


@AUTH_ROUTER.post("/login", response_model=AccountOut, dependencies=[Depends(verify_origin)])
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    username = payload.username.strip().lower()
    key = limit_login(request.client.host if request.client else "unknown", username)
    db.execute(delete(m.AppSession).where(m.AppSession.expires_at < utcnow()))
    user = db.scalar(select(m.AppUser).where(m.AppUser.username == username, m.AppUser.active.is_(True)))
    if user is None or not verify_password(payload.password, user.password_hash):
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos")
    clear_login(key)
    token = secrets.token_urlsafe(48)
    db.add(m.AppSession(user_id=user.id, token_hash=session_hash(token), expires_at=utcnow() + timedelta(seconds=IDLE_SECONDS)))
    db.commit()
    response = JSONResponse({"username": user.username, "role": user.role})
    set_cookie(response, token)
    response.headers["Cache-Control"] = "no-store"
    return response


@AUTH_ROUTER.get("/me", response_model=AccountOut)
def me(user: CurrentUser = Depends(current_user)):
    return {"username": user.username, "role": user.role}


@AUTH_ROUTER.post("/ping", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(current_user)])
def ping():
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@AUTH_ROUTER.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(verify_origin)])
def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.execute(delete(m.AppSession).where(m.AppSession.token_hash == session_hash(token)))
        db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(COOKIE_NAME, path="/api")
    return response


@AUTH_ROUTER.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_own_password(payload: OwnPasswordIn, user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    """Cambio de la propia contraseña; cierra las demás sesiones de la cuenta."""
    account = db.get(m.AppUser, user.id)
    if not verify_password(payload.current_password, account.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña actual no es correcta")
    try:
        account.password_hash = hash_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    revoke_sessions(db, account.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================
# ADMINISTRACIÓN DE CUENTAS (solo master; nunca otorga el rol master)
# ============================================================


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    active: bool


class UserCreate(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN)
    role: Literal["admin", "user"]
    password: str = Field(min_length=12, max_length=1024)


class UserUpdate(BaseModel):
    role: Literal["admin", "user"] | None = None
    active: bool | None = None


class PasswordReset(BaseModel):
    password: str = Field(min_length=12, max_length=1024)


def managed_user_or_404(db: Session, user_id: int) -> m.AppUser:
    account = db.get(m.AppUser, user_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cuenta no encontrada")
    if account.role == "master":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Las cuentas master solo se administran por consola")
    return account


@AUTH_ROUTER.get("/users", response_model=list[UserOut], dependencies=[Depends(require_master)])
def list_users(db: Session = Depends(get_db)):
    return [
        UserOut(id=u.id, username=u.username, role=u.role, active=u.active)
        for u in db.scalars(select(m.AppUser).order_by(m.AppUser.username)).all()
    ]


@AUTH_ROUTER.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_master)])
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    username = payload.username.lower()
    if db.scalar(select(m.AppUser.id).where(m.AppUser.username == username)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese nombre")
    account = m.AppUser(username=username, role=payload.role, password_hash=hash_password(payload.password))
    db.add(account)
    db.commit()
    return UserOut(id=account.id, username=account.username, role=account.role, active=account.active)


@AUTH_ROUTER.patch("/users/{user_id}", response_model=UserOut, dependencies=[Depends(require_master)])
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    account = managed_user_or_404(db, user_id)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(account, field, value)
    if changes:
        # Un cambio de rol o una desactivación debe aplicarse de inmediato.
        revoke_sessions(db, account.id)
    db.commit()
    return UserOut(id=account.id, username=account.username, role=account.role, active=account.active)


@AUTH_ROUTER.put("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_master)])
def reset_user_password(user_id: int, payload: PasswordReset, db: Session = Depends(get_db)):
    account = managed_user_or_404(db, user_id)
    account.password_hash = hash_password(payload.password)
    revoke_sessions(db, account.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
