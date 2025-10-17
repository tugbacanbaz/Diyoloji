from logManager import logger
from crawler import run_crawl

# Hedef: https://www.turkcell.com.tr/destek/wiyo
CONFIG = {
    "BASE_URL":  "https://www.turkcell.com.tr",
    "SEED_PATH": "/destek/wiyo",
    "START_URL": "https://www.turkcell.com.tr/destek/wiyo",

    # Çıktılar
    "OUT_CSV":   "15.wiyo.csv",
    "OUT_JSONL": "15.wiyo.jsonl",

    # Davranış ayarları
    "PAGELOAD_WAIT_SEC": 15,
    "SLEEP_MIN_MAX": (0.5, 1.1),
    "SKIP_PATTERNS": [
        "#", "mailto:", "tel:",
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".zip", ".rar", ".7z", ".xlsx", ".xls", ".doc", ".docx", ".ppt", ".pptx", ".pdf"
    ],

    # Yalnızca bu ağacın altını gez
    "ALLOWED_PREFIX": "/destek/wiyo",

    # URL parça indeksleri: /destek/wiyo/<category>/<slug>
    "CATEGORY_IDX": 2,
    "SUBCATEGORY_IDX": 3,
}

if __name__ == "__main__":
    logger.warning("RUN: Turkcell Destek > WIYO (generic) crawl")
    run_crawl(CONFIG)
    logger.warning("DONE: Outputs -> 15.wiyo.csv, 15.wiyo.jsonl")
