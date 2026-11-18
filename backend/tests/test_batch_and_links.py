"""Pruebas aisladas en SQLite: no utilizan PostgreSQL operativo."""
import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models as m
from app.database import Base, get_db
from app.main import app
from app import auth as authmod


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(m.AppUser(username="master", role="master", password_hash=authmod.hash_password("MasterTestPassword123")))
        kinds = [m.ComponentType(name=x) for x in ("Robot", "Controlador de robot", "SmartPad")]
        session.add_all(kinds)
        session.flush()
        products = [
            m.Product(name=n, model=n, component_type_id=type_id, tracking_mode="individual", asset_code_prefix=prefix)
            for n, type_id, prefix in (
                ("KR150", kinds[0].id, "KR"), ("KR240", kinds[0].id, "KR2"),
                ("KR C4", kinds[1].id, "KRC"), ("KCP4", kinds[2].id, "SP"),
            )
        ]
        qty_products = [
            m.Product(name="Sensor", tracking_mode="quantity"),
            m.Product(name="Cable", tracking_mode="quantity"),
        ]
        session.add_all(products + qty_products)
        session.flush()
        assets = [
            m.Asset(product_id=product.id, asset_code=f"C-{prefix}-01")
            for product, prefix in zip(products, ("KR", "KR2", "KRC", "SP"))
        ]
        session.add_all(assets)
        session.add(m.Project(name="Planta Norte"))
        session.commit()

    def override_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test:
        assert test.post("/api/auth/login", json={"username":"master", "password":"MasterTestPassword123"}).status_code == 200
        yield test, engine
    app.dependency_overrides.clear()
    engine.dispose()


def test_robot_cannot_be_linked_to_robot(client):
    http, _ = client
    r = http.post("/api/assets/1/relationships", json={"target_asset_id": 2, "relationship_type": "controller"})
    assert r.status_code == 400
    r = http.post("/api/assets/1/relationships", json={"target_asset_id": 3, "relationship_type": "controller"})
    assert r.status_code == 201, r.text
    r = http.post("/api/assets/2/relationships", json={"target_asset_id": 3, "relationship_type": "controller"})
    assert r.status_code == 409
    r = http.post("/api/assets/2/relationships", json={"target_asset_id": 4, "relationship_type": "smartpad"})
    assert r.status_code == 201


def test_batch_assets_is_atomic(client):
    http, engine = client
    ok = http.post("/api/projects/1/assets/batch", json={"asset_ids": [1, 2]})
    assert ok.status_code == 201, ok.text
    assert ok.json()["assigned_count"] == 2
    available = http.get("/api/assets?available_for_projects=true")
    assert available.status_code == 200
    assert {row["id"] for row in available.json()} == {3, 4}
    invalid = http.post("/api/projects/1/assets/batch", json={"asset_ids": [3, 1]})
    assert invalid.status_code == 409
    with Session(engine) as db:
        count = db.scalar(select(func.count()).select_from(m.ProjectAsset))
        assert count == 2, "No deben guardarse asignaciones parciales"
    duplicate = http.post("/api/projects/1/assets/batch", json={"asset_ids": [3, 3]})
    assert duplicate.status_code == 422


def test_batch_products_is_atomic_and_retirement_preserves_history(client):
    http, engine = client
    fail = http.post("/api/projects/1/products/batch", json={"items": [
        {"product_id": 5, "quantity": 2}, {"product_id": 9999, "quantity": 1}
    ]})
    assert fail.status_code == 404
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(m.ProjectProduct)) == 0
    ok = http.post("/api/projects/1/products/batch", json={"items": [
        {"product_id": 5, "quantity": 2}, {"product_id": 6, "quantity": 3}
    ]})
    assert ok.status_code == 201, ok.text
    duplicate = http.post("/api/projects/1/products/batch", json={"items": [
        {"product_id": 6, "quantity": 2}, {"product_id": 6, "quantity": 3}
    ]})
    assert duplicate.status_code == 422
    detail = http.get("/api/projects/1").json()
    id_ = detail["product_assignments"][0]["id"]
    assert http.delete(f"/api/projects/1/products/{id_}").status_code == 200
    detail = http.get("/api/projects/1").json()
    assert len(detail["product_assignments"]) == 2
    assert sum(row["released_at"] is None for row in detail["product_assignments"]) == 1
