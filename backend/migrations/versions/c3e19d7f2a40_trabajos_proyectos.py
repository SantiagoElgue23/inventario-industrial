"""Trabajos: salidas temporales, devoluciones y conciliacion.

Revision ID: c3e19d7f2a40
Revises: a8d4c2f19b73
"""
from alembic import op
import sqlalchemy as sa

revision = "c3e19d7f2a40"
down_revision = "a8d4c2f19b73"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("works",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text), sa.Column("responsible", sa.String(120)),
        sa.Column("planned_out_date", sa.Date), sa.Column("planned_return_date", sa.Date),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("departed_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("close_note", sa.Text),
        sa.CheckConstraint("status IN ('draft', 'open', 'closed')", name="ck_work_status"),
        sa.CheckConstraint("planned_out_date IS NULL OR planned_return_date IS NULL OR planned_return_date >= planned_out_date", name="ck_work_planned_dates"),
    )
    op.create_index("ix_works_project_id", "works", ["project_id"])

    op.create_table("work_product_lines",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("work_id", sa.Integer, sa.ForeignKey("works.id"), nullable=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id"), nullable=False),
        sa.Column("origin_location_id", sa.Integer, sa.ForeignKey("locations.id")),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("returned_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("consumed_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("lost_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("product_name_snapshot", sa.String(240), nullable=False),
        sa.Column("location_name_snapshot", sa.String(180), nullable=False),
        sa.Column("unit_value_snapshot", sa.Numeric(14, 2)),
        sa.Column("value_currency_snapshot", sa.String(3), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_work_product_quantity"),
        sa.CheckConstraint("returned_quantity >= 0 AND consumed_quantity >= 0 AND lost_quantity >= 0", name="ck_work_product_nonnegative"),
        sa.CheckConstraint("returned_quantity + consumed_quantity + lost_quantity <= quantity", name="ck_work_product_reconciled"),
    )
    for field in ("work_id", "product_id", "origin_location_id"):
        op.create_index(f"ix_work_product_lines_{field}", "work_product_lines", [field])

    op.create_table("work_asset_lines",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("work_id", sa.Integer, sa.ForeignKey("works.id"), nullable=False),
        sa.Column("asset_id", sa.Integer, sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("origin_location_id", sa.Integer, sa.ForeignKey("locations.id")),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("returned_at", sa.DateTime(timezone=True)),
        sa.Column("asset_code_snapshot", sa.String(32), nullable=False),
        sa.Column("asset_name_snapshot", sa.String(240), nullable=False),
        sa.Column("serial_snapshot", sa.String(100)),
        sa.CheckConstraint("returned_at IS NULL OR dispatched_at IS NOT NULL", name="ck_work_asset_returned_only_if_out"),
    )
    for field in ("work_id", "asset_id"):
        op.create_index(f"ix_work_asset_lines_{field}", "work_asset_lines", [field])

    op.create_index("uq_work_asset_outstanding", "work_asset_lines", ["asset_id"], unique=True,
        postgresql_where=sa.text("returned_at IS NULL"), sqlite_where=sa.text("returned_at IS NULL"))

    op.create_table("work_return_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("work_id", sa.Integer, sa.ForeignKey("works.id"), nullable=False),
        sa.Column("product_line_id", sa.Integer, sa.ForeignKey("work_product_lines.id")),
        sa.Column("asset_line_id", sa.Integer, sa.ForeignKey("work_asset_lines.id")),
        sa.Column("quantity", sa.Numeric(14, 3)),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("(product_line_id IS NOT NULL AND asset_line_id IS NULL AND quantity > 0) OR (product_line_id IS NULL AND asset_line_id IS NOT NULL AND quantity IS NULL)", name="ck_work_return_event_kind"),
    )
    op.create_index("ix_work_return_events_work_id", "work_return_events", ["work_id"])


def downgrade():
    op.drop_index("ix_work_return_events_work_id", table_name="work_return_events")
    op.drop_table("work_return_events")
    for field in ("work_id", "asset_id"):
        op.drop_index(f"ix_work_asset_lines_{field}", table_name="work_asset_lines")
    op.drop_index("uq_work_asset_outstanding", table_name="work_asset_lines")
    op.drop_table("work_asset_lines")
    for field in ("work_id", "product_id", "origin_location_id"):
        op.drop_index(f"ix_work_product_lines_{field}", table_name="work_product_lines")
    op.drop_table("work_product_lines")
    op.drop_index("ix_works_project_id", table_name="works")
    op.drop_table("works")
