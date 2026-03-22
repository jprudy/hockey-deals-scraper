from __future__ import annotations

# human_like_extraction_csv.py -- Sport Excellence (clearance-hockey) -- v5.2 + PATCH
# Adds: --out support, BOM-safe CSV, price formatting without commas.

import argparse
import csv
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

# ----- Console UTF-8 (Windows)
if os.name == "nt":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------- Paths / defaults ----------
ROOT = Path(__file__).parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
DEFAULT_CSV_PATH = DATA / "sportexcellence_latest.csv"

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

COLL_URL = "https://sportsexcellence.com/collections/clearance-hockey"
TARGET_PAGES = [COLL_URL]

OVERWRITE = True  # overwrite to avoid stale rows
HEADLESS = True
MAX_PRODUCTS = 5000

FAST_JSON_SCREEN = True
SKIP_OUT_OF_STOCK = True
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

# ===== Hard filters =====
NEWSLETTER_RE = re.compile(r"\b(subscribe|newsletter|sign\s*up)\b", re.I)
LOGO_RE = re.compile(r"Sports_Excellence_Logo|/logo", re.I)

# Non-hockey words (belt & suspenders)
NON_HOCKEY_EXCLUDES = re.compile(
    r"\b(baseball|softball|lacrosse|soccer|football|basketball|volleyball|tennis|pickleball|golf)\b",
    re.I,
)

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
        (r"\b(goalie )?mask(s)?\b", "Mask"),
        (r"\b(throat|neck)\s*(guard|protector)s?\b", "Neck Guard"),
        (r"\bchest\b.*\barm\b|\bc\/?a\b|\bchest\s*&\s*arm\b", "Chest & Arm Protector"),
        (r"\bcatch(er)? glove(s)?\b|\bcatcher\b", "Catcher Glove"),
        (r"\bblocker(s)?\b", "Blocker"),
        (r"\b(goalie )?pant(s)?\b", "Goalie Pants"),
        (r"\bjock(s)?\/?jill(s)?\b|\bpelvic protector\b|\bjock\b", "Jock/Jill"),
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

ACCESSORY_KEYWORDS = [
    (re.compile(r"\btape(s)?\b", re.I), "Tape"),
    (re.compile(r"\bwheels?\b", re.I), "Wheels"),
    (re.compile(r"\blaces?\b", re.I), "Laces"),
    (re.compile(r"\bbag(s)?\b", re.I), "Bag"),
    (re.compile(r"\bpuck(s)?\b", re.I), "Puck"),
    (re.compile(r"\bgrip(s)?\b", re.I), "Grip"),
    (re.compile(r"\bwax\b", re.I), "Wax"),
    (re.compile(r"\bvisor(s)?\b", re.I), "Visor"),
    (re.compile(r"\bshield(s)?\b", re.I), "Shield"),
    (re.compile(r"\bblade(s)?\b", re.I), "Blade"),
    (re.compile(r"\bguard(s)?\b", re.I), "Guard"),
    (re.compile(r"\bclean(er|ing)\b", re.I), "Cleaner"),
    (re.compile(r"\bbottle(s)?\b", re.I), "Bottle"),
    (re.compile(r"\bnet(s)?\b", re.I), "Net"),
    (re.compile(r"\btarget(s)?\b", re.I), "Target"),
    (re.compile(r"\bcone(s)?\b", re.I), "Cone"),
    (re.compile(r"\bcoach(ing)?\b", re.I), "Coaching"),
    (re.compile(r"\bboard(s)?\b", re.I), "Board"),
    (re.compile(r"\bdecal(s)?|sticker(s)?\b", re.I), "Decal"),
]
PLAYER_GOALIE_SUBNAMES = {
    "Mask",
    "Chest & Arm Protector",
    "Catcher Glove",
    "Blocker",
    "Goalie Pants",
    "Leg Pads",
    "Goalie Skates",
    "Goalie Stick",
    "Helmet",
    "Shoulder Pads",
    "Elbow Pads",
    "Gloves",
    "Hockey Pants",
    "Shin Guards",
    "Skates",
    "Stick",
    "Jersey",
    "Socks",
    "Mouth Guard",
    "Neck Guard",
    "Jock/Jill",
}

STOPWORDS = set(
    """
pack packs assorted variety multi color colours colorway black white red blue green grey gray clear
pair set kit size oz inch inches mm cm junior jr youth senior sr intermediate intermidiate int pro elite league
""".split()
)


def normspaces(s: str) -> str:
    if not s:
        return s
    return re.sub(r"\s{2,}", " ", s.replace("\u00A0", " ").replace("\u202F", " ").replace("\u2007", " "))


PRICE_DEC = re.compile(r"\b(\d{1,4}(?:[.,]\d{3})*(?:[.,]\d{2}))\b")
CUR_WORDS = re.compile(r"(?:\$|cad|price|sale|regular|compare|was)", re.I)
EXCLUDE_WORDS = ("save", "payment", "payments", "sezzle", "klarna", "afterpay", "affirm", "per month")


def parse_price(text: str) -> float | None:
    if not text:
        return None
    t = normspaces(text).strip()
    if "$" not in t and not CUR_WORDS.search(t):
        return None
    m = PRICE_DEC.search(t)
    if not m:
        return None
    token = m.group(1).replace(",", "")
    if token.count(",") == 1 and token.count(".") == 0:
        token = token.replace(",", ".")
    try:
        v = float(token)
        return v if 0 < v <= 10000 else None
    except ValueError:
        return None


PRICE_TOKENS_RE = re.compile(
    r"((?:\$|CAD|USD)\s*\d{1,4}(?:[.,]\d{3})*(?:[.,]\d{2})|\d{1,4}(?:[.,]\d{3})*(?:[.,]\d{2})\s*(?:CAD|USD)|\bSave\b\s*\$?\s*\d+(?:[.,]\d{2})?|\b\d{1,3}%\s*off\b)",
    re.I,
)
CURRENCY_WORDS_RE = re.compile(r"(?:\s|^)(?:CAD|USD|C\$|US\$)(?=\s|$)", re.I)


def strip_price_tokens(s: str) -> str:
    s = PRICE_TOKENS_RE.sub("", s)
    s = CURRENCY_WORDS_RE.sub("", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" ,.-:|")
    s = re.sub(r"(?:\s|^)(?:CAD|USD|C\$|US\$)\s*$", "", s, flags=re.I)
    return s


def clean_title(t: str) -> str:
    if not t:
        return ""
    t = normspaces(t).replace("\n", " ").replace("\r", " ")
    t = re.sub(r"\b(Quick\s*view|Sale\s*price|Regular\s*price|Save\s*\$?\d+[.\d]*|Save\s*\d+%|\d+%\s*off)\b", "", t, flags=re.I)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t.rstrip(" -:|")


def clean_product_title(raw: str) -> str:
    t = strip_price_tokens(clean_title(raw))
    if not t:
        return ""
    if NEWSLETTER_RE.search(t):
        return ""
    return t


def rand_wait(a: float = 0.2, b: float = 0.8) -> None:
    time.sleep(random.uniform(a, b))


def human_scroll(page, steps: int = 8) -> None:
    height = page.evaluate("() => document.body.scrollHeight") or 4000
    step = max(300, height // steps)
    y = 0
    for _ in range(steps):
        y += step
        page.evaluate(f"() => window.scrollTo(0,{y});")
        time.sleep(random.uniform(0.2, 0.6))


def normalize_url(base: str, href: str) -> str:
    return urljoin(base, href or "") if href else base


def dismiss_popups(page) -> None:
    for sel in [
        "button#onetrust-accept-btn-handler",
        "button[aria-label='Accept all']",
        "button:has-text('Accept')",
        "button:has-text('Got it')",
        "div[role='dialog'] button[aria-label='Close']",
        ".popup-close, .close-button, .modal__close-button, .modal__close",
        "button[aria-label='Close dialog']",
        "button:has-text('Continue shopping')",
    ]:
        try:
            el = page.query_selector(sel)
            if el:
                el.click()
        except Exception:
            pass


def numbers_near_price_words(text: str) -> list[float]:
    out: list[float] = []
    if not text:
        return out
    for m in re.finditer(r"\d{1,4}(?:[.,]\d{3})*(?:[.,]\d{2})", text):
        start = max(0, m.start() - 18)
        end = min(len(text), m.end() + 18)
        ctx = text[start:end].lower()
        if any(w in ctx for w in EXCLUDE_WORDS):
            continue
        if "$" in ctx or "cad" in ctx or any(w in ctx for w in ("sale", "regular", "compare", "was", "price")):
            try:
                out.append(float(m.group(0).replace(",", "")))
            except ValueError:
                pass
    return out


SIZE_RXS = [
    (re.compile(r"\b(youth|yth)\b", re.I), "Youth"),
    (re.compile(r"\b(junior|jr\.?)\b", re.I), "Junior"),
    (re.compile(r"\b(intermediate|intermidiate|int\.?)\b", re.I), "Intermediate"),
    (re.compile(r"\b(senior|sr\.?)\b", re.I), "Senior"),
]


def detect_size(text: str) -> str:
    s = text.lower()
    for rx, name in SIZE_RXS:
        if rx.search(s):
            return name
    return ""


def keyword_for_accessories_only(desc: str) -> str:
    for rx, label in ACCESSORY_KEYWORDS:
        if rx.search(desc):
            return label
    tokens = re.findall(r"[A-Za-z][A-Za-z\-&]+", desc)
    for w in reversed(tokens):
        lw = w.lower()
        if lw not in STOPWORDS and len(w) >= 3:
            return w.title()
    return "Other"


def strike_price_in_tree(el, max_levels: int = 3) -> float | None:
    try:
        node = el
        levels = 0
        while node and levels <= max_levels:
            texts = node.evaluate(
                """
                (root) => {
                  const out = [];
                  const all = root.querySelectorAll('*');
                  for (const n of all) {
                    const cs = getComputedStyle(n);
                    const deco = (cs.textDecorationLine || cs.textDecoration || '').toLowerCase();
                    if (deco.includes('line-through')) {
                      const t = (n.textContent || '').trim();
                      if (t) out.push(t);
                    }
                  }
                  const cs2 = getComputedStyle(root);
                  const deco2 = (cs2.textDecorationLine || cs2.textDecoration || '').toLowerCase();
                  if (deco2.includes('line-through')) {
                    const t2 = (root.textContent || '').trim();
                    if (t2) out.push(t2);
                  }
                  return out;
                }
            """
            )
            for t in texts:
                v = parse_price(t)
                if v:
                    return v
            node = node.evaluate_handle("n => n.parentElement").as_element() if node else None
            levels += 1
    except Exception:
        pass
    return None


def reconcile_prices(sale, reg, block_text):
    nums = sorted(set(numbers_near_price_words(block_text)))
    if sale is None and reg is None:
        if len(nums) >= 2:
            sale, reg = nums[0], nums[-1]
        elif len(nums) == 1:
            sale = nums[0]
    else:
        if sale is None and nums:
            sale = nums[0]
        if reg is None and len(nums) >= 2 and (sale is None or nums[-1] > sale):
            reg = nums[-1]
    if sale is not None and reg is not None and reg <= sale and len(nums) >= 2:
        sale, reg = nums[0], nums[-1]
    return sale, reg


GOALIE_WORDS = re.compile(r"\b(goalie|goaltender)\b", re.I)


def ensure_not_goalie_without_keyword(cat: str, sub: str, text_for_check: str):
    if cat == "Goalie Gear" or "goalie" in sub.lower():
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


def get_text(el):
    try:
        return el.inner_text().strip() if el else ""
    except TypeError:
        return ""


# ===== Grid scoping (robust)
GRID_ROOT_SELECTORS = [
    "#product-grid",
    "ul#product-grid",
    ".boost-pfs-filter-products",
    ".product-grid",
    ".collection__products",
    ".collection",
    "[data-product-grid]",
    "main",
]


def collect_product_urls_scoped(page) -> set[str]:
    js = """
    (roots) => {
      const out = new Set();
      for (const r of roots) {
        if (!r) continue;
        const cards = r.querySelectorAll("a[href*='/products/']");
        for (const a of cards) {
          const href = a.getAttribute('href');
          if (!href) continue;
          try {
            const url = new URL(href, location.href);
            out.add(url.origin + url.pathname);
          } catch(e) {
            try {
              const u = new URL(href, location.href);
              out.add(u.origin + u.pathname);
            } catch(e2) {}
          }
        }
      }
      return Array.from(out);
    }
    """
    roots = []
    for sel in GRID_ROOT_SELECTORS:
        try:
            root = page.query_selector(sel)
            if root:
                roots.append(root)
        except Exception:
            pass
    if not roots:
        roots = [page.query_selector("body")]

    try:
        urls = page.evaluate(js, [r for r in roots if r])
    except Exception:
        urls = []
    out: set[str] = set()
    for u in urls:
        try:
            p = urlparse(u)
            if "/products/" not in p.path:
                continue
            out.add(p.scheme + "://" + p.netloc + p.path)
        except Exception:
            pass
    return out


def url_with_page(base_url: str, n: int) -> str:
    p = urlparse(base_url)
    q = parse_qs(p.query)
    q["page"] = [str(n)]
    return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(q, doseq=True), p.fragment))


def crawl_pages_numbered(page, start_url: str, max_pages: int = 120):
    all_seen = collect_product_urls_scoped(page)
    print(f"    [Collect] page=1 -> {len(all_seen)} product links")
    for n in range(2, max_pages + 1):
        next_url = url_with_page(start_url, n)
        print(f"    [Pages] visiting page={n}")
        try:
            page.goto(next_url, timeout=30000)
            page.wait_for_load_state("domcontentloaded")
            human_scroll(page, 6)
            try:
                page.wait_for_load_state("networkidle", timeout=3200)
            except Exception:
                pass
        except PWTimeout:
            print("    [Pages] timeout; stopping.")
            break
        cur = collect_product_urls_scoped(page)
        new = cur - all_seen
        print(f"    [Collect] found {len(new)} new on page {n}")
        if not new:
            print("    [Pages] no new products; stopping.")
            break
        all_seen |= cur
        print(f"    [Pages] total unique so far: {len(all_seen)}")
    return all_seen


# ===== Shopify JSON helpers
def product_json_url(product_url: str) -> str:
    p = urlparse(product_url)
    m = re.search(r"/products/([^/?#]+)", p.path)
    handle = m.group(1) if m else p.path.rstrip("/").split("/")[-1]
    return urlunparse((p.scheme, p.netloc, f"/products/{handle}.js", "", "", ""))


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


def best_discounted_variant_json(data):
    if not data or "variants" not in data:
        return None, None, None, None, "", "", ""
    best = None
    avail_any = None
    for v in data["variants"]:
        available = bool(v.get("available"))
        avail_any = available if avail_any is None else (avail_any or available)
        price = money_from_shopify(v.get("price"))
        compare = money_from_shopify(v.get("compare_at_price"))
        if not is_real_discount(compare, price):
            continue
        pct_score = (compare - price) / compare if compare else 0
        score = (pct_score, compare - price)
        if best is None or score > best[0]:
            best = (score, price, compare, v.get("title", ""))
    title = data.get("title", "")
    vendor = data.get("vendor", "") or "Other"
    image = data.get("featured_image") or (data["images"][0] if data.get("images") else "")
    if best is None:
        return None, None, title, avail_any, "", vendor, image
    _, price, compare, vtitle = best
    return price, compare, title, avail_any, vtitle, vendor, image


def fetch_shopify_product_json(context, product_url: str):
    try:
        r = context.request.get(product_json_url(product_url), timeout=8000)
        if not r.ok:
            return None
        return r.json()
    except Exception:
        return None


# ---- price formatting: no thousands commas
def fmt_price(x):
    return f"{x:.2f}" if isinstance(x, (int, float)) else ""


# ===== Tile lookup (scoped; no <body> use for text)
def find_tile_container(page, product_url: str):
    m = re.search(r"/products/([^/?#]+)", urlparse(product_url).path)
    handle = m.group(1) if m else ""
    if not handle:
        return None, None
    for root_sel in GRID_ROOT_SELECTORS:
        sel = f"{root_sel} a[href*='/products/{handle}']"
        try:
            a = page.query_selector(sel)
        except Exception:
            a = None
        if a:
            try:
                container = a.evaluate_handle(
                    """
                    el => el.closest('li,article,.card,.productgrid--item,.grid__item,.ProductItem,.product-item,.card-information')
                           || el.parentElement
                """
                ).as_element()
            except Exception:
                container = a
            return a, container
    return None, None


# ================= Extraction =================
def extract_list(page, base_url, json_cache: dict | None = None, links: set[str] | None = None):
    if links is None:
        links = collect_product_urls_scoped(page)

    counters = {
        "total": 0,
        "kept": 0,
        "skip_newsletter": 0,
        "skip_logo": 0,
        "skip_no_deal": 0,
        "skip_out_of_stock": 0,
        "skip_nonhockey": 0,
        "skip_no_title": 0,
        "pdp_price_fallback": 0,
    }
    rows = []
    for idx, deal in enumerate(sorted(links)[:MAX_PRODUCTS], start=1):
        counters["total"] += 1

        data = (json_cache or {}).get(deal)
        js_sale = js_reg = None
        js_title = js_vendor = js_image = vtitle = ""
        js_avail = None
        if data:
            js_sale, js_reg, js_title, js_avail, vtitle, js_vendor, js_image = best_discounted_variant_json(data)

        # Title/Brand/Image from JSON first
        title = clean_product_title(js_title) if js_title else ""
        brand = (js_vendor or "").strip() or "Other"
        img = normalize_url(deal, js_image) if js_image else ""

        a, container = find_tile_container(page, deal)

        # Fallback title from tile only if JSON title missing
        if not title and container:
            title_raw = ""
            for sel in [".card__heading", ".card-information__text", ".full-unstyled-link", "h3", "h2"]:
                n = container.query_selector(sel)
                if n:
                    title_raw = n.inner_text().strip()
                    if title_raw:
                        break
            if not title_raw and a:
                title_raw = a.get_attribute("title") or a.inner_text().strip()
            title = clean_product_title(title_raw) or title

        # Final guards
        if not title:
            counters["skip_no_title"] += 1
            continue
        if NEWSLETTER_RE.search(title):
            counters["skip_newsletter"] += 1
            continue
        if NON_HOCKEY_EXCLUDES.search(title):
            counters["skip_nonhockey"] += 1
            continue

        # Prices: prefer JSON if discounted
        sale = js_sale if (js_sale and js_reg and js_sale < js_reg) else None
        reg = js_reg if (js_sale and js_reg and js_sale < js_reg) else None

        # Tile prices if needed
        if (sale is None or reg is None) and container:
            sale_node = (
                container.query_selector(".Price--highlight")
                or container.query_selector(".price-item--sale")
                or container.query_selector(".price__sale .price-item--price")
                or container.query_selector(".price__sale .price-item--last")
                or container.query_selector(".price--sale")
            )
            reg_node = (
                container.query_selector(".Price--compareAt")
                or container.query_selector(".price-item--regular")
                or container.query_selector(".price__regular .price-item--regular")
                or container.query_selector(".price--compare")
                or container.query_selector("s, del")
            )

            def parse_price_local(node):
                return parse_price(get_text(node))

            sale_t = parse_price_local(sale_node)
            reg_t = parse_price_local(reg_node)
            if reg_t is None and container:
                reg_t = strike_price_in_tree(container, max_levels=3)
            block_text = normspaces(get_text(container))
            sale_t, reg_t = reconcile_prices(sale_t, reg_t, block_text)
            if sale_t is not None and reg_t is not None and sale_t < reg_t:
                sale, reg = sale or sale_t, reg or reg_t

        if (sale is None or reg is None) and container:
            ptext = price_area_text(container)
            nums = sorted(set(numbers_near_price_words(ptext)))
            if len(nums) >= 2 and nums[0] > 0 and nums[0] < nums[-1]:
                sale, reg = nums[0], nums[-1]

        # ensure genuine deal
        if not (
            sale
            and reg
            and sale < reg
            and (reg - sale) >= MIN_ABS_DISCOUNT_CAD
            and ((reg - sale) / reg * 100) >= MIN_DISCOUNT_PCT
        ):
            # Grid tile often missing after crawl_pages_numbered (browser left on page N).
            if container is None:
                p_sale, p_reg = try_pdp_prices(page, deal)
                if (
                    p_sale is not None
                    and p_reg is not None
                    and p_sale < p_reg
                    and (p_reg - p_sale) >= MIN_ABS_DISCOUNT_CAD
                    and ((p_reg - p_sale) / p_reg * 100) >= MIN_DISCOUNT_PCT
                ):
                    sale, reg = p_sale, p_reg
                    counters["pdp_price_fallback"] += 1
        if not (
            sale
            and reg
            and sale < reg
            and (reg - sale) >= MIN_ABS_DISCOUNT_CAD
            and ((reg - sale) / reg * 100) >= MIN_DISCOUNT_PCT
        ):
            counters["skip_no_deal"] += 1
            continue

        # Stock state
        stock = "Unknown"
        if js_avail is True:
            stock = "In Stock"
        elif js_avail is False:
            if SKIP_OUT_OF_STOCK:
                counters["skip_out_of_stock"] += 1
                continue
            stock = "Out of Stock"

        # Image: avoid store logo; prefer JSON
        if (not img) and container:
            img_el = container.query_selector("img")
            if img_el:
                cand = (
                    img_el.get_attribute("src")
                    or img_el.get_attribute("data-src")
                    or img_el.get_attribute("data-srcset")
                    or img_el.get_attribute("srcset")
                    or ""
                )
                if cand and "," in cand:
                    cand = cand.split(",")[0].split()[0]
                cand = normalize_url(deal, cand)
                if not LOGO_RE.search(cand):
                    img = cand
        if LOGO_RE.search(img):
            counters["skip_logo"] += 1
            continue

        # Brand from title if JSON empty
        if not brand or brand == "Other":
            for rx, name in BRAND_RXS:
                if rx.search(title):
                    brand = name
                    break
            if not brand:
                brand = "Other"

        # Category/Subcat/Size
        cat = DEFAULTS["Category"]
        sub = ""
        s = f"{title} {vtitle} {deal}"
        goalie_hint = bool(GOALIE_WORDS.search(s))
        for rx, sublabel in SUBCAT_RXS:
            if rx.search(s.lower()):
                sub = sublabel
                cat = SUBCAT_TO_CAT.get(sublabel, "Accessories")
                if sublabel == "Stick" and goalie_hint:
                    sub, cat = "Goalie Stick", "Goalie Gear"
                if sublabel == "Skates" and goalie_hint:
                    sub, cat = "Goalie Skates", "Goalie Gear"
                break
        size = detect_size(title) or detect_size(vtitle)
        if not sub:
            sub_acc = keyword_for_accessories_only(title)
            if sub_acc in PLAYER_GOALIE_SUBNAMES:
                sub_acc = "Other"
            sub = sub_acc
        cat, sub = ensure_not_goalie_without_keyword(cat, sub, s)
        if cat not in ("Accessories", "Player Gear", "Goalie Gear"):
            cat = "Accessories"

        def pct_discount(orig, salev):
            if not orig or not salev or salev >= orig:
                return ""
            pct = round(100 * (orig - salev) / orig)
            return "" if pct < 1 or pct > 90 else str(pct)

        row = {
            "ID": f"{urlparse(base_url).netloc}-L{idx:04d}",
            "ProductName": title,
            "Description": title,
            "OriginalPrice": fmt_price(reg),
            "SalePrice": fmt_price(sale),
            "ImageURL": img,
            "Category": cat,
            "Subcategory": sub,
            "Size": size or DEFAULTS["Size"],
            "Brand": brand,
            "Stock": stock,
            "LinkRetailer": base_url,
            "DealURL": deal,
            "StartDate": DEFAULTS["StartDate"],
            "EndDate": DEFAULTS["EndDate"],
            "discount%": pct_discount(reg, sale),
            "Featured": DEFAULTS["Featured"],
        }
        if idx <= 3:
            print(f"    #{idx} SALE={row['SalePrice']} REG={row['OriginalPrice']} CAT={cat} SUB={sub} BRAND={brand} {title}")
        rows.append(row)
        counters["kept"] += 1

    print(
        "[Summary] "
        f"Kept={counters['kept']}  "
        f"pdp_price_fallback={counters['pdp_price_fallback']}  "
        f"Skip: no_title={counters['skip_no_title']}, newsletter={counters['skip_newsletter']}, "
        f"nonhockey={counters['skip_nonhockey']}, logo={counters['skip_logo']}, "
        f"no_deal={counters['skip_no_deal']}, oos={counters['skip_out_of_stock']}"
    )
    return rows


# ---------------- CSV helpers (BOM-safe) ----------------
BOM = "\ufeff"


def _clean_key(k):
    return str(k).replace(BOM, "").strip()


def _clean_row(d):
    return {_clean_key(k): v for k, v in d.items()}


# normalize fieldnames once
FIELDS = [_clean_key(c) for c in FIELDS]


def ensure_csv(headers, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=[_clean_key(c) for c in headers]).writeheader()


def read_by_url(path: Path):
    data = {}
    if not path.exists():
        return data
    # utf-8-sig strips a possible BOM from the first header
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            row = _clean_row(row)
            u = row.get("DealURL", "")
            if u:
                data[u] = row
    return data


def write_rows(rows, headers, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[_clean_key(c) for c in headers], extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(_clean_row(r))
    try:
        tmp.replace(path)
        print(f"[OK] Wrote {len(rows)} rows to {path.resolve()}")
    except PermissionError:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        alt = path.with_name(f"{path.stem}_{ts}{path.suffix}")
        tmp.replace(alt)
        print(f"[OK] Wrote {len(rows)} rows to {alt.resolve()} (original in use).")


def merge_update(existing_by_url: dict, new_rows: list[dict]) -> list[dict]:
    upd = {
        "ProductName",
        "Description",
        "OriginalPrice",
        "SalePrice",
        "ImageURL",
        "Brand",
        "Subcategory",
        "Category",
        "discount%",
        "StartDate",
        "EndDate",
        "Featured",
        "Size",
        "Stock",
    }
    for r in new_rows:
        u = r["DealURL"]
        if u in existing_by_url:
            base = existing_by_url[u]
            for k in upd:
                v = r.get(k, "")
                if v not in ("", None):
                    base[k] = v
        else:
            existing_by_url[u] = r
    return list(existing_by_url.values())


# ---- price area helper (needs to be after get_text)
PRICE_AREAS = [
    ".price",
    ".price__container",
    ".product__price",
    ".product__price-container",
    ".card__price",
    ".productgrid--price",
    ".boost-pfs-filter-product-item-price",
    ".price__sale",
    ".price--on-sale",
    ".price--sale",
    ".product-price",
    "[data-product-price]",
    ".price-item--sale",
    ".price-item--regular",
    ".price__regular",
    ".price__badges",
]


def try_pdp_prices(page, product_url: str) -> tuple[float | None, float | None]:
    """
    When collection-grid pricing fails (common after multi-page crawl: `page` is not on
    the product's listing page), load the PDP briefly and read sale/compare prices.
    """
    try:
        page.goto(product_url, timeout=20000, wait_until="domcontentloaded")
        rand_wait(0.12, 0.28)
        dismiss_popups(page)
        sale_node = (
            page.query_selector(".Price--highlight")
            or page.query_selector(".price-item--sale")
            or page.query_selector(".price__sale .price-item--price")
            or page.query_selector(".price__sale .price-item--last")
            or page.query_selector(".price--sale")
        )
        reg_node = (
            page.query_selector(".Price--compareAt")
            or page.query_selector(".price-item--regular")
            or page.query_selector(".price__regular .price-item--regular")
            or page.query_selector(".price--compare")
            or page.query_selector("s.price-item--regular")
        )
        sale = parse_price(get_text(sale_node))
        reg = parse_price(get_text(reg_node))
        main = page.query_selector("main, [data-product], .product, #MainContent") or page.query_selector("body")
        if main:
            if reg is None:
                reg = strike_price_in_tree(main, max_levels=4)
            ptext = price_area_text(main)
            nums = sorted(set(numbers_near_price_words(ptext)))
            if len(nums) >= 2 and nums[0] > 0 and nums[0] < nums[-1]:
                sale = sale if sale is not None else nums[0]
                reg = reg if reg is not None else nums[-1]
        if sale is not None and reg is not None and sale < reg:
            return sale, reg
    except Exception:
        pass
    return None, None


def price_area_text(container) -> str:
    if not container:
        return ""
    for sel in PRICE_AREAS:
        node = container.query_selector(sel)
        if node:
            try:
                base = node.inner_text() or ""
                hidden = " ".join((e.inner_text() or "") for e in node.query_selector_all(".visually-hidden,[aria-hidden='true']"))
                aria = " ".join((e.get_attribute("aria-label") or "") for e in node.query_selector_all("[aria-label]"))
                return f"{base} {hidden} {aria}"
            except Exception:
                pass
    return ""


def main() -> None:
    # --out support
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--out", default=str(DEFAULT_CSV_PATH))
    args, _ = ap.parse_known_args()
    csv_path = Path(args.out)

    print(f"[i] Output CSV: {csv_path.resolve()}")
    if OVERWRITE and csv_path.exists():
        csv_path.unlink()
    ensure_csv(FIELDS, csv_path)

    out = []
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

                all_seen = crawl_pages_numbered(page, url, max_pages=120)
                print(f"    [Pages] total unique after paging: {len(all_seen)}")
            except PWTimeout:
                print(f"[!] Timeout: {url}")
                all_seen = set()

            json_cache = {}
            if FAST_JSON_SCREEN and all_seen:
                product_links = list(all_seen)
                for i, u in enumerate(product_links, start=1):
                    try:
                        data = fetch_shopify_product_json(context, u)
                        if data:
                            json_cache[u] = data
                    except Exception:
                        pass
                    if i % 60 == 0:
                        print(f"    [JSON] prefetched {i}/{len(product_links)}")

            # Pagination leaves `page` on the last ?page=N URL; extract_list uses live DOM for
            # tiles. Rewind to page 1 so page-1 products resolve in the grid.
            if all_seen:
                print("    [Rewind] collection page 1 for grid pricing context")
                try:
                    page.goto(url, timeout=50000)
                    page.wait_for_load_state("domcontentloaded")
                    rand_wait(0.4, 0.8)
                    dismiss_popups(page)
                    human_scroll(page, 6)
                except PWTimeout:
                    print("    [Rewind] timeout (continuing with current DOM)")

            rows = extract_list(page, url, json_cache if FAST_JSON_SCREEN else None, links=all_seen or None)
            print(f"    Extracted {len(rows)} products")
            out.extend(rows)

        context.close()
        browser.close()

    if OVERWRITE:
        write_rows(out, FIELDS, csv_path)
        return
    existing = read_by_url(csv_path)
    merged = merge_update(existing, out)
    write_rows(merged, FIELDS, csv_path)


if __name__ == "__main__":
    main()
