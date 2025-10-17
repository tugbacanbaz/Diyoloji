from logManager import logger
from crawler import run_crawl

# Hedef: https://www.turkcell.com.tr/destek/servisler-ve-internet
CONFIG = {
    "BASE_URL":  "https://www.turkcell.com.tr",
    "SEED_PATH": "/destek/servisler-ve-internet",
    "START_URL": "https://www.turkcell.com.tr/destek/servisler-ve-internet",

    # Çıktılar
    "OUT_CSV":   "7.service.csv",
    "OUT_JSONL": "7.service.jsonl",

    # Davranış ayarları
    "PAGELOAD_WAIT_SEC": 15,
    "SLEEP_MIN_MAX": (0.5, 1.1),
    "SKIP_PATTERNS": [
        "#", "mailto:", "tel:",
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".zip", ".rar", ".7z", ".xlsx", ".xls", ".doc", ".docx", ".ppt", ".pptx", ".pdf"
    ],

    # Yalnızca bu ağacın altını gez
    "ALLOWED_PREFIX": "/destek/servisler-ve-internet",

    # URL segment indeksleri: /destek/servisler-ve-internet/<category>/<slug>
    "CATEGORY_IDX": 2,
    "SUBCATEGORY_IDX": 3,
}

if __name__ == "__main__":
    logger.warning("RUN: Turkcell Destek > Servisler ve İnternet (generic) crawl")
    run_crawl(CONFIG)
    logger.warning("DONE: Outputs -> 7.service.csv, 7.service.jsonl")
