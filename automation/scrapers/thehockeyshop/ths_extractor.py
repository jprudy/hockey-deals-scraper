import csv
import re
import time
import random
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

RUN_ID = datetime.utcnow().strftime("%Y%m%d%H%M%S")

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
DEFAULT_OUT = DATA / "thehockeyshop_latest.csv"

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

HEADLESS = True
OVERWRITE = True
MAX_PRODUCTS = 8000

TARGET_PAGES = [
    "https://www.thehockeyshop.com/collections/hockey-deals-clearance",
]

MIN_DISCOUNT_PCT = 1.0
MIN_ABS_DISCOUNT_CAD = 0.50

DEFAULTS = {
    "Description": "",
    "Category": "Accessories",
    "Subcategory": "",
    "Size": "",
    "Brand": "Other",
    "Stock": "Unknown",
    "StartDate": datetime.today().strftime("%Y-%m-%d"),
    "EndDate": (datetime.today() + timedelta(days=14)).strftime("%Y-%m-%d"),
    "Featured": "",
}

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
    "Chest & Arm Protector": "Goalie Gear",
    "Catcher Glove": "Goalie Gear",
    "Blocker": "Goalie Gear",
    "Goalie Pants": "Goalie Gear",
    "Leg Pads": "Goalie Gear",
    "Goalie Skates": "Goalie Gear",
    "Goalie Stick": "Goalie Gear",
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
        (r"\b(goalie )?mask(s)?\b", "Mask"),
        (r"\b(throat|neck)\s*(guard|protector)s?\b", "Neck Guard"),
        (r"\bchest\b.*\barm\b|\bc\/?a\b|\bchest\s*&\s*arm\b", "Chest & Arm Protector"),
        (r"\bcatch(er)? glove(s)?\b|\bcatcher\b", "Catcher Glove"),
        (r"\bblocker(s)?\b", "Blocker"),
        (r"\b(goalie )?pant(s)?\b", "Goalie Pants"),
        (r"\b(leg )?pad(s)?\b", "Leg Pads"),
        (r"\b(goalie )?skate(s)?\b", "Goalie Skates"),
        (r"\b(goalie )?stick(s)?\b", "Goalie Stick"),
        (r"\bhelmet(s)?\b", "Helmet"),
        (r"\bmouth ?guard(s)?\b|\bmouthguard(s)?\b", "Mouth Guard"),
        (r"\bshoulder pad(s)?\b", "Shoulder Pads"),
        (r"\belbow pad(s)?\b", "Elbow Pads"),
        (r"\bglove(s)?\b", "Gloves"),
        (r"\bjersey(s)?\b", "Jersey"),
        (r"\bhockey pant(s)?\b|\bpant(s)?\b", "Hockey Pants"),
        (r"\bshin guard(s)?\b|\bshinguard(s)?\b", "Shin Guards"),
        (r"\bsock(s)?\b", "Socks"),
        (r"\b(skate(s)?)(?! guard)\b", "Skates"),
        (r"\bstick(s)?\b", "Stick"),
    ]
]

GOALIE_WORDS = re.compile(r"\b(goalie|goaltender)\b", re.I)
SIZE_RXS = [
    (re.compile(r"\b(youth|yth)\b", re.I), "Youth"),
    (re.compile(r"\b(junior|jr\.?)\b", re.I), "Junior"),
    (re.compile(r"\b(intermediate|intermidiate|int\.?)\b", re.I), "Intermediate"),
    (re.compile(r"\b(senior|sr\.?)\b", re.I), "Senior"),
]


def rand_wait(a=0.2, b=0.7):
    time.sleep(random.uniform(a, b))


def canonical_deal_url(u: str) -> str:
    p = urlparse(u)
    return f"{p.scheme}://{p.netloc}{p.path}"


def product_json_url(product_url: str) -> str:
    p = urlparse(product_url)
    path = p.path.rstrip("/")
    if not path.endswith(".js"):
        path += ".js"
    return urlunparse((p.scheme, p.netloc, path, "", "", ""))


def money_from_shopify(v):
    if v is None:
        return None
    try:
        iv = int(str(v).strip())
        if iv <= 0:
            return None
        return round(iv / 100.0, 2)
    except Exception:
        return None


def detect_size(text: str) -> str:
    s = (text or "").lower()
    for rx, name in SIZE_RXS:
        if rx.search(s):
            return name
    return ""


def ensure_not_goalie_without_keyword(cat: str, sub: str, text_for_check: str):
    if cat == "Goalie Gear" or "goalie" in (sub or "").lower():
        if not GOALIE_WORDS.search(text_for_check):
            if sub in ("Goalie Stick",):
                return "Player Gear", "Stick"
            if sub in ("Goalie Skates",):
                return "Player Gear", "Skates"
            if sub in ("Goalie Pants",):
                return "Player Gear", "Hockey Pants"
            if sub in ("Mask",):
                return "Player Gear", "Helmet"
            return "Accessories", "Other"
    return cat, sub


def fmt_price(x):
    return f"{x:.2f}" if isinstance(x, (int, float)) else ""


def pct_discount(reg, sale):
    if not reg or not sale or sale >= reg:
        return ""
    pct = round(100 * (reg - sale) / reg)
    return "" if pct < 1 or pct > 90 else str(pct)


def dismiss_popups(page):
    for sel in [
        "button#onetrust-accept-btn-handler",
        "button[aria-label='Accept all']",
        "button:has-text('Accept')",
        "button:has-text('Got it')",
        "button:has-text('Close')",
        "div[role='dialog'] button[aria-label='Close']",
        ".popup-close, .close-button, .modal__close-button, .modal__close",
    ]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
        except Exception:
            pass


def human_scroll(page, steps=8):
    try:
        height = page.evaluate("() => document.body.scrollHeight") or 4000
    except Exception:
        height = 4000
    step = max(350, height // steps)
    y = 0
    for _ in range(steps):
        y += step
        try:
            page.evaluate(f"() => window.scrollTo(0,{y});")
        except Exception:
            pass
        rand_wait(0.15, 0.45)


LOAD_MORE_SELECTORS = [
    "button:has-text('Load more')",
    "a:has-text('Load more')",
    "button:has-text('Load More')",
    "a:has-text('Load More')",
    "button:has-text('LOAD MORE')",
    "a:has-text('LOAD MORE')",
    "button.button--primary:has-text('Load More')",
    "button.button--secondary:has-text('Load More')",
    ".boost-pfs-filter-load-more, .boost-pfs-filter-load-more-button, a.boost-pfs-filter-load-more-button",
    ".load-more, .load-more__button, .js-load-more, #load-more",
    "[data-load-more], [data-collection-ajax-load-more], [data-action='load-more']",
    ".collection__loadMore button, .collection__loadMore a, .collection__load-more button, .collection__load-more a",
    ".product-grid__load-more button, .product-grid__load-more a",
]


def collect_product_urls(page) -> set:
    urls = page.eval_on_selector_all(
        "a[href*='/products/']",
        "els => els.map(e => e.getAttribute('href')).filter(Boolean)",
    )
    out = set()
    base = page.url
    for h in urls:
        try:
            u = urljoin(base, h)
            p = urlparse(u)
            out.add(p.scheme + "://" + p.netloc + p.path)
        except Exception:
            pass
    return out


def _btn_disabled(btn) -> bool:
    try:
        if btn.get_attribute("disabled") is not None:
            return True
        if (btn.get_attribute("aria-disabled") or "").lower() == "true":
            return True
        txt = (btn.inner_text() or "").strip().lower()
        if "no more" in txt or "end of" in txt:
            return True
    except Exception:
        pass
    return False


def load_all_products(page, max_clicks=220, grow_timeout_ms=22000):
    seen = collect_product_urls(page)
    last = len(seen)
    print(f"    [LoadMore] starting with {last} unique products")
    no_growth = 0
    clicks = 0

    while clicks < max_clicks:
        btn = None
        for sel in LOAD_MORE_SELECTORS:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    for j in range(min(6, loc.count())):
                        cand = loc.nth(j)
                        if cand.is_visible():
                            btn = cand
                            break
                if btn:
                    break
            except Exception:
                continue

        if not btn:
            page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(450)
            cur = collect_product_urls(page)
            if len(cur) == last:
                no_growth += 1
                if no_growth >= 2:
                    print("    [LoadMore] no button & no growth; stopping.")
                    break
            else:
                last = len(cur)
                no_growth = 0
            continue

        if _btn_disabled(btn):
            print("    [LoadMore] button disabled; stopping.")
            break

        try:
            btn.scroll_into_view_if_needed()
            page.wait_for_timeout(260)
            btn.click(timeout=7500)
        except Exception:
            try:
                handle = btn.element_handle()
                if handle:
                    page.evaluate("(b)=>b.click()", handle)
            except Exception:
                pass

        clicks += 1
        grew = False
        t0 = time.time()
        while (time.time() - t0) * 1000 < grow_timeout_ms:
            page.wait_for_timeout(520)
            cur = collect_product_urls(page)
            if len(cur) > last:
                print(f"    [LoadMore] click {clicks}: {last} -> {len(cur)}")
                last = len(cur)
                grew = True
                break

        no_growth = 0 if grew else (no_growth + 1)
        if no_growth >= 2:
            print("    [LoadMore] no growth after clicks; stopping.")
            break

    return last


def best_discounted_variant(data: dict):
    variants = data.get("variants") or []
    best = None

    for v in variants:
        price = money_from_shopify(v.get("price"))
        compare = money_from_shopify(v.get("compare_at_price"))
        if price is None or compare is None:
            continue
        if compare <= price:
            continue

        abs_disc = compare - price
        pct = (abs_disc / compare) * 100 if compare else 0
        if abs_disc < MIN_ABS_DISCOUNT_CAD or pct < MIN_DISCOUNT_PCT:
            continue

        score = (pct, abs_disc)
        if best is None or score > best["score"]:
            best = {
                "score": score,
                "sale": price,
                "reg": compare,
                "avail": bool(v.get("available")),
                "vtitle": (v.get("title") or "").strip(),
            }

    if not best:
        return None, None, False, ""

    return best["sale"], best["reg"], best["avail"], best["vtitle"]


def fetch_product_json(context, product_url: str, tries=3):
    u = product_json_url(product_url)
    for _ in range(tries):
        try:
            r = context.request.get(u, timeout=15000)
            if r.ok:
                return r.json()
        except Exception:
            pass
        time.sleep(0.25)
    return None


def extract_deals_from_collection(context, page, collection_url: str) -> list[dict]:
    product_urls = sorted(collect_product_urls(page))
    print(f"    [Collect] unique product URLs: {len(product_urls)}")

    by_url = {}
    base_netloc = urlparse(collection_url).netloc

    kept = 0
    dropped_no_discount = 0
    dropped_no_json = 0

    for i, u in enumerate(product_urls[:MAX_PRODUCTS], start=1):
        deal = canonical_deal_url(u)

        data = fetch_product_json(context, deal)
        if not data:
            dropped_no_json += 1
            continue

        sale, reg, avail, vtitle = best_discounted_variant(data)
        if sale is None or reg is None:
            dropped_no_discount += 1
            continue

        title = (data.get("title") or "").strip()
        if not title:
            continue

        vendor = (data.get("vendor") or "").strip()
        brand = vendor or ""
        if not brand:
            for rx, name in BRAND_RXS:
                if rx.search(title):
                    brand = name
                    break
        if not brand:
            brand = DEFAULTS["Brand"]

        img = data.get("featured_image") or ""
        if not img:
            imgs = data.get("images") or []
            if imgs:
                img = imgs[0]
        if img.startswith("//"):
            img = "https:" + img

        cat = DEFAULTS["Category"]
        sub = ""
        s_for_cat = f"{title} {deal}"
        goalie_hint = bool(GOALIE_WORDS.search(s_for_cat))
        for rx, sublabel in SUBCAT_RXS:
            if rx.search(s_for_cat.lower()):
                sub = sublabel
                cat = SUBCAT_TO_CAT.get(sublabel, "Accessories")
                if sublabel == "Stick" and goalie_hint:
                    sub, cat = "Goalie Stick", "Goalie Gear"
                if sublabel == "Skates" and goalie_hint:
                    sub, cat = "Goalie Skates", "Goalie Gear"
                break

        size = detect_size(title) or detect_size(vtitle)

        if not size:
            cat = "Accessories"
            sub = sub or "Other"

        cat, sub = ensure_not_goalie_without_keyword(cat, sub, s_for_cat)
        if cat not in ("Accessories", "Player Gear", "Goalie Gear"):
            cat = "Accessories"
        if not sub:
            sub = "Other"

        row = {
            "ID": f"{base_netloc}-J{i:04d}",
            "ProductName": title,
            "Description": title,
            "OriginalPrice": fmt_price(reg),
            "SalePrice": fmt_price(sale),
            "ImageURL": img,
            "Category": cat,
            "Subcategory": sub,
            "Size": size or DEFAULTS["Size"],
            "Brand": brand,
            "Stock": "In Stock" if avail else DEFAULTS["Stock"],
            "LinkRetailer": collection_url,
            "DealURL": deal,
            "StartDate": DEFAULTS["StartDate"],
            "EndDate": DEFAULTS["EndDate"],
            "discount%": pct_discount(reg, sale),
            "Featured": DEFAULTS["Featured"],
        }

        by_url[deal] = row
        kept += 1

        if i % 100 == 0:
            print(f"    [JSON] {i}/{len(product_urls)} | kept={kept}")

    print(
        f"    [Result] kept={kept} dropped_no_discount={dropped_no_discount} dropped_no_json={dropped_no_json}"
    )
    return list(by_url.values())


BOM = "\ufeff"


def _clean_key(k):
    return str(k).replace(BOM, "").strip()


FIELDS = [_clean_key(c) for c in FIELDS]


def ensure_csv(headers, path: Path):
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=[_clean_key(c) for c in headers]).writeheader()


def write_rows(rows, headers, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")

    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[_clean_key(c) for c in headers], extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    try:
        tmp.replace(path)
        print(f"[OK] Wrote {len(rows)} rows to {path.resolve()}")
    except PermissionError:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        alt = path.with_name(f"{path.stem}_{ts}{path.suffix}")
        tmp.replace(alt)
        print(f"[!] {path.name} locked. Wrote {len(rows)} rows to {alt.resolve()} instead.")


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args, _ = ap.parse_known_args()
    out_path = Path(args.out)

    print(f"[i] Output CSV: {out_path.resolve()}")
    if OVERWRITE and out_path.exists():
        out_path.unlink()
    ensure_csv(FIELDS, out_path)

    all_rows = []

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

        for url in TARGET_PAGES:
            print(f"\n[+] Visiting: {url}")
            try:
                page.goto(url, timeout=50000)
                page.wait_for_load_state("domcontentloaded")
                rand_wait(0.6, 1.0)
                dismiss_popups(page)
                human_scroll(page, 6)

                total_visible = load_all_products(page, max_clicks=220, grow_timeout_ms=22000)
                print(f"    [LoadMore] total unique products visible: {total_visible}")

                try:
                    page.wait_for_load_state("networkidle", timeout=3000)
                except Exception:
                    pass

            except PWTimeout:
                print(f"[!] Timeout: {url}")

            rows = extract_deals_from_collection(context, page, url)
            print(f"    Extracted {len(rows)} deals via JSON")
            all_rows.extend(rows)

        context.close()
        browser.close()

    final_by_url = {r["DealURL"]: r for r in all_rows}
    final_rows = list(final_by_url.values())

    write_rows(final_rows, FIELDS, out_path)


if __name__ == "__main__":
    main()
