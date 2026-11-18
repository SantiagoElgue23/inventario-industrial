from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def audit_user_column():
    """Cuenta que realizó una operación. Se conserva el registro si la cuenta se elimina."""
    return mapped_column(ForeignKey("app_users.id", ondelete="SET NULL"), nullable=True, index=True)


def username_of(user: "AppUser | None") -> str | None:
    return user.username if user is not None else None


# ============================================================
# CATEGORÍAS
# ============================================================

class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    products: Mapped[list["Product"]] = relationship(back_populates="category")


# ============================================================
# TIPOS DE COMPONENTES
# ============================================================

class ComponentType(Base):
    __tablename__ = "component_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    products: Mapped[list["Product"]] = relationship(
        back_populates="component_type"
    )
    attributes: Mapped[list["AttributeDefinition"]] = relationship(
        back_populates="component_type",
        cascade="all, delete-orphan",
    )


# ============================================================
# CARACTERÍSTICAS TÉCNICAS CONFIGURABLES
# ============================================================

class AttributeDefinition(Base):
    __tablename__ = "attribute_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component_type_id: Mapped[int] = mapped_column(
        ForeignKey("component_types.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    data_type: Mapped[str] = mapped_column(
        String(20), default="text", nullable=False
    )
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    component_type: Mapped["ComponentType"] = relationship(
        back_populates="attributes"
    )
    values: Mapped[list["ProductAttributeValue"]] = relationship(
        back_populates="definition"
    )

    __table_args__ = (
        UniqueConstraint(
            "component_type_id",
            "name",
            name="uq_attribute_type_name",
        ),
    )


# ============================================================
# PRODUCTOS / CATÁLOGO GENERAL
# Un producto representa un tipo, modelo o referencia de inventario.
# No representa necesariamente una unidad física individual.
# ============================================================

class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Los datos descriptivos pueden quedar vacíos durante el inventariado.
    name: Mapped[str | None] = mapped_column(String(240), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand: Mapped[str | None] = mapped_column(
        String(120), nullable=True, index=True
    )
    model: Mapped[str | None] = mapped_column(
        String(160), nullable=True, index=True
    )

    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True, index=True
    )
    component_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("component_types.id"), nullable=True, index=True
    )

    # quantity: el producto se administra mediante existencias.
    # individual: sus unidades físicas se registran como Asset.
    tracking_mode: Mapped[str] = mapped_column(
        String(20), default="quantity", nullable=False
    )

    # Prefijo usado al generar códigos individuales: KR, SP, KRC, etc.
    asset_code_prefix: Mapped[str | None] = mapped_column(
        String(10), nullable=True, index=True
    )

    # Valor unitario de referencia. Puede quedar sin definir.
    unit_value: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    value_currency: Mapped[str] = mapped_column(
        String(3), default="PYG", nullable=False
    )

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    category: Mapped["Category | None"] = relationship(back_populates="products")
    component_type: Mapped["ComponentType | None"] = relationship(
        back_populates="products"
    )
    source_records: Mapped[list["SourceRecord"]] = relationship(
        back_populates="product"
    )
    attribute_values: Mapped[list["ProductAttributeValue"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    balances: Mapped[list["StockBalance"]] = relationship(
        back_populates="product"
    )
    movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="product"
    )
    transfers: Mapped[list["StockTransfer"]] = relationship(
        back_populates="product"
    )
    assets: Mapped[list["Asset"]] = relationship(back_populates="product")
    project_assignments: Mapped[list["ProjectProduct"]] = relationship(
        back_populates="product"
    )

    __table_args__ = (
        CheckConstraint(
            "tracking_mode IN ('quantity', 'individual')",
            name="ck_product_tracking_mode",
        ),
        CheckConstraint(
            "(tracking_mode = 'quantity' AND asset_code_prefix IS NULL) "
            "OR "
            "(tracking_mode = 'individual' AND asset_code_prefix IS NOT NULL)",
            name="ck_product_tracking_prefix",
        ),
        CheckConstraint(
            "unit_value IS NULL OR unit_value >= 0",
            name="ck_product_unit_value_nonnegative",
        ),
    )


# ============================================================
# VALORES DE CARACTERÍSTICAS TÉCNICAS
# ============================================================

class ProductAttributeValue(Base):
    __tablename__ = "product_attribute_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), index=True
    )
    attribute_definition_id: Mapped[int] = mapped_column(
        ForeignKey("attribute_definitions.id"), index=True
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)

    product: Mapped["Product"] = relationship(back_populates="attribute_values")
    definition: Mapped["AttributeDefinition"] = relationship(
        back_populates="values"
    )

    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "attribute_definition_id",
            name="uq_product_attribute",
        ),
    )


# ============================================================
# SECUENCIAS DE CÓDIGOS INTERNOS
# ============================================================

class AssetCodeSequence(Base):
    __tablename__ = "asset_code_sequences"

    prefix: Mapped[str] = mapped_column(String(10), primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


# ============================================================
# UBICACIONES JERÁRQUICAS
# Nivel 1: warehouse (Almacén 1 / Almacén 2) o area (Galpón).
# Nivel 2: shelf (estantería perteneciente a un almacén).
# ============================================================

class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    location_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id"), nullable=True, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    parent: Mapped["Location | None"] = relationship(
        back_populates="children",
        remote_side=lambda: [Location.id],
    )
    children: Mapped[list["Location"]] = relationship(
        back_populates="parent"
    )
    assets: Mapped[list["Asset"]] = relationship(back_populates="location")
    balances: Mapped[list["StockBalance"]] = relationship(
        back_populates="location"
    )
    movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="location"
    )

    __table_args__ = (
        CheckConstraint(
            "location_type IN ('warehouse', 'shelf', 'area')",
            name="ck_location_type",
        ),
        CheckConstraint(
            "(location_type = 'shelf' AND parent_id IS NOT NULL) "
            "OR "
            "(location_type IN ('warehouse', 'area') AND parent_id IS NULL)",
            name="ck_location_parent_type",
        ),
        UniqueConstraint(
            "parent_id",
            "name",
            name="uq_location_parent_name",
        ),
        Index(
            "uq_location_root_name",
            "name",
            unique=True,
            postgresql_where=text("parent_id IS NULL"),
            sqlite_where=text("parent_id IS NULL"),
        ),
    )


# ============================================================
# ACTIVOS INDIVIDUALES
# Un Asset puede existir temporalmente sin un Product asociado.
# Si tiene Product, este debe ser de seguimiento individual.
# El número de serie del fabricante es opcional.
# El código interno se genera automáticamente y es obligatorio.
# ============================================================

class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # El activo puede existir sin estar asociado a un producto.
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id"),
        nullable=True,
        index=True,
    )

    asset_code: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )

    manufacturer_serial: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )

    manufacturer_brand: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )

    functional_status: Mapped[str] = mapped_column(
        String(30), default="unverified", nullable=False
    )

    lifecycle_status: Mapped[str] = mapped_column(
        String(30), default="in_stock", nullable=False
    )

    observations: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id"), nullable=True, index=True
    )

    # Valor específico de esta unidad.
    # Si es NULL, se puede utilizar el valor del producto asociado.
    estimated_value: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )

    value_currency: Mapped[str] = mapped_column(
        String(3), default="PYG", nullable=False
    )

    active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    # Relaciones
    product: Mapped["Product | None"] = relationship(
        back_populates="assets"
    )

    location: Mapped["Location | None"] = relationship(
        back_populates="assets"
    )

    source_records: Mapped[list["SourceRecord"]] = relationship(
        back_populates="asset",
        foreign_keys="SourceRecord.asset_id",
    )

    relationships_as_parent: Mapped[list["AssetRelationship"]] = relationship(
        back_populates="source_asset",
        foreign_keys="AssetRelationship.source_asset_id",
    )

    relationships_as_component: Mapped[list["AssetRelationship"]] = relationship(
        back_populates="target_asset",
        foreign_keys="AssetRelationship.target_asset_id",
    )

    project_assignments: Mapped[list["ProjectAsset"]] = relationship(
        back_populates="asset"
    )

    __table_args__ = (
        UniqueConstraint(
            "manufacturer_brand",
            "manufacturer_serial",
            name="uq_asset_brand_serial",
        ),
        CheckConstraint(
            "functional_status IN "
            "('unverified', 'functional', 'damaged')",
            name="ck_asset_functional_status",
        ),
        CheckConstraint(
            "lifecycle_status IN ('in_stock', 'sold', 'disposed', 'lost')",
            name="ck_asset_lifecycle_status",
        ),
        CheckConstraint(
            "estimated_value IS NULL OR estimated_value >= 0",
            name="ck_asset_value_nonnegative",
        ),
    )


# ============================================================
# ASOCIACIONES ENTRE ACTIVOS
# Ejemplo: robot -> controlador / SmartPad / manojo de cables.
# ============================================================

class AssetRelationship(Base):
    __tablename__ = "asset_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id"), nullable=False, index=True
    )
    target_asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    source_asset: Mapped["Asset"] = relationship(
        back_populates="relationships_as_parent",
        foreign_keys=[source_asset_id],
    )
    target_asset: Mapped["Asset"] = relationship(
        back_populates="relationships_as_component",
        foreign_keys=[target_asset_id],
    )

    __table_args__ = (
        CheckConstraint(
            "source_asset_id <> target_asset_id",
            name="ck_asset_relationship_not_self",
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_asset_relationship_dates",
        ),
        Index(
            "uq_asset_relationship_active_role",
            "source_asset_id",
            "relationship_type",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
            sqlite_where=text("ended_at IS NULL"),
        ),
        Index(
            "uq_asset_relationship_active_target",
            "target_asset_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
            sqlite_where=text("ended_at IS NULL"),
        ),
    )


# ============================================================
# REFERENCIAS ORIGINALES DE INVENTREE / IMPORTACIÓN
# ============================================================

class SourceRecord(Base):
    __tablename__ = "source_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_system: Mapped[str] = mapped_column(
        String(40), default="InvenTree", nullable=False
    )
    source_id: Mapped[str] = mapped_column(
        String(80), unique=True, index=True, nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), index=True, nullable=False
    )
    original_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_category: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )
    legacy_stock_reference: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 3), nullable=True
    )
    serial_candidate: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("assets.id"), nullable=True, index=True
    )
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    product: Mapped["Product"] = relationship(back_populates="source_records")
    asset: Mapped["Asset | None"] = relationship(
        back_populates="source_records",
        foreign_keys=[asset_id],
    )


# ============================================================
# EXISTENCIAS POR CANTIDAD
# location_id puede ser NULL mientras la ubicación no esté identificada.
# ============================================================

class StockBalance(Base):
    __tablename__ = "stock_balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), index=True, nullable=False
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id"), index=True, nullable=True
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("0"), nullable=False
    )
    verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    product: Mapped["Product"] = relationship(back_populates="balances")
    location: Mapped["Location | None"] = relationship(back_populates="balances")

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_stock_balance_nonnegative"),
        Index(
            "uq_stock_balance_product_location",
            "product_id",
            "location_id",
            unique=True,
            postgresql_where=text("location_id IS NOT NULL"),
            sqlite_where=text("location_id IS NOT NULL"),
        ),
        Index(
            "uq_stock_balance_product_unknown_location",
            "product_id",
            unique=True,
            postgresql_where=text("location_id IS NULL"),
            sqlite_where=text("location_id IS NULL"),
        ),
    )


# ============================================================
# HISTORIAL DE MOVIMIENTOS DE STOCK
# ============================================================

class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), index=True, nullable=False
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id"), index=True, nullable=True
    )
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    quantity_before: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False
    )
    quantity_after: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="approved", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    created_by_id: Mapped[int | None] = audit_user_column()
    created_by_user: Mapped["AppUser | None"] = relationship(foreign_keys=[created_by_id])

    @property
    def created_by(self) -> str | None:
        return username_of(self.created_by_user)

    product: Mapped["Product"] = relationship(back_populates="movements")
    location: Mapped["Location | None"] = relationship(back_populates="movements")

    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('entry', 'exit', 'count')",
            name="ck_stock_movement_type",
        ),
        CheckConstraint("quantity >= 0", name="ck_stock_movement_quantity"),
        CheckConstraint(
            "quantity_before >= 0 AND quantity_after >= 0",
            name="ck_stock_movement_balances",
        ),
    )


# ============================================================
# TRASLADOS ENTRE UBICACIONES
# Un traslado se registra como una única operación auditada.
# ============================================================

class StockTransfer(Base):
    __tablename__ = "stock_transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), index=True, nullable=False
    )
    source_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id"), index=True, nullable=True
    )
    destination_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id"), index=True, nullable=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    source_quantity_before: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False
    )
    source_quantity_after: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False
    )
    destination_quantity_before: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False
    )
    destination_quantity_after: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    created_by_id: Mapped[int | None] = audit_user_column()
    created_by_user: Mapped["AppUser | None"] = relationship(foreign_keys=[created_by_id])

    @property
    def created_by(self) -> str | None:
        return username_of(self.created_by_user)

    product: Mapped["Product"] = relationship(back_populates="transfers")
    source_location: Mapped["Location | None"] = relationship(
        foreign_keys=[source_location_id]
    )
    destination_location: Mapped["Location | None"] = relationship(
        foreign_keys=[destination_location_id]
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_stock_transfer_quantity"),
        CheckConstraint(
            "source_quantity_before >= 0 AND source_quantity_after >= 0 "
            "AND destination_quantity_before >= 0 "
            "AND destination_quantity_after >= 0",
            name="ck_stock_transfer_balances",
        ),
        CheckConstraint(
            "NOT (source_location_id IS NULL AND destination_location_id IS NULL) "
            "AND (source_location_id IS NULL OR destination_location_id IS NULL "
            "OR source_location_id <> destination_location_id)",
            name="ck_stock_transfer_distinct_locations",
        ),
    )


# ============================================================
# PROYECTOS
# ============================================================

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="planning", nullable=False
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    asset_assignments: Mapped[list["ProjectAsset"]] = relationship(
        back_populates="project"
    )
    product_assignments: Mapped[list["ProjectProduct"]] = relationship(
        back_populates="project"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('planning', 'active', 'on_hold', 'completed', 'cancelled')",
            name="ck_project_status",
        ),
        CheckConstraint(
            "start_date IS NULL OR end_date IS NULL OR end_date >= start_date",
            name="ck_project_dates",
        ),
    )


class ProjectAsset(Base):
    __tablename__ = "project_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True, nullable=False
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id"), index=True, nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="asset_assignments")
    asset: Mapped["Asset"] = relationship(back_populates="project_assignments")

    __table_args__ = (
        CheckConstraint(
            "released_at IS NULL OR released_at >= assigned_at",
            name="ck_project_asset_dates",
        ),
        Index(
            "uq_project_asset_active",
            "project_id",
            "asset_id",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
            sqlite_where=text("released_at IS NULL"),
        ),
        Index(
            "uq_project_asset_single_active_project",
            "asset_id",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
            sqlite_where=text("released_at IS NULL"),
        ),
    )


class ProjectProduct(Base):
    __tablename__ = "project_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True, nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), index=True, nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="product_assignments")
    product: Mapped["Product"] = relationship(
        back_populates="project_assignments"
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_project_product_quantity"),
        CheckConstraint(
            "released_at IS NULL OR released_at >= assigned_at",
            name="ck_project_product_dates",
        ),
        Index(
            "uq_project_product_active",
            "project_id",
            "product_id",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
            sqlite_where=text("released_at IS NULL"),
        ),
    )

# ============================================================
# TRABAJOS - recursos temporalmente fuera del almacén
# ============================================================

class Work(Base):
    __tablename__ = "works"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    responsible: Mapped[str | None] = mapped_column(String(120))
    planned_out_date: Mapped[date | None] = mapped_column(Date)
    planned_return_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    departed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    close_note: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = audit_user_column()
    closed_by_id: Mapped[int | None] = audit_user_column()
    created_by_user: Mapped["AppUser | None"] = relationship(foreign_keys=[created_by_id])
    closed_by_user: Mapped["AppUser | None"] = relationship(foreign_keys=[closed_by_id])

    project: Mapped["Project"] = relationship()
    products: Mapped[list["WorkProductLine"]] = relationship(back_populates="work")
    assets: Mapped[list["WorkAssetLine"]] = relationship(back_populates="work")

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'open', 'closed')", name="ck_work_status"),
        CheckConstraint(
            "planned_out_date IS NULL OR planned_return_date IS NULL OR planned_return_date >= planned_out_date",
            name="ck_work_planned_dates",
        ),
    )


class WorkProductLine(Base):
    __tablename__ = "work_product_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    origin_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    returned_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal("0"))
    consumed_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal("0"))
    lost_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal("0"))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatched_by_id: Mapped[int | None] = audit_user_column()
    dispatched_by_user: Mapped["AppUser | None"] = relationship(foreign_keys=[dispatched_by_id])
    product_name_snapshot: Mapped[str] = mapped_column(String(240), nullable=False)
    location_name_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    unit_value_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    value_currency_snapshot: Mapped[str] = mapped_column(String(3), nullable=False)

    work: Mapped["Work"] = relationship(back_populates="products")
    product: Mapped["Product"] = relationship()
    location: Mapped["Location | None"] = relationship()
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_work_product_quantity"),
        CheckConstraint("returned_quantity >= 0 AND consumed_quantity >= 0 AND lost_quantity >= 0", name="ck_work_product_nonnegative"),
        CheckConstraint("returned_quantity + consumed_quantity + lost_quantity <= quantity", name="ck_work_product_reconciled"),
    )


class WorkAssetLine(Base):
    __tablename__ = "work_asset_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    origin_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatched_by_id: Mapped[int | None] = audit_user_column()
    dispatched_by_user: Mapped["AppUser | None"] = relationship(foreign_keys=[dispatched_by_id])
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    asset_code_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_name_snapshot: Mapped[str] = mapped_column(String(240), nullable=False)
    serial_snapshot: Mapped[str | None] = mapped_column(String(100))

    work: Mapped["Work"] = relationship(back_populates="assets")
    asset: Mapped["Asset"] = relationship()
    location: Mapped["Location | None"] = relationship(foreign_keys=[origin_location_id])
    __table_args__ = (
        CheckConstraint("returned_at IS NULL OR dispatched_at IS NOT NULL", name="ck_work_asset_returned_only_if_out"),
        Index("uq_work_asset_outstanding", "asset_id", unique=True,
              postgresql_where=text("returned_at IS NULL"),
              sqlite_where=text("returned_at IS NULL")),
    )


class WorkReturnEvent(Base):
    __tablename__ = "work_return_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), nullable=False, index=True)
    product_line_id: Mapped[int | None] = mapped_column(ForeignKey("work_product_lines.id"))
    asset_line_id: Mapped[int | None] = mapped_column(ForeignKey("work_asset_lines.id"))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    returned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_by_id: Mapped[int | None] = audit_user_column()

    __table_args__ = (
        CheckConstraint(
            "(product_line_id IS NOT NULL AND asset_line_id IS NULL AND quantity > 0) OR "
            "(product_line_id IS NULL AND asset_line_id IS NOT NULL AND quantity IS NULL)",
            name="ck_work_return_event_kind",
        ),
    )


# Cuentas personales. No se crean contraseñas por defecto.
# El rol master solo se asigna por consola (backend/app/auth_bootstrap.py).
class AppUser(Base):
    __tablename__ = "app_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user", server_default="user")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sessions: Mapped[list["AppSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("role IN ('master', 'admin', 'user')", name="ck_app_user_role"),
    )


class AppSession(Base):
    __tablename__ = "app_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user: Mapped[AppUser] = relationship(back_populates="sessions")
