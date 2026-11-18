"""Pruebas de permisos con sesión y BD aisladas; no toca PostgreSQL."""
import os
from pathlib import Path
import sys

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timedelta, timezone

from app.database import Base, get_db
from app import auth as authmod
from app import models as m
from app.main import app


@pytest.fixture
def env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        for name in ("master", "admin", "user"):
            db.add(m.AppUser(username=name, role=name, password_hash=authmod.hash_password("SecureTestPassword1234")))
        product = m.Product(name="Controlador de robot", tracking_mode="individual", asset_code_prefix="KRC", unit_value=10000, value_currency="USD")
        project = m.Project(name="Planta Norte", status="planning")
        db.add_all([product, project]);db.flush()
        asset = m.Asset(asset_code="C-KRC-01", product_id=product.id, functional_status="functional", estimated_value=8000, value_currency="USD", observations="Unidad real")
        db.add(asset);db.flush()
        db.add(m.ProjectAsset(asset_id=asset.id, project_id=project.id))
        db.commit()
    def override_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as http:
        yield http, sessions
    app.dependency_overrides.clear()
    engine.dispose()


def as_role(http, role):
    r = http.post('/api/auth/login',json={'username': role,'password':'SecureTestPassword1234'})
    assert r.status_code == 200, r.text


def test_auth_required_and_roles(env):
    http, _ = env
    assert http.get('/api/products').status_code == 401
    as_role(http,'user')
    detail = http.get('/api/products/1').json()
    assert 'unit_value' not in detail
    assert 'estimated_value' not in detail['assets'][0]
    unit = http.get('/api/assets/1').json()
    assert 'estimated_value' not in unit
    assert unit['project_names'] == ['Planta Norte']
    project = http.get('/api/projects/1').json()
    assert 'valuation_by_currency' not in project
    assert http.put('/api/assets/1',json={'estimated_value':1}).status_code==403
    assert http.put('/api/assets/1',json={'functional_status':'damaged'}).status_code==200
    assert http.delete('/api/assets/1').status_code==403
    assert http.post('/api/categories',json={'name':'No permitido'}).status_code==403
    assert http.get('/api/auth/users').status_code==403
    assert http.post('/api/auth/users',json={'username':'intruso','role':'admin','password':'ChangedPassword1234'}).status_code==403

    as_role(http,'admin')
    assert http.get('/api/assets/1').json()['estimated_value'] == '8000.00'
    assert http.get('/api/projects/1').json()['valuation_by_currency']['USD'] == '8000.00'
    assert http.put('/api/assets/1',json={'estimated_value':1}).status_code==403
    assert http.put('/api/assets/1',json={'observations':'Modificado'}).status_code==200
    assert http.post('/api/categories',json={'name':'Permitido'}).status_code==201

    as_role(http,'master')
    assert http.put('/api/assets/1',json={'estimated_value':9000}).status_code==200
    assert http.get('/api/assets/1').json()['estimated_value'] == '9000.00'
    user_id = next(u['id'] for u in http.get('/api/auth/users').json() if u['username'] == 'user')
    assert http.put(f'/api/auth/users/{user_id}/password',json={'password':'NuevaPassword1234'}).status_code==204


def test_master_manages_accounts_but_cannot_grant_master(env):
    http, _ = env
    as_role(http, 'master')
    # Crear una cuenta personal con rol admin.
    created = http.post('/api/auth/users', json={'username': 'ana.perez', 'role': 'admin', 'password': 'AnaPassword12345'})
    assert created.status_code == 201, created.text
    assert created.json()['role'] == 'admin'
    assert http.post('/api/auth/users', json={'username': 'ana.perez', 'role': 'user', 'password': 'AnaPassword12345'}).status_code == 409
    # El rol master no se puede otorgar desde la API, ni al crear ni al editar.
    assert http.post('/api/auth/users', json={'username': 'otro', 'role': 'master', 'password': 'OtroPassword12345'}).status_code == 422
    ana_id = created.json()['id']
    assert http.patch(f'/api/auth/users/{ana_id}', json={'role': 'master'}).status_code == 422
    # Las cuentas master no se administran desde la web.
    master_id = next(u['id'] for u in http.get('/api/auth/users').json() if u['role'] == 'master')
    assert http.patch(f'/api/auth/users/{master_id}', json={'active': False}).status_code == 403
    assert http.put(f'/api/auth/users/{master_id}/password', json={'password': 'Cambiada123456'}).status_code == 403

    # La cuenta nueva inicia sesión con su rol, sin depender del nombre.
    r = http.post('/api/auth/login', json={'username': 'ana.perez', 'password': 'AnaPassword12345'})
    assert r.json() == {'username': 'ana.perez', 'role': 'admin'}
    assert http.post('/api/categories', json={'name': 'Creada por Ana'}).status_code == 201
    assert http.get('/api/auth/users').status_code == 403

    # Desactivarla cierra sus sesiones de inmediato.
    as_role(http, 'master')
    assert http.patch(f'/api/auth/users/{ana_id}', json={'active': False}).json()['active'] is False
    assert http.post('/api/auth/login', json={'username': 'ana.perez', 'password': 'AnaPassword12345'}).status_code == 401


def test_change_own_password(env):
    http, _ = env
    as_role(http, 'user')
    assert http.post('/api/auth/password', json={'current_password': 'incorrecta', 'new_password': 'OtraPassword12345'}).status_code == 400
    assert http.post('/api/auth/password', json={'current_password': 'SecureTestPassword1234', 'new_password': 'OtraPassword12345'}).status_code == 204
    # Las sesiones anteriores quedan cerradas.
    assert http.get('/api/products').status_code == 401
    assert http.post('/api/auth/login', json={'username': 'user', 'password': 'OtraPassword12345'}).status_code == 200


def test_session_inactivity(env):
    http,sessions=env
    as_role(http,'user')
    with sessions() as db:
        row = db.scalar(select(m.AppSession).join(m.AppUser).where(m.AppUser.username=='user'))
        row.expires_at = datetime.now(timezone.utc)-timedelta(minutes=1)
        db.commit()
    assert http.get('/api/products').status_code == 401


def test_optional_pagination(env):
    http, sessions = env
    with sessions() as db:
        db.add_all([m.Product(name=f"Artículo {i:02d}", tracking_mode="quantity") for i in range(5)])
        db.commit()
    as_role(http, 'admin')
    full = http.get('/api/products')
    assert full.status_code == 200 and 'x-total-count' not in full.headers
    page = http.get('/api/products', params={'limit': 2, 'offset': 1})
    assert page.headers['x-total-count'] == str(len(full.json()))
    assert [p['id'] for p in page.json()] == [p['id'] for p in full.json()[1:3]]
    assert http.get('/api/products', params={'limit': 0}).status_code == 422


def test_stock_transfer_registers_user(env):
    http, sessions = env
    with sessions() as db:
        product = m.Product(name="Bornera", tracking_mode="quantity")
        deposito = m.Location(name="Depósito", location_type="warehouse")
        db.add_all([product, deposito]); db.flush()
        a3 = m.Location(name="A3", location_type="shelf", parent_id=deposito.id)
        a4 = m.Location(name="A4", location_type="shelf", parent_id=deposito.id)
        db.add_all([a3, a4]); db.flush()
        db.add_all([
            m.StockBalance(product_id=product.id, location_id=a3.id, quantity=10, verified=True),
            m.StockBalance(product_id=product.id, location_id=a4.id, quantity=0, verified=True),
        ])
        db.commit()
        ids = product.id, a3.id, a4.id
    as_role(http, 'user')
    r = http.post(f'/api/products/{ids[0]}/transfers', json={'source_location_id': ids[1], 'destination_location_id': ids[2], 'quantity': 4})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body['created_by'] == 'user'
    assert float(body['source_quantity_after']) == 6 and float(body['destination_quantity_after']) == 4
    listed = http.get(f'/api/products/{ids[0]}/transfers').json()
    assert listed[0]['created_by'] == 'user'
