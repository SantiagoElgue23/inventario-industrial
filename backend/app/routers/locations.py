"""Ubicaciones jerárquicas (almacenes, estanterías y áreas)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, selectinload

from .. import models as m
from .. import schemas as s
from ..database import get_db
from ..auth import require_admin
from ..common import (
    commit_or_conflict,
    get_location_or_404,
    location_payload,
    validate_location_parent,
)


router = APIRouter(prefix="/api")

# ============================================================
# UBICACIONES JERÁRQUICAS
# ============================================================


@router.get("/locations", response_model=list[s.LocationOut], tags=["Ubicaciones"])
def list_locations(include_inactive: bool = False, db: Session = Depends(get_db)):
    stmt = select(m.Location).options(
        selectinload(m.Location.parent),
        selectinload(m.Location.children),
    )
    if not include_inactive:
        stmt = stmt.where(m.Location.active.is_(True))
    rows = db.scalars(stmt.order_by(m.Location.parent_id.nullsfirst(), m.Location.name)).all()
    return [location_payload(row) for row in rows]


@router.post("/locations", response_model=s.LocationOut, status_code=201, tags=["Ubicaciones"], dependencies=[Depends(require_admin)])
def create_location(payload: s.LocationCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    validate_location_parent(db, payload.location_type, payload.parent_id)
    duplicate_stmt = select(m.Location).where(
        func.lower(m.Location.name) == name.casefold(),
        m.Location.parent_id.is_(None) if payload.parent_id is None else m.Location.parent_id == payload.parent_id,
    )
    if db.scalar(duplicate_stmt):
        raise HTTPException(status_code=409, detail="Ya existe una ubicación con ese nombre en ese nivel")
    row = m.Location(
        name=name,
        location_type=payload.location_type,
        parent_id=payload.parent_id,
    )
    db.add(row)
    commit_or_conflict(db, "Ya existe una ubicación con ese nombre en ese nivel")
    row = db.scalar(
        select(m.Location).options(selectinload(m.Location.parent), selectinload(m.Location.children)).where(m.Location.id == row.id)
    )
    return location_payload(row)


@router.put("/locations/{location_id}", response_model=s.LocationOut, tags=["Ubicaciones"], dependencies=[Depends(require_admin)])
def update_location(location_id: int, payload: s.LocationUpdate, db: Session = Depends(get_db)):
    row = get_location_or_404(db, location_id)
    fields = payload.model_fields_set
    new_name = payload.name if "name" in fields else row.name
    new_type = payload.location_type if "location_type" in fields else row.location_type
    new_parent_id = payload.parent_id if "parent_id" in fields else row.parent_id
    if not new_name:
        raise HTTPException(status_code=400, detail="El nombre de la ubicación no puede quedar vacío")
    validate_location_parent(db, new_type, new_parent_id, current_location_id=row.id)

    if new_type != "warehouse" and any(child.active for child in row.children):
        raise HTTPException(status_code=409, detail="No se puede cambiar el tipo: la ubicación tiene estanterías activas")
    if new_parent_id is not None:
        parent = db.get(m.Location, new_parent_id)
        if parent is None or parent.id == row.id:
            raise HTTPException(status_code=400, detail="Ubicación superior no válida")

    duplicate_stmt = select(m.Location).where(
        func.lower(m.Location.name) == new_name.casefold(),
        m.Location.id != row.id,
        m.Location.parent_id.is_(None) if new_parent_id is None else m.Location.parent_id == new_parent_id,
    )
    if db.scalar(duplicate_stmt):
        raise HTTPException(status_code=409, detail="Ya existe una ubicación con ese nombre en ese nivel")

    row.name = new_name
    row.location_type = new_type
    row.parent_id = new_parent_id
    commit_or_conflict(db, "No se pudo actualizar la ubicación por un conflicto de nombre")
    row = db.scalar(
        select(m.Location).options(selectinload(m.Location.parent), selectinload(m.Location.children)).where(m.Location.id == location_id)
    )
    return location_payload(row)


@router.delete("/locations/{location_id}", tags=["Ubicaciones"], dependencies=[Depends(require_admin)])
def archive_location(location_id: int, db: Session = Depends(get_db)):
    row = get_location_or_404(db, location_id)
    if any(child.active for child in row.children):
        raise HTTPException(status_code=409, detail="Primero archivá las estanterías o ubicaciones dependientes")
    has_assets = db.scalar(
        select(exists().where(m.Asset.location_id == location_id, m.Asset.active.is_(True)))
    )
    has_stock = db.scalar(
        select(exists().where(m.StockBalance.location_id == location_id, m.StockBalance.quantity > 0))
    )
    work_products_out = db.scalar(select(m.WorkProductLine.id).join(m.Work).where(
        m.WorkProductLine.origin_location_id == location_id,
        m.WorkProductLine.dispatched_at.is_not(None), m.Work.status == "open",
        (m.WorkProductLine.quantity - m.WorkProductLine.returned_quantity
         - m.WorkProductLine.consumed_quantity - m.WorkProductLine.lost_quantity) > 0,
    ).limit(1)) is not None
    work_assets_out = db.scalar(select(m.WorkAssetLine.id).join(m.Work).where(
        m.WorkAssetLine.origin_location_id == location_id,
        m.WorkAssetLine.dispatched_at.is_not(None), m.WorkAssetLine.returned_at.is_(None),
        m.Work.status == "open",
    ).limit(1)) is not None
    if has_assets or has_stock or work_products_out or work_assets_out:
        raise HTTPException(status_code=409, detail="La ubicación contiene recursos o tiene devoluciones pendientes de un trabajo")
    row.active = False
    db.commit()
    return {"message": "Ubicación archivada; se conserva el historial"}


@router.post("/locations/{location_id}/restore", tags=["Ubicaciones"], dependencies=[Depends(require_admin)])
def restore_location(location_id: int, db: Session = Depends(get_db)):
    row = get_location_or_404(db, location_id)
    if row.parent_id is not None:
        parent = db.get(m.Location, row.parent_id)
        if parent is None or not parent.active:
            raise HTTPException(status_code=409, detail="No se puede restaurar: el almacén superior está inactivo")
    row.active = True
    db.commit()
    return {"message": "Ubicación restaurada"}
