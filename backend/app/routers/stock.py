"""Existencias por ubicación: saldos, movimientos y traslados."""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .. import models as m
from .. import schemas as s
from ..database import get_db
from ..auth import CurrentUser, current_user
from ..common import (
    Page,
    fetch_page,
    pagination,
    validate_location,
    validate_quantity_product,
)


router = APIRouter(prefix="/api")

# ============================================================
# MOVIMIENTOS DE EXISTENCIAS
# ============================================================


@router.get(
    "/products/{product_id}/balances",
    response_model=list[s.StockBalanceOut],
    tags=["Existencias"],
)
def list_product_balances(product_id: int, db: Session = Depends(get_db)):
    product = validate_quantity_product(db.get(m.Product, product_id))

    stmt = (
        select(m.StockBalance)
        .options(
            selectinload(m.StockBalance.location).selectinload(m.Location.parent)
        )
        .where(m.StockBalance.product_id == product.id)
        .order_by(m.StockBalance.location_id.nullsfirst())
    )
    balances = db.scalars(stmt).all()

    return [
        {
            "product_id": balance.product_id,
            "location_id": balance.location_id,
            "location_name": balance.location.name if balance.location else None,
            "parent_name": (
                balance.location.parent.name
                if balance.location and balance.location.parent
                else None
            ),
            "location_type": (
                balance.location.location_type if balance.location else None
            ),
            "quantity": balance.quantity,
            "verified": balance.verified,
            "updated_at": balance.updated_at,
        }
        for balance in balances
    ]


@router.post(
    "/products/{product_id}/movements",
    response_model=s.MovementOut,
    status_code=201,
    tags=["Existencias"],
)
def create_movement(
    product_id: int,
    payload: s.MovementCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(current_user),
):
    product = validate_quantity_product(db.get(m.Product, product_id))
    validate_location(db, payload.location_id)

    balance_stmt = select(m.StockBalance).where(
        m.StockBalance.product_id == product.id,
        m.StockBalance.location_id.is_(None)
        if payload.location_id is None
        else m.StockBalance.location_id == payload.location_id,
    ).with_for_update()
    balance = db.scalar(balance_stmt)
    if balance is None:
        balance = m.StockBalance(
            product_id=product.id,
            location_id=payload.location_id,
            quantity=Decimal("0"),
            verified=False,
        )
        db.add(balance)
        db.flush()

    before = balance.quantity
    if not balance.verified and payload.movement_type != "count":
        raise HTTPException(
            status_code=400,
            detail="Primero registrá el conteo físico inicial para esta ubicación",
        )

    if payload.movement_type == "entry":
        after = before + payload.quantity
    elif payload.movement_type == "exit":
        after = before - payload.quantity
    else:
        after = payload.quantity

    if after < 0:
        raise HTTPException(status_code=400, detail="La extracción supera las existencias registradas")

    balance.quantity = after
    balance.verified = True
    movement = m.StockMovement(
        product_id=product.id,
        location_id=payload.location_id,
        movement_type=payload.movement_type,
        quantity=payload.quantity,
        quantity_before=before,
        quantity_after=after,
        note=payload.note,
        status="approved",
        created_by_id=user.id,
    )
    db.add(movement)
    db.commit()
    db.refresh(movement)
    return movement


@router.get(
    "/products/{product_id}/movements",
    response_model=list[s.MovementOut],
    tags=["Existencias"],
)
def list_movements(
    product_id: int,
    response: Response,
    location_id: int | None = None,
    page: Page = Depends(pagination),
    db: Session = Depends(get_db),
):
    if db.get(m.Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    stmt = select(m.StockMovement).where(m.StockMovement.product_id == product_id)
    if location_id is not None:
        stmt = stmt.where(m.StockMovement.location_id == location_id)
    return fetch_page(db, stmt.order_by(m.StockMovement.created_at.desc(), m.StockMovement.id.desc()), page, response)


@router.post(
    "/products/{product_id}/transfers",
    response_model=s.StockTransferOut,
    status_code=201,
    tags=["Existencias"],
)
def create_stock_transfer(
    product_id: int,
    payload: s.StockTransferCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(current_user),
):
    """Traslada stock entre dos ubicaciones con una única transacción."""
    product = validate_quantity_product(db.get(m.Product, product_id))
    validate_location(db, payload.source_location_id)
    validate_location(db, payload.destination_location_id)

    if payload.source_location_id == payload.destination_location_id:
        raise HTTPException(
            status_code=400,
            detail="El origen y el destino deben ser diferentes.",
        )

    # Se bloquean las existencias del artículo en un orden estable para evitar
    # que dos traslados simultáneos generen saldos inconsistentes.
    balances = db.scalars(
        select(m.StockBalance)
        .where(m.StockBalance.product_id == product.id)
        .order_by(m.StockBalance.location_id.nullsfirst())
        .with_for_update()
    ).all()
    balances_by_location = {balance.location_id: balance for balance in balances}

    source = balances_by_location.get(payload.source_location_id)
    destination = balances_by_location.get(payload.destination_location_id)

    if source is None or not source.verified:
        raise HTTPException(
            status_code=400,
            detail="El origen no tiene un conteo físico inicial verificado.",
        )
    if destination is None or not destination.verified:
        raise HTTPException(
            status_code=400,
            detail="El destino no tiene un conteo físico inicial verificado. Registrá primero su conteo, aunque sea 0.",
        )

    quantity = payload.quantity
    source_before = source.quantity
    destination_before = destination.quantity

    if quantity > source_before:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No se puede trasladar {quantity}: el origen solamente dispone "
                f"de {source_before}."
            ),
        )

    source_after = source_before - quantity
    destination_after = destination_before + quantity

    source.quantity = source_after
    destination.quantity = destination_after

    transfer = m.StockTransfer(
        product_id=product.id,
        source_location_id=payload.source_location_id,
        destination_location_id=payload.destination_location_id,
        quantity=quantity,
        source_quantity_before=source_before,
        source_quantity_after=source_after,
        destination_quantity_before=destination_before,
        destination_quantity_after=destination_after,
        note=payload.note,
        created_by_id=user.id,
    )
    db.add(transfer)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="No se pudo registrar el traslado por un conflicto de datos. Actualizá los saldos e intentá nuevamente.",
        ) from exc
    except Exception:
        db.rollback()
        raise

    transfer = db.scalar(
        select(m.StockTransfer)
        .options(
            selectinload(m.StockTransfer.source_location).selectinload(m.Location.parent),
            selectinload(m.StockTransfer.destination_location).selectinload(m.Location.parent),
        )
        .where(m.StockTransfer.id == transfer.id)
    )
    return {
        "id": transfer.id,
        "product_id": transfer.product_id,
        "source_location_id": transfer.source_location_id,
        "source_location_name": (
            transfer.source_location.name if transfer.source_location else None
        ),
        "source_parent_name": (
            transfer.source_location.parent.name
            if transfer.source_location and transfer.source_location.parent
            else None
        ),
        "destination_location_id": transfer.destination_location_id,
        "destination_location_name": (
            transfer.destination_location.name
            if transfer.destination_location
            else None
        ),
        "destination_parent_name": (
            transfer.destination_location.parent.name
            if transfer.destination_location and transfer.destination_location.parent
            else None
        ),
        "quantity": transfer.quantity,
        "source_quantity_before": transfer.source_quantity_before,
        "source_quantity_after": transfer.source_quantity_after,
        "destination_quantity_before": transfer.destination_quantity_before,
        "destination_quantity_after": transfer.destination_quantity_after,
        "note": transfer.note,
        "created_by": transfer.created_by,
        "created_at": transfer.created_at,
    }


@router.get(
    "/products/{product_id}/transfers",
    response_model=list[s.StockTransferOut],
    tags=["Existencias"],
)
def list_stock_transfers(product_id: int, db: Session = Depends(get_db)):
    if db.get(m.Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    transfers = db.scalars(
        select(m.StockTransfer)
        .options(
            selectinload(m.StockTransfer.source_location).selectinload(m.Location.parent),
            selectinload(m.StockTransfer.destination_location).selectinload(m.Location.parent),
        )
        .where(m.StockTransfer.product_id == product_id)
        .order_by(m.StockTransfer.created_at.desc())
    ).all()

    return [
        {
            "id": transfer.id,
            "product_id": transfer.product_id,
            "source_location_id": transfer.source_location_id,
            "source_location_name": (
                transfer.source_location.name if transfer.source_location else None
            ),
            "source_parent_name": (
                transfer.source_location.parent.name
                if transfer.source_location and transfer.source_location.parent
                else None
            ),
            "destination_location_id": transfer.destination_location_id,
            "destination_location_name": (
                transfer.destination_location.name
                if transfer.destination_location
                else None
            ),
            "destination_parent_name": (
                transfer.destination_location.parent.name
                if transfer.destination_location and transfer.destination_location.parent
                else None
            ),
            "quantity": transfer.quantity,
            "source_quantity_before": transfer.source_quantity_before,
            "source_quantity_after": transfer.source_quantity_after,
            "destination_quantity_before": transfer.destination_quantity_before,
            "destination_quantity_after": transfer.destination_quantity_after,
            "note": transfer.note,
            "created_by": transfer.created_by,
            "created_at": transfer.created_at,
        }
        for transfer in transfers
    ]
