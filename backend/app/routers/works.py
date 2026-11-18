"""Trabajos de Proyectos.

Salida temporal: el stock físico se reduce y queda asociado al trabajo.
Devolución: el stock físico aumenta por la cantidad efectivamente recibida.
Cierre: el remanente se clasifica expresamente como consumido o perdido.
No modifica ni confunde las asignaciones administrativas de Proyecto.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import decimal_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, PlainSerializer, model_validator
from sqlalchemy import and_, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from .. import models as m
from ..auth import CurrentUser, current_user

router = APIRouter(prefix="/api", tags=["Trabajos"])
ZERO = Decimal("0")


def now():
    return datetime.now(timezone.utc)


class WorkCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    description: str | None = None
    responsible: str | None = Field(default=None, max_length=120)
    planned_out_date: date | None = None
    planned_return_date: date | None = None

    @model_validator(mode="after")
    def dates(self):
        if self.planned_out_date and self.planned_return_date and self.planned_return_date < self.planned_out_date:
            raise ValueError("La devolución prevista no puede ser anterior a la salida")
        return self


class ProductToPrepare(BaseModel):
    product_id: int = Field(gt=0)
    origin_location_id: int | None = Field(default=None, gt=0)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class WorkPrepare(BaseModel):
    products: list[ProductToPrepare] = Field(default_factory=list, max_length=100)
    asset_ids: list[int] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_items(self):
        if not self.products and not self.asset_ids:
            raise ValueError("Seleccioná al menos un artículo o una unidad física")
        if len(set(self.asset_ids)) != len(self.asset_ids) or any(x <= 0 for x in self.asset_ids):
            raise ValueError("Las unidades físicas no pueden repetirse")
        return self


class ProductReturn(BaseModel):
    line_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class WorkReturn(BaseModel):
    products: list[ProductReturn] = Field(default_factory=list, max_length=100)
    asset_line_ids: list[int] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique(self):
        ids = [r.line_id for r in self.products]
        if len(ids) != len(set(ids)) or len(self.asset_line_ids) != len(set(self.asset_line_ids)):
            raise ValueError("No repitas una misma línea en la devolución")
        if not ids and not self.asset_line_ids:
            raise ValueError("No se seleccionó ninguna devolución")
        return self


class WorkCloseLine(BaseModel):
    line_id: int = Field(gt=0)
    remaining_as: Literal["consumed", "lost"]


class WorkClose(BaseModel):
    confirm: bool
    remaining_as: Literal["consumed", "lost"] = "consumed"
    decisions: list[WorkCloseLine] = Field(default_factory=list)
    note: str | None = None

    @model_validator(mode="after")
    def validate_decisions(self):
        ids = [line.line_id for line in self.decisions]
        if len(ids) != len(set(ids)):
            raise ValueError("No repitas líneas en la conciliación")
        return self


# ============================================================
# MODELOS DE RESPUESTA
# ============================================================

# Las cantidades de Trabajos se envían como número JSON (no como texto),
# igual que antes de declarar los modelos, para no cambiar el contrato del frontend.
JsonNumber = Annotated[Decimal, PlainSerializer(decimal_encoder, when_used="json")]


class MessageOut(BaseModel):
    message: str


class WorkSummaryOut(BaseModel):
    id: int
    project_id: int
    name: str
    description: str | None
    responsible: str | None
    planned_out_date: date | None
    planned_return_date: date | None
    status: str
    created_at: datetime
    departed_at: datetime | None
    closed_at: datetime | None
    close_note: str | None
    created_by: str | None = None
    closed_by: str | None = None


class WorkProductLineOut(BaseModel):
    id: int
    product_id: int
    origin_location_id: int | None
    name: str
    location: str
    quantity: JsonNumber
    returned: JsonNumber
    consumed: JsonNumber
    lost: JsonNumber
    pending: JsonNumber
    dispatched_at: datetime | None
    dispatched_by: str | None = None
    unit_value: JsonNumber | None
    currency: str


class WorkAssetLineOut(BaseModel):
    id: int
    asset_id: int
    name: str
    asset_code: str
    serial: str | None
    dispatched_at: datetime | None
    dispatched_by: str | None = None
    returned_at: datetime | None


class WorkOut(WorkSummaryOut):
    products: list[WorkProductLineOut]
    assets: list[WorkAssetLineOut]
    material_cost: dict[str, JsonNumber]
    loss_cost: dict[str, JsonNumber]
    valuation_incomplete: bool


class WorkAssetOptionOut(BaseModel):
    id: int
    asset_code: str
    name: str
    serial: str | None


class WorkStockSummaryOut(BaseModel):
    products: dict[str, JsonNumber]
    assets: dict[str, int]


def work_or_404(db: Session, work_id: int, lock: bool = False):
    q = select(m.Work).where(m.Work.id == work_id)
    if lock:
        q = q.with_for_update()
    work = db.scalar(q)
    if work is None:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    # Las colecciones se consultan explícitamente para reflejar los cambios recientes.
    return work


def lines(db, work_id):
    products = db.scalars(select(m.WorkProductLine).where(m.WorkProductLine.work_id == work_id).order_by(m.WorkProductLine.id)).all()
    assets = db.scalars(select(m.WorkAssetLine).where(m.WorkAssetLine.work_id == work_id).order_by(m.WorkAssetLine.id)).all()
    return products, assets


def work_view(db: Session, work: m.Work, include_lines: bool = True):
    out = {
        "id": work.id, "project_id": work.project_id, "name": work.name,
        "description": work.description, "responsible": work.responsible,
        "planned_out_date": work.planned_out_date,
        "planned_return_date": work.planned_return_date,
        "status": work.status, "created_at": work.created_at,
        "departed_at": work.departed_at, "closed_at": work.closed_at,
        "close_note": work.close_note,
        "created_by": m.username_of(work.created_by_user),
        "closed_by": m.username_of(work.closed_by_user),
    }
    if not include_lines:
        return out
    p_lines, a_lines = lines(db, work.id)
    out["products"] = [
        {
            "id": line.id, "product_id": line.product_id, "origin_location_id": line.origin_location_id,
            "name": line.product_name_snapshot, "location": line.location_name_snapshot,
            "quantity": line.quantity, "returned": line.returned_quantity,
            "consumed": line.consumed_quantity, "lost": line.lost_quantity,
            "pending": (line.quantity - line.returned_quantity - line.consumed_quantity - line.lost_quantity) if line.dispatched_at else ZERO,
            "dispatched_at": line.dispatched_at, "dispatched_by": m.username_of(line.dispatched_by_user),
            "unit_value": line.unit_value_snapshot,
            "currency": line.value_currency_snapshot,
        }
        for line in p_lines
    ]
    out["assets"] = [
        {
            "id": line.id, "asset_id": line.asset_id,
            "name": line.asset_name_snapshot, "asset_code": line.asset_code_snapshot,
            "serial": line.serial_snapshot, "dispatched_at": line.dispatched_at,
            "dispatched_by": m.username_of(line.dispatched_by_user),
            "returned_at": line.returned_at,
        }
        for line in a_lines
    ]
    cost = {}
    unknown = False
    lost_cost = {}
    for line in p_lines:
        if line.consumed_quantity or line.lost_quantity:
            if line.unit_value_snapshot is None:
                unknown = True
            else:
                currency = line.value_currency_snapshot
                cost[currency] = cost.get(currency, ZERO) + line.consumed_quantity * line.unit_value_snapshot
                lost_cost[currency] = lost_cost.get(currency, ZERO) + line.lost_quantity * line.unit_value_snapshot
    out["material_cost"] = cost
    out["loss_cost"] = lost_cost
    out["valuation_incomplete"] = unknown
    return out


@router.get("/projects/{project_id}/works", response_model=list[WorkSummaryOut])
def list_project_works(project_id: int, db: Session = Depends(get_db)):
    if db.get(m.Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    rows = db.scalars(select(m.Work).where(m.Work.project_id == project_id).order_by(m.Work.created_at.desc(), m.Work.id.desc())).all()
    return [work_view(db, row, include_lines=False) for row in rows]


@router.post("/projects/{project_id}/works", response_model=WorkOut, status_code=201)
def create_work(project_id: int, payload: WorkCreate, db: Session = Depends(get_db), user: CurrentUser = Depends(current_user)):
    project = db.get(m.Project, project_id)
    if not project or not project.active or project.status in {"completed", "cancelled"}:
        raise HTTPException(status_code=409, detail="El proyecto no admite nuevos trabajos")
    work = m.Work(project_id=project_id, created_by_id=user.id, **payload.model_dump())
    db.add(work)
    db.commit()
    return work_view(db, work)


@router.get("/projects/{project_id}/work-assets", response_model=list[WorkAssetOptionOut])
def available_work_assets(project_id: int, db: Session = Depends(get_db)):
    if db.get(m.Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    occupied = exists(select(m.WorkAssetLine.id).where(
        m.WorkAssetLine.asset_id == m.Asset.id,
        m.WorkAssetLine.returned_at.is_(None),
    ))
    assigned_elsewhere = exists(select(m.ProjectAsset.id).where(
        m.ProjectAsset.asset_id == m.Asset.id,
        m.ProjectAsset.released_at.is_(None),
        m.ProjectAsset.project_id != project_id,
    ))
    rows = db.scalars(select(m.Asset).options(selectinload(m.Asset.product))
        .where(m.Asset.active.is_(True), m.Asset.lifecycle_status == "in_stock",
               ~occupied, ~assigned_elsewhere)
        .order_by(m.Asset.asset_code)).all()
    return [{"id": a.id, "asset_code": a.asset_code,
             "name": a.product.name if a.product else "Unidad sin artículo",
             "serial": a.manufacturer_serial} for a in rows]


@router.delete("/works/{work_id}", response_model=MessageOut)
def delete_work_draft(work_id: int, db: Session = Depends(get_db)):
    work = work_or_404(db, work_id, lock=True)
    if work.status != "draft":
        raise HTTPException(status_code=409, detail="Solo se pueden eliminar borradores sin salidas registradas")
    product_lines, asset_lines = lines(db, work.id)
    if any(line.dispatched_at for line in product_lines + asset_lines):
        raise HTTPException(status_code=409, detail="Hay salidas registradas; no se puede eliminar el trabajo")
    for line in product_lines + asset_lines:
        db.delete(line)
    db.delete(work)
    db.commit()
    return {"message": "Borrador eliminado"}


@router.get("/works/{work_id}", response_model=WorkOut)
def get_work(work_id: int, db: Session = Depends(get_db)):
    return work_view(db, work_or_404(db, work_id))


@router.post("/works/{work_id}/prepare", response_model=WorkOut)
def prepare_work(work_id: int, payload: WorkPrepare, db: Session = Depends(get_db)):
    work = work_or_404(db, work_id, lock=True)
    if work.status == "closed":
        raise HTTPException(status_code=409, detail="El trabajo ya está cerrado")
    project = db.get(m.Project, work.project_id)
    if not project or not project.active or project.status in {"completed", "cancelled"}:
        raise HTTPException(status_code=409, detail="El proyecto no admite nuevas salidas")
    # Validamos todo antes de insertar. La reserva de stock ocurre sólo al despachar.
    for item in payload.products:
        product = db.get(m.Product, item.product_id)
        if not product or not product.active or product.tracking_mode != "quantity":
            raise HTTPException(status_code=400, detail=f"Artículo #{item.product_id} no disponible por cantidad")
        location = db.get(m.Location, item.origin_location_id) if item.origin_location_id else None
        if location and not location.active:
            raise HTTPException(status_code=400, detail="La ubicación origen está archivada")
        db.add(m.WorkProductLine(
            work_id=work.id, product_id=product.id, origin_location_id=item.origin_location_id,
            quantity=item.quantity, returned_quantity=ZERO, consumed_quantity=ZERO, lost_quantity=ZERO,
            product_name_snapshot=product.name or f"Artículo #{product.id}",
            location_name_snapshot=location.name if location else "Sin ubicación identificada",
            unit_value_snapshot=product.unit_value, value_currency_snapshot=product.value_currency,
        ))
    for asset_id in payload.asset_ids:
        asset = db.scalar(select(m.Asset).options(selectinload(m.Asset.product)).where(m.Asset.id == asset_id))
        if not asset or not asset.active or asset.lifecycle_status != "in_stock":
            raise HTTPException(status_code=400, detail=f"Unidad física #{asset_id} no disponible")
        other = db.scalar(select(m.WorkAssetLine.id).where(
            m.WorkAssetLine.asset_id == asset_id,
            m.WorkAssetLine.returned_at.is_(None),
        ).limit(1))
        if other is not None:
            raise HTTPException(status_code=409, detail=f"La unidad {asset.asset_code} ya está preparada o fuera en otro trabajo")
        other_project = db.scalar(select(m.ProjectAsset.project_id).where(
            m.ProjectAsset.asset_id == asset_id, m.ProjectAsset.released_at.is_(None),
            m.ProjectAsset.project_id != work.project_id,
        ).limit(1))
        if other_project is not None:
            raise HTTPException(status_code=409, detail=f"La unidad {asset.asset_code} pertenece a otro proyecto")
        db.add(m.WorkAssetLine(
            work_id=work.id, asset_id=asset.id, origin_location_id=asset.location_id,
            asset_code_snapshot=asset.asset_code,
            asset_name_snapshot=(asset.product.name if asset.product else "Unidad sin artículo"),
            serial_snapshot=asset.manufacturer_serial,
        ))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Una unidad ya está preparada en otro trabajo") from exc
    return work_view(db, work)


@router.delete("/works/{work_id}/prepared/{kind}/{line_id}", response_model=WorkOut)
def remove_prepared_item(work_id: int, kind: Literal["product", "asset"], line_id: int, db: Session = Depends(get_db)):
    work = work_or_404(db, work_id, lock=True)
    if work.status == "closed":
        raise HTTPException(status_code=409, detail="No se puede modificar un trabajo cerrado")
    model = m.WorkProductLine if kind == "product" else m.WorkAssetLine
    line = db.scalar(select(model).where(model.id == line_id, model.work_id == work.id))
    if not line:
        raise HTTPException(status_code=404, detail="Elemento no encontrado")
    if line.dispatched_at is not None:
        raise HTTPException(status_code=409, detail="El elemento ya salió; debe gestionarse mediante devolución")
    db.delete(line)
    db.commit()
    return work_view(db, work)


def lock_balance(db: Session, product_id: int, location_id: int | None):
    filter_location = m.StockBalance.location_id.is_(None) if location_id is None else m.StockBalance.location_id == location_id
    return db.scalar(select(m.StockBalance).where(m.StockBalance.product_id == product_id, filter_location).with_for_update())


@router.post("/works/{work_id}/dispatch", response_model=WorkOut)
def dispatch_work(work_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(current_user)):
    work = work_or_404(db, work_id, lock=True)
    if work.status == "closed":
        raise HTTPException(status_code=409, detail="Un trabajo cerrado no admite salidas")
    product_lines, asset_lines = lines(db, work.id)
    pending_p = [line for line in product_lines if not line.dispatched_at]
    pending_a = [line for line in asset_lines if not line.dispatched_at]
    if not pending_p and not pending_a:
        raise HTTPException(status_code=400, detail="No hay materiales preparados para despachar")
    # Bloqueos ordenados para serializar operaciones concurrentes por ubicación/producto.
    keys = sorted({(line.product_id, line.origin_location_id) for line in pending_p}, key=lambda x: (x[0], -1 if x[1] is None else x[1]))
    balances = {key: lock_balance(db, *key) for key in keys}
    totals = {}
    for line in pending_p:
        key = (line.product_id, line.origin_location_id)
        totals[key] = totals.get(key, ZERO) + line.quantity
    for key, quantity in totals.items():
        balance = balances[key]
        if not balance or not balance.verified:
            raise HTTPException(status_code=409, detail=f"El artículo #{key[0]} no tiene conteo inicial verificado en el origen")
        if balance.quantity < quantity:
            raise HTTPException(status_code=409, detail=f"Stock insuficiente para el artículo #{key[0]}: disponible {balance.quantity}, solicitado {quantity}")
    asset_ids = sorted(line.asset_id for line in pending_a)
    assets = {row.id: row for row in db.scalars(select(m.Asset).where(m.Asset.id.in_(asset_ids)).order_by(m.Asset.id).with_for_update()).all()} if asset_ids else {}
    for line in pending_a:
        asset = assets.get(line.asset_id)
        if not asset or not asset.active or asset.lifecycle_status != "in_stock":
            raise HTTPException(status_code=409, detail=f"La unidad {line.asset_code_snapshot} no está disponible")
        occupied = db.scalar(select(m.WorkAssetLine.id).where(
            m.WorkAssetLine.asset_id == asset.id,
            m.WorkAssetLine.id != line.id,
            m.WorkAssetLine.dispatched_at.is_not(None), m.WorkAssetLine.returned_at.is_(None),
        ).limit(1))
        if occupied is not None:
            raise HTTPException(status_code=409, detail=f"La unidad {line.asset_code_snapshot} ya está en un trabajo")
    timestamp = now()
    for line in pending_p:
        balance = balances[(line.product_id, line.origin_location_id)]
        before = balance.quantity
        balance.quantity -= line.quantity
        # La valoración y descripción históricas se congelan al confirmar
        # la salida física, no cuando se preparó el borrador.
        product = db.get(m.Product, line.product_id)
        line.product_name_snapshot = product.name or f"Artículo #{product.id}"
        line.unit_value_snapshot = product.unit_value
        line.value_currency_snapshot = product.value_currency
        line.dispatched_at = timestamp
        line.dispatched_by_id = user.id
        db.add(m.StockMovement(
            product_id=line.product_id, location_id=line.origin_location_id,
            movement_type="exit", quantity=line.quantity, quantity_before=before,
            quantity_after=balance.quantity, note=f"Salida temporal a Trabajo #{work.id}: {work.name}",
            status="approved", created_by_id=user.id,
        ))
    for line in pending_a:
        asset = assets[line.asset_id]
        # El origen se conserva para poder restituirlo durante la devolución.
        line.origin_location_id = asset.location_id
        line.dispatched_at = timestamp
        line.dispatched_by_id = user.id
        asset.location_id = None
    work.status = "open"
    work.departed_at = work.departed_at or timestamp
    db.commit()
    return work_view(db, work)


@router.post("/works/{work_id}/returns", response_model=WorkOut)
def return_work(work_id: int, payload: WorkReturn, db: Session = Depends(get_db), user: CurrentUser = Depends(current_user)):
    work = work_or_404(db, work_id, lock=True)
    if work.status != "open":
        raise HTTPException(status_code=409, detail="Solo se admiten devoluciones de trabajos en curso")
    product_lines, asset_lines = lines(db, work.id)
    pmap = {line.id: line for line in product_lines}
    amap = {line.id: line for line in asset_lines}
    for item in payload.products:
        line = pmap.get(item.line_id)
        if not line or line.dispatched_at is None:
            raise HTTPException(status_code=400, detail="El artículo no fue despachado en este trabajo")
        remaining = line.quantity - line.returned_quantity - line.consumed_quantity - line.lost_quantity
        if item.quantity > remaining:
            raise HTTPException(status_code=409, detail=f"La devolución supera lo pendiente de {line.product_name_snapshot}")
    for line_id in payload.asset_line_ids:
        line = amap.get(line_id)
        if not line or not line.dispatched_at or line.returned_at:
            raise HTTPException(status_code=409, detail="La unidad no está pendiente de devolución en este trabajo")
        if line.origin_location_id is not None:
            location = db.get(m.Location, line.origin_location_id)
            if not location or not location.active:
                raise HTTPException(status_code=409, detail="La ubicación de origen de una unidad ya no está activa")
    keys = sorted({(pmap[item.line_id].product_id, pmap[item.line_id].origin_location_id) for item in payload.products}, key=lambda x: (x[0], -1 if x[1] is None else x[1]))
    balances = {key: lock_balance(db, *key) for key in keys}
    for key, balance in balances.items():
        if not balance or not balance.verified:
            raise HTTPException(status_code=409, detail=f"El origen del artículo #{key[0]} ya no tiene stock verificado")
    timestamp = now()
    for item in payload.products:
        line = pmap[item.line_id]
        balance = balances[(line.product_id, line.origin_location_id)]
        before = balance.quantity
        balance.quantity += item.quantity
        line.returned_quantity += item.quantity
        db.add(m.StockMovement(
            product_id=line.product_id, location_id=line.origin_location_id,
            movement_type="entry", quantity=item.quantity, quantity_before=before,
            quantity_after=balance.quantity, note=f"Devolución de Trabajo #{work.id}: {work.name}", status="approved",
            created_by_id=user.id,
        ))
        db.add(m.WorkReturnEvent(work_id=work.id, product_line_id=line.id, quantity=item.quantity, returned_at=timestamp, created_by_id=user.id))
    asset_ids = sorted(amap[item].asset_id for item in payload.asset_line_ids)
    assets = {row.id: row for row in db.scalars(select(m.Asset).where(m.Asset.id.in_(asset_ids)).order_by(m.Asset.id).with_for_update()).all()} if asset_ids else {}
    for line_id in payload.asset_line_ids:
        line = amap[line_id]
        asset = assets.get(line.asset_id)
        if not asset or not asset.active or asset.lifecycle_status != "in_stock":
            raise HTTPException(status_code=409, detail=f"No se puede devolver {line.asset_code_snapshot}; revisá su estado")
        asset.location_id = line.origin_location_id
        line.returned_at = timestamp
        db.add(m.WorkReturnEvent(work_id=work.id, asset_line_id=line.id, returned_at=timestamp, created_by_id=user.id))
    db.commit()
    return work_view(db, work)


@router.post("/works/{work_id}/close", response_model=WorkOut)
def close_work(work_id: int, payload: WorkClose, db: Session = Depends(get_db), user: CurrentUser = Depends(current_user)):
    work = work_or_404(db, work_id, lock=True)
    if work.status != "open":
        raise HTTPException(status_code=409, detail="Solo se pueden cerrar trabajos en curso")
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Es obligatorio confirmar la conciliación de materiales")
    p_lines, a_lines = lines(db, work.id)
    if any(line.dispatched_at is None for line in p_lines + a_lines):
        raise HTTPException(status_code=409, detail="Primero despachá o eliminá los elementos que aún están preparados")
    if any(line.dispatched_at and line.returned_at is None for line in a_lines):
        raise HTTPException(status_code=409, detail="Hay unidades físicas sin devolver; no se cerrará el trabajo")
    line_modes = {decision.line_id: decision.remaining_as for decision in payload.decisions}
    unknown = set(line_modes) - {line.id for line in p_lines}
    if unknown:
        raise HTTPException(status_code=400, detail="Se indicó una línea ajena a este trabajo")
    for line in p_lines:
        remaining = line.quantity - line.returned_quantity - line.consumed_quantity - line.lost_quantity
        if line_modes.get(line.id, payload.remaining_as) == "consumed":
            line.consumed_quantity += remaining
        else:
            line.lost_quantity += remaining
    work.status = "closed"
    work.closed_at = now()
    work.closed_by_id = user.id
    work.close_note = payload.note
    db.commit()
    return work_view(db, work)


@router.get("/work-stock-summary", response_model=WorkStockSummaryOut)
def work_stock_summary(db: Session = Depends(get_db)):
    rows = db.execute(select(m.WorkProductLine.product_id,
        func.sum(m.WorkProductLine.quantity - m.WorkProductLine.returned_quantity - m.WorkProductLine.consumed_quantity - m.WorkProductLine.lost_quantity))
        .join(m.Work).where(m.Work.status == "open", m.WorkProductLine.dispatched_at.is_not(None))
        .group_by(m.WorkProductLine.product_id)).all()
    assets = db.execute(select(m.Asset.product_id, func.count(m.WorkAssetLine.id))
        .join(m.WorkAssetLine, m.WorkAssetLine.asset_id == m.Asset.id)
        .join(m.Work, m.Work.id == m.WorkAssetLine.work_id)
        .where(m.Work.status == "open", m.WorkAssetLine.dispatched_at.is_not(None), m.WorkAssetLine.returned_at.is_(None))
        .group_by(m.Asset.product_id)).all()
    return {
        "products": {str(product_id): quantity for product_id, quantity in rows},
        "assets": {str(product_id): count for product_id, count in assets if product_id is not None},
    }


def pdf_output(work: m.Work, db: Session, mode: str) -> BytesIO:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os
    from zoneinfo import ZoneInfo
    from xml.sax.saxutils import escape

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if os.path.exists(font_path):
        if "AppSans" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("AppSans", font_path))
        font = "AppSans"
    else:
        font = "Helvetica"
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("AppBody", parent=styles["Normal"], fontName=font, fontSize=9, leading=13)
    title = ParagraphStyle("AppTitle", parent=normal, fontSize=16, leading=22, alignment=TA_CENTER, spaceAfter=12)
    small = ParagraphStyle("AppSmall", parent=normal, fontSize=8)
    def para(value):
        return Paragraph(escape(str(value or "—")), small)
    def qty(value):
        return str(value.normalize() if isinstance(value, Decimal) else value)
    def local_date(value):
        if value is None:
            return "Pendiente"
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(ZoneInfo("America/Asuncion")).strftime("%d/%m/%Y %H:%M")
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=35, rightMargin=35, topMargin=40, bottomMargin=40)
    project = db.get(m.Project, work.project_id)
    content = [Paragraph(("COMPROBANTE DE SALIDA" if mode == "out" else "COMPROBANTE DE DEVOLUCIÓN"), title)]
    content.append(Paragraph(f"Proyecto: {escape(project.name)} | Trabajo #{work.id}: {escape(work.name)}", normal))
    status_label = {"draft":"Preparación", "open":"En curso", "closed":"Cerrado"}.get(work.status, work.status)
    content.append(Paragraph(f"Responsable: {escape(work.responsible or 'No registrado')} | Estado: {status_label}", normal))
    content.append(Paragraph(f"Salida real: {local_date(work.departed_at)} | Cierre real: {local_date(work.closed_at) if work.closed_at else 'En curso'} (hora Paraguay)", normal))
    content.append(Spacer(1, 14))
    products, assets = lines(db, work.id)
    headers = ["Componente", "Origen / código", "Salió", "Devuelto", "Diferencia"]
    data = [[para(h) for h in headers]]
    for line in products:
        if not line.dispatched_at:
            continue
        data.append([para(line.product_name_snapshot), para(line.location_name_snapshot), para(qty(line.quantity)),
                     para(qty(line.returned_quantity) if mode == "return" else "—"),
                     para(qty(line.quantity - line.returned_quantity) if mode == "return" else "—")])
    for line in assets:
        if not line.dispatched_at:
            continue
        data.append([para(line.asset_name_snapshot), para(line.asset_code_snapshot), para("1"),
                     para("1" if line.returned_at else "0") if mode == "return" else para("—"),
                     para("0" if line.returned_at else "1") if mode == "return" else para("—")])
    if len(data) == 1:
        data.append([para("Sin materiales"), para(""), para(""), para(""), para("")])
    table = Table(data, colWidths=[155, 130, 55, 65, 75], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,0), colors.HexColor("#EAF0F9")),
        ("GRID", (0,0),(-1,-1), 0.25, colors.HexColor("#CDD7E5")),
        ("VALIGN", (0,0),(-1,-1), "TOP"),
        ("TOPPADDING",(0,0),(-1,-1),7), ("BOTTOMPADDING",(0,0),(-1,-1),7),
    ]))
    content.append(table)
    if mode == "return":
        content.append(Spacer(1, 12))
        content.append(Paragraph("Diferencia = salida - devolución. La clasificación final de las diferencias se registra al cerrar el trabajo.", normal))
        if work.status == "closed":
            for line in products:
                if line.consumed_quantity or line.lost_quantity:
                    content.append(Paragraph(f"{escape(line.product_name_snapshot)}: consumido {qty(line.consumed_quantity)}, perdido {qty(line.lost_quantity)}", small))
    content.append(Spacer(1, 28))
    content.append(Paragraph("Entrega / Responsable: ____________________________________", normal))
    content.append(Spacer(1, 16))
    content.append(Paragraph("Recepción / Control: _______________________________________", normal))
    content.append(Spacer(1, 12))
    content.append(Paragraph("Emitido digitalmente: " + escape(local_date(now()) + " (hora Paraguay)"), small))
    doc.build(content)
    buf.seek(0)
    return buf


@router.get(
    "/works/{work_id}/pdf/{mode}",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/pdf": {}}}},
)
def work_pdf(work_id: int, mode: Literal["out", "return"], db: Session = Depends(get_db)):
    work = work_or_404(db, work_id)
    if work.status == "draft":
        raise HTTPException(status_code=409, detail="Primero confirmá una salida")
    if mode == "return" and work.status != "closed":
        raise HTTPException(status_code=409, detail="El PDF de devolución final se emite después del cierre")
    stream = pdf_output(work, db, mode)
    return StreamingResponse(stream, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="trabajo_{work.id}_{mode}.pdf"'
    })
