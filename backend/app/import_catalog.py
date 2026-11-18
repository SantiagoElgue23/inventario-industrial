"""
Importación controlada del catálogo desde el Excel de depuración.

Lee únicamente la hoja "Depuracion".
- Conserva una SourceRecord por cada ID original de InvenTree.
- Crea categorías y tipos reutilizando los ya existentes.
- No fusiona candidatos a duplicados.
- Agrupa las filas de tipo "Robot" por modelo comercial para el módulo Robots.
- Crea activos únicamente cuando existe un número de serie identificable.
- No importa stock como existencia real.
- No crea ni modifica ubicaciones, proyectos, movimientos ni balances.

Uso desde la carpeta backend:
    python -m app.import_catalog --file import_data/catalogo.xlsx
    python -m app.import_catalog --file import_data/catalogo.xlsx --apply

La primera orden ejecuta una simulación sin escribir en la base de datos.
La segunda aplica la importación en una única transacción.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from numbers import Integral, Real
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import case, inspect, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .database import SessionLocal, engine
from . import models as m


SHEET_NAME = "Depuracion"
DUPLICATE_SHEET_NAME = "Posibles duplicados"

COL_SOURCE_ID = "ID InvenTree (no modificar)"
COL_ORIGINAL_NAME = "Nombre original (no modificar)"
COL_ORIGINAL_CATEGORY = "Categoría original (no modificar)"
COL_NAME = "Nombre propuesto"
COL_DESCRIPTION = "Descripción propuesta"
COL_BRAND = "Marca"
COL_MODEL = "Modelo"
COL_CATEGORY = "Categoría propuesta"
COL_COMPONENT_TYPE = "Tipo de componente"
COL_LEGACY_STOCK = "Stock total original (solo referencia)"

REQUIRED_COLUMNS = [
    COL_SOURCE_ID,
    COL_ORIGINAL_NAME,
    COL_ORIGINAL_CATEGORY,
    COL_NAME,
    COL_DESCRIPTION,
    COL_BRAND,
    COL_MODEL,
    COL_CATEGORY,
    COL_COMPONENT_TYPE,
    COL_LEGACY_STOCK,
]

INDIVIDUAL_CATEGORY = "Robots y equipamiento industrial"
ROBOT_COMPONENT_TYPE = "Robot"

REQUIRED_TABLE_COLUMNS = {
    "categories": {"id", "name", "active"},
    "component_types": {"id", "name", "active"},
    "products": {
        "id", "name", "description", "brand", "model", "category_id",
        "component_type_id", "tracking_mode", "asset_code_prefix",
        "unit_value", "value_currency", "active",
    },
    "assets": {
        "id", "product_id", "asset_code", "manufacturer_serial",
        "manufacturer_brand", "functional_status",
        "lifecycle_status", "observations", "location_id",
        "estimated_value", "value_currency", "active",
    },
    "asset_code_sequences": {"prefix", "last_value", "updated_at"},
    "source_records": {
        "id", "source_system", "source_id", "product_id", "original_name",
        "original_category", "legacy_stock_reference", "serial_candidate",
        "asset_id", "raw_data",
    },
}


def clean(value: Any) -> str | None:
    """Convierte celdas vacías a None y conserva el texto original limpio."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text or None


def normalized_key(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.casefold().split())


def source_id_text(value: Any) -> str:
    if value is None or pd.isna(value):
        raise ValueError("Se encontró una fila sin ID de InvenTree.")
    if isinstance(value, Integral):
        return str(int(value))
    if isinstance(value, Real) and math.isfinite(float(value)) and float(value).is_integer():
        return str(int(value))
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]
    if not text:
        raise ValueError("Se encontró una fila sin ID de InvenTree.")
    return text


def serial_text(value: Any) -> str | None:
    """Solo se usa para filas de tipo Robot: Modelo contiene el serial."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, Integral):
        text = str(int(value))
    elif isinstance(value, Real) and math.isfinite(float(value)) and float(value).is_integer():
        text = str(int(value))
    else:
        text = str(value).strip()
        if re.fullmatch(r"\d+\.0+", text):
            text = text.split(".", 1)[0]

    return text if re.fullmatch(r"\d{4,}", text) else None


def decimal_or_none(value: Any) -> Decimal | None:
    text = clean(value)
    if text is None:
        return None
    try:
        number = Decimal(text.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"Valor numérico no válido en stock de referencia: {text!r}") from exc
    if not number.is_finite():
        raise ValueError(f"Valor no finito en stock de referencia: {text!r}")
    return number


def json_safe_value(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if hasattr(value, "item") and callable(value.item):
        try:
            value = value.item()
        except (ValueError, TypeError):
            pass

    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    if isinstance(value, (str, int, float)):
        return value
    return str(value)


def json_safe_row(row: pd.Series) -> dict[str, Any]:
    return {str(key): json_safe_value(value) for key, value in row.items()}


def ascii_slug(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Z0-9]", "", ascii_text.upper())


def make_asset_prefix(
    name: str | None,
    model: str | None,
    component_type: str | None,
) -> str:
    """Genera prefijos de código legibles, estables y válidos para la API."""
    type_key = normalized_key(component_type)

    if type_key == "robot":
        tokens = re.findall(r"[A-Z0-9]+", unicodedata.normalize(
            "NFKD", name or ""
        ).encode("ascii", "ignore").decode("ascii").upper())
        candidate = "".join(tokens[:2])[:10]
        return candidate if len(candidate) >= 2 else "ROB"

    if "smartpad" in type_key or "smart pad" in type_key:
        return "SP"

    if type_key == "controlador de robot":
        candidate = ascii_slug(model or name)[:10]
        return candidate if len(candidate) >= 2 else "KRC"

    if type_key == "partes de controladores":
        candidate = ascii_slug(model or name)[:10]
        return candidate if len(candidate) >= 2 else "KSD"

    if type_key == "cables":
        return "CAB"

    if type_key == "fuente de alimentacion":
        candidate = ascii_slug(model)[:10]
        return candidate if len(candidate) >= 2 else "FUE"

    if type_key == "placas electronicas varias":
        candidate = ascii_slug(model)[:10]
        return candidate if len(candidate) >= 2 else "PCB"

    candidate = ascii_slug(model or name)[:10]
    if len(candidate) < 2:
        candidate = ascii_slug(component_type)[:10]
    return candidate if len(candidate) >= 2 else "EQ"


def validate_database_schema() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    missing_tables = sorted(set(REQUIRED_TABLE_COLUMNS) - existing_tables)
    if missing_tables:
        raise RuntimeError(
            "Faltan tablas de la migración actual: "
            + ", ".join(missing_tables)
            + ". No se ejecutará create_all ni se modificará el esquema. "
              "Verificá primero que Alembic esté en head."
        )

    problems: list[str] = []
    for table, required_columns in REQUIRED_TABLE_COLUMNS.items():
        existing_columns = {column["name"] for column in inspector.get_columns(table)}
        missing_columns = sorted(required_columns - existing_columns)
        if missing_columns:
            problems.append(f"{table}: {', '.join(missing_columns)}")

    if problems:
        raise RuntimeError(
            "El esquema de la base de datos no coincide con los modelos actuales: "
            + "; ".join(problems)
            + ". No se realizó ningún cambio."
        )


def load_and_validate_workbook(path: Path) -> tuple[pd.DataFrame, int]:
    if not path.exists():
        raise FileNotFoundError(
            f"No se encontró el Excel: {path.resolve()}"
        )

    workbook = pd.ExcelFile(path)
    if SHEET_NAME not in workbook.sheet_names:
        raise ValueError(f"El Excel no contiene la hoja {SHEET_NAME!r}.")

    frame = pd.read_excel(path, sheet_name=SHEET_NAME)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(
            "Faltan columnas requeridas en el Excel: " + ", ".join(missing)
        )

    if frame.empty:
        raise ValueError("La hoja de depuración no contiene registros.")

    source_ids = [source_id_text(value) for value in frame[COL_SOURCE_ID]]
    if len(source_ids) != len(set(source_ids)):
        duplicates = sorted({
            item for item in source_ids if source_ids.count(item) > 1
        })
        raise ValueError(
            "Hay IDs de InvenTree repetidos en la hoja principal: "
            + ", ".join(duplicates[:20])
        )

    if frame[COL_NAME].map(clean).isna().any():
        raise ValueError("Hay registros sin Nombre propuesto.")

    if frame[COL_CATEGORY].map(clean).isna().any():
        raise ValueError("Hay registros sin Categoría propuesta.")

    # Si la hoja original está presente, comprobar que contiene los mismos IDs.
    if "Original InvenTree" in workbook.sheet_names:
        original = pd.read_excel(path, sheet_name="Original InvenTree")
        if "ID" in original.columns:
            original_ids = {
                source_id_text(value)
                for value in original["ID"]
                if clean(value) is not None
            }
            if original_ids != set(source_ids):
                missing_in_original = sorted(set(source_ids) - original_ids)
                missing_in_review = sorted(original_ids - set(source_ids))
                raise ValueError(
                    "Los IDs de 'Depuracion' no coinciden con "
                    "'Original InvenTree'. "
                    f"Faltan en original: {missing_in_original[:10]}; "
                    f"faltan en depuración: {missing_in_review[:10]}."
                )

    duplicate_pair_count = 0
    if DUPLICATE_SHEET_NAME in workbook.sheet_names:
        duplicate_frame = pd.read_excel(path, sheet_name=DUPLICATE_SHEET_NAME)
        duplicate_pair_count = len(duplicate_frame)

    return frame, duplicate_pair_count


def build_import_plan(frame: pd.DataFrame) -> dict[str, Any]:
    category_names: dict[str, str] = {}
    component_type_names: dict[str, str] = {}
    product_groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []

    for _, excel_row in frame.iterrows():
        raw = excel_row.to_dict()
        source_id = source_id_text(excel_row[COL_SOURCE_ID])

        name = clean(excel_row[COL_NAME]) or clean(excel_row[COL_ORIGINAL_NAME])
        if not name:
            name = f"Artículo InvenTree {source_id}"

        description = clean(excel_row[COL_DESCRIPTION])
        brand = clean(excel_row[COL_BRAND])
        model_value = clean(excel_row[COL_MODEL])
        category_name = clean(excel_row[COL_CATEGORY])
        component_type_name = clean(excel_row[COL_COMPONENT_TYPE])

        category_key = normalized_key(category_name)
        type_key = normalized_key(component_type_name)
        category_names[category_key] = category_name
        if component_type_name:
            component_type_names[type_key] = component_type_name

        is_robot = type_key == normalized_key(ROBOT_COMPONENT_TYPE)
        serial = serial_text(excel_row[COL_MODEL]) if is_robot else None

        # En las filas de robot, Modelo es un número de serie cuando
        # contiene solo dígitos. El nombre ya contiene el modelo comercial.
        product_model = model_value
        if is_robot and (
            serial is not None or normalized_key(model_value) == normalized_key(name)
        ):
            product_model = None

        individual_tracking = (
            category_key == normalized_key(INDIVIDUAL_CATEGORY) or is_robot
        )
        prefix = (
            make_asset_prefix(name, product_model or model_value, component_type_name)
            if individual_tracking
            else None
        )

        if is_robot:
            product_key = (
                "robot-model",
                category_key,
                type_key,
                normalized_key(brand),
                normalized_key(name),
                normalized_key(product_model),
            )
        else:
            # No se fusionan productos no robóticos: los 393 pares de candidatos
            # conservan trazabilidad de origen y cada ID original debe conservarse.
            product_key = ("source-row", source_id)

        info = {
            "source_id": source_id,
            "name": name,
            "description": description,
            "brand": brand,
            "model": product_model,
            "category_name": category_name,
            "component_type_name": component_type_name,
            "individual_tracking": individual_tracking,
            "asset_code_prefix": prefix,
            "serial_candidate": serial,
            "legacy_stock_reference": decimal_or_none(
                excel_row[COL_LEGACY_STOCK]
            ),
            "original_name": clean(excel_row[COL_ORIGINAL_NAME]),
            "original_category": clean(excel_row[COL_ORIGINAL_CATEGORY]),
            "raw_data": json_safe_row(excel_row),
            "product_key": product_key,
        }
        rows.append(info)

        if product_key not in product_groups:
            product_groups[product_key] = {
                "key": product_key,
                "name": name,
                "description": description,
                "brand": brand,
                "model": product_model,
                "category_name": category_name,
                "component_type_name": component_type_name,
                "tracking_mode": "individual" if individual_tracking else "quantity",
                "asset_code_prefix": prefix,
                "source_ids": [source_id],
            }
        else:
            group = product_groups[product_key]
            group["source_ids"].append(source_id)
            if not group["description"] and description:
                group["description"] = description

    serial_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["serial_candidate"]:
            brand_key = normalized_key(row["brand"])
            serial_groups[(brand_key, row["serial_candidate"])].append(row)

    duplicate_serial_groups = 0
    conflicting_serial_groups = 0
    same_model_duplicate_groups = 0
    for entries in serial_groups.values():
        if len(entries) > 1:
            duplicate_serial_groups += 1
        product_keys = {entry["product_key"] for entry in entries}
        if len(product_keys) > 1:
            conflicting_serial_groups += 1
        elif len(entries) > 1:
            same_model_duplicate_groups += 1

    return {
        "rows": rows,
        "product_groups": list(product_groups.values()),
        "category_names": list(category_names.values()),
        "component_type_names": list(component_type_names.values()),
        "serial_groups": serial_groups,
        "duplicate_serial_groups": duplicate_serial_groups,
        "same_model_duplicate_groups": same_model_duplicate_groups,
        "conflicting_serial_groups": conflicting_serial_groups,
        "robot_rows": sum(
            1 for row in rows
            if normalized_key(row["component_type_name"]) == "robot"
        ),
        "robot_model_count": sum(
            1 for group in product_groups.values()
            if group["key"][0] == "robot-model"
        ),
    }


def lookup_existing_names(db, model_class, names: list[str]) -> tuple[dict[str, Any], list[str]]:
    existing_rows = db.scalars(select(model_class)).all()
    existing_by_key: dict[str, list[Any]] = defaultdict(list)
    for item in existing_rows:
        existing_by_key[normalized_key(item.name)].append(item)

    result: dict[str, Any] = {}
    to_create: list[str] = []

    for name in names:
        key = normalized_key(name)
        matches = existing_by_key.get(key, [])
        if len(matches) > 1:
            raise RuntimeError(
                f"Hay más de un registro existente equivalente a {name!r}. "
                "Se detiene la importación para evitar duplicados."
            )
        if matches:
            if not matches[0].active:
                raise RuntimeError(
                    f"El registro {name!r} ya existe, pero está inactivo. "
                    "Activarlo requiere una decisión explícita; no se modificó."
                )
            result[key] = matches[0]
        else:
            to_create.append(name)

    return result, to_create


def validate_source_record_state(db, source_ids: list[str]) -> bool:
    existing = db.execute(
        select(m.SourceRecord.source_id, m.SourceRecord.source_system).where(
            m.SourceRecord.source_id.in_(source_ids)
        )
    ).all()

    if not existing:
        return False

    if len(existing) == len(source_ids) and all(
        (system or "").casefold() == "inventree" for _, system in existing
    ):
        print(
            "Estos 468 IDs de InvenTree ya están importados. "
            "No se realizaron cambios (importación idempotente)."
        )
        return True

    details = ", ".join(str(source_id) for source_id, _ in existing[:20])
    raise RuntimeError(
        "Se encontraron SourceRecord parciales o IDs ocupados por otro origen "
        f"({details}). No se importó nada para evitar duplicados."
    )


def validate_serial_collisions(db, plan: dict[str, Any]) -> None:
    serials = sorted({serial for _, serial in plan["serial_groups"].keys()})
    if not serials:
        return

    existing_assets = db.scalars(
        select(m.Asset).where(m.Asset.manufacturer_serial.in_(serials))
    ).all()

    incoming_keys = set(plan["serial_groups"].keys())
    collisions = []
    for asset in existing_assets:
        key = (normalized_key(asset.manufacturer_brand), asset.manufacturer_serial)
        if key in incoming_keys:
            collisions.append(
                f"{asset.manufacturer_brand or '(sin marca)'} / "
                f"{asset.manufacturer_serial} / {asset.asset_code}"
            )

    if collisions:
        raise RuntimeError(
            "Ya existen activos con números de serie que aparecen en el Excel: "
            + "; ".join(collisions[:20])
            + ". No se asociarán ni modificarán activos existentes."
        )


def next_asset_code(db, prefix: str) -> str:
    prefix = prefix.strip().upper()
    if not prefix.isascii() or not prefix.isalnum() or not 2 <= len(prefix) <= 10:
        raise ValueError(f"Prefijo de código inválido: {prefix!r}")

    marker = f"C-{prefix}-"
    existing_codes = db.scalars(
        select(m.Asset.asset_code).where(m.Asset.asset_code.like(marker + "%"))
    ).all()
    max_existing = 0
    for code in existing_codes:
        suffix = code[len(marker):] if code.startswith(marker) else ""
        if suffix.isdigit():
            max_existing = max(max_existing, int(suffix))

    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        insert_fn = pg_insert
    elif dialect == "sqlite":
        insert_fn = sqlite_insert
    else:
        raise RuntimeError(
            f"El generador de códigos internos no admite el motor {dialect!r}."
        )

    now = datetime.now(timezone.utc)
    sequence = m.AssetCodeSequence
    statement = (
        insert_fn(sequence)
        .values(
            prefix=prefix,
            last_value=max_existing + 1,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=[sequence.prefix],
            set_={
                "last_value": case(
                    (sequence.last_value < max_existing, max_existing),
                    else_=sequence.last_value,
                ) + 1,
                "updated_at": now,
            },
        )
        .returning(sequence.last_value)
    )
    number = db.scalar(statement)
    return f"C-{prefix}-{number:02d}"


def print_plan(plan: dict[str, Any], duplicate_pair_count: int,
               existing_categories: dict[str, Any],
               categories_to_create: list[str],
               existing_types: dict[str, Any],
               types_to_create: list[str]) -> None:
    print("\n========== VALIDACIÓN DEL CATÁLOGO ==========")
    print(f"Filas de 'Depuracion': {len(plan['rows'])}")
    print(f"Categorías detectadas: {len(plan['category_names'])}")
    print(f"  Se reutilizan: {len(existing_categories)}")
    print(f"  Se crearían: {len(categories_to_create)}")
    print(f"Tipos de componente no vacíos: {len(plan['component_type_names'])}")
    print(f"  Se reutilizan: {len(existing_types)}")
    print(f"  Se crearían: {len(types_to_create)}")
    print(f"Filas sin tipo de componente: "
          f"{sum(1 for row in plan['rows'] if not row['component_type_name'])}")
    print(f"Productos/modelos que se crearían: {len(plan['product_groups'])}")
    print(f"  Modelos de robot agrupados: {plan['robot_model_count']}")
    print(f"Filas originales de tipo Robot: {plan['robot_rows']}")
    print(f"SourceRecord que se conservarían: {len(plan['rows'])}")
    print(f"Filas con candidato a número de serie: "
          f"{sum(1 for row in plan['rows'] if row['serial_candidate'])}")
    print(f"Números de serie únicos detectados: {len(plan['serial_groups'])}")
    print(f"Grupos con serial repetido: {plan['duplicate_serial_groups']}")
    print(f"  Repetidos dentro del mismo modelo: "
          f"{plan['same_model_duplicate_groups']}")
    print(f"  Asociados a modelos distintos: "
          f"{plan['conflicting_serial_groups']}")
    print(f"Activos físicos que se crearían: {len(plan['serial_groups'])}")
    print(f"Pares de posibles duplicados sin decisión: {duplicate_pair_count}")
    print("Fusiones automáticas de productos: 0")
    print("Balances/stock real que se crearían: 0")
    print("Movimientos de stock que se crearían: 0")
    print("Ubicaciones o proyectos que se modificarían: 0")
    print("====================================================\n")


def import_file(path: Path, apply: bool = False) -> None:
    frame, duplicate_pair_count = load_and_validate_workbook(path)
    plan = build_import_plan(frame)
    validate_database_schema()

    db = SessionLocal()
    try:
        source_ids = [row["source_id"] for row in plan["rows"]]
        if validate_source_record_state(db, source_ids):
            return

        existing_categories, categories_to_create = lookup_existing_names(
            db, m.Category, plan["category_names"]
        )
        existing_types, types_to_create = lookup_existing_names(
            db, m.ComponentType, plan["component_type_names"]
        )

        validate_serial_collisions(db, plan)

        print_plan(
            plan,
            duplicate_pair_count,
            existing_categories,
            categories_to_create,
            existing_types,
            types_to_create,
        )

        if not apply:
            print(
                "MODO SIMULACIÓN: no se escribió ningún dato.\n"
                "Si los resultados son correctos, repetí el comando agregando --apply."
            )
            return

        category_map = dict(existing_categories)
        for name in categories_to_create:
            category = m.Category(name=name, active=True)
            db.add(category)
            db.flush()
            category_map[normalized_key(name)] = category

        type_map = dict(existing_types)
        for name in types_to_create:
            component_type = m.ComponentType(name=name, active=True)
            db.add(component_type)
            db.flush()
            type_map[normalized_key(name)] = component_type

        product_map: dict[tuple[Any, ...], m.Product] = {}
        for group in plan["product_groups"]:
            category = category_map[normalized_key(group["category_name"])]
            component_type = (
                type_map.get(normalized_key(group["component_type_name"]))
                if group["component_type_name"]
                else None
            )
            product = m.Product(
                name=group["name"],
                description=group["description"],
                brand=group["brand"],
                model=group["model"],
                category_id=category.id,
                component_type_id=component_type.id if component_type else None,
                tracking_mode=group["tracking_mode"],
                asset_code_prefix=group["asset_code_prefix"],
                unit_value=None,
                value_currency="PYG",
                active=True,
            )
            db.add(product)
            db.flush()
            product_map[group["key"]] = product

        source_map: dict[str, m.SourceRecord] = {}
        for row in plan["rows"]:
            product = product_map[row["product_key"]]
            source = m.SourceRecord(
                source_system="InvenTree",
                source_id=row["source_id"],
                product_id=product.id,
                original_name=row["original_name"],
                original_category=row["original_category"],
                legacy_stock_reference=row["legacy_stock_reference"],
                serial_candidate=row["serial_candidate"],
                asset_id=None,
                raw_data=row["raw_data"],
            )
            db.add(source)
            source_map[row["source_id"]] = source
        db.flush()

        assets_created = 0
        unassigned_conflicts = 0
        for (brand_key, serial), entries in plan["serial_groups"].items():
            product_keys = {entry["product_key"] for entry in entries}
            is_conflict = len(product_keys) > 1

            if not is_conflict:
                product = product_map[next(iter(product_keys))]
                product_id = product.id
                prefix = product.asset_code_prefix
            else:
                product_id = None
                prefixes = [
                    product_map[key].asset_code_prefix
                    for key in product_keys
                    if product_map[key].asset_code_prefix
                ]
                common = prefixes[0] if prefixes else "ROB"
                for candidate in prefixes[1:]:
                    common = os.path.commonprefix([common, candidate])
                prefix = common if len(common) >= 2 else "ROB"
                unassigned_conflicts += 1

            brand = entries[0]["brand"]
            if not prefix:
                raise RuntimeError(
                    f"No se pudo determinar prefijo de código para el serial {serial}."
                )

            duplicate_ids = [entry["source_id"] for entry in entries]
            notes = []
            if len(entries) > 1:
                notes.append(
                    "El serial aparece en varias filas originales: "
                    + ", ".join(duplicate_ids)
                    + ". Se conserva un único activo físico."
                )
            if is_conflict:
                notes.append(
                    "El mismo serial aparece asociado a modelos distintos. "
                    "El activo se deja sin producto hasta verificar el modelo."
                )

            asset = m.Asset(
                product_id=product_id,
                asset_code=next_asset_code(db, prefix),
                manufacturer_serial=serial,
                manufacturer_brand=brand,
                functional_status="unverified",
                lifecycle_status="in_stock",
                observations=" ".join(notes) or None,
                location_id=None,
                estimated_value=None,
                value_currency="PYG",
                active=True,
            )
            db.add(asset)
            db.flush()
            assets_created += 1

            for entry in entries:
                source_map[entry["source_id"]].asset_id = asset.id

        db.commit()

        print("IMPORTACIÓN APLICADA CORRECTAMENTE.")
        print(f"Categorías disponibles: {len(plan['category_names'])}")
        print(f"Tipos de componente disponibles: {len(plan['component_type_names'])}")
        print(f"Productos/modelos creados: {len(product_map)}")
        print(f"SourceRecord creados: {len(source_map)}")
        print(f"Activos creados: {assets_created}")
        print(f"Activos sin producto por conflicto de modelo: {unassigned_conflicts}")
        print("Balances y movimientos creados: 0")
        print("Ubicaciones y proyectos modificados: 0")
        print("Los productos y activos de prueba preexistentes no fueron modificados.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Valida o importa el catálogo de depuración."
    )
    parser.add_argument(
        "--file",
        default="import_data/catalogo.xlsx",
        help="Ruta del archivo Excel (relativa a la carpeta backend si es relativa).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica la importación. Sin esta opción solo ejecuta una simulación.",
    )
    args = parser.parse_args()
    import_file(Path(args.file), apply=args.apply)


if __name__ == "__main__":
    main()
