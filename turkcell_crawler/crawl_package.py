from logManager import logger
from crawler import run_crawl

# Hedef: https://www.turkcell.com.tr/destek/tarife-ve-paketler
CONFIG = {
    "BASE_URL":  "https://www.turkcell.com.tr",
    "SEED_PATH": "/destek/tarife-ve-paketler",
    "START_URL": "https://www.turkcell.com.tr/destek/tarife-ve-paketler",

    # İstenen dosya adları
    "OUT_CSV":   "2.package.csv",
    "OUT_JSONL": "2.package.jsonl",

    # Davranış ayarları
    "PAGELOAD_WAIT_SEC": 15,
    "SLEEP_MIN_MAX": (0.5, 1.1),
    "SKIP_PATTERNS": [
        "#", "mailto:", "tel:",
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".zip", ".rar", ".7z", ".xlsx", ".xls", ".doc", ".docx", ".ppt", ".pptx", ".pdf"
    ],

    # Sadece bu ağacın altındaki linkleri al
    "ALLOWED_PREFIX": "/destek/tarife-ve-paketler",

    # URL parça indeksleri: /destek/tarife-ve-paketler/<category>/<slug>
    "CATEGORY_IDX": 2,
    "SUBCATEGORY_IDX": 3,
}

if __name__ == "__main__":
    logger.warning("RUN: Turkcell Destek > Tarife ve Paketler (generic) crawl")
    run_crawl(CONFIG)
    logger.warning("DONE: Outputs -> 2.package.csv, 2.package.jsonl")
