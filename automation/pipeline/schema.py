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
    "brand",
    "category",
    "subcategory",
    "size",
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


def sanitize_wp_text(value: object) -> str:
    """
    Remove characters that often break imports / UIs (aligned with legacy WP-safe merge):
    BOM, NBSP, narrow/no-break spaces, zero-width chars, CR/LF/TAB.
    """
    if value is None:
        return ""
    s = str(value)
    return (
        s.replace("\ufeff", "")
        .replace("\u00a0", " ")
        .replace("\u202f", " ")
        .replace("\u2007", " ")
        .replace("\u200b", "")
        .replace("\u200c", "")
        .replace("\u200d", "")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\t", " ")
        .strip()
    )


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
    row = {key: sanitize_wp_text(mapped_raw.get(key, "")) for key in CSV_HEADERS}
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
        stock_text = sanitize_wp_text(raw.get("Stock", ""))
        stock_lower = stock_text.lower()
        in_stock = "true" if "in stock" in stock_lower or stock_lower == "true" else "false"
        title = sanitize_wp_text(raw.get("ProductName", ""))
        desc = sanitize_wp_text(raw.get("Description", "")) or title
        return {
            "run_id": sanitize_wp_text(raw.get("run_id", "")),
            "scraped_at": sanitize_wp_text(raw.get("scraped_at", "")),
            "import_source": "scraped",
            "source": "ths",
            "external_key": sanitize_wp_text(raw.get("external_key", "")),
            "source_store": "thehockeyshop",
            "source_url": sanitize_wp_text(raw.get("DealURL", "")),
            "source_product_id": sanitize_wp_text(raw.get("ID", "")),
            "title": title,
            "price": sanitize_wp_text(raw.get("OriginalPrice", "")),
            "sale_price": sanitize_wp_text(raw.get("SalePrice", "")),
            "currency": "CAD",
            "in_stock": in_stock,
            "stock_text": stock_text,
            "image_url": sanitize_wp_text(raw.get("ImageURL", "")),
            "description": desc,
            "brand": sanitize_wp_text(raw.get("Brand", "")),
            "category": sanitize_wp_text(raw.get("Category", "")),
            "subcategory": sanitize_wp_text(raw.get("Subcategory", "")),
            "size": sanitize_wp_text(raw.get("Size", "")),
        }

    if "product_name" in raw or "url" in raw:
        source = sanitize_wp_text(raw.get("source", "")) or sanitize_wp_text(raw.get("source_store", ""))
        source_store = sanitize_wp_text(raw.get("source_store", "")) or source
        product_name = sanitize_wp_text(raw.get("product_name", ""))
        price_reg = sanitize_wp_text(raw.get("original_price", "")) or sanitize_wp_text(raw.get("price", ""))
        sale = sanitize_wp_text(raw.get("price", ""))
        desc = sanitize_wp_text(raw.get("description", "")) or product_name
        return {
            "run_id": sanitize_wp_text(raw.get("run_id", "")),
            "scraped_at": sanitize_wp_text(raw.get("scraped_at", "")),
            "import_source": "scraped",
            "source": source,
            "external_key": sanitize_wp_text(raw.get("external_key", "")),
            "source_store": source_store,
            "source_url": sanitize_wp_text(raw.get("url", "")),
            "source_product_id": sanitize_wp_text(raw.get("source_product_id", "")),
            "title": product_name,
            # Internal normalized format expects price=regular and sale_price=current sale.
            "price": price_reg,
            "sale_price": sale,
            "currency": "CAD",
            "in_stock": sanitize_wp_text(raw.get("in_stock", "")),
            "stock_text": sanitize_wp_text(raw.get("stock_text", "")),
            "image_url": sanitize_wp_text(raw.get("image_url", "")),
            "description": desc,
            "brand": sanitize_wp_text(raw.get("brand", "")) or sanitize_wp_text(raw.get("Brand", "")),
            "category": sanitize_wp_text(raw.get("category", "")) or sanitize_wp_text(raw.get("Category", "")),
            "subcategory": sanitize_wp_text(raw.get("subcategory", ""))
            or sanitize_wp_text(raw.get("Subcategory", "")),
            "size": sanitize_wp_text(raw.get("size", "")) or sanitize_wp_text(raw.get("Size", "")),
        }

    return {k: sanitize_wp_text(v) if isinstance(v, str) else v for k, v in raw.items()}


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
