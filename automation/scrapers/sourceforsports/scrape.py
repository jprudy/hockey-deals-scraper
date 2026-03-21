from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

FIELDS = [
    "ID",
    "ProductName",
    "Description",
    "OriginalPrice",
    "SalePrice",
    "ImageURL",
    "Category",
    "Subcategory",
    "Size",
    "Brand",
    "Stock",
    "LinkRetailer",
    "DealURL",
    "StartDate",
    "EndDate",
    "discount%",
    "Featured",
]

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
DEFAULT_CSV_PATH = DATA / "sourceforsports_latest.csv"

TARGET_PAGES = [
    "https://www.sourceforsports.ca/collections/hockey-equipment/clearance",
    "https://www.sourceforsports.ca/collections/goalie-equipment/clearance",
]

OVERWRITE = False
PRUNE_NON_MATCHING = True
PRUNE_DOMAIN = "sourceforsports.ca"
HEADLESS = True
MAX_PAGES = 40
TILES_LIMIT = None
SPEED_FAST = True
MIN_DISCOUNT_PCT = 1.0
MIN_ABS_DISCOUNT_CAD = 0.50
SKIP_OUT_OF_STOCK = True
VARIANT_POLICY = "any_in_stock"
REQUIRE_RED_ON_GRID = False
REQUIRE_SAVE_WORD_ON_TILE = False
SAVE_WORD_RX = re.compile(r"\bsave\b", re.I)
REQUIRE_PDP_COMPARE_FOR_DEFAULT = not SPEED_FAST
REQUIRE_SAVE_ON_PDP = False
PDP_TIMEOUT_MS = 1500
RED_R_MIN, RED_G_MAX, RED_B_MAX = 185, 120, 120
RED_CLASS_HINTS = (
    "Price--highlight",
    "price-item--sale",
    "price--sale",
    "price--on-sale",
    "text-red",
    "sale-price",
    "sale",
)
PDP_PRICE_SELECTORS = [".product__price", ".price", ".price__container", "[data-product-price]"]
PDP_SALE_SELECTORS = [
    ".price__sale .price-item--price",
    ".product__price .price-item--sale",
    "[data-price-type='current']",
    ".price .price-item--sale",
]
PDP_COMPARE_SELECTORS = [
    ".price__regular .price-item--regular",
    ".price-item--compare",
    "s.price-item--regular",
    "s, del",
    "[data-price-type='compare']",
]
ID_MODE = "stable"
RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
PROGRESS_EVERY = 25

BRANDS = [
    "Bauer",
    "CCM",
    "Warrior",
    "True Hockey",
    "True",
    "STX",
    "Easton",
    "Reebok",
    "Nike",
    "Sher-Wood",
    "Sherwood",
    "Jofa",
    "Koho",
    "Mission",
    "Graf",
    "Franklin",
    "Mylec",
    "Winnwell",
    "Torspo",
    "DR",
    "Vaughn",
    "Brian's",
    "Brians",
    "Kenesky",
    "Passau",
]
BRAND_RXS = [(re.compile(rf"\b{re.escape(b).replace(' ', r'\s+')}\b", re.I), b) for b in BRANDS]
SUBCAT_TO_CAT = {
    "Mask": "Goalie Gear",
    "Throat Protector": "Accessories",
    "Chest & Arm Protector": "Goalie Gear",
    "Catcher Glove": "Goalie Gear",
    "Blocker": "Goalie Gear",
    "Goalie Pants": "Goalie Gear",
    "Leg Pads": "Goalie Gear",
    "Goalie Skates": "Goalie Gear",
    "Goalie Stick": "Goalie Gear",
    "Jock/Jill": "Accessories",
    "Neck Guard": "Accessories",
    "Mouth Guard": "Accessories",
    "Jersey": "Accessories",
    "Socks": "Accessories",
    "Helmet": "Player Gear",
    "Shoulder Pads": "Player Gear",
    "Elbow Pads": "Player Gear",
    "Gloves": "Player Gear",
    "Hockey Pants": "Player Gear",
    "Shin Guards": "Player Gear",
    "Skates": "Player Gear",
    "Stick": "Player Gear",
}
SUBCAT_RXS = [
    (re.compile(p, re.I), s)
    for p, s in [
        (r"\bshoulder(s)?(\s*pad(s)?)?\b", "Shoulder Pads"),
        (r"\belbow(s)?(\s*(pad|guard)(s)?)?\b", "Elbow Pads"),
        (r"\b(goalie )?mask(s)?\b", "Mask"),
        (r"\b(throat|neck)\s*(guard|protector)s?\b", "Neck Guard"),
        (r"\bchest\b.*\barm\b|\bc\/?a\b|\bchest\s*&\s*arm\b", "Chest & Arm Protector"),
        (r"\bcatch(er)? glove(s)?\b|\bcatcher\b", "Catcher Glove"),
        (r"\bblocker(s)?\b", "Blocker"),
        (r"\b(goalie )?pant(s)?\b", "Goalie Pants"),
        (r"\bjock(s)?\/?jill(s)?\b|\bpelvic protector\b|\bjock\b", "Jock/Jill"),
        (r"\bleg\s*pad(s)?\b", "Leg Pads"),
        (r"\bgoalie\s*(leg\s*)?pad(s)?\b", "Leg Pads"),
        (r"\b(goalie )?skate(s)?\b", "Goalie Skates"),
        (r"\b(goalie )?stick(s)?\b", "Goalie Stick"),
        (r"\bhelmet(s)?\b", "Helmet"),
        (r"\bmouth ?guard(s)?\b|\bmouthguard(s)?\b", "Mouth Guard"),
        (r"\bglove(s)?\b", "Gloves"),
        (r"\bjersey(s)?\b", "Jersey"),
        (r"\bhockey pant(s)?\b|\bpant(s)?\b|\bgirdle(s)?\b", "Hockey Pants"),
        (r"\bshin( |-)?guard(s)?\b|\bshinguard(s)?\b", "Shin Guards"),
        (r"\bsock(s)?\b", "Socks"),
        (r"\b(skate(s)?)(?! guard)\b", "Skates"),
        (r"\bstick(s)?\b", "Stick"),
    ]
]
SIZE_RXS = [
    (re.compile(r"\b(youth|yth)\b", re.I), "Youth"),
    (re.compile(r"\b(junior|jr\.?)\b", re.I), "Junior"),
    (re.compile(r"\b(intermediate|intermidiate|int\.?)\b", re.I), "Intermediate"),
    (re.compile(r"\b(senior|sr\.?)\b", re.I), "Senior"),
]
GOALIE_WORDS = re.compile(r"\b(goalie|goaltender)\b", re.I)
BOM = "\ufeff"


def detect_size(text: str) -> str:
    s = text.lower()
    for rx, name in SIZE_RXS:
        if rx.search(s):
            return name
    return ""


def brand_from_text(text: str) -> str:
    for rx, name in BRAND_RXS:
        if rx.search(text):
            return name
    return "Other"


def classify(title: str, url: str, product_type: str) -> tuple[str, str, str, str]:
    title = title or ""
    url_path_text = urlparse(url).path.replace("-", " ")
    tu = f"{title} {url_path_text}".strip()
    tu_lower = tu.lower()
    size = detect_size(tu)
    brand = brand_from_text(tu)
    sub = ""
    for rx, sublabel in SUBCAT_RXS:
        if rx.search(tu_lower):
            sub = sublabel
            break
    goalie_hint = bool(GOALIE_WORDS.search(tu_lower))
    if not sub:
        pt = (product_type or "").lower()
        def has(*ws):
            return any(w in pt for w in ws)
        if has("skate"):
            sub = "Skates"
        elif has("stick"):
            sub = "Stick"
        elif has("glove") and not has("goalie"):
            sub = "Gloves"
        elif has("helmet"):
            sub = "Helmet"
        elif has("blocker"):
            sub = "Blocker"
        elif has("catch") or has("trapper"):
            sub = "Catcher Glove"
    cat = SUBCAT_TO_CAT.get(sub, "Accessories") if sub else "Accessories"
    if sub == "Stick" and goalie_hint:
        sub, cat = "Goalie Stick", "Goalie Gear"
    if sub == "Skates" and goalie_hint:
        sub, cat = "Goalie Skates", "Goalie Gear"
    if cat == "Goalie Gear" and not goalie_hint:
        if sub in ("Goalie Stick", "Goalie Skates", "Goalie Pants", "Mask"):
            equiv = {
                "Goalie Stick": "Stick",
                "Goalie Skates": "Skates",
                "Goalie Pants": "Hockey Pants",
                "Mask": "Helmet",
            }
            sub = equiv.get(sub, "Other")
            cat = SUBCAT_TO_CAT.get(sub, "Accessories")
        else:
            cat, sub = "Accessories", "Other"
    if not sub:
        sub = "Other"
    return cat, sub, size, brand


def normspaces(s: str) -> str:
    if not s:
        return s
    return re.sub(r"\s{2,}", " ", s.replace("\u00A0", " ").replace("\u202F", " ").replace("\u2007", " "))


def money_from_shopify(v):
    if v is None:
        return None
    try:
        s = str(v).strip()
        s = re.sub(r"[^\d.]", "", s)
        if s == "":
            return None
        if "." in s:
            return float(s)
        iv = int(s)
        return iv / 100.0 if iv >= 1000 else float(iv)
    except Exception:
        try:
            return float(v)
        except Exception:
            return None


def is_real_discount(compare, price) -> bool:
    if compare is None or price is None:
        return False
    if compare <= price:
        return False
    abs_disc = compare - price
    pct_disc = (abs_disc / compare) * 100 if compare else 0
    return abs_disc >= MIN_ABS_DISCOUNT_CAD and pct_disc >= MIN_DISCOUNT_PCT


def pct(compare, price):
    return round(100 * (compare - price) / compare) if (compare and price and compare > price) else 0


def clean_title(t: str) -> str:
    if not t:
        return ""
    t = normspaces(t)
    t = re.sub(
        r"\b(Quick\s*view|Sale\s*price|Regular\s*price|Save\s*\$?\d+[.\d]*|Save\s*\d+%|\d+%\s*off)\b",
        "",
        t,
        flags=re.I,
    )
    t = re.sub(r"\s{2,}", " ", t).strip(" ,.-:|·•")
    return t


def normalize_url(base, href):
    return urljoin(base, href or "") if href else base


def url_with_page(base_url: str, n: int) -> str:
    p = urlparse(base_url)
    q = parse_qs(p.query)
    q["page"] = [str(n)]
    return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(q, doseq=True), p.fragment))


def short_id_from_url(u: str) -> str:
    h = hashlib.sha1(u.encode("utf-8")).hexdigest()[:8]
    host = urlparse(u).netloc.replace("www.", "")
    return f"{host}-{h}" if ID_MODE == "stable" else f"{host}-{RUN_ID}-{h}"


def is_color_redish(rgb_str: str) -> bool:
    m = re.search(r"rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", rgb_str or "")
    if not m:
        return False
    r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return (r >= RED_R_MIN) and (g <= RED_G_MAX) and (b <= RED_B_MAX)


def collect_tiles_with_flags(page):
    anchors = page.query_selector_all("a[href*='/products/']")
    out, seen = {}, set()
    base = page.url
    for a in anchors:
        href = a.get_attribute("href") or ""
        if not href:
            continue
        u = normalize_url(base, href)
        p = urlparse(u)
        u = f"{p.scheme}://{p.netloc}{p.path}"
        if u in seen:
            continue
        seen.add(u)
        cont = (
            a.evaluate_handle(
                """
            el => el.closest('li,article,.card,.productgrid--item,.grid__item,.ProductItem,.product-item,.product-grid-item')
               || el.parentElement
        """
            ).as_element()
            or a
        )
        red = False
        try:
            sale_el = cont.query_selector(
                ".Price--highlight, .price-item--sale, .price--sale, .price--on-sale, .price__sale .price-item--price, .price__current"
            )
            if sale_el:
                cls = (sale_el.get_attribute("class") or "").lower()
                if any(h in cls for h in (c.lower() for c in RED_CLASS_HINTS)):
                    red = True
                else:
                    col = sale_el.evaluate("(e)=>getComputedStyle(e).color")
                    red = is_color_redish(col)
        except Exception:
            pass
        has_save = False
        try:
            txt = cont.inner_text() or ""
            if SAVE_WORD_RX.search(txt):
                has_save = True
        except Exception:
            pass
        out[u] = {"red": red, "save": has_save}
    return out


def crawl_collection_with_tileinfo(page, start_url: str, max_pages=40):
    info = {}
    for n in range(1, max_pages + 1):
        url = url_with_page(start_url, n) if n > 1 else start_url
        try:
            page.goto(url, timeout=30000)
            page.wait_for_load_state("domcontentloaded")
        except PWTimeout:
            break
        if page.locator("a[href*='/products/']").count() == 0:
            break
        cur = collect_tiles_with_flags(page)
        grew = False
        for k, v in cur.items():
            if k not in info:
                info[k] = v
                grew = True
        if not grew:
            break
    return info


def product_json_url(product_url: str) -> str:
    p = urlparse(product_url)
    path = p.path.rstrip("/")
    if not path.endswith(".js"):
        path += ".js"
    return urlunparse((p.scheme, p.netloc, path, "", "", ""))


def fetch_shopify_product_json(context, product_url: str):
    try:
        r = context.request.get(product_json_url(product_url), timeout=8000)
        if not r.ok:
            return None
        return r.json()
    except Exception:
        return None


def pick_variants_by_policy(variants):
    if VARIANT_POLICY == "first_available_only":
        for v in variants:
            if v.get("available"):
                return [v]
        return []
    elif VARIANT_POLICY == "all_in_stock":
        return [v for v in variants if v.get("available")]
    return [v for v in variants if v.get("available")]


def best_discounted_variant_json(data):
    if not data or "variants" not in data:
        return None, None, False, ""
    cand = pick_variants_by_policy(data["variants"])
    if not cand:
        return None, None, False, ""
    best = None
    for v in cand:
        price = money_from_shopify(v.get("price"))
        compare = money_from_shopify(v.get("compare_at_price"))
        if not is_real_discount(compare, price):
            continue
        pct_score = (compare - price) / compare if compare else 0
        score = (pct_score, compare - price)
        if best is None or score > best[0]:
            best = (score, price, compare, v.get("title", ""))
    if not best:
        return None, None, False, ""
    _, price, compare, vtitle = best
    return price, compare, True, vtitle


def _clean_key(k):
    return str(k).replace(BOM, "").strip()


def _clean_row(d):
    return {_clean_key(k): v for k, v in d.items()}


FIELDS = [_clean_key(c) for c in FIELDS]


def ensure_csv(headers, path: Path):
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=[_clean_key(c) for c in headers]).writeheader()


def write_rows(rows, headers, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[_clean_key(c) for c in headers], extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(_clean_row(r))
    print(f"[sourceforsports] wrote {len(rows)} rows to {path.resolve()}", flush=True)


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--out", default=os.environ.get("OUTPUT_CSV_PATH", str(DEFAULT_CSV_PATH)))
    args, _ = ap.parse_known_args()
    csv_path = Path(args.out)
    if OVERWRITE and csv_path.exists():
        csv_path.unlink()
    ensure_csv(FIELDS, csv_path)

    out = []
    c_tiles = c_grid_ok = c_json_ok = c_final_ok = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/119 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 860},
            locale="en-CA",
        )
        page = context.new_page()
        page.set_default_timeout(20000)
        for coll in TARGET_PAGES:
            tiles = crawl_collection_with_tileinfo(page, coll, max_pages=MAX_PAGES)
            if TILES_LIMIT:
                tiles = dict(list(tiles.items())[:TILES_LIMIT])
            c_tiles += len(tiles)
            print(f"[sourceforsports] collection={coll} tiles={len(tiles)}", flush=True)

            for i, (product_url, flags) in enumerate(tiles.items(), start=1):
                if PROGRESS_EVERY and (i % PROGRESS_EVERY == 0):
                    print(
                        f"[sourceforsports] progress={i}/{len(tiles)} kept={len(out)} json_ok={c_json_ok} final_ok={c_final_ok}",
                        flush=True,
                    )
                if REQUIRE_RED_ON_GRID and not flags.get("red", False):
                    continue
                if REQUIRE_SAVE_WORD_ON_TILE and not flags.get("save", False):
                    continue
                c_grid_ok += 1

                data = fetch_shopify_product_json(context, product_url)
                if not data:
                    continue
                sale_json, reg_json, available, _ = best_discounted_variant_json(data)
                if sale_json is None or reg_json is None:
                    continue
                if SKIP_OUT_OF_STOCK and not available:
                    continue
                c_json_ok += 1

                sale, reg = sale_json, reg_json
                if sale >= reg:
                    continue
                pct_disc = pct(reg, sale)
                if pct_disc < 1 or pct_disc > 90:
                    continue
                c_final_ok += 1

                title = clean_title(data.get("title", ""))
                vendor = data.get("vendor", "") or "Other"
                image = data.get("featured_image") or (data["images"][0] if data.get("images") else "")
                image = normalize_url(product_url, image) if image else ""
                product_type = data.get("type") or data.get("product_type") or ""
                cat, sub, size, brand_guess = classify(title, product_url, product_type)
                brand = brand_guess if brand_guess != "Other" else (vendor or "Other")
                rid = short_id_from_url(product_url)
                out.append(
                    _clean_row(
                        {
                            "ID": rid,
                            "ProductName": title,
                            "Description": title,
                            "OriginalPrice": f"{reg:.2f}",
                            "SalePrice": f"{sale:.2f}",
                            "ImageURL": image,
                            "Category": cat,
                            "Subcategory": sub,
                            "Size": size,
                            "Brand": brand,
                            "Stock": "In Stock" if available else "Out of Stock",
                            "LinkRetailer": coll,
                            "DealURL": product_url,
                            "StartDate": datetime.today().strftime("%Y-%m-%d"),
                            "EndDate": (datetime.today() + timedelta(days=14)).strftime("%Y-%m-%d"),
                            "discount%": str(pct_disc),
                            "Featured": "",
                        }
                    )
                )
        context.close()
        browser.close()

    print(f"[sourceforsports] funnel tiles={c_tiles} after_grid={c_grid_ok} after_json={c_json_ok} kept={len(out)}", flush=True)
    write_rows(out, FIELDS, csv_path)


if __name__ == "__main__":
    main()
