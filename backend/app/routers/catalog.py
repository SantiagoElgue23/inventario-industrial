"""Catálogo: categorías, tipos de componente y características técnicas."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import models as m
from .. import schemas as s
from ..database import get_db
from ..auth import require_admin
from ..common import (
    commit_or_conflict,
)


router = APIRouter(prefix="/api")

# ============================================================
# CATEGORÍAS
# ============================================================


@router.get("/categories", response_model=list[s.CategoryOut], tags=["Catálogo"])
def list_categories(include_inactive: bool = False, db: Session = Depends(get_db)):
    stmt = select(m.Category).options(selectinload(m.Category.products))
    if not include_inactive:
        stmt = stmt.where(m.Category.active.is_(True))
    rows = db.scalars(stmt.order_by(m.Category.name)).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "active": row.active,
            "product_count": len(row.products),
        }
        for row in rows
    ]


@router.post("/categories", response_model=s.CategoryOut, status_code=201, tags=["Catálogo"], dependencies=[Depends(require_admin)])
def create_category(payload: s.CategoryCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    duplicate = db.scalar(
        select(m.Category).where(func.lower(m.Category.name) == name.casefold())
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Ya existe una categoría con ese nombre")
    row = m.Category(name=name)
    db.add(row)
    commit_or_conflict(db, "Ya existe una categoría con ese nombre")
    db.refresh(row)
    return {"id": row.id, "name": row.name, "active": row.active, "product_count": 0}


@router.put("/categories/{category_id}", response_model=s.CategoryOut, tags=["Catálogo"], dependencies=[Depends(require_admin)])
def update_category(category_id: int, payload: s.CategoryUpdate, db: Session = Depends(get_db)):
    row = db.get(m.Category, category_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    name = payload.name.strip()
    duplicate = db.scalar(
        select(m.Category).where(
            func.lower(m.Category.name) == name.casefold(),
            m.Category.id != category_id,
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Ya existe otra categoría con ese nombre")
    row.name = name
    commit_or_conflict(db, "Ya existe otra categoría con ese nombre")
    db.refresh(row)
    return {
        "id": row.id,
        "name": row.name,
        "active": row.active,
        "product_count": len(row.products),
    }


@router.delete("/categories/{category_id}", tags=["Catálogo"], dependencies=[Depends(require_admin)])
def archive_category(category_id: int, db: Session = Depends(get_db)):
    row = db.get(m.Category, category_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    row.active = False
    db.commit()
    return {"message": "Categoría archivada; los productos conservan su referencia"}


@router.post("/categories/{category_id}/restore", tags=["Catálogo"], dependencies=[Depends(require_admin)])
def restore_category(category_id: int, db: Session = Depends(get_db)):
    row = db.get(m.Category, category_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    row.active = True
    db.commit()
    return {"message": "Categoría restaurada"}


# ============================================================
# TIPOS DE COMPONENTES Y CARACTERÍSTICAS
# ============================================================


@router.get("/component-types", response_model=list[s.ComponentTypeOut], tags=["Catálogo"])
def list_component_types(include_inactive: bool = False, db: Session = Depends(get_db)):
    stmt = select(m.ComponentType).options(selectinload(m.ComponentType.products))
    if not include_inactive:
        stmt = stmt.where(m.ComponentType.active.is_(True))
    rows = db.scalars(stmt.order_by(m.ComponentType.name)).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "active": row.active,
            "product_count": len(row.products),
        }
        for row in rows
    ]


@router.post("/component-types", response_model=s.ComponentTypeOut, status_code=201, tags=["Catálogo"], dependencies=[Depends(require_admin)])
def create_component_type(payload: s.ComponentTypeCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    duplicate = db.scalar(
        select(m.ComponentType).where(func.lower(m.ComponentType.name) == name.casefold())
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Ya existe un tipo de componente con ese nombre")
    row = m.ComponentType(name=name)
    db.add(row)
    commit_or_conflict(db, "Ya existe un tipo de componente con ese nombre")
    db.refresh(row)
    return {"id": row.id, "name": row.name, "active": row.active, "product_count": 0}


@router.put("/component-types/{type_id}", response_model=s.ComponentTypeOut, tags=["Catálogo"], dependencies=[Depends(require_admin)])
def update_component_type(type_id: int, payload: s.ComponentTypeUpdate, db: Session = Depends(get_db)):
    row = db.get(m.ComponentType, type_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tipo de componente no encontrado")
    name = payload.name.strip()
    duplicate = db.scalar(
        select(m.ComponentType).where(
            func.lower(m.ComponentType.name) == name.casefold(),
            m.ComponentType.id != type_id,
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Ya existe otro tipo con ese nombre")
    row.name = name
    commit_or_conflict(db, "Ya existe otro tipo con ese nombre")
    db.refresh(row)
    return {
        "id": row.id,
        "name": row.name,
        "active": row.active,
        "product_count": len(row.products),
    }


@router.delete("/component-types/{type_id}", tags=["Catálogo"], dependencies=[Depends(require_admin)])
def archive_component_type(type_id: int, db: Session = Depends(get_db)):
    row = db.get(m.ComponentType, type_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tipo de componente no encontrado")
    row.active = False
    db.commit()
    return {"message": "Tipo de componente archivado; se conservan sus referencias"}


@router.post("/component-types/{type_id}/restore", tags=["Catálogo"], dependencies=[Depends(require_admin)])
def restore_component_type(type_id: int, db: Session = Depends(get_db)):
    row = db.get(m.ComponentType, type_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tipo de componente no encontrado")
    row.active = True
    db.commit()
    return {"message": "Tipo de componente restaurado"}


@router.get(
    "/component-types/{type_id}/attributes",
    response_model=list[s.AttributeDefinitionOut],
    tags=["Catálogo"],
)
def list_attributes(type_id: int, include_inactive: bool = False, db: Session = Depends(get_db)):
    component_type = db.get(m.ComponentType, type_id)
    if component_type is None:
        raise HTTPException(status_code=404, detail="Tipo de componente no encontrado")
    stmt = select(m.AttributeDefinition).where(
        m.AttributeDefinition.component_type_id == type_id
    )
    if not include_inactive:
        stmt = stmt.where(m.AttributeDefinition.active.is_(True))
    return db.scalars(
        stmt.order_by(m.AttributeDefinition.sort_order, m.AttributeDefinition.name)
    ).all()


@router.post(
    "/component-types/{type_id}/attributes",
    response_model=s.AttributeDefinitionOut,
    status_code=201,
    tags=["Catálogo"],
    dependencies=[Depends(require_admin)],
)
def create_attribute(type_id: int, payload: s.AttributeDefinitionCreate, db: Session = Depends(get_db)):
    component_type = db.get(m.ComponentType, type_id)
    if component_type is None or not component_type.active:
        raise HTTPException(status_code=404, detail="Tipo de componente no encontrado o inactivo")
    duplicate = db.scalar(
        select(m.AttributeDefinition).where(
            m.AttributeDefinition.component_type_id == type_id,
            func.lower(m.AttributeDefinition.name) == payload.name.casefold(),
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Ya existe esa característica para el tipo")
    row = m.AttributeDefinition(
        component_type_id=type_id,
        name=payload.name,
        data_type=payload.data_type,
        unit=payload.unit,
        required=payload.required,
        sort_order=payload.sort_order,
    )
    db.add(row)
    commit_or_conflict(db, "Ya existe esa característica para el tipo")
    db.refresh(row)
    return row


@router.put("/attributes/{attribute_id}", response_model=s.AttributeDefinitionOut, tags=["Catálogo"], dependencies=[Depends(require_admin)])
def update_attribute(attribute_id: int, payload: s.AttributeDefinitionUpdate, db: Session = Depends(get_db)):
    row = db.get(m.AttributeDefinition, attribute_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Característica no encontrada")
    fields = payload.model_fields_set
    for field in ("name", "data_type", "required", "sort_order"):
        if field in fields and getattr(payload, field) is None:
            raise HTTPException(
                status_code=400,
                detail=f"El campo {field} no puede quedar vacío",
            )
    if "name" in fields and payload.name is not None:
        duplicate = db.scalar(
            select(m.AttributeDefinition).where(
                m.AttributeDefinition.component_type_id == row.component_type_id,
                func.lower(m.AttributeDefinition.name) == payload.name.casefold(),
                m.AttributeDefinition.id != attribute_id,
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Ya existe esa característica para el tipo")
    for field in ("name", "data_type", "unit", "required", "sort_order"):
        if field in fields:
            setattr(row, field, getattr(payload, field))
    commit_or_conflict(db, "No se pudo actualizar la característica por un conflicto de datos")
    db.refresh(row)
    return row


@router.delete("/attributes/{attribute_id}", tags=["Catálogo"], dependencies=[Depends(require_admin)])
def archive_attribute(attribute_id: int, db: Session = Depends(get_db)):
    row = db.get(m.AttributeDefinition, attribute_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Característica no encontrada")
    row.active = False
    db.commit()
    return {"message": "Característica archivada"}


@router.post("/attributes/{attribute_id}/restore", tags=["Catálogo"], dependencies=[Depends(require_admin)])
def restore_attribute(attribute_id: int, db: Session = Depends(get_db)):
    row = db.get(m.AttributeDefinition, attribute_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Característica no encontrada")
    row.active = True
    db.commit()
    return {"message": "Característica restaurada"}
