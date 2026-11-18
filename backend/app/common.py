"""Utilidades compartidas por los routers: búsquedas, validaciones, paginación y serialización."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, Query, Response
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from . import models as m
from . import schemas as s

# ============================================================
# PAGINACIÓN
# ============================================================

TOTAL_COUNT_HEADER = "X-Total-Count"


@dataclass(frozen=True)
class Page:
    limit: int | None
    offset: int


def pagination(
    limit: int | None = Query(default=None, ge=1, le=500, description="Máximo de registros; sin valor devuelve todos"),
    offset: int = Query(default=0, ge=0, description="Registros a omitir desde el inicio"),
) -> Page:
    return Page(limit=limit, offset=offset)


def fetch_page(db: Session, stmt: Select, page: Page, response: Response) -> list:
    """Ejecuta ``stmt`` (ya ordenado) aplicando la página pedida.

    Sin ``limit`` devuelve todos los registros, como antes de existir la
    paginación. Con ``limit``, el total sin paginar se informa en ``X-Total-Count``.
    """
    if page.limit is None:
        return list(db.scalars(stmt).all())
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    response.headers[TOTAL_COUNT_HEADER] = str(total)
    return list(db.scalars(stmt.limit(page.limit).offset(page.offset)).all())


# ============================================================
# UTILIDADES GENERALES
# ============================================================


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def commit_or_conflict(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=message) from exc


def product_load_options():
    return (
        selectinload(m.Product.category),
        selectinload(m.Product.component_type),
        selectinload(m.Product.balances),
        selectinload(m.Product.source_records),
        selectinload(m.Product.assets).selectinload(m.Asset.location),
        selectinload(m.Product.attribute_values).selectinload(
            m.ProductAttributeValue.definition
        ),
    )


def asset_load_options():
    return (
        selectinload(m.Asset.product).selectinload(m.Product.category),
        selectinload(m.Asset.product).selectinload(m.Product.component_type),
        selectinload(m.Asset.location),
        selectinload(m.Asset.project_assignments).selectinload(m.ProjectAsset.project),
        selectinload(m.Asset.relationships_as_parent)
        .selectinload(m.AssetRelationship.target_asset)
        .selectinload(m.Asset.product),
        selectinload(m.Asset.relationships_as_parent)
        .selectinload(m.AssetRelationship.target_asset)
        .selectinload(m.Asset.location),
    )


def get_product_or_404(db: Session, product_id: int) -> m.Product:
    product = db.scalar(
        select(m.Product)
        .options(*product_load_options())
        .where(m.Product.id == product_id)
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product


def get_asset_or_404(db: Session, asset_id: int) -> m.Asset:
    asset = db.scalar(
        select(m.Asset)
        .options(*asset_load_options())
        .where(m.Asset.id == asset_id)
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Activo no encontrado")
    return asset


def get_project_or_404(db: Session, project_id: int) -> m.Project:
    project = db.scalar(
        select(m.Project)
        .options(
            selectinload(m.Project.asset_assignments)
            .selectinload(m.ProjectAsset.asset)
            .selectinload(m.Asset.product),
            selectinload(m.Project.asset_assignments)
            .selectinload(m.ProjectAsset.asset)
            .selectinload(m.Asset.location),
            selectinload(m.Project.product_assignments)
            .selectinload(m.ProjectProduct.product),
        )
        .where(m.Project.id == project_id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return project


def get_location_or_404(db: Session, location_id: int) -> m.Location:
    location = db.get(m.Location, location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Ubicación no encontrada")
    return location


def validate_category(db: Session, category_id: int | None) -> None:
    if category_id is None:
        return
    category = db.get(m.Category, category_id)
    if category is None or not category.active:
        raise HTTPException(status_code=400, detail="La categoría no existe o está inactiva")


def validate_component_type(db: Session, type_id: int | None) -> None:
    if type_id is None:
        return
    component_type = db.get(m.ComponentType, type_id)
    if component_type is None or not component_type.active:
        raise HTTPException(
            status_code=400,
            detail="El tipo de componente no existe o está inactivo",
        )


def validate_location(db: Session, location_id: int | None) -> None:
    if location_id is None:
        return
    location = db.get(m.Location, location_id)
    if location is None or not location.active:
        raise HTTPException(status_code=400, detail="La ubicación no existe o está inactiva")


def validate_individual_product(product: m.Product | None) -> m.Product:
    if product is None or not product.active:
        raise HTTPException(status_code=404, detail="Producto no encontrado o archivado")
    if product.tracking_mode != "individual":
        raise HTTPException(
            status_code=400,
            detail="El producto no está configurado para seguimiento individual",
        )
    if not product.asset_code_prefix:
        raise HTTPException(
            status_code=400,
            detail="El producto no tiene un prefijo de código configurado",
        )
    return product


def validate_quantity_product(product: m.Product | None) -> m.Product:
    if product is None or not product.active:
        raise HTTPException(status_code=404, detail="Producto no encontrado o archivado")
    if product.tracking_mode != "quantity":
        raise HTTPException(
            status_code=400,
            detail="El producto se administra mediante activos individuales",
        )
    return product


def validate_asset_product_if_present(asset: m.Asset) -> None:
    """Valida el producto únicamente cuando el activo tiene uno asociado."""
    if asset.product_id is not None:
        validate_individual_product(asset.product)


def get_asset_code_prefix(asset_code: str) -> str:
    """Extrae y valida el prefijo de un código interno C-PREFIJO-NÚMERO."""
    parts = asset_code.split("-")
    if (
        len(parts) != 3
        or parts[0] != "C"
        or not (2 <= len(parts[1]) <= 10)
        or not parts[1].isascii()
        or not parts[1].isalnum()
        or not parts[2].isdigit()
    ):
        raise HTTPException(
            status_code=409,
            detail="El código interno del activo no tiene un formato válido.",
        )
    return parts[1]


def robot_product_filter():
    """Filtra modelos de robot sin incluir SmartPads ni equipamiento auxiliar."""
    is_robot_type = m.Product.component_type.has(
        m.ComponentType.name.ilike("robot")
    )
    # Compatibilidad con registros antiguos sin tipo, pero identificados
    # explícitamente como robot/SCARA en el nombre.
    untyped_robot = and_(
        m.Product.component_type_id.is_(None),
        or_(
            m.Product.name.ilike("%robot%"),
            m.Product.name.ilike("%scara%"),
            m.Product.model.ilike("%robot%"),
            m.Product.model.ilike("%scara%"),
        ),
    )
    return or_(is_robot_type, untyped_robot)

# ============================================================
# SERIALIZACIÓN DE RESPUESTAS
# ============================================================


def asset_summary_payload(asset: m.Asset) -> dict:
    product = asset.product
    return {
        "id": asset.id,
        "product_id": asset.product_id,
        "product_name": product.name if product else None,
        "product_brand": product.brand if product else None,
        "product_model": product.model if product else None,
        "asset_code": asset.asset_code,
        "manufacturer_serial": asset.manufacturer_serial,
        "manufacturer_brand": asset.manufacturer_brand,
        "functional_status": asset.functional_status,
        "lifecycle_status": asset.lifecycle_status,
        "observations": asset.observations,
        "project_names": sorted({r.project.name for r in asset.project_assignments if r.released_at is None}),
        "location_id": asset.location_id,
        "location_name": asset.location.name if asset.location else None,
        "estimated_value": asset.estimated_value,
        "value_currency": asset.value_currency,
        "active": asset.active,
    }


def asset_payload(asset: m.Asset) -> dict:
    return {
        **asset_summary_payload(asset),
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
        "archived_at": asset.archived_at,
    }


def relationship_payload(relationship: m.AssetRelationship) -> dict:
    return {
        "id": relationship.id,
        "source_asset_id": relationship.source_asset_id,
        "target_asset_id": relationship.target_asset_id,
        "relationship_type": relationship.relationship_type,
        "started_at": relationship.started_at,
        "ended_at": relationship.ended_at,
        "note": relationship.note,
        "target_asset": asset_summary_payload(relationship.target_asset),
    }


def asset_detail_payload(asset: m.Asset) -> dict:
    history = sorted(
        asset.relationships_as_parent,
        key=lambda row: row.started_at,
        reverse=True,
    )
    return {
        **asset_payload(asset),
        "active_relationships": [
            relationship_payload(row) for row in history if row.ended_at is None
        ],
        "relationship_history": [relationship_payload(row) for row in history],
    }


def product_payload(product: m.Product) -> dict:
    verified_balances = [balance for balance in product.balances if balance.verified]
    stock_verified = bool(verified_balances)
    total_stock = (
        sum((balance.quantity for balance in verified_balances), Decimal("0"))
        if stock_verified
        else None
    )

    attributes = [
        {
            "definition_id": value.attribute_definition_id,
            "name": value.definition.name,
            "value": value.value,
            "unit": value.definition.unit,
        }
        for value in product.attribute_values
        if value.definition.active
        and value.definition.component_type_id == product.component_type_id
    ]

    active_assets = [asset for asset in product.assets if asset.active]
    available_asset_count = sum(
        1 for asset in active_assets if asset.lifecycle_status == "in_stock"
    )

    if product.tracking_mode == "individual":
        total_stock = None
        stock_verified = False

    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "brand": product.brand,
        "model": product.model,
        "category_id": product.category_id,
        "category_name": product.category.name if product.category else None,
        "component_type_id": product.component_type_id,
        "component_type_name": (
            product.component_type.name if product.component_type else None
        ),
        "tracking_mode": product.tracking_mode,
        "asset_code_prefix": product.asset_code_prefix,
        "unit_value": product.unit_value,
        "value_currency": product.value_currency,
        "active": product.active,
        "total_stock": total_stock,
        "stock_verified": stock_verified,
        "source_count": len(product.source_records),
        "search_aliases": sorted({
            record.original_name.strip()
            for record in product.source_records
            if record.original_name and record.original_name.strip()
        }),
        "asset_count": available_asset_count,
        "assets": [
            asset_summary_payload(asset)
            for asset in sorted(active_assets, key=lambda item: item.asset_code)
        ],
        "attributes": attributes,
    }


def location_payload(location: m.Location) -> dict:
    return {
        "id": location.id,
        "name": location.name,
        "location_type": location.location_type,
        "parent_id": location.parent_id,
        "parent_name": location.parent.name if location.parent else None,
        "active": location.active,
        "children_count": sum(1 for child in location.children if child.active),
    }


def project_valuation(project: m.Project) -> tuple[dict[str, Decimal], bool]:
    totals: dict[str, Decimal] = {}
    complete = True

    for assignment in project.asset_assignments:
        if assignment.released_at is not None:
            continue
        asset = assignment.asset
        if asset.estimated_value is not None:
            value = asset.estimated_value
            currency = asset.value_currency
        elif asset.product and asset.product.unit_value is not None:
            value = asset.product.unit_value
            currency = asset.product.value_currency
        else:
            complete = False
            continue
        totals[currency] = totals.get(currency, Decimal("0")) + value

    for assignment in project.product_assignments:
        if assignment.released_at is not None:
            continue
        product = assignment.product
        if product.unit_value is None:
            complete = False
            continue
        totals[product.value_currency] = (
            totals.get(product.value_currency, Decimal("0"))
            + assignment.quantity * product.unit_value
        )

    return totals, complete


def project_payload(project: m.Project, detail: bool = False) -> dict:
    active_assets = [
        row for row in project.asset_assignments if row.released_at is None
    ]
    active_products = [
        row for row in project.product_assignments if row.released_at is None
    ]
    valuation, valuation_complete = project_valuation(project)

    result = {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "start_date": project.start_date,
        "end_date": project.end_date,
        "active": project.active,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "asset_count": len(active_assets),
        "product_count": len(active_products),
        "valuation_by_currency": valuation,
        "valuation_complete": valuation_complete,
    }

    if detail:
        result["asset_assignments"] = [
            {
                "id": row.id,
                "project_id": row.project_id,
                "asset_id": row.asset_id,
                "assigned_at": row.assigned_at,
                "released_at": row.released_at,
                "note": row.note,
                "asset": asset_summary_payload(row.asset),
            }
            for row in sorted(
                project.asset_assignments,
                key=lambda item: item.assigned_at,
                reverse=True,
            )
        ]
        result["product_assignments"] = [
            {
                "id": row.id,
                "project_id": row.project_id,
                "product_id": row.product_id,
                "quantity": row.quantity,
                "assigned_at": row.assigned_at,
                "released_at": row.released_at,
                "note": row.note,
                "product_name": row.product.name,
                "unit_value": row.product.unit_value,
                "value_currency": row.product.value_currency,
            }
            for row in sorted(
                project.product_assignments,
                key=lambda item: item.assigned_at,
                reverse=True,
            )
        ]
    return result


# ============================================================
# CÓDIGOS INTERNOS Y CARACTERÍSTICAS
# ============================================================


def generate_asset_code(db: Session, prefix: str) -> str:
    prefix = prefix.strip().upper()
    if (
        not prefix.isascii()
        or not prefix.isalnum()
        or not 2 <= len(prefix) <= 10
    ):
        raise HTTPException(
            status_code=400,
            detail="El prefijo de código debe tener entre 2 y 10 caracteres alfanuméricos.",
        )
    dialect = db.get_bind().dialect.name
    insert_fn = pg_insert if dialect == "postgresql" else sqlite_insert

    statement = (
        insert_fn(m.AssetCodeSequence)
        .values(prefix=prefix, last_value=1, updated_at=utcnow())
        .on_conflict_do_update(
            index_elements=[m.AssetCodeSequence.prefix],
            set_={
                "last_value": m.AssetCodeSequence.last_value + 1,
                "updated_at": utcnow(),
            },
        )
        .returning(m.AssetCodeSequence.last_value)
    )
    number = db.scalar(statement)
    return f"C-{prefix}-{number:02d}"


def save_attribute_values(
    db: Session,
    product: m.Product,
    values: list[s.AttributeValueIn],
) -> None:
    submitted: dict[int, str] = {}
    for item in values:
        if item.attribute_definition_id in submitted:
            raise HTTPException(
                status_code=400,
                detail="No se puede enviar dos veces la misma característica",
            )
        submitted[item.attribute_definition_id] = item.value.strip()

    definitions: dict[int, m.AttributeDefinition] = {}
    for definition_id in submitted:
        definition = db.get(m.AttributeDefinition, definition_id)
        if definition is None or not definition.active:
            raise HTTPException(
                status_code=400,
                detail=f"La característica {definition_id} no existe o está inactiva",
            )
        if product.component_type_id != definition.component_type_id:
            raise HTTPException(
                status_code=400,
                detail=f"La característica '{definition.name}' no pertenece al tipo de componente del producto",
            )
        definitions[definition_id] = definition

    if product.component_type_id is not None:
        required_definitions = db.scalars(
            select(m.AttributeDefinition).where(
                m.AttributeDefinition.component_type_id == product.component_type_id,
                m.AttributeDefinition.active.is_(True),
                m.AttributeDefinition.required.is_(True),
            )
        ).all()
        missing_required = [
            definition.name
            for definition in required_definitions
            if not submitted.get(definition.id, "").strip()
        ]
        if missing_required:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Faltan características obligatorias: "
                    + ", ".join(missing_required)
                ),
            )

    existing_rows = db.scalars(
        select(m.ProductAttributeValue).where(
            m.ProductAttributeValue.product_id == product.id
        )
    ).all()
    existing_by_definition = {
        row.attribute_definition_id: row for row in existing_rows
    }

    # La lista enviada representa el conjunto completo de características del producto.
    for definition_id, row in existing_by_definition.items():
        if definition_id not in submitted:
            db.delete(row)

    for definition_id, value in submitted.items():
        existing = existing_by_definition.get(definition_id)
        if value == "":
            if existing is not None:
                db.delete(existing)
            continue
        if existing is not None:
            existing.value = value
        else:
            db.add(
                m.ProductAttributeValue(
                    product_id=product.id,
                    attribute_definition_id=definition_id,
                    value=value,
                )
            )


def validate_location_parent(
    db: Session,
    location_type: str,
    parent_id: int | None,
    current_location_id: int | None = None,
) -> None:
    if location_type in {"warehouse", "area"}:
        if parent_id is not None:
            raise HTTPException(
                status_code=400,
                detail="Un almacén o área debe ser una ubicación principal",
            )
        return

    if location_type != "shelf":
        raise HTTPException(status_code=400, detail="Tipo de ubicación no válido")
    if parent_id is None:
        raise HTTPException(
            status_code=400,
            detail="Una estantería debe pertenecer a un almacén",
        )
    if current_location_id is not None and parent_id == current_location_id:
        raise HTTPException(status_code=400, detail="Una ubicación no puede ser su propia madre")

    parent = db.get(m.Location, parent_id)
    if parent is None or not parent.active or parent.location_type != "warehouse":
        raise HTTPException(
            status_code=400,
            detail="La estantería debe pertenecer a un almacén activo",
        )


def close_asset_relationships(db: Session, asset_id: int) -> None:
    relationships = db.scalars(
        select(m.AssetRelationship).where(
            or_(
                m.AssetRelationship.source_asset_id == asset_id,
                m.AssetRelationship.target_asset_id == asset_id,
            ),
            m.AssetRelationship.ended_at.is_(None),
        )
    ).all()
    now = utcnow()
    for relationship in relationships:
        relationship.ended_at = now


def release_asset_from_projects(db: Session, asset_id: int) -> None:
    assignments = db.scalars(
        select(m.ProjectAsset).where(
            m.ProjectAsset.asset_id == asset_id,
            m.ProjectAsset.released_at.is_(None),
        )
    ).all()
    now = utcnow()
    for assignment in assignments:
        assignment.released_at = now


def is_robot_product(product: m.Product) -> bool:
    """Devuelve True solo para modelos clasificados explícitamente como Robot.

    Los SmartPads, controladores, cables y repuestos pueden pertenecer a la
    categoría de equipamiento industrial, pero no son modelos de robot.
    """
    type_name = (
        product.component_type.name.strip().casefold()
        if product.component_type is not None
        else ""
    )
    if type_name == "robot":
        return True
    if type_name:
        return False

    # Compatibilidad con modelos antiguos aún sin tipo asignado.
    values = [
        product.name or "",
        product.model or "",
    ]
    normalized = " ".join(values).casefold()
    return "robot" in normalized or "scara" in normalized

