"""Proyectos y asignación de activos y artículos."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from .. import models as m
from .. import schemas as s
from ..database import get_db
from ..auth import require_archive
from ..common import (
    utcnow,
    commit_or_conflict,
    get_asset_or_404,
    get_project_or_404,
    validate_quantity_product,
    validate_asset_product_if_present,
    asset_summary_payload,
    project_payload,
)


router = APIRouter(prefix="/api")

# ============================================================
# PROYECTOS
# ============================================================


@router.get("/projects", response_model=list[s.ProjectOut], tags=["Proyectos"])
def list_projects(
    q: str | None = None,
    status: s.ProjectStatus | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    stmt = select(m.Project).options(
        selectinload(m.Project.asset_assignments).selectinload(m.ProjectAsset.asset).selectinload(m.Asset.product),
        selectinload(m.Project.product_assignments).selectinload(m.ProjectProduct.product),
    )
    if not include_inactive:
        stmt = stmt.where(m.Project.active.is_(True))
    if status:
        stmt = stmt.where(m.Project.status == status)
    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(or_(m.Project.name.ilike(term), m.Project.description.ilike(term)))
    rows = db.scalars(stmt.order_by(m.Project.name)).all()
    return [project_payload(row) for row in rows]


@router.post("/projects", response_model=s.ProjectOut, status_code=201, tags=["Proyectos"])
def create_project(payload: s.ProjectCreate, db: Session = Depends(get_db)):
    project = m.Project(
        name=payload.name,
        description=payload.description,
        status=payload.status,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(project)
    db.commit()
    return project_payload(get_project_or_404(db, project.id))


@router.get("/projects/{project_id}", response_model=s.ProjectDetailOut, tags=["Proyectos"])
def get_project(project_id: int, db: Session = Depends(get_db)):
    return project_payload(get_project_or_404(db, project_id), detail=True)


@router.put("/projects/{project_id}", response_model=s.ProjectOut, tags=["Proyectos"])
def update_project(project_id: int, payload: s.ProjectUpdate, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    fields = payload.model_fields_set
    for field in ("name", "description", "status", "start_date", "end_date"):
        if field in fields:
            value = getattr(payload, field)
            if field in {"name", "status"} and not value:
                raise HTTPException(
                    status_code=400,
                    detail=f"El campo {field} no puede quedar vacío",
                )
            setattr(project, field, value)
    if project.start_date and project.end_date and project.end_date < project.start_date:
        raise HTTPException(status_code=400, detail="La fecha final no puede ser anterior a la inicial")
    commit_or_conflict(db, "No se pudo actualizar el proyecto")
    return project_payload(get_project_or_404(db, project_id))


@router.delete("/projects/{project_id}", tags=["Proyectos"], dependencies=[Depends(require_archive)])
def archive_project(project_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    if not project.active:
        return {"message": "El proyecto ya estaba archivado"}
    if db.scalar(select(m.Work.id).where(m.Work.project_id == project_id, m.Work.status != "closed").limit(1)) is not None:
        raise HTTPException(status_code=409, detail="Hay trabajos sin cerrar; cerralos antes de archivar el proyecto")
    now = utcnow()
    for assignment in project.asset_assignments:
        if assignment.released_at is None:
            assignment.released_at = now
    for assignment in project.product_assignments:
        if assignment.released_at is None:
            assignment.released_at = now
    project.active = False
    db.commit()
    return {"message": "Proyecto archivado; se conservaron sus asignaciones e historial"}


@router.post("/projects/{project_id}/restore", tags=["Proyectos"], dependencies=[Depends(require_archive)])
def restore_project(project_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    project.active = True
    db.commit()
    return {"message": "Proyecto restaurado"}


@router.post(
    "/projects/{project_id}/assets",
    response_model=s.ProjectAssetAssignmentOut,
    status_code=201,
    tags=["Proyectos"],
)
def assign_asset_to_project(project_id: int, payload: s.ProjectAssetAssign, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    if not project.active or project.status in {"completed", "cancelled"}:
        raise HTTPException(status_code=409, detail="No se pueden asignar recursos a un proyecto archivado, finalizado o cancelado")
    asset = get_asset_or_404(db, payload.asset_id)
    if not asset.active or asset.lifecycle_status != "in_stock":
        raise HTTPException(status_code=409, detail="El activo no está disponible")
    if db.scalar(select(m.WorkAssetLine.id).join(m.Work).where(
        m.WorkAssetLine.asset_id == asset.id, m.WorkAssetLine.dispatched_at.is_not(None),
        m.WorkAssetLine.returned_at.is_(None), m.Work.status == "open",
    ).limit(1)) is not None:
        raise HTTPException(status_code=409, detail="El activo está fuera en un trabajo")
    validate_asset_product_if_present(asset)
    assigned_elsewhere = db.scalar(
        select(m.ProjectAsset).where(
            m.ProjectAsset.asset_id == asset.id,
            m.ProjectAsset.released_at.is_(None),
        )
    )
    if assigned_elsewhere:
        raise HTTPException(status_code=409, detail="El activo ya está asignado a un proyecto")
    assignment = m.ProjectAsset(project_id=project.id, asset_id=asset.id, note=payload.note)
    db.add(assignment)
    commit_or_conflict(db, "El activo ya está asignado a un proyecto")
    return {
        "id": assignment.id,
        "project_id": assignment.project_id,
        "asset_id": assignment.asset_id,
        "assigned_at": assignment.assigned_at,
        "released_at": assignment.released_at,
        "note": assignment.note,
        "asset": asset_summary_payload(get_asset_or_404(db, asset.id)),
    }


@router.post(
    "/projects/{project_id}/assets/batch",
    status_code=201,
    tags=["Proyectos"],
)
def assign_project_assets_batch(
    project_id: int,
    payload: s.ProjectAssetsBatch,
    db: Session = Depends(get_db),
):
    """Asigna múltiples activos en una sola transacción, o ninguno."""
    project = get_project_or_404(db, project_id)
    if not project.active or project.status in {"completed", "cancelled"}:
        raise HTTPException(status_code=409, detail="El proyecto no admite asignaciones")

    ids = payload.asset_ids
    assets = db.scalars(
        select(m.Asset)
        .options(selectinload(m.Asset.product))
        .where(m.Asset.id.in_(ids))
        .with_for_update()
    ).all()
    if len(assets) != len(ids):
        raise HTTPException(status_code=404, detail="Uno o más activos no existen")
    for asset in assets:
        if not asset.active or asset.lifecycle_status != "in_stock":
            raise HTTPException(status_code=409, detail=f"El activo {asset.asset_code} no está disponible")
        validate_asset_product_if_present(asset)

    busy_in_work = db.scalar(select(m.WorkAssetLine.asset_id).join(m.Work).where(
        m.WorkAssetLine.asset_id.in_(ids), m.WorkAssetLine.dispatched_at.is_not(None),
        m.WorkAssetLine.returned_at.is_(None), m.Work.status == "open",
    ).limit(1))
    if busy_in_work is not None:
        raise HTTPException(status_code=409, detail="Una unidad está fuera en un trabajo")
    occupied = db.scalar(
        select(m.ProjectAsset.asset_id).where(
            m.ProjectAsset.asset_id.in_(ids),
            m.ProjectAsset.released_at.is_(None),
        ).limit(1)
    )
    if occupied is not None:
        raise HTTPException(status_code=409, detail="Al menos un activo ya está asignado a un proyecto")

    db.add_all([m.ProjectAsset(project_id=project.id, asset_id=asset_id) for asset_id in ids])
    commit_or_conflict(db, "No se pudo completar la asignación múltiple de activos")
    return {"assigned_count": len(ids)}


@router.delete("/projects/{project_id}/assets/{assignment_id}", tags=["Proyectos"])
def release_project_asset(project_id: int, assignment_id: int, db: Session = Depends(get_db)):
    assignment = db.scalar(
        select(m.ProjectAsset).where(
            m.ProjectAsset.id == assignment_id,
            m.ProjectAsset.project_id == project_id,
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="Asignación de activo no encontrada")
    if assignment.released_at is None:
        assignment.released_at = utcnow()
        db.commit()
    return {"message": "Activo liberado del proyecto", "assignment_id": assignment.id}


@router.post(
    "/projects/{project_id}/products",
    response_model=s.ProjectProductAssignmentOut,
    status_code=201,
    tags=["Proyectos"],
)
def assign_product_to_project(project_id: int, payload: s.ProjectProductAssign, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    if not project.active or project.status in {"completed", "cancelled"}:
        raise HTTPException(status_code=409, detail="No se pueden asignar recursos a un proyecto archivado, finalizado o cancelado")
    product = validate_quantity_product(db.get(m.Product, payload.product_id))
    assignment = m.ProjectProduct(
        project_id=project.id,
        product_id=product.id,
        quantity=payload.quantity,
        note=payload.note,
    )
    db.add(assignment)
    commit_or_conflict(db, "Este producto ya tiene una asignación vigente en el proyecto")
    return {
        "id": assignment.id,
        "project_id": assignment.project_id,
        "product_id": assignment.product_id,
        "quantity": assignment.quantity,
        "assigned_at": assignment.assigned_at,
        "released_at": assignment.released_at,
        "note": assignment.note,
        "product_name": product.name,
        "unit_value": product.unit_value,
        "value_currency": product.value_currency,
    }


@router.post(
    "/projects/{project_id}/products/batch",
    status_code=201,
    tags=["Proyectos"],
)
def assign_project_products_batch(
    project_id: int,
    payload: s.ProjectProductsBatch,
    db: Session = Depends(get_db),
):
    """Valida todos los artículos y confirma todas las asignaciones juntas."""
    project = get_project_or_404(db, project_id)
    if not project.active or project.status in {"completed", "cancelled"}:
        raise HTTPException(status_code=409, detail="El proyecto no admite asignaciones")

    ids = [item.product_id for item in payload.items]
    products = db.scalars(select(m.Product).where(m.Product.id.in_(ids))).all()
    if len(products) != len(ids):
        raise HTTPException(status_code=404, detail="Uno o más artículos no existen")
    for product in products:
        validate_quantity_product(product)

    already_assigned = db.scalar(
        select(m.ProjectProduct.product_id).where(
            m.ProjectProduct.project_id == project.id,
            m.ProjectProduct.product_id.in_(ids),
            m.ProjectProduct.released_at.is_(None),
        ).limit(1)
    )
    if already_assigned is not None:
        raise HTTPException(status_code=409, detail="Un artículo ya tiene una asignación vigente en el proyecto")

    db.add_all([
        m.ProjectProduct(project_id=project.id, product_id=item.product_id, quantity=item.quantity)
        for item in payload.items
    ])
    commit_or_conflict(db, "No se pudo completar la asignación múltiple de artículos")
    return {"assigned_count": len(ids)}


@router.delete("/projects/{project_id}/products/{assignment_id}", tags=["Proyectos"])
def release_project_product(project_id: int, assignment_id: int, db: Session = Depends(get_db)):
    assignment = db.scalar(
        select(m.ProjectProduct).where(
            m.ProjectProduct.id == assignment_id,
            m.ProjectProduct.project_id == project_id,
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="Asignación de producto no encontrada")
    if assignment.released_at is None:
        assignment.released_at = utcnow()
        db.commit()
    return {"message": "Producto liberado del proyecto", "assignment_id": assignment.id}
