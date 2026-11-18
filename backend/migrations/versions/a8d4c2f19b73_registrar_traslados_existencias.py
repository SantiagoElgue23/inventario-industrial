"""Registrar traslados de existencias entre ubicaciones

Revision ID: a8d4c2f19b73
Revises: fb85e95ae71e
Create Date: 2026-11-06 17:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a8d4c2f19b73"
down_revision: Union[str, Sequence[str], None] = "fb85e95ae71e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stock_transfers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("source_location_id", sa.Integer(), nullable=True),
        sa.Column("destination_location_id", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("source_quantity_before", sa.Numeric(14, 3), nullable=False),
        sa.Column("source_quantity_after", sa.Numeric(14, 3), nullable=False),
        sa.Column("destination_quantity_before", sa.Numeric(14, 3), nullable=False),
        sa.Column("destination_quantity_after", sa.Numeric(14, 3), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_stock_transfer_quantity"),
        sa.CheckConstraint(
            "source_quantity_before >= 0 AND source_quantity_after >= 0 "
            "AND destination_quantity_before >= 0 "
            "AND destination_quantity_after >= 0",
            name="ck_stock_transfer_balances",
        ),
        sa.CheckConstraint(
            "NOT (source_location_id IS NULL AND destination_location_id IS NULL) "
            "AND (source_location_id IS NULL OR destination_location_id IS NULL "
            "OR source_location_id <> destination_location_id)",
            name="ck_stock_transfer_distinct_locations",
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["source_location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["destination_location_id"], ["locations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_stock_transfers_product_id"),
        "stock_transfers",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stock_transfers_source_location_id"),
        "stock_transfers",
        ["source_location_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stock_transfers_destination_location_id"),
        "stock_transfers",
        ["destination_location_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_stock_transfers_destination_location_id"),
        table_name="stock_transfers",
    )
    op.drop_index(
        op.f("ix_stock_transfers_source_location_id"),
        table_name="stock_transfers",
    )
    op.drop_index(
        op.f("ix_stock_transfers_product_id"),
        table_name="stock_transfers",
    )
    op.drop_table("stock_transfers")
