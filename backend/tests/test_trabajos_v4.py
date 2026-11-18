"""Pruebas aisladas sin conectarse a PostgreSQL productivo."""
import os
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app import models as m
from app.main import app
from app import auth as authmod


def setup():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        db.add(m.AppUser(username="master",role="master",password_hash=authmod.hash_password("MasterTestPassword123")))
        project = m.Project(name="Planta Norte", status="planning")
        sensor = m.Product(name="Sensor PNP", tracking_mode="quantity", unit_value=Decimal("50000"), value_currency="PYG")
        motor = m.Product(name="Motor de robot", tracking_mode="individual", asset_code_prefix="KR", value_currency="PYG")
        warehouse = m.Location(name="Almacen A", location_type="warehouse")
        db.add_all([project,sensor,motor,warehouse]);db.flush()
        balance = m.StockBalance(product_id=sensor.id, location_id=warehouse.id, quantity=Decimal("10"), verified=True)
        asset = m.Asset(product_id=motor.id, asset_code="C-KR-01", location_id=warehouse.id)
        db.add_all([balance,asset]);db.commit()
        ids = project.id,sensor.id,asset.id,warehouse.id
    def override():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override
    http = TestClient(app)
    assert http.post("/api/auth/login",json={"username":"master", "password":"MasterTestPassword123"}).status_code == 200
    return http, sessions, engine, ids


def test_work_lifecycle_pdf_and_inventory():
    client,sessions,engine,(project_id,product_id,asset_id,location_id)=setup()
    try:
        r=client.post(f"/api/projects/{project_id}/works",json={"name":"Mantenimiento", "responsible":"Técnico A"})
        assert r.status_code==201,r.text
        wid=r.json()["id"]
        r=client.post(f"/api/works/{wid}/prepare",json={"products":[{"product_id":product_id,"origin_location_id":location_id,"quantity":4}],"asset_ids":[asset_id]})
        assert r.status_code==200,r.text
        assert r.json()["status"]=="draft"
        with sessions() as db:
            assert db.scalar(select(m.StockBalance.quantity)) == Decimal("10")
        r=client.post(f"/api/works/{wid}/dispatch")
        assert r.status_code==200,r.text
        assert r.json()["status"]=="open"
        assert len(r.json()["assets"])==1
        with sessions() as db:
            assert db.scalar(select(m.StockBalance.quantity)) == Decimal("6")
            assert db.get(m.Asset,asset_id).location_id is None
        r=client.get("/api/work-stock-summary")
        assert r.status_code==200,r.text
        assert float(r.json()["products"][str(product_id)])==4
        assert r.json()["assets"][str(2)]==1
        pdf=client.get(f"/api/works/{wid}/pdf/out")
        assert pdf.status_code==200,pdf.text[:60] if pdf.status_code!=200 else ''
        assert pdf.content[:4]==b"%PDF"
        r=client.post(f"/api/works/{wid}/returns",json={"products":[{"line_id":client.get(f'/api/works/{wid}').json()['products'][0]['id'],"quantity":3}], "asset_line_ids":[client.get(f'/api/works/{wid}').json()['assets'][0]['id']]})
        assert r.status_code==200,r.text
        with sessions() as db:
            assert db.scalar(select(m.StockBalance.quantity)) == Decimal("9")
            assert db.get(m.Asset,asset_id).location_id==location_id
        r=client.post(f"/api/works/{wid}/close",json={"confirm":True,"remaining_as":"consumed","note":"Se utilizó un sensor"})
        assert r.status_code==200,r.text
        assert r.json()["status"]=="closed"
        assert float(r.json()["material_cost"]["PYG"])==50000
        # Auditoría: cada etapa registra la cuenta que la realizó.
        work = r.json()
        assert work["created_by"] == "master" and work["closed_by"] == "master"
        assert work["products"][0]["dispatched_by"] == "master"
        assert work["assets"][0]["dispatched_by"] == "master"
        movements = client.get(f"/api/products/{product_id}/movements").json()
        assert movements and all(mv["created_by"] == "master" for mv in movements)
        with sessions() as db:
            assert db.scalar(select(m.WorkReturnEvent.created_by_id).limit(1)) is not None
        assert client.get('/api/work-stock-summary').json()['products']=={}
        pdf=client.get(f"/api/works/{wid}/pdf/return")
        assert pdf.status_code==200
        assert pdf.content.startswith(b"%PDF")
    finally:
        app.dependency_overrides.clear();engine.dispose()


def test_overspend_is_rejected_atomically():
    client,sessions,engine,(project_id,product_id,asset_id,location_id)=setup()
    try:
        wid=client.post(f"/api/projects/{project_id}/works",json={"name":"Otra prueba"}).json()['id']
        r=client.post(f"/api/works/{wid}/prepare",json={"products":[{"product_id":product_id,"origin_location_id":location_id,"quantity":11}],"asset_ids":[asset_id]})
        assert r.status_code==200,r.text
        r=client.post(f"/api/works/{wid}/dispatch")
        assert r.status_code==409
        with sessions() as db:
            assert db.scalar(select(m.StockBalance.quantity))==Decimal("10")
            assert db.get(m.Asset,asset_id).location_id==location_id
            assert db.scalar(select(m.StockMovement.id)) is None
    finally:
        app.dependency_overrides.clear();engine.dispose()


def test_draft_can_be_edited_and_close_requires_return_of_assets():
    client,sessions,engine,(project_id,product_id,asset_id,location_id)=setup()
    try:
        wid=client.post(f"/api/projects/{project_id}/works",json={"name":"Control"}).json()['id']
        detail=client.post(f"/api/works/{wid}/prepare",json={"products":[],"asset_ids":[asset_id]}).json()
        line_id=detail['assets'][0]['id']
        r=client.delete(f"/api/works/{wid}/prepared/asset/{line_id}")
        assert r.status_code==200,r.text
        assert not r.json()['assets']
        detail=client.post(f"/api/works/{wid}/prepare",json={"products":[],"asset_ids":[asset_id]}).json()
        assert client.post(f"/api/works/{wid}/dispatch").status_code==200
        assert client.post(f"/api/works/{wid}/close",json={"confirm":True}).status_code==409
        assert client.delete(f"/api/projects/{project_id}").status_code==409
        assert client.delete(f"/api/assets/{asset_id}").status_code==409
    finally:
        app.dependency_overrides.clear();engine.dispose()
