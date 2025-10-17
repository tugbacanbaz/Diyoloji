from logManager import logger
from crawler import run_crawl

# Hedef: https://www.turkcell.com.tr/destek/financell
CONFIG = {
    "BASE_URL":  "https://www.turkcell.com.tr",
    "SEED_PATH": "/destek/financell",
    "START_URL": "https://www.turkcell.com.tr/destek/financell",

    # Çıktılar
    "OUT_CSV":   "12.financell.csv",
    "OUT_JSONL": "12.financell.jsonl",

    # Davranış ayarları
    "PAGELOAD_WAIT_SEC": 15,
    "SLEEP_MIN_MAX": (0.5, 1.1),
    "SKIP_PATTERNS": [
        "#", "mailto:", "tel:",
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".zip", ".rar", ".7z", ".xlsx", ".xls", ".doc", ".docx", ".ppt", ".pptx", ".pdf"
    ],

    # Yalnızca bu ağacın altını gez
    "ALLOWED_PREFIX": "/destek/financell",

    # URL parça indeksleri: /destek/financell/<category>/<slug>
    "CATEGORY_IDX": 2,
    "SUBCATEGORY_IDX": 3,
}

if __name__ == "__main__":
    logger.warning("RUN: Turkcell Destek > Financell (generic) crawl")
    run_crawl(CONFIG)
    logger.warning("DONE: Outputs -> 12.financell.csv, 12.financell.jsonl")
