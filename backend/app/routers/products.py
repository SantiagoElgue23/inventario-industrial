"""Inventario general de artículos y vista de robots."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from .. import models as m
from .. import schemas as s
from ..database import get_db
from ..auth import CurrentUser, current_user, ensure_can_set_values, require_archive
from ..common import (
    Page,
    fetch_page,
    pagination,
    commit_or_conflict,
    product_load_options,
    get_product_or_404,
    validate_category,
    validate_component_type,
    robot_product_filter,
    product_payload,
    save_attribute_values,
    is_robot_product,
)


router = APIRouter(prefix="/api")

# ============================================================
# INVENTARIO GENERAL / PRODUCTOS
# ============================================================


@router.get("/products", response_model=list[s.ProductOut], tags=["Inventario"])
def list_products(
    response: Response,
    q: str | None = None,
    category_id: int | None = None,
    component_type_id: int | None = None,
    tracking_mode: str | None = Query(default=None, pattern="^(quantity|individual)$"),
    include_inactive: bool = False,
    page: Page = Depends(pagination),
    db: Session = Depends(get_db),
):
    stmt = select(m.Product).options(*product_load_options())
    if not include_inactive:
        stmt = stmt.where(m.Product.active.is_(True))
    if category_id is not None:
        stmt = stmt.where(m.Product.category_id == category_id)
    if component_type_id is not None:
        stmt = stmt.where(m.Product.component_type_id == component_type_id)
    if tracking_mode:
        stmt = stmt.where(m.Product.tracking_mode == tracking_mode)
    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                m.Product.name.ilike(term),
                m.Product.description.ilike(term),
                m.Product.brand.ilike(term),
                m.Product.model.ilike(term),
                m.Product.category.has(m.Category.name.ilike(term)),
                m.Product.component_type.has(m.ComponentType.name.ilike(term)),
            )
        )
    rows = fetch_page(db, stmt.order_by(m.Product.name.nulls_last(), m.Product.id), page, response)
    return [product_payload(row) for row in rows]


@router.post("/products", response_model=s.ProductOut, status_code=201, tags=["Inventario"])
def create_product(payload: s.ProductCreate, db: Session = Depends(get_db), user: CurrentUser = Depends(current_user)):
    ensure_can_set_values(user, payload)
    validate_category(db, payload.category_id)
    validate_component_type(db, payload.component_type_id)
    product = m.Product(
        name=payload.name,
        description=payload.description,
        brand=payload.brand,
        model=payload.model,
        category_id=payload.category_id,
        component_type_id=payload.component_type_id,
        tracking_mode=payload.tracking_mode,
        asset_code_prefix=payload.asset_code_prefix,
        unit_value=payload.unit_value,
        value_currency=payload.value_currency,
    )
    db.add(product)
    db.flush()
    save_attribute_values(db, product, payload.attributes)
    db.commit()
    return product_payload(get_product_or_404(db, product.id))


@router.get("/products/{product_id}", response_model=s.ProductOut, tags=["Inventario"])
def get_product(product_id: int, db: Session = Depends(get_db)):
    return product_payload(get_product_or_404(db, product_id))


@router.put("/products/{product_id}", response_model=s.ProductOut, tags=["Inventario"])
def update_product(product_id: int, payload: s.ProductUpdate, db: Session = Depends(get_db), user: CurrentUser = Depends(current_user)):
    ensure_can_set_values(user, payload)
    product = get_product_or_404(db, product_id)
    fields = payload.model_fields_set
    previous_component_type_id = product.component_type_id

    if "category_id" in fields:
        validate_category(db, payload.category_id)
    if "component_type_id" in fields:
        validate_component_type(db, payload.component_type_id)

    if "tracking_mode" in fields and payload.tracking_mode is None:
        raise HTTPException(status_code=400, detail="El modo de seguimiento no puede quedar vacío")

    new_tracking_mode = (
        payload.tracking_mode if "tracking_mode" in fields else product.tracking_mode
    )
    new_prefix = (
        payload.asset_code_prefix
        if "asset_code_prefix" in fields
        else product.asset_code_prefix
    )

    if new_tracking_mode == "quantity":
        if "asset_code_prefix" in fields and payload.asset_code_prefix is not None:
            raise HTTPException(
                status_code=400,
                detail="Los productos administrados por cantidad no deben tener prefijo de código.",
            )
        new_prefix = None
    elif not new_prefix:
        raise HTTPException(
            status_code=400,
            detail="Los productos de seguimiento individual necesitan un prefijo de código",
        )

    if new_tracking_mode != product.tracking_mode:
        has_assets = db.scalar(
            select(exists().where(m.Asset.product_id == product.id))
        )
        has_balances = db.scalar(
            select(exists().where(m.StockBalance.product_id == product.id))
        )
        has_movements = db.scalar(
            select(exists().where(m.StockMovement.product_id == product.id))
        )
        has_project_assignments = db.scalar(
            select(exists().where(m.ProjectProduct.product_id == product.id))
        )
        if has_assets or has_balances or has_movements or has_project_assignments:
            raise HTTPException(
                status_code=409,
                detail="No se puede cambiar el seguimiento después de registrar activos, existencias, movimientos o asignaciones a proyectos",
            )

    if product.assets and new_prefix != product.asset_code_prefix:
        raise HTTPException(
            status_code=409,
            detail="No se puede cambiar el prefijo de código después de generar activos",
        )

    if "value_currency" in fields and payload.value_currency is None:
        raise HTTPException(status_code=400, detail="La moneda no puede quedar vacía")

    for field in (
        "name",
        "description",
        "brand",
        "model",
        "category_id",
        "component_type_id",
        "unit_value",
        "value_currency",
    ):
        if field in fields:
            setattr(product, field, getattr(payload, field))

    product.tracking_mode = new_tracking_mode
    product.asset_code_prefix = new_prefix

    component_type_changed = (
        "component_type_id" in fields
        and payload.component_type_id != previous_component_type_id
    )
    if "attributes" in fields:
        save_attribute_values(db, product, payload.attributes or [])
    elif component_type_changed:
        # No conservar valores técnicos pertenecientes al tipo anterior.
        save_attribute_values(db, product, [])

    commit_or_conflict(db, "No se pudo actualizar el producto por un conflicto de integridad")
    return product_payload(get_product_or_404(db, product_id))


@router.delete("/products/{product_id}", tags=["Inventario"], dependencies=[Depends(require_archive)])
def archive_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(m.Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    if not product.active:
        return {"message": "El producto ya estaba archivado"}

    active_assets = db.scalar(
        select(
            exists().where(
                m.Asset.product_id == product_id,
                m.Asset.active.is_(True),
                m.Asset.lifecycle_status == "in_stock",
            )
        )
    )
    positive_stock = db.scalar(
        select(exists().where(m.StockBalance.product_id == product_id, m.StockBalance.quantity > 0))
    )
    active_project_assignments = db.scalar(
        select(
            exists().where(
                m.ProjectProduct.product_id == product_id,
                m.ProjectProduct.released_at.is_(None),
            )
        )
    )
    if active_assets or positive_stock or active_project_assignments:
        raise HTTPException(
            status_code=409,
            detail="No se puede archivar: el producto todavía tiene activos, existencias o asignaciones a proyectos vigentes",
        )
    product.active = False
    db.commit()
    return {"message": "Producto archivado; se conservaron sus datos e historial"}


@router.post("/products/{product_id}/restore", tags=["Inventario"], dependencies=[Depends(require_archive)])
def restore_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(m.Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    product.active = True
    db.commit()
    return {"message": "Producto restaurado"}


# ============================================================
# VISTA ESPECIALIZADA DE ROBOTS
# ============================================================


@router.get("/robots", response_model=list[s.ProductOut], tags=["Robots"])
def list_robot_models(
    q: str | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    stmt = select(m.Product).options(*product_load_options()).where(
        m.Product.tracking_mode == "individual",
        robot_product_filter(),
    )
    if not include_inactive:
        stmt = stmt.where(m.Product.active.is_(True))
    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(m.Product.name.ilike(term), m.Product.model.ilike(term), m.Product.brand.ilike(term))
        )
    rows = db.scalars(stmt.order_by(m.Product.name.nulls_last(), m.Product.model.nulls_last())).all()
    return [product_payload(row) for row in rows]


@router.get("/robots/{product_id}", response_model=s.ProductOut, tags=["Robots"])
def get_robot_model(product_id: int, db: Session = Depends(get_db)):
    product = get_product_or_404(db, product_id)
    if product.tracking_mode != "individual" or not is_robot_product(product):
        raise HTTPException(status_code=404, detail="Modelo de robot no encontrado")
    return product_payload(product)
