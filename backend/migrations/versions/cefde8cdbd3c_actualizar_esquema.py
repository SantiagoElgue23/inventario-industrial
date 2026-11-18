
"""Actualizar esquema

Revision ID: cefde8cdbd3c
Revises:
Create Date: 2026-11-05 09:35:40.451201

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cefde8cdbd3c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Actualizar la estructura de PostgreSQL."""

    # ========================================================
    # TABLA: SECUENCIAS DE CÓDIGOS INTERNOS
    # ========================================================

    op.create_table(
        'asset_code_sequences',
        sa.Column('prefix', sa.String(length=10), nullable=False),
        sa.Column('last_value', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('prefix')
    )

    # ========================================================
    # TABLA: RELACIONES ENTRE ACTIVOS
    # ========================================================

    op.create_table(
        'asset_relationships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_asset_id', sa.Integer(), nullable=False),
        sa.Column('target_asset_id', sa.Integer(), nullable=False),
        sa.Column('relationship_type', sa.String(length=40), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),

        sa.CheckConstraint(
            'ended_at IS NULL OR ended_at >= started_at',
            name='ck_asset_relationship_dates'
        ),

        sa.CheckConstraint(
            'source_asset_id <> target_asset_id',
            name='ck_asset_relationship_not_self'
        ),

        sa.ForeignKeyConstraint(
            ['source_asset_id'],
            ['assets.id']
        ),

        sa.ForeignKeyConstraint(
            ['target_asset_id'],
            ['assets.id']
        ),

        sa.PrimaryKeyConstraint('id')
    )

    op.create_index(
        op.f('ix_asset_relationships_source_asset_id'),
        'asset_relationships',
        ['source_asset_id'],
        unique=False
    )

    op.create_index(
        op.f('ix_asset_relationships_target_asset_id'),
        'asset_relationships',
        ['target_asset_id'],
        unique=False
    )

    op.create_index(
        'uq_asset_relationship_active_role',
        'asset_relationships',
        ['source_asset_id', 'relationship_type'],
        unique=True,
        postgresql_where=sa.text('ended_at IS NULL'),
        sqlite_where=sa.text('ended_at IS NULL')
    )

    op.create_index(
        'uq_asset_relationship_active_target',
        'asset_relationships',
        ['target_asset_id'],
        unique=True,
        postgresql_where=sa.text('ended_at IS NULL'),
        sqlite_where=sa.text('ended_at IS NULL')
    )

    # ========================================================
    # ACTUALIZAR TABLA: ASSETS
    # ========================================================

    op.add_column(
        'assets',
        sa.Column('asset_code', sa.String(length=32), nullable=False)
    )

    op.add_column(
        'assets',
        sa.Column('manufacturer_serial', sa.String(length=100), nullable=True)
    )

    op.add_column(
        'assets',
        sa.Column('manufacturer_brand', sa.String(length=120), nullable=True)
    )

    op.add_column(
        'assets',
        sa.Column('review_status', sa.String(length=30), nullable=False)
    )

    op.add_column(
        'assets',
        sa.Column('functional_status', sa.String(length=30), nullable=False)
    )

    op.add_column(
        'assets',
        sa.Column('lifecycle_status', sa.String(length=30), nullable=False)
    )

    op.add_column(
        'assets',
        sa.Column('location_id', sa.Integer(), nullable=True)
    )

    op.add_column(
        'assets',
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)
    )

    op.alter_column(
        'assets',
        'product_id',
        existing_type=sa.INTEGER(),
        nullable=False
    )

    # Eliminar restricciones e índices antiguos.

    op.drop_index(
        op.f('ix_assets_serial_number'),
        table_name='assets'
    )

    op.drop_constraint(
        op.f('uq_asset_brand_serial'),
        'assets',
        type_='unique'
    )

    # Crear nueva restricción para fabricante y número de serie.

    op.create_unique_constraint(
        'uq_asset_brand_serial',
        'assets',
        ['manufacturer_brand', 'manufacturer_serial']
    )

    # Crear nuevos índices.

    op.create_index(
        op.f('ix_assets_asset_code'),
        'assets',
        ['asset_code'],
        unique=True
    )

    op.create_index(
        op.f('ix_assets_location_id'),
        'assets',
        ['location_id'],
        unique=False
    )

    op.create_index(
        op.f('ix_assets_manufacturer_serial'),
        'assets',
        ['manufacturer_serial'],
        unique=False
    )

    # Crear clave foránea con nombre explícito.

    op.create_foreign_key(
        'fk_assets_location_id_locations',
        'assets',
        'locations',
        ['location_id'],
        ['id']
    )

    # Eliminar columnas antiguas.

    op.drop_column('assets', 'serial_number')
    op.drop_column('assets', 'brand')
    op.drop_column('assets', 'status')

    # ========================================================
    # ACTUALIZAR TABLA: PRODUCTS
    # ========================================================

    op.add_column(
        'products',
        sa.Column('tracking_mode', sa.String(length=20), nullable=False)
    )

    op.add_column(
        'products',
        sa.Column('asset_code_prefix', sa.String(length=10), nullable=True)
    )

    # Eliminar código interno antiguo de productos.

    op.drop_index(
        op.f('ix_products_code'),
        table_name='products'
    )

    op.create_index(
        op.f('ix_products_asset_code_prefix'),
        'products',
        ['asset_code_prefix'],
        unique=False
    )

    op.drop_column('products', 'code')


def downgrade() -> None:
    """Revertir la migración."""

    # ========================================================
    # REVERTIR TABLA: PRODUCTS
    # ========================================================

    op.add_column(
        'products',
        sa.Column(
            'code',
            sa.VARCHAR(length=24),
            autoincrement=False,
            nullable=False
        )
    )

    op.drop_index(
        op.f('ix_products_asset_code_prefix'),
        table_name='products'
    )

    op.create_index(
        op.f('ix_products_code'),
        'products',
        ['code'],
        unique=True
    )

    op.drop_column('products', 'asset_code_prefix')
    op.drop_column('products', 'tracking_mode')

    # ========================================================
    # REVERTIR TABLA: ASSETS
    # ========================================================

    op.add_column(
        'assets',
        sa.Column(
            'status',
            sa.VARCHAR(length=40),
            autoincrement=False,
            nullable=False
        )
    )

    op.add_column(
        'assets',
        sa.Column(
            'brand',
            sa.VARCHAR(length=120),
            autoincrement=False,
            nullable=True
        )
    )

    op.add_column(
        'assets',
        sa.Column(
            'serial_number',
            sa.VARCHAR(length=100),
            autoincrement=False,
            nullable=False
        )
    )

    # Eliminar clave foránea de ubicación.

    op.drop_constraint(
        'fk_assets_location_id_locations',
        'assets',
        type_='foreignkey'
    )

    op.drop_index(
        op.f('ix_assets_manufacturer_serial'),
        table_name='assets'
    )

    op.drop_index(
        op.f('ix_assets_location_id'),
        table_name='assets'
    )

    op.drop_index(
        op.f('ix_assets_asset_code'),
        table_name='assets'
    )

    op.drop_constraint(
        'uq_asset_brand_serial',
        'assets',
        type_='unique'
    )

    # Restaurar restricción anterior.

    op.create_unique_constraint(
        op.f('uq_asset_brand_serial'),
        'assets',
        ['brand', 'serial_number'],
        postgresql_nulls_not_distinct=False
    )

    op.create_index(
        op.f('ix_assets_serial_number'),
        'assets',
        ['serial_number'],
        unique=False
    )

    op.alter_column(
        'assets',
        'product_id',
        existing_type=sa.INTEGER(),
        nullable=True
    )

    # Eliminar columnas nuevas.

    op.drop_column('assets', 'updated_at')
    op.drop_column('assets', 'location_id')
    op.drop_column('assets', 'lifecycle_status')
    op.drop_column('assets', 'functional_status')
    op.drop_column('assets', 'review_status')
    op.drop_column('assets', 'manufacturer_brand')
    op.drop_column('assets', 'manufacturer_serial')
    op.drop_column('assets', 'asset_code')

    # ========================================================
    # ELIMINAR TABLAS NUEVAS
    # ========================================================

    op.drop_index(
        'uq_asset_relationship_active_target',
        table_name='asset_relationships',
        postgresql_where=sa.text('ended_at IS NULL'),
        sqlite_where=sa.text('ended_at IS NULL')
    )

    op.drop_index(
        'uq_asset_relationship_active_role',
        table_name='asset_relationships',
        postgresql_where=sa.text('ended_at IS NULL'),
        sqlite_where=sa.text('ended_at IS NULL')
    )

    op.drop_index(
        op.f('ix_asset_relationships_target_asset_id'),
        table_name='asset_relationships'
    )

    op.drop_index(
        op.f('ix_asset_relationships_source_asset_id'),
        table_name='asset_relationships'
    )

    op.drop_table('asset_relationships')
    op.drop_table('asset_code_sequences')
