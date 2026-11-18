"""Auditoría: registrar qué cuenta realizó cada operación de stock y de trabajos.

Las operaciones anteriores a esta migración quedan sin usuario (NULL).

Revision ID: a3c7e1d9b5f2
Revises: f2a6d3b8c1e4
"""
from alembic import op
import sqlalchemy as sa

revision = "a3c7e1d9b5f2"
down_revision = "f2a6d3b8c1e4"
branch_labels = None
depends_on = None

# (tabla, columna)
AUDIT_COLUMNS = [
    ("stock_movements", "created_by_id"),
    ("stock_transfers", "created_by_id"),
    ("works", "created_by_id"),
    ("works", "closed_by_id"),
    ("work_product_lines", "dispatched_by_id"),
    ("work_asset_lines", "dispatched_by_id"),
    ("work_return_events", "created_by_id"),
]


def upgrade():
    for table, column in AUDIT_COLUMNS:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column(column, sa.Integer, nullable=True))
            batch.create_foreign_key(
                f"fk_{table}_{column}_app_users", "app_users", [column], ["id"], ondelete="SET NULL"
            )
            batch.create_index(f"ix_{table}_{column}", [column])


def downgrade():
    for table, column in reversed(AUDIT_COLUMNS):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_{column}")
            batch.drop_constraint(f"fk_{table}_{column}_app_users", type_="foreignkey")
            batch.drop_column(column)
