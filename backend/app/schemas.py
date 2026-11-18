from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# ============================================================
# CONFIGURACIÓN BASE
# ============================================================

class SchemaBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ReadSchema(SchemaBase):
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        extra="forbid",
    )


def empty_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def normalize_currency(value: str | None) -> str:
    normalized = (value or "PYG").strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise ValueError("La moneda debe ser un código de tres letras, por ejemplo PYG.")
    return normalized


# ============================================================
# CATEGORÍAS
# ============================================================

class CategoryBase(SchemaBase):
    name: str = Field(min_length=1, max_length=120)


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(CategoryBase):
    pass


class CategoryOut(ReadSchema):
    id: int
    name: str
    active: bool
    product_count: int = 0


# ============================================================
# TIPOS DE COMPONENTES
# ============================================================

class ComponentTypeBase(SchemaBase):
    name: str = Field(min_length=1, max_length=120)


class ComponentTypeCreate(ComponentTypeBase):
    pass


class ComponentTypeUpdate(ComponentTypeBase):
    pass


class ComponentTypeOut(ReadSchema):
    id: int
    name: str
    active: bool
    product_count: int = 0


# ============================================================
# CARACTERÍSTICAS TÉCNICAS CONFIGURABLES
# ============================================================

DataType = Literal["text", "number", "boolean", "date"]


class AttributeDefinitionCreate(SchemaBase):
    name: str = Field(min_length=1, max_length=120)
    data_type: DataType = "text"
    unit: str | None = Field(default=None, max_length=40)
    required: bool = False
    sort_order: int = 0

    @field_validator("unit", mode="before")
    @classmethod
    def normalize_unit(cls, value):
        return empty_to_none(value)


class AttributeDefinitionUpdate(SchemaBase):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    data_type: DataType | None = None
    unit: str | None = Field(default=None, max_length=40)
    required: bool | None = None
    sort_order: int | None = None

    @field_validator("name", "unit", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value):
        return empty_to_none(value)

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for field in ("name", "data_type", "required", "sort_order"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"El campo {field} no puede quedar vacío.")
        return self


class AttributeDefinitionOut(ReadSchema):
    id: int
    component_type_id: int
    name: str
    data_type: DataType
    unit: str | None
    required: bool
    active: bool
    sort_order: int


class AttributeValueIn(SchemaBase):
    attribute_definition_id: int = Field(gt=0)
    value: str


class AttributeValueOut(SchemaBase):
    definition_id: int
    name: str
    value: str
    unit: str | None = None


# ============================================================
# ESTADOS DE ACTIVOS
# ============================================================

FunctionalStatus = Literal[
    "unverified",
    "functional",
    "damaged",
]

LifecycleStatus = Literal["in_stock", "sold", "disposed", "lost"]
TrackingMode = Literal["quantity", "individual"]


# ============================================================
# PRODUCTOS / INVENTARIO GENERAL
# ============================================================

class ProductCreate(SchemaBase):
    # Los campos descriptivos pueden quedar vacíos durante el inventariado.
    name: str | None = Field(default=None, max_length=240)
    description: str | None = None
    brand: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=160)
    category_id: int | None = Field(default=None, gt=0)
    component_type_id: int | None = Field(default=None, gt=0)

    tracking_mode: TrackingMode = "quantity"
    asset_code_prefix: str | None = Field(
        default=None,
        min_length=2,
        max_length=10,
        pattern=r"^[A-Z0-9]+$",
    )

    unit_value: Decimal | None = Field(default=None, ge=0)
    value_currency: str = "PYG"

    attributes: list[AttributeValueIn] = Field(default_factory=list)

    @field_validator(
        "name", "description", "brand", "model", mode="before"
    )
    @classmethod
    def normalize_optional_text(cls, value):
        return empty_to_none(value)

    @field_validator("asset_code_prefix", mode="before")
    @classmethod
    def normalize_prefix(cls, value):
        if isinstance(value, str):
            value = value.strip().upper()
            return value or None
        return value

    @field_validator("value_currency", mode="before")
    @classmethod
    def validate_currency(cls, value):
        return normalize_currency(value)

    @model_validator(mode="after")
    def validate_tracking_configuration(self):
        if self.tracking_mode == "individual" and not self.asset_code_prefix:
            raise ValueError(
                "Los productos de seguimiento individual necesitan un prefijo de código."
            )
        if self.tracking_mode == "quantity" and self.asset_code_prefix is not None:
            raise ValueError(
                "Los productos administrados por cantidad no deben tener prefijo de código."
            )
        return self


class ProductUpdate(SchemaBase):
    # PUT parcial: los campos omitidos conservan sus valores actuales.
    name: str | None = Field(default=None, max_length=240)
    description: str | None = None
    brand: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=160)
    category_id: int | None = Field(default=None, gt=0)
    component_type_id: int | None = Field(default=None, gt=0)
    tracking_mode: TrackingMode | None = None
    asset_code_prefix: str | None = Field(
        default=None,
        min_length=2,
        max_length=10,
        pattern=r"^[A-Z0-9]+$",
    )
    unit_value: Decimal | None = Field(default=None, ge=0)
    value_currency: str | None = None
    attributes: list[AttributeValueIn] | None = None

    @field_validator(
        "name", "description", "brand", "model", "asset_code_prefix",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value):
        if isinstance(value, str) and value.strip() == "":
            return None
        if isinstance(value, str) and value == value.strip():
            return value
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("asset_code_prefix", mode="before")
    @classmethod
    def normalize_prefix(cls, value):
        if isinstance(value, str):
            value = value.strip().upper()
            return value or None
        return value

    @field_validator("value_currency", mode="before")
    @classmethod
    def validate_optional_currency(cls, value):
        if value is None:
            return None
        return normalize_currency(value)


class ProductOut(ReadSchema):
    id: int
    name: str | None = None
    description: str | None = None
    brand: str | None = None
    model: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    component_type_id: int | None = None
    component_type_name: str | None = None
    tracking_mode: TrackingMode
    asset_code_prefix: str | None = None
    unit_value: Decimal | None = None
    value_currency: str = "PYG"
    active: bool
    total_stock: Decimal | None = None
    stock_verified: bool = False
    source_count: int = 0
    search_aliases: list[str] = Field(default_factory=list)
    asset_count: int = 0
    assets: list["AssetSummaryOut"] = Field(default_factory=list)
    attributes: list[AttributeValueOut] = Field(default_factory=list)


# ============================================================
# ACTIVOS INDIVIDUALES
# ============================================================

class AssetSummaryOut(ReadSchema):
    id: int
    product_id: int | None = None
    product_name: str | None = None
    product_brand: str | None = None
    product_model: str | None = None
    asset_code: str
    manufacturer_serial: str | None = None
    manufacturer_brand: str | None = None
    project_names: list[str] = Field(default_factory=list)
    functional_status: FunctionalStatus
    lifecycle_status: LifecycleStatus
    observations: str | None = None
    location_id: int | None = None
    location_name: str | None = None
    estimated_value: Decimal | None = None
    value_currency: str = "PYG"
    active: bool = True


class AssetOut(AssetSummaryOut):
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


class AssetCreate(SchemaBase):
    # El producto es opcional mientras el activo no esté clasificado.
    # El prefijo se toma del producto o se indica directamente si no hay producto.
    product_id: int | None = Field(default=None, gt=0)
    asset_code_prefix: str | None = Field(
        default=None,
        min_length=2,
        max_length=10,
        pattern=r"^[A-Z0-9]+$",
    )
    manufacturer_serial: str | None = Field(default=None, max_length=100)
    manufacturer_brand: str | None = Field(default=None, max_length=120)
    functional_status: FunctionalStatus = "unverified"
    observations: str | None = None
    location_id: int | None = Field(default=None, gt=0)
    estimated_value: Decimal | None = Field(default=None, ge=0)
    value_currency: str = "PYG"

    @field_validator(
        "manufacturer_serial", "manufacturer_brand", "observations", mode="before"
    )
    @classmethod
    def normalize_optional_fields(cls, value):
        return empty_to_none(value)

    @field_validator("asset_code_prefix", mode="before")
    @classmethod
    def normalize_asset_prefix(cls, value):
        if isinstance(value, str):
            value = value.strip().upper()
            return value or None
        return value

    @field_validator("value_currency", mode="before")
    @classmethod
    def validate_currency(cls, value):
        return normalize_currency(value)

    @model_validator(mode="after")
    def validate_prefix_without_product(self):
        if self.product_id is None and not self.asset_code_prefix:
            raise ValueError(
                "Debés indicar un prefijo de código cuando el activo no tiene producto asociado."
            )
        return self


class AssetUpdate(SchemaBase):
    # Los campos omitidos conservan sus valores actuales.
    # product_id: null desasocia el activo sin modificar su código interno.
    product_id: int | None = Field(default=None, gt=0)
    manufacturer_serial: str | None = Field(default=None, max_length=100)
    manufacturer_brand: str | None = Field(default=None, max_length=120)
    functional_status: FunctionalStatus | None = None
    observations: str | None = None
    location_id: int | None = Field(default=None, gt=0)
    estimated_value: Decimal | None = Field(default=None, ge=0)
    value_currency: str | None = None

    @field_validator(
        "manufacturer_serial", "manufacturer_brand", "observations", mode="before"
    )
    @classmethod
    def normalize_optional_fields(cls, value):
        return empty_to_none(value)

    @field_validator("value_currency", mode="before")
    @classmethod
    def validate_optional_currency(cls, value):
        if value is None:
            return None
        return normalize_currency(value)


# ============================================================
# ASOCIACIONES ENTRE ACTIVOS
# ============================================================

class AssetRelationshipCreate(SchemaBase):
    target_asset_id: int = Field(gt=0)
    relationship_type: str = Field(
        min_length=2,
        max_length=40,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    note: str | None = None

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value):
        return empty_to_none(value)


class AssetRelationshipEnd(SchemaBase):
    note: str | None = None

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value):
        return empty_to_none(value)


class AssetRelationshipOut(ReadSchema):
    id: int
    source_asset_id: int
    target_asset_id: int
    relationship_type: str
    started_at: datetime
    ended_at: datetime | None = None
    note: str | None = None
    target_asset: AssetSummaryOut


class AssetDetailOut(AssetOut):
    active_relationships: list[AssetRelationshipOut] = Field(default_factory=list)
    relationship_history: list[AssetRelationshipOut] = Field(default_factory=list)


# ============================================================
# UBICACIONES
# ============================================================

LocationType = Literal["warehouse", "shelf", "area"]


class LocationCreate(SchemaBase):
    name: str = Field(min_length=1, max_length=120)
    location_type: LocationType
    parent_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_parent_configuration(self):
        if self.location_type == "shelf" and self.parent_id is None:
            raise ValueError("Una estantería debe pertenecer a un almacén.")
        if self.location_type in {"warehouse", "area"} and self.parent_id is not None:
            raise ValueError("Un almacén o área debe ser una ubicación principal.")
        return self


class LocationUpdate(SchemaBase):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    location_type: LocationType | None = None
    parent_id: int | None = Field(default=None, gt=0)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return empty_to_none(value)


class LocationOut(ReadSchema):
    id: int
    name: str
    location_type: LocationType
    parent_id: int | None = None
    parent_name: str | None = None
    active: bool
    children_count: int = 0


# ============================================================
# MOVIMIENTOS DE EXISTENCIAS
# ============================================================

MovementType = Literal["entry", "exit", "count"]


class MovementCreate(SchemaBase):
    location_id: int | None = Field(default=None, gt=0)
    movement_type: MovementType
    quantity: Decimal = Field(ge=0)
    note: str | None = None

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value):
        return empty_to_none(value)

    @model_validator(mode="after")
    def validate_quantity(self):
        if self.movement_type in {"entry", "exit"} and self.quantity <= 0:
            raise ValueError(
                "Los ingresos y extracciones deben tener una cantidad mayor que cero."
            )
        return self


class MovementOut(ReadSchema):
    id: int
    product_id: int
    location_id: int | None = None
    movement_type: MovementType
    quantity: Decimal
    quantity_before: Decimal
    quantity_after: Decimal
    note: str | None = None
    status: str
    created_by: str | None = None
    created_at: datetime


class StockTransferCreate(SchemaBase):
    source_location_id: int | None = Field(default=None, gt=0)
    destination_location_id: int | None = Field(default=None, gt=0)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    note: str | None = None

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value):
        return empty_to_none(value)

    @model_validator(mode="after")
    def validate_locations(self):
        if self.source_location_id == self.destination_location_id:
            raise ValueError("El origen y el destino deben ser diferentes.")
        return self


class StockTransferOut(ReadSchema):
    id: int
    product_id: int
    source_location_id: int | None = None
    source_location_name: str | None = None
    source_parent_name: str | None = None
    destination_location_id: int | None = None
    destination_location_name: str | None = None
    destination_parent_name: str | None = None
    quantity: Decimal
    source_quantity_before: Decimal
    source_quantity_after: Decimal
    destination_quantity_before: Decimal
    destination_quantity_after: Decimal
    note: str | None = None
    created_by: str | None = None
    created_at: datetime


class StockBalanceOut(ReadSchema):
    product_id: int
    location_id: int | None = None
    location_name: str | None = None
    parent_name: str | None = None
    location_type: LocationType | None = None
    quantity: Decimal
    verified: bool
    updated_at: datetime


# ============================================================
# PROYECTOS
# ============================================================

ProjectStatus = Literal[
    "planning", "active", "on_hold", "completed", "cancelled"
]


class ProjectCreate(SchemaBase):
    name: str = Field(min_length=1, max_length=180)
    description: str | None = None
    status: ProjectStatus = "planning"
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value):
        return empty_to_none(value)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("La fecha de finalización no puede ser anterior al inicio.")
        return self


class ProjectUpdate(SchemaBase):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = None
    status: ProjectStatus | None = None
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("name", "description", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        return empty_to_none(value)


class ProjectOut(ReadSchema):
    id: int
    name: str
    description: str | None = None
    status: ProjectStatus
    start_date: date | None = None
    end_date: date | None = None
    active: bool
    created_at: datetime
    updated_at: datetime
    asset_count: int = 0
    product_count: int = 0
    valuation_by_currency: dict[str, Decimal | None] = Field(default_factory=dict)
    valuation_complete: bool = False


class ProjectAssetAssign(SchemaBase):
    asset_id: int = Field(gt=0)
    note: str | None = None

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value):
        return empty_to_none(value)


class ProjectProductAssign(SchemaBase):
    product_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    note: str | None = None

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value):
        return empty_to_none(value)


class ProjectAssetsBatch(SchemaBase):
    asset_ids: list[int] = Field(min_length=1, max_length=100)

    @field_validator("asset_ids")
    @classmethod
    def validate_asset_ids(cls, ids):
        if any(asset_id <= 0 for asset_id in ids) or len(ids) != len(set(ids)):
            raise ValueError("Los activos deben ser positivos y no repetirse")
        return ids


class ProjectProductBatchItem(SchemaBase):
    product_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0)


class ProjectProductsBatch(SchemaBase):
    items: list[ProjectProductBatchItem] = Field(min_length=1, max_length=100)

    @field_validator("items")
    @classmethod
    def validate_product_ids(cls, items):
        ids = [item.product_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("No se puede seleccionar dos veces el mismo artículo")
        return items


class ProjectAssignmentEnd(SchemaBase):
    note: str | None = None

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value):
        return empty_to_none(value)


class ProjectAssetAssignmentOut(ReadSchema):
    id: int
    project_id: int
    asset_id: int
    assigned_at: datetime
    released_at: datetime | None = None
    note: str | None = None
    asset: AssetSummaryOut


class ProjectProductAssignmentOut(ReadSchema):
    id: int
    project_id: int
    product_id: int
    quantity: Decimal
    assigned_at: datetime
    released_at: datetime | None = None
    note: str | None = None
    product_name: str | None = None
    unit_value: Decimal | None = None
    value_currency: str = "PYG"


class ProjectDetailOut(ProjectOut):
    asset_assignments: list[ProjectAssetAssignmentOut] = Field(default_factory=list)
    product_assignments: list[ProjectProductAssignmentOut] = Field(default_factory=list)

# Resolver la referencia adelantada de ProductOut.assets.
# AssetSummaryOut se declara más abajo en el archivo.
ProductOut.model_rebuild()
