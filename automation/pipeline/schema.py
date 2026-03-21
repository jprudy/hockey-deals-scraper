from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

CSV_HEADERS: List[str] = [
    "run_id",
    "scraped_at",
    "import_source",
    "source",
    "external_key",
    "source_store",
    "source_url",
    "source_product_id",
    "title",
    "price",
    "sale_price",
    "currency",
    "in_stock",
    "stock_text",
    "image_url",
    "description",
]

REQUIRED_FIELDS: List[str] = [
    "run_id",
    "scraped_at",
    "import_source",
    "source",
    "external_key",
    "source_store",
    "source_url",
    "title",
    "price",
    "currency",
    "in_stock",
]

SOURCE_STORE = "thehockeyshop"
IMPORT_SOURCE = "scraped"

TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


@dataclass
class ValidationResult:
    ok: bool
    row: Dict[str, str]
    errors: List[str]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_bool(value: str) -> Optional[bool]:
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    return None


def parse_decimal(value: str) -> Optional[Decimal]:
    text = str(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def validate_and_normalize_row(raw: Dict[str, str], run_id: str) -> ValidationResult:
    mapped_raw = map_source_row(raw)
    row = {key: str(mapped_raw.get(key, "")).strip() for key in CSV_HEADERS}
    errors: List[str] = []

    row["run_id"] = run_id
    row["import_source"] = row["import_source"] or IMPORT_SOURCE
    row["source"] = row["source"] or row["source_store"] or SOURCE_STORE
    row["source_store"] = row["source_store"] or row["source"] or SOURCE_STORE
    if not row["scraped_at"]:
        row["scraped_at"] = utc_now_iso()
    if not row["external_key"]:
        generated = generate_external_key(row)
        if generated:
            row["external_key"] = generated

    for field in REQUIRED_FIELDS:
        if not row.get(field):
            errors.append(f"missing_required:{field}")

    if row.get("import_source") and row["import_source"] != IMPORT_SOURCE:
        errors.append("invalid_import_source")

    if row.get("in_stock"):
        parsed_bool = parse_bool(row["in_stock"])
        if parsed_bool is None:
            errors.append("invalid_in_stock")
        else:
            row["in_stock"] = "true" if parsed_bool else "false"

    price = parse_decimal(row.get("price", ""))
    if price is None:
        errors.append("invalid_price")
    else:
        row["price"] = f"{price:.2f}"

    if row.get("sale_price"):
        sale_price = parse_decimal(row["sale_price"])
        if sale_price is None:
            errors.append("invalid_sale_price")
        else:
            row["sale_price"] = f"{sale_price:.2f}"

    currency = row.get("currency", "").upper()
    if currency and len(currency) == 3:
        row["currency"] = currency
    else:
        errors.append("invalid_currency")

    return ValidationResult(ok=not errors, row=row, errors=errors)


def row_key(row: Dict[str, str]) -> Tuple[str, str]:
    return (row.get("source_store", ""), row.get("external_key", ""))


def map_source_row(raw: Dict[str, str]) -> Dict[str, str]:
    """
    Maps known source formats (including THS legacy CSV) into normalized keys.
    """
    if "ProductName" in raw or "DealURL" in raw or "OriginalPrice" in raw:
        stock = str(raw.get("Stock", "")).strip().lower()
        in_stock = "true" if "in stock" in stock or stock == "true" else "false"
        return {
            "run_id": str(raw.get("run_id", "")).strip(),
            "scraped_at": str(raw.get("scraped_at", "")).strip(),
            "import_source": "scraped",
            "source": "ths",
            "external_key": str(raw.get("external_key", "")).strip(),
            "source_store": "thehockeyshop",
            "source_url": str(raw.get("DealURL", "")).strip(),
            "source_product_id": str(raw.get("ID", "")).strip(),
            "title": str(raw.get("ProductName", "")).strip(),
            "price": str(raw.get("OriginalPrice", "")).strip(),
            "sale_price": str(raw.get("SalePrice", "")).strip(),
            "currency": "CAD",
            "in_stock": in_stock,
            "stock_text": str(raw.get("Stock", "")).strip(),
            "image_url": str(raw.get("ImageURL", "")).strip(),
            "description": str(raw.get("Description", "")).strip()
            or str(raw.get("ProductName", "")).strip(),
        }

    if "product_name" in raw or "url" in raw:
        source = str(raw.get("source", "")).strip() or str(raw.get("source_store", "")).strip()
        source_store = str(raw.get("source_store", "")).strip() or source
        return {
            "run_id": str(raw.get("run_id", "")).strip(),
            "scraped_at": str(raw.get("scraped_at", "")).strip(),
            "import_source": "scraped",
            "source": source,
            "external_key": str(raw.get("external_key", "")).strip(),
            "source_store": source_store,
            "source_url": str(raw.get("url", "")).strip(),
            "source_product_id": str(raw.get("source_product_id", "")).strip(),
            "title": str(raw.get("product_name", "")).strip(),
            # Internal normalized format expects price=regular and sale_price=current sale.
            "price": str(raw.get("original_price", "")).strip() or str(raw.get("price", "")).strip(),
            "sale_price": str(raw.get("price", "")).strip(),
            "currency": "CAD",
            "in_stock": str(raw.get("in_stock", "")).strip(),
            "stock_text": str(raw.get("stock_text", "")).strip(),
            "image_url": str(raw.get("image_url", "")).strip(),
            "description": str(raw.get("description", "")).strip() or str(raw.get("product_name", "")).strip(),
        }

    return raw


def canonicalize_url(raw_url: str) -> str:
    if not raw_url:
        return ""
    parts = urlsplit(raw_url.strip())
    filtered = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in TRACKING_QUERY_KEYS:
            continue
        filtered.append((key, value))
    query = urlencode(filtered, doseq=True)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def generate_external_key(row: Dict[str, str]) -> Optional[str]:
    product_id = str(row.get("source_product_id", "")).strip()
    source_store = str(row.get("source_store", "")).strip() or SOURCE_STORE
    if product_id:
        return f"{IMPORT_SOURCE}:{source_store}:{product_id}"
    canonical = canonicalize_url(str(row.get("source_url", "")))
    if canonical:
        return f"{IMPORT_SOURCE}:{source_store}:{canonical}"
    return None
