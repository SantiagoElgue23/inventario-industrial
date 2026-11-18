"""Activos individuales y asociaciones entre activos."""
import unicodedata
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .. import models as m
from .. import schemas as s
from ..database import get_db
from ..auth import CurrentUser, current_user, ensure_can_set_values, require_archive
from ..common import (
    Page,
    fetch_page,
    pagination,
    utcnow,
    commit_or_conflict,
    asset_load_options,
    get_asset_or_404,
    validate_location,
    validate_individual_product,
    validate_asset_product_if_present,
    get_asset_code_prefix,
    asset_payload,
    relationship_payload,
    asset_detail_payload,
    generate_asset_code,
    close_asset_relationships,
    release_asset_from_projects,
)


router = APIRouter(prefix="/api")

# ============================================================
# ACTIVOS INDIVIDUALES
# ============================================================


@router.get("/assets", response_model=list[s.AssetOut], tags=["Activos"])
def list_assets(
    response: Response,
    q: str | None = None,
    product_id: int | None = None,
    functional_status: s.FunctionalStatus | None = None,
    lifecycle_status: s.LifecycleStatus | None = None,
    include_non_stock: bool = False,
    include_archived: bool = False,
    unassigned_only: bool = False,
    available_for_projects: bool = False,
    page: Page = Depends(pagination),
    db: Session = Depends(get_db),
):
    stmt = select(m.Asset).options(*asset_load_options())
    if product_id is not None and unassigned_only:
        raise HTTPException(
            status_code=400,
            detail="No combines product_id con unassigned_only=true",
        )
    if unassigned_only:
        stmt = stmt.where(m.Asset.product_id.is_(None))
    if available_for_projects:
        stmt = stmt.where(~exists(select(m.ProjectAsset.id).where(
            m.ProjectAsset.asset_id == m.Asset.id,
            m.ProjectAsset.released_at.is_(None),
        )), ~exists(select(m.WorkAssetLine.id).join(m.Work).where(
            m.WorkAssetLine.asset_id == m.Asset.id,
            m.WorkAssetLine.dispatched_at.is_not(None),
            m.WorkAssetLine.returned_at.is_(None), m.Work.status == "open",
        )))
    if not include_archived:
        stmt = stmt.where(m.Asset.active.is_(True))
    if product_id is not None:
        stmt = stmt.where(m.Asset.product_id == product_id)
    if functional_status:
        stmt = stmt.where(m.Asset.functional_status == functional_status)
    if lifecycle_status:
        stmt = stmt.where(m.Asset.lifecycle_status == lifecycle_status)
    elif not include_non_stock:
        stmt = stmt.where(m.Asset.lifecycle_status == "in_stock")
    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                m.Asset.asset_code.ilike(term),
                m.Asset.manufacturer_serial.ilike(term),
                m.Asset.manufacturer_brand.ilike(term),
                m.Asset.product.has(m.Product.name.ilike(term)),
                m.Asset.product.has(m.Product.model.ilike(term)),
                m.Asset.product.has(m.Product.brand.ilike(term)),
            )
        )
    rows = fetch_page(db, stmt.order_by(m.Asset.asset_code), page, response)
    return [asset_payload(row) for row in rows]


@router.post("/assets", response_model=s.AssetOut, status_code=201, tags=["Activos"])
def create_asset(payload: s.AssetCreate, db: Session = Depends(get_db), user: CurrentUser = Depends(current_user)):
    ensure_can_set_values(user, payload)
    product = None
    if payload.product_id is not None:
        product = validate_individual_product(db.get(m.Product, payload.product_id))
        prefix = product.asset_code_prefix
        if payload.asset_code_prefix is not None and payload.asset_code_prefix != prefix:
            raise HTTPException(
                status_code=400,
                detail="El prefijo indicado no coincide con el prefijo de código del producto",
            )
    else:
        prefix = payload.asset_code_prefix
        if not prefix:
            raise HTTPException(
                status_code=400,
                detail="Debés indicar un prefijo de código para el activo sin producto asociado",
            )

    validate_location(db, payload.location_id)

    manufacturer_brand = payload.manufacturer_brand or (
        product.brand if product is not None else None
    )
    if payload.manufacturer_serial and not manufacturer_brand:
        raise HTTPException(
            status_code=400,
            detail="Si registrás un número de serie, indicá el fabricante",
        )

    code = generate_asset_code(db, prefix)
    asset = m.Asset(
        product_id=product.id if product is not None else None,
        asset_code=code,
        manufacturer_serial=payload.manufacturer_serial,
        manufacturer_brand=manufacturer_brand,
        functional_status=payload.functional_status,
        lifecycle_status="in_stock",
        observations=payload.observations,
        location_id=payload.location_id,
        estimated_value=payload.estimated_value,
        value_currency=payload.value_currency,
    )
    db.add(asset)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "El número de serie ya existe para ese fabricante "
                "o hubo un conflicto al generar el código interno"
            ),
        ) from exc
    return asset_payload(get_asset_or_404(db, asset.id))


@router.get("/assets/{asset_id}", response_model=s.AssetDetailOut, tags=["Activos"])
def get_asset(asset_id: int, db: Session = Depends(get_db)):
    return asset_detail_payload(get_asset_or_404(db, asset_id))


@router.put("/assets/{asset_id}", response_model=s.AssetOut, tags=["Activos"])
def update_asset(asset_id: int, payload: s.AssetUpdate, db: Session = Depends(get_db), user: CurrentUser = Depends(current_user)):
    ensure_can_set_values(user, payload)
    asset = get_asset_or_404(db, asset_id)
    fields = payload.model_fields_set

    if "product_id" in fields:
        if payload.product_id is None:
            # Desasociar el producto sin borrar el activo ni alterar su código.
            asset.product = None
        else:
            product = validate_individual_product(db.get(m.Product, payload.product_id))
            existing_prefix = get_asset_code_prefix(asset.asset_code)
            if product.asset_code_prefix != existing_prefix:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "El prefijo del producto no coincide con el código interno existente. "
                        "El código interno es permanente y no se modifica."
                    ),
                )
            asset.product = product

    in_work = db.scalar(select(m.WorkAssetLine.id).join(m.Work).where(
        m.WorkAssetLine.asset_id == asset_id, m.WorkAssetLine.dispatched_at.is_not(None),
        m.WorkAssetLine.returned_at.is_(None), m.Work.status == "open",
    ).limit(1)) is not None
    if in_work and "location_id" in fields:
        raise HTTPException(status_code=409, detail="La unidad está fuera en un trabajo; primero registrá su devolución")
    if "location_id" in fields:
        validate_location(db, payload.location_id)
        asset.location_id = payload.location_id

    new_serial = (
        payload.manufacturer_serial
        if "manufacturer_serial" in fields
        else asset.manufacturer_serial
    )
    new_brand = (
        payload.manufacturer_brand
        if "manufacturer_brand" in fields
        else asset.manufacturer_brand
    )
    if new_serial and not new_brand:
        new_brand = asset.product.brand if asset.product is not None else None
    if new_serial and not new_brand:
        raise HTTPException(status_code=400, detail="Un número de serie requiere fabricante")

    if "manufacturer_serial" in fields:
        asset.manufacturer_serial = new_serial
    if "manufacturer_brand" in fields or (new_serial and not asset.manufacturer_brand):
        asset.manufacturer_brand = new_brand

    for field in ("functional_status",):
        if field in fields and getattr(payload, field) is None:
            raise HTTPException(
                status_code=400,
                detail=f"El campo {field} no puede quedar vacío",
            )

    if "value_currency" in fields and payload.value_currency is None:
        raise HTTPException(status_code=400, detail="La moneda no puede quedar vacía")

    for field in (
        "functional_status",
        "observations",
        "estimated_value",
        "value_currency",
    ):
        if field in fields:
            setattr(asset, field, getattr(payload, field))

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="El número de serie ya está registrado para ese fabricante",
        ) from exc
    return asset_payload(get_asset_or_404(db, asset_id))


@router.delete("/assets/{asset_id}", tags=["Activos"], dependencies=[Depends(require_archive)])
def archive_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = get_asset_or_404(db, asset_id)
    if not asset.active:
        return {"message": "El activo ya estaba archivado", "asset_code": asset.asset_code}
    if db.scalar(select(m.WorkAssetLine.id).join(m.Work).where(
        m.WorkAssetLine.asset_id == asset_id, m.WorkAssetLine.dispatched_at.is_not(None),
        m.WorkAssetLine.returned_at.is_(None), m.Work.status == "open",
    ).limit(1)) is not None:
        raise HTTPException(status_code=409, detail="No se puede archivar una unidad que está fuera en un trabajo")
    asset.active = False
    asset.archived_at = utcnow()
    close_asset_relationships(db, asset.id)
    release_asset_from_projects(db, asset.id)
    db.commit()
    return {"message": "Activo archivado; se conservaron su código, datos e historial", "asset_code": asset.asset_code}


@router.post("/assets/{asset_id}/restore", tags=["Activos"], dependencies=[Depends(require_archive)])
def restore_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = get_asset_or_404(db, asset_id)
    if asset.product is not None and not asset.product.active:
        raise HTTPException(
            status_code=409,
            detail="No se puede restaurar: el producto asociado está archivado",
        )
    asset.active = True
    asset.archived_at = None
    db.commit()
    return {"message": "Activo restaurado", "asset_code": asset.asset_code}


# ============================================================
# ASOCIACIONES ENTRE ACTIVOS
# ============================================================


@router.get(
    "/assets/{asset_id}/relationships",
    response_model=list[s.AssetRelationshipOut],
    tags=["Asociaciones"],
)
def list_asset_relationships(asset_id: int, include_history: bool = False, db: Session = Depends(get_db)):
    if db.get(m.Asset, asset_id) is None:
        raise HTTPException(status_code=404, detail="Activo no encontrado")
    stmt = (
        select(m.AssetRelationship)
        .options(
            selectinload(m.AssetRelationship.target_asset).selectinload(m.Asset.product),
            selectinload(m.AssetRelationship.target_asset).selectinload(m.Asset.location),
        )
        .where(m.AssetRelationship.source_asset_id == asset_id)
    )
    if not include_history:
        stmt = stmt.where(m.AssetRelationship.ended_at.is_(None))
    rows = db.scalars(stmt.order_by(m.AssetRelationship.started_at.desc())).all()
    return [relationship_payload(row) for row in rows]


@router.post(
    "/assets/{asset_id}/relationships",
    response_model=s.AssetRelationshipOut,
    status_code=201,
    tags=["Asociaciones"],
)
def create_asset_relationship(asset_id: int, payload: s.AssetRelationshipCreate, db: Session = Depends(get_db)):
    source = get_asset_or_404(db, asset_id)
    target = get_asset_or_404(db, payload.target_asset_id)
    if not source.active or not target.active:
        raise HTTPException(status_code=400, detail="No se pueden asociar activos archivados")
    if source.id == target.id:
        raise HTTPException(status_code=400, detail="Un activo no puede asociarse consigo mismo")
    if source.lifecycle_status != "in_stock" or target.lifecycle_status != "in_stock":
        raise HTTPException(status_code=400, detail="Ambos activos deben estar disponibles")
    validate_asset_product_if_present(source)
    validate_asset_product_if_present(target)

    # Por ahora, esta asociación es exclusivamente robot -> controlador/SmartPad.
    # Las relaciones diferentes requerirán una regla explícita en el futuro.
    def component_kind(asset: m.Asset) -> str:
        name = (
            asset.product.component_type.name
            if asset.product and asset.product.component_type else ""
        )
        return "".join(
            char for char in unicodedata.normalize("NFD", name.casefold())
            if unicodedata.category(char) != "Mn"
        ).strip()

    if component_kind(source) != "robot":
        raise HTTPException(
            status_code=400,
            detail="El equipo principal debe estar clasificado como Robot",
        )
    expected_kind = {"controller": "controlador de robot", "smartpad": "smartpad"}
    if payload.relationship_type not in expected_kind:
        raise HTTPException(
            status_code=400,
            detail="Por ahora solo se permiten controladores y SmartPads como componentes",
        )
    if component_kind(target) != expected_kind[payload.relationship_type]:
        raise HTTPException(
            status_code=400,
            detail="El tipo del componente no coincide con la función elegida",
        )

    existing_role = db.scalar(
        select(m.AssetRelationship).where(
            m.AssetRelationship.source_asset_id == source.id,
            m.AssetRelationship.relationship_type == payload.relationship_type,
            m.AssetRelationship.ended_at.is_(None),
        )
    )
    if existing_role:
        raise HTTPException(status_code=409, detail="El activo principal ya tiene un componente asociado con ese rol")

    existing_parent = db.scalar(
        select(m.AssetRelationship).where(
            m.AssetRelationship.target_asset_id == target.id,
            m.AssetRelationship.ended_at.is_(None),
        )
    )
    if existing_parent:
        raise HTTPException(status_code=409, detail="El componente ya está asociado a otro activo")

    relationship = m.AssetRelationship(
        source_asset_id=source.id,
        target_asset_id=target.id,
        relationship_type=payload.relationship_type,
        note=payload.note,
    )
    db.add(relationship)
    commit_or_conflict(db, "No se pudo crear la asociación porque el componente ya fue asignado")
    relationship = db.scalar(
        select(m.AssetRelationship)
        .options(
            selectinload(m.AssetRelationship.target_asset).selectinload(m.Asset.product),
            selectinload(m.AssetRelationship.target_asset).selectinload(m.Asset.location),
        )
        .where(m.AssetRelationship.id == relationship.id)
    )
    return relationship_payload(relationship)


@router.delete(
    "/assets/{asset_id}/relationships/{relationship_id}",
    response_model=s.AssetRelationshipOut,
    tags=["Asociaciones"],
)
def end_asset_relationship(asset_id: int, relationship_id: int, db: Session = Depends(get_db)):
    relationship = db.scalar(
        select(m.AssetRelationship)
        .options(
            selectinload(m.AssetRelationship.target_asset).selectinload(m.Asset.product),
            selectinload(m.AssetRelationship.target_asset).selectinload(m.Asset.location),
        )
        .where(
            m.AssetRelationship.id == relationship_id,
            m.AssetRelationship.source_asset_id == asset_id,
        )
    )
    if relationship is None:
        raise HTTPException(status_code=404, detail="Asociación no encontrada")
    if relationship.ended_at is None:
        relationship.ended_at = utcnow()
        db.commit()
    return relationship_payload(relationship)
