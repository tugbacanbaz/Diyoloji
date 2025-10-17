from logManager import logger
from crawler import run_crawl

# Hedef: https://www.turkcell.com.tr/destek/online-alisveris
CONFIG = {
    "BASE_URL":  "https://www.turkcell.com.tr",
    "SEED_PATH": "/destek/online-alisveris",
    "START_URL": "https://www.turkcell.com.tr/destek/online-alisveris",

    # Çıktılar
    "OUT_CSV":   "9.pasaj.csv",
    "OUT_JSONL": "9.pasaj.jsonl",

    # Davranış ayarları
    "PAGELOAD_WAIT_SEC": 15,
    "SLEEP_MIN_MAX": (0.5, 1.1),
    "SKIP_PATTERNS": [
        "#", "mailto:", "tel:",
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".zip", ".rar", ".7z", ".xlsx", ".xls", ".doc", ".docx", ".ppt", ".pptx", ".pdf"
    ],

    # Yalnızca bu ağacın altını gez
    "ALLOWED_PREFIX": "/destek/online-alisveris",

    # URL segment indeksleri: /destek/online-alisveris/<category>/<slug>
    "CATEGORY_IDX": 2,
    "SUBCATEGORY_IDX": 3,
}

if __name__ == "__main__":
    logger.warning("RUN: Turkcell Destek > Online Alışveriş (generic) crawl")
    run_crawl(CONFIG)
    logger.warning("DONE: Outputs -> 9.pasaj.csv, 9.pasaj.jsonl")
