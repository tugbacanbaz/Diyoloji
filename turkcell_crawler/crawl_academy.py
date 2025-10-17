from logManager import logger
from crawler import run_crawl

# Hedef: https://www.turkcell.com.tr/destek/turkcell-akademi
CONFIG = {
    "BASE_URL":  "https://www.turkcell.com.tr",
    "SEED_PATH": "/destek/turkcell-akademi",
    "START_URL": "https://www.turkcell.com.tr/destek/turkcell-akademi",

    # Çıktılar
    "OUT_CSV":   "13.academy.csv",
    "OUT_JSONL": "13.academy.jsonl",

    # Davranış ayarları
    "PAGELOAD_WAIT_SEC": 15,
    "SLEEP_MIN_MAX": (0.5, 1.1),
    "SKIP_PATTERNS": [
        "#", "mailto:", "tel:",
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".zip", ".rar", ".7z", ".xlsx", ".xls", ".doc", ".docx", ".ppt", ".pptx", ".pdf"
    ],

    # Yalnızca bu ağacın altını gez
    "ALLOWED_PREFIX": "/destek/turkcell-akademi",

    # URL parça indeksleri: /destek/turkcell-akademi/<category>/<slug>
    "CATEGORY_IDX": 2,
    "SUBCATEGORY_IDX": 3,
}

if __name__ == "__main__":
    logger.warning("RUN: Turkcell Destek > Turkcell Akademi (generic) crawl")
    run_crawl(CONFIG)
    logger.warning("DONE: Outputs -> 13.academy.csv, 13.academy.jsonl")
