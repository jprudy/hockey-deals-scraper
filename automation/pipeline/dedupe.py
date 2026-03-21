from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Dict, List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def _norm_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _safe_price(value: str) -> Decimal:
    try:
        return Decimal(str(value or "").strip())
    except (InvalidOperation, TypeError):
        return Decimal("999999999")


def _canonicalize_url(raw_url: str) -> str:
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


def deduplicate_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Primary key: normalized product_name + brand
    Fallback key: canonicalized url
    Winner: lowest price
    """
    by_name_brand: Dict[str, Dict[str, str]] = {}
    by_url: Dict[str, Dict[str, str]] = {}

    for row in rows:
        product_name = _norm_text(str(row.get("product_name", "")))
        brand = _norm_text(str(row.get("brand", "")))
        primary_key = f"{product_name}||{brand}" if product_name and brand else ""
        url_key = _canonicalize_url(str(row.get("url", "")))

        existing = None
        if primary_key:
            existing = by_name_brand.get(primary_key)
        if existing is None and url_key:
            existing = by_url.get(url_key)

        if existing is None:
            winner = row
        else:
            winner = row if _safe_price(str(row.get("price", ""))) < _safe_price(str(existing.get("price", ""))) else existing

        if primary_key:
            by_name_brand[primary_key] = winner
        if url_key:
            by_url[url_key] = winner

    deduped_by_identity: Dict[str, Dict[str, str]] = {}
    for row in list(by_name_brand.values()) + list(by_url.values()):
        identity = _canonicalize_url(str(row.get("url", ""))) or f"{_norm_text(str(row.get('product_name', '')))}||{_norm_text(str(row.get('brand', '')))}||{row.get('price', '')}"
        deduped_by_identity[identity] = row

    return list(deduped_by_identity.values())
