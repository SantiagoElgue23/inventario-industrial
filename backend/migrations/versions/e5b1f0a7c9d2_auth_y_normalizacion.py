"""Autenticación y supresión de revisión; conservar observaciones.

Revision ID: e5b1f0a7c9d2
Revises: c3e19d7f2a40
"""
from alembic import op
import sqlalchemy as sa

revision = "e5b1f0a7c9d2"
down_revision = "c3e19d7f2a40"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("app_users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(32), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_table("app_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_app_sessions_user_id", "app_sessions", ["user_id"])
    with op.batch_alter_table("assets") as batch:
        batch.alter_column("review_note", new_column_name="observations")
        batch.drop_constraint("ck_asset_review_status", type_="check")
        batch.drop_column("review_status")
    # Eliminar mensajes de revisión generados automáticamente al importar
    # desde InvenTree. Conservamos observaciones técnicas reales, incluidos
    # avisos sobre seriales duplicados o modelos sin identificar.
    for phrase in (
        "Importado desde catálogo InvenTree.",
        "Confirmar presencia física, ubicación y estado durante el inventariado.",
        "El stock histórico se conserva solo como referencia; no se importó como existencia.",
    ):
        op.execute(sa.text("UPDATE assets SET observations = TRIM(REPLACE(observations, :phrase, '')) WHERE observations IS NOT NULL").bindparams(phrase=phrase))
    op.execute("UPDATE assets SET observations = NULL WHERE observations = ''")
    # Los estados heredados dejan de crear opciones adicionales en el formulario.
    op.execute("UPDATE assets SET functional_status = 'unverified' WHERE functional_status IS NULL OR functional_status NOT IN ('functional', 'damaged', 'unverified')")
    with op.batch_alter_table("assets") as batch:
        batch.drop_constraint("ck_asset_functional_status", type_="check")
        batch.create_check_constraint("ck_asset_functional_status", "functional_status IN ('functional', 'damaged', 'unverified')")


def downgrade():
    with op.batch_alter_table("assets") as batch:
        batch.drop_constraint("ck_asset_functional_status", type_="check")
        batch.create_check_constraint("ck_asset_functional_status", "functional_status IN ('unverified', 'functional', 'damaged', 'under_repair', 'out_of_service')")
        batch.add_column(sa.Column("review_status", sa.String(30), nullable=False, server_default="pending"))
        batch.create_check_constraint("ck_asset_review_status", "review_status IN ('pending', 'reviewed')")
        batch.alter_column("observations", new_column_name="review_note")
    op.drop_index("ix_app_sessions_user_id", table_name="app_sessions")
    op.drop_table("app_sessions")
    op.drop_table("app_users")
