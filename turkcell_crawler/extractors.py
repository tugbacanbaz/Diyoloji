import time, random, csv, json, urllib.parse, unicodedata, re
from bs4 import BeautifulSoup

# ---- ÇALIŞMA ZAMANI KONFİG ----
# crawler.py içinden set edilecek; defaultlar güvenli.
BASE_URL = "https://www.turkcell.com.tr"
SKIP_PATTERNS = [
    "#", "mailto:", "tel:",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".zip", ".rar", ".7z", ".xlsx", ".xls", ".doc", ".docx", ".ppt", ".pptx", ".pdf"
]
SLEEP_MIN_MAX = (0.5, 1.1)

def set_globals(base_url=None, skip_patterns=None, sleep_min_max=None):
    global BASE_URL, SKIP_PATTERNS, SLEEP_MIN_MAX
    if base_url is not None:
        BASE_URL = base_url
    if skip_patterns is not None:
        SKIP_PATTERNS = skip_patterns
    if sleep_min_max is not None:
        SLEEP_MIN_MAX = sleep_min_max

# -------------------- utils --------------------
def rnd_sleep(a=None, b=None):
    a = a if a is not None else SLEEP_MIN_MAX[0]
    b = b if b is not None else SLEEP_MIN_MAX[1]
    time.sleep(random.uniform(a, b))

def to_abs(url: str) -> str:
    return urllib.parse.urljoin(BASE_URL, url)

def is_skip(href: str) -> bool:
    if not href:
        return True
    low = href.lower().strip()
    return any(p in low for p in SKIP_PATTERNS)

def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii")
    return s.lower().strip()

def clean_text(txt: str) -> str:
    txt = (txt or "").replace("\xa0", " ")
    txt = re.sub(r"[\u200b-\u200f\u202a-\u202e]", "", txt)
    txt = re.sub(r"[\r\n]+", " ", txt)
    txt = re.sub(r"\s{2,}", " ", txt)
    return txt.strip()

def dedupe_consecutive(parts):
    out = []
    for p in parts:
        if not out or p != out[-1]:
            out.append(p)
    return out

def collapse_repeated_sequence(parts):
    n = len(parts)
    if n >= 2 and n % 2 == 0:
        half = n // 2
        if parts[:half] == parts[half:]:
            return parts[:half]
    return parts

def _strip_ellipsis(txt: str) -> str:
    if not txt:
        return txt
    txt = re.sub(r"[\.…]+$", "", txt).strip()
    return txt

def _breadcrumb_text_from_any(node):
    el = (
        node.select_one("[title]") or
        node.select_one("[aria-label]") or
        node.select_one("a") or
        node.select_one("span") or
        node
    )
    for attr in ("title", "aria-label"):
        val = el.get(attr)
        if val and val.strip():
            txt = val.strip()
            break
    else:
        txt = el.get_text(" ", strip=True)

    txt = re.sub(r"\s+", " ", txt).strip()
    txt = _strip_ellipsis(txt)
    if txt in {">", "/", "›"}:
        return ""
    return txt

# -------------------- link discovery --------------------
def extract_links_from_listing(html: str, allowed_prefix: str):
    """
    Liste/akordeon sayfasından `allowed_prefix` altındaki makale linklerini çek.
    Örn: allowed_prefix = '/destek/hattiniz'
    """
    soup = BeautifulSoup(html, "html.parser")
    links = set()

    # 1) A tag'leri
    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        if not href or is_skip(href):
            continue
        absu = to_abs(href)
        p = urllib.parse.urlparse(absu)
        if p.netloc.endswith("turkcell.com.tr") and p.path.startswith(allowed_prefix):
            links.add(absu)

    # 2) data-href / data-url
    for btn in soup.select("[data-href], [data-url]"):
        val = (btn.get("data-href") or btn.get("data-url") or "").strip()
        if not val or is_skip(val):
            continue
        absu = to_abs(val)
        p = urllib.parse.urlparse(absu)
        if p.netloc.endswith("turkcell.com.tr") and p.path.startswith(allowed_prefix):
            links.add(absu)

    return links

# -------------------- article extraction --------------------
def extract_article_fields(html: str, url: str, category_idx=2, subcategory_idx=3):
    """
    Sayfadan başlık, breadcrumb, kategori ve SADECE makale gövdesini çıkar.
    category/subcategory URL segment indeksleri ile belirlenir.
    """
    from urllib.parse import urlparse

    soup = BeautifulSoup(html, "html.parser")

    # Başlık
    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else (soup.title.string.strip() if soup.title and soup.title.string else "")

    # Breadcrumb
    breadcrumb = ""
    ant_items = soup.select(".ant-breadcrumb li")
    if ant_items:
        parts = []
        for li in ant_items:
            klass = " ".join(li.get("class", []))
            if "ant-breadcrumb-separator" in klass:
                continue
            txt = _breadcrumb_text_from_any(li)
            if txt:
                parts.append(txt)
        parts = collapse_repeated_sequence(parts)
        parts = dedupe_consecutive(parts)
        if parts:
            last = _strip_ellipsis(parts[-1])
            ttl  = _strip_ellipsis(title)
            if last == ttl or last.rstrip(":") == ttl.rstrip(":"):
                parts = parts[:-1]
        if parts:
            breadcrumb = " > ".join(parts)

    if not breadcrumb:
        for sel in ("nav.breadcrumb li", ".breadcrumb li", "[aria-label='breadcrumb'] li"):
            nodes = soup.select(sel)
            if nodes:
                parts = []
                for n in nodes:
                    txt = _breadcrumb_text_from_any(n)
                    if txt:
                        parts.append(txt)
                parts = collapse_repeated_sequence(parts)
                parts = dedupe_consecutive(parts)
                if parts:
                    last = _strip_ellipsis(parts[-1])
                    ttl  = _strip_ellipsis(title)
                    if last == ttl or last.rstrip(":") == ttl.rstrip(":"):
                        parts = parts[:-1]
                if parts:
                    breadcrumb = " > ".join(parts)
                    break

    # Gürültüleri temizle
    for bad in soup.select(
        "header, nav, footer, aside, noscript, script, style, "
        ".footer, .site-footer, .global-footer, "
        ".header, .site-header, .global-header, "
        ".menu, .mega-menu, .breadcrumbs, .breadcrumb"
    ):
        bad.decompose()

    # Makale kökü
    article_root = None
    if h1:
        cur = h1
        stop_tags = {"main", "article", "section", "div"}
        while cur and cur.name != "body":
            if cur.name in stop_tags:
                article_root = cur
                break
            cur = cur.parent
    if not article_root:
        article_root = soup.select_one("main article") or soup.select_one("main") or soup.select_one("article") or soup.body

    if article_root:
        # "Diğer içerikler" sonrası kes
        other_titles = ["diger icerikler", "benzer icerikler", "ilgili icerikler", "onerilen icerikler"]
        cut_nodes = []
        for hdr in article_root.find_all(["h2", "h3", "h4"]):
            txt = norm(hdr.get_text(" ", strip=True))
            if any(key in txt for key in other_titles):
                cut_nodes.append(hdr)
        for hdr in cut_nodes:
            sib = hdr.next_sibling
            hdr.decompose()
            while sib:
                nxt = sib.next_sibling
                try:
                    sib.extract() if hasattr(sib, "extract") else None
                except Exception:
                    pass
                sib = nxt

        # Tipik related blokları kaldır
        for rel in article_root.select(
            ".related, .related-articles, .other-contents, .suggestions, .recommendations, "
            ".sidebar, .rail, .cards, [data-component*='related'], [aria-label*='ilgili']"
        ):
            rel.decompose()

        for a in article_root.find_all("a"):
            t = norm(a.get_text(" ", strip=True))
            if "tumunu gor" in t or "tumunu goster" in t or "tumunu goruntule" in t or "tumunu görüntüle" in t:
                try:
                    a.decompose()
                except Exception:
                    pass

    main_like = article_root or soup
    raw_text = main_like.get_text(" ", strip=True)
    content_text = clean_text(raw_text)
    content_html = clean_text(str(main_like))

    # URL'den kategori çıkar
    parts = [p for p in urlparse(url).path.split("/") if p]
    category = parts[category_idx] if len(parts) > category_idx else ""
    subcategory = parts[subcategory_idx] if len(parts) > subcategory_idx else ""

    return {
        "url": url,
        "title": title,
        "breadcrumb": breadcrumb,
        "category": category,
        "subcategory": subcategory,
        "content_text": content_text,
        "content_html": content_html
    }

# -------------------- persistence helpers --------------------
def write_csv_header_if_missing(path, header):
    try:
        with open(path, "r", encoding="utf-8"):
            return
    except FileNotFoundError:
        with open(path, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(header)

def append_csv_row(path, row):
    with open(path, "a", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(row)

def append_jsonl(path, obj):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
