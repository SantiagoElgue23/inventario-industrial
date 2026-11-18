
"""ampliar inventario proyectos y ubicaciones

Revision ID: fb85e95ae71e
Revises: b1cc99037e2b
Create Date: 2026-11-05 15:01:30.504475

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fb85e95ae71e'
down_revision: Union[str, Sequence[str], None] = 'b1cc99037e2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ========================================================
    # PROYECTOS
    # ========================================================

    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=180), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('planning', 'active', 'on_hold', 'completed', 'cancelled')",
            name='ck_project_status'
        ),
        sa.CheckConstraint(
            'start_date IS NULL OR end_date IS NULL OR end_date >= start_date',
            name='ck_project_dates'
        ),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index(
        op.f('ix_projects_name'),
        'projects',
        ['name'],
        unique=False
    )

    # ========================================================
    # PRODUCTOS ASOCIADOS A PROYECTOS
    # ========================================================

    op.create_table(
        'project_products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Numeric(14, 3), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('released_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.CheckConstraint(
            'quantity > 0',
            name='ck_project_product_quantity'
        ),
        sa.CheckConstraint(
            'released_at IS NULL OR released_at >= assigned_at',
            name='ck_project_product_dates'
        ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index(
        op.f('ix_project_products_product_id'),
        'project_products',
        ['product_id'],
        unique=False
    )

    op.create_index(
        op.f('ix_project_products_project_id'),
        'project_products',
        ['project_id'],
        unique=False
    )

    op.create_index(
        'uq_project_product_active',
        'project_products',
        ['project_id', 'product_id'],
        unique=True,
        postgresql_where=sa.text('released_at IS NULL'),
        sqlite_where=sa.text('released_at IS NULL')
    )

    # ========================================================
    # ACTIVOS ASOCIADOS A PROYECTOS
    # ========================================================

    op.create_table(
        'project_assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('released_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.CheckConstraint(
            'released_at IS NULL OR released_at >= assigned_at',
            name='ck_project_asset_dates'
        ),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index(
        op.f('ix_project_assets_asset_id'),
        'project_assets',
        ['asset_id'],
        unique=False
    )

    op.create_index(
        op.f('ix_project_assets_project_id'),
        'project_assets',
        ['project_id'],
        unique=False
    )

    op.create_index(
        'uq_project_asset_active',
        'project_assets',
        ['project_id', 'asset_id'],
        unique=True,
        postgresql_where=sa.text('released_at IS NULL'),
        sqlite_where=sa.text('released_at IS NULL')
    )

    op.create_index(
        'uq_project_asset_single_active_project',
        'project_assets',
        ['asset_id'],
        unique=True,
        postgresql_where=sa.text('released_at IS NULL'),
        sqlite_where=sa.text('released_at IS NULL')
    )

    # ========================================================
    # ACTIVOS: VALOR Y ARCHIVADO
    # ========================================================

    op.add_column(
        'assets',
        sa.Column('estimated_value', sa.Numeric(14, 2), nullable=True)
    )

    op.add_column(
        'assets',
        sa.Column('value_currency', sa.String(3), nullable=False)
    )

    op.add_column(
        'assets',
        sa.Column('active', sa.Boolean(), nullable=False)
    )

    op.add_column(
        'assets',
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True)
    )

    # ========================================================
    # UBICACIONES JERÁRQUICAS
    # ========================================================

    op.add_column(
        'locations',
        sa.Column('location_type', sa.String(20), nullable=False)
    )

    op.add_column(
        'locations',
        sa.Column('parent_id', sa.Integer(), nullable=True)
    )

    op.add_column(
        'locations',
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False)
    )

    op.add_column(
        'locations',
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)
    )

    op.drop_index(
        op.f('ix_locations_name'),
        table_name='locations'
    )

    op.create_index(
        op.f('ix_locations_parent_id'),
        'locations',
        ['parent_id'],
        unique=False
    )

    op.create_unique_constraint(
        'uq_location_parent_name',
        'locations',
        ['parent_id', 'name']
    )

    op.create_index(
        'uq_location_root_name',
        'locations',
        ['name'],
        unique=True,
        postgresql_where=sa.text('parent_id IS NULL'),
        sqlite_where=sa.text('parent_id IS NULL')
    )

    # Nombre explícito para permitir un downgrade correcto.
    op.create_foreign_key(
        'locations_parent_id_fkey',
        'locations',
        'locations',
        ['parent_id'],
        ['id']
    )

    # ========================================================
    # PRODUCTOS: VALOR UNITARIO
    # ========================================================

    op.add_column(
        'products',
        sa.Column('unit_value', sa.Numeric(14, 2), nullable=True)
    )

    op.add_column(
        'products',
        sa.Column('value_currency', sa.String(3), nullable=False)
    )

    # Los datos descriptivos pueden quedar vacíos.
    op.alter_column(
        'products',
        'name',
        existing_type=sa.VARCHAR(length=240),
        nullable=True
    )

    op.alter_column(
        'products',
        'category_id',
        existing_type=sa.INTEGER(),
        nullable=True
    )

    # ========================================================
    # REGISTROS DE IMPORTACIÓN
    # ========================================================

    op.alter_column(
        'source_records',
        'original_name',
        existing_type=sa.TEXT(),
        nullable=True
    )

    # ========================================================
    # EXISTENCIAS Y UBICACIONES
    # ========================================================

    op.alter_column(
        'stock_balances',
        'location_id',
        existing_type=sa.INTEGER(),
        nullable=True
    )

    op.drop_constraint(
        'uq_product_location_balance',
        'stock_balances',
        type_='unique'
    )

    op.create_index(
        'uq_stock_balance_product_location',
        'stock_balances',
        ['product_id', 'location_id'],
        unique=True,
        postgresql_where=sa.text('location_id IS NOT NULL'),
        sqlite_where=sa.text('location_id IS NOT NULL')
    )

    op.create_index(
        'uq_stock_balance_product_unknown_location',
        'stock_balances',
        ['product_id'],
        unique=True,
        postgresql_where=sa.text('location_id IS NULL'),
        sqlite_where=sa.text('location_id IS NULL')
    )

    op.alter_column(
        'stock_movements',
        'location_id',
        existing_type=sa.INTEGER(),
        nullable=True
    )

    # ========================================================
    # RESTRICCIONES CHECK FALTANTES
    # ========================================================

    # PRODUCTOS

    op.create_check_constraint(
        'ck_product_tracking_mode',
        'products',
        "tracking_mode IN ('quantity', 'individual')"
    )

    op.create_check_constraint(
        'ck_product_tracking_prefix',
        'products',
        "(tracking_mode = 'quantity' AND asset_code_prefix IS NULL) "
        "OR "
        "(tracking_mode = 'individual' AND asset_code_prefix IS NOT NULL)"
    )

    op.create_check_constraint(
        'ck_product_unit_value_nonnegative',
        'products',
        'unit_value IS NULL OR unit_value >= 0'
    )

    # UBICACIONES

    op.create_check_constraint(
        'ck_location_type',
        'locations',
        "location_type IN ('warehouse', 'shelf', 'area')"
    )

    op.create_check_constraint(
        'ck_location_parent_type',
        'locations',
        "(location_type = 'shelf' AND parent_id IS NOT NULL) "
        "OR "
        "(location_type IN ('warehouse', 'area') AND parent_id IS NULL)"
    )

    # ACTIVOS

    op.create_check_constraint(
        'ck_asset_review_status',
        'assets',
        "review_status IN ('pending', 'reviewed')"
    )

    op.create_check_constraint(
        'ck_asset_functional_status',
        'assets',
        "functional_status IN "
        "('unverified', 'functional', 'damaged', "
        "'under_repair', 'out_of_service')"
    )

    op.create_check_constraint(
        'ck_asset_lifecycle_status',
        'assets',
        "lifecycle_status IN ('in_stock', 'sold', 'disposed', 'lost')"
    )

    op.create_check_constraint(
        'ck_asset_value_nonnegative',
        'assets',
        'estimated_value IS NULL OR estimated_value >= 0'
    )

    # EXISTENCIAS

    op.create_check_constraint(
        'ck_stock_balance_nonnegative',
        'stock_balances',
        'quantity >= 0'
    )

    # MOVIMIENTOS

    op.create_check_constraint(
        'ck_stock_movement_type',
        'stock_movements',
        "movement_type IN ('entry', 'exit', 'count')"
    )

    op.create_check_constraint(
        'ck_stock_movement_quantity',
        'stock_movements',
        'quantity >= 0'
    )

    op.create_check_constraint(
        'ck_stock_movement_balances',
        'stock_movements',
        'quantity_before >= 0 AND quantity_after >= 0'
    )


def downgrade() -> None:
    """Downgrade schema."""

    # ========================================================
    # ELIMINAR RESTRICCIONES CHECK AGREGADAS
    # ========================================================

    op.drop_constraint(
        'ck_stock_movement_balances',
        'stock_movements',
        type_='check'
    )

    op.drop_constraint(
        'ck_stock_movement_quantity',
        'stock_movements',
        type_='check'
    )

    op.drop_constraint(
        'ck_stock_movement_type',
        'stock_movements',
        type_='check'
    )

    op.drop_constraint(
        'ck_stock_balance_nonnegative',
        'stock_balances',
        type_='check'
    )

    op.drop_constraint(
        'ck_asset_value_nonnegative',
        'assets',
        type_='check'
    )

    op.drop_constraint(
        'ck_asset_lifecycle_status',
        'assets',
        type_='check'
    )

    op.drop_constraint(
        'ck_asset_functional_status',
        'assets',
        type_='check'
    )

    op.drop_constraint(
        'ck_asset_review_status',
        'assets',
        type_='check'
    )

    op.drop_constraint(
        'ck_location_parent_type',
        'locations',
        type_='check'
    )

    op.drop_constraint(
        'ck_location_type',
        'locations',
        type_='check'
    )

    op.drop_constraint(
        'ck_product_unit_value_nonnegative',
        'products',
        type_='check'
    )

    op.drop_constraint(
        'ck_product_tracking_prefix',
        'products',
        type_='check'
    )

    op.drop_constraint(
        'ck_product_tracking_mode',
        'products',
        type_='check'
    )

    # ========================================================
    # RESTAURAR EXISTENCIAS
    # ========================================================

    op.alter_column(
        'stock_movements',
        'location_id',
        existing_type=sa.INTEGER(),
        nullable=False
    )

    op.drop_index(
        'uq_stock_balance_product_unknown_location',
        table_name='stock_balances',
        postgresql_where=sa.text('location_id IS NULL'),
        sqlite_where=sa.text('location_id IS NULL')
    )

    op.drop_index(
        'uq_stock_balance_product_location',
        table_name='stock_balances',
        postgresql_where=sa.text('location_id IS NOT NULL'),
        sqlite_where=sa.text('location_id IS NOT NULL')
    )

    op.create_unique_constraint(
        'uq_product_location_balance',
        'stock_balances',
        ['product_id', 'location_id']
    )

    op.alter_column(
        'stock_balances',
        'location_id',
        existing_type=sa.INTEGER(),
        nullable=False
    )

    # ========================================================
    # RESTAURAR REGISTROS DE IMPORTACIÓN
    # ========================================================

    op.alter_column(
        'source_records',
        'original_name',
        existing_type=sa.TEXT(),
        nullable=False
    )

    # ========================================================
    # RESTAURAR PRODUCTOS
    # ========================================================

    op.alter_column(
        'products',
        'category_id',
        existing_type=sa.INTEGER(),
        nullable=False
    )

    op.alter_column(
        'products',
        'name',
        existing_type=sa.VARCHAR(length=240),
        nullable=False
    )

    op.drop_column('products', 'value_currency')
    op.drop_column('products', 'unit_value')

    # ========================================================
    # RESTAURAR UBICACIONES
    # ========================================================

    op.drop_constraint(
        'locations_parent_id_fkey',
        'locations',
        type_='foreignkey'
    )

    op.drop_index(
        'uq_location_root_name',
        table_name='locations',
        postgresql_where=sa.text('parent_id IS NULL'),
        sqlite_where=sa.text('parent_id IS NULL')
    )

    op.drop_constraint(
        'uq_location_parent_name',
        'locations',
        type_='unique'
    )

    op.drop_index(
        op.f('ix_locations_parent_id'),
        table_name='locations'
    )

    op.create_index(
        op.f('ix_locations_name'),
        'locations',
        ['name'],
        unique=True
    )

    op.drop_column('locations', 'updated_at')
    op.drop_column('locations', 'created_at')
    op.drop_column('locations', 'parent_id')
    op.drop_column('locations', 'location_type')

    # ========================================================
    # RESTAURAR ACTIVOS
    # ========================================================

    op.drop_column('assets', 'archived_at')
    op.drop_column('assets', 'active')
    op.drop_column('assets', 'value_currency')
    op.drop_column('assets', 'estimated_value')

    # ========================================================
    # ELIMINAR TABLAS DE PROYECTOS
    # ========================================================

    op.drop_index(
        'uq_project_asset_single_active_project',
        table_name='project_assets',
        postgresql_where=sa.text('released_at IS NULL'),
        sqlite_where=sa.text('released_at IS NULL')
    )

    op.drop_index(
        'uq_project_asset_active',
        table_name='project_assets',
        postgresql_where=sa.text('released_at IS NULL'),
        sqlite_where=sa.text('released_at IS NULL')
    )

    op.drop_index(
        op.f('ix_project_assets_project_id'),
        table_name='project_assets'
    )

    op.drop_index(
        op.f('ix_project_assets_asset_id'),
        table_name='project_assets'
    )

    op.drop_table('project_assets')

    op.drop_index(
        'uq_project_product_active',
        table_name='project_products',
        postgresql_where=sa.text('released_at IS NULL'),
        sqlite_where=sa.text('released_at IS NULL')
    )

    op.drop_index(
        op.f('ix_project_products_project_id'),
        table_name='project_products'
    )

    op.drop_index(
        op.f('ix_project_products_product_id'),
        table_name='project_products'
    )

    op.drop_table('project_products')

    op.drop_index(
        op.f('ix_projects_name'),
        table_name='projects'
    )

    op.drop_table('projects')
