"""Salud de la API y resumen general."""
from fastapi import APIRouter, Depends
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..database import get_db
from ..common import (
    robot_product_filter,
)


# /health no exige sesión: lo usan monitoreo y balanceadores.
public_router = APIRouter(prefix="/api", tags=["Sistema"])
router = APIRouter(prefix="/api", tags=["Sistema"])


@public_router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "database": "connected"}


@router.get("/summary", tags=["Sistema"])
def summary(db: Session = Depends(get_db)):
    return {
        "products": db.scalar(
            select(func.count()).select_from(m.Product).where(m.Product.active.is_(True))
        ) or 0,
        "categories": db.scalar(
            select(func.count()).select_from(m.Category).where(m.Category.active.is_(True))
        ) or 0,
        "component_types": db.scalar(
            select(func.count()).select_from(m.ComponentType).where(m.ComponentType.active.is_(True))
        ) or 0,
        "pending_stock_count": db.scalar(
            select(func.count())
            .select_from(m.Product)
            .where(
                m.Product.active.is_(True),
                m.Product.tracking_mode == "quantity",
                ~exists(
                    select(1).where(
                        m.StockBalance.product_id == m.Product.id,
                        m.StockBalance.verified.is_(True),
                    )
                ),
            )
        ) or 0,
        "assets": db.scalar(
            select(func.count())
            .select_from(m.Asset)
            .where(
                m.Asset.active.is_(True),
                m.Asset.lifecycle_status == "in_stock",
            )
        ) or 0,
        "robot_models": db.scalar(
            select(func.count())
            .select_from(m.Product)
            .where(
                m.Product.active.is_(True),
                m.Product.tracking_mode == "individual",
                robot_product_filter(),
            )
        ) or 0,
        "active_projects": db.scalar(
            select(func.count())
            .select_from(m.Project)
            .where(m.Project.active.is_(True), m.Project.status == "active")
        ) or 0,
    }
