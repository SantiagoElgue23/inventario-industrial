"""Rol por cuenta: separa el rol del nombre de usuario.

Las cuentas existentes master, admin y user conservan su rol actual.

Revision ID: f2a6d3b8c1e4
Revises: e5b1f0a7c9d2
"""
from alembic import op
import sqlalchemy as sa

revision = "f2a6d3b8c1e4"
down_revision = "e5b1f0a7c9d2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("app_users") as batch:
        batch.add_column(sa.Column("role", sa.String(16), nullable=True))
    op.execute(
        "UPDATE app_users SET role = CASE "
        "WHEN username IN ('master', 'admin') THEN username ELSE 'user' END"
    )
    with op.batch_alter_table("app_users") as batch:
        batch.alter_column("role", existing_type=sa.String(16), nullable=False, server_default="user")
        batch.create_check_constraint("ck_app_user_role", "role IN ('master', 'admin', 'user')")


def downgrade():
    # El esquema anterior deduce el rol del nombre; las cuentas personales
    # creadas después de esta migración dejan de tener acceso.
    with op.batch_alter_table("app_users") as batch:
        batch.drop_constraint("ck_app_user_role", type_="check")
        batch.drop_column("role")
