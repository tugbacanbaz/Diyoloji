from logManager import logger
from crawler import run_crawl

# Hedef: https://www.turkcell.com.tr/destek/4-5g
CONFIG = {
    "BASE_URL":  "https://www.turkcell.com.tr",
    "SEED_PATH": "/destek/4-5g",
    "START_URL": "https://www.turkcell.com.tr/destek/4-5g",

    # Çıktılar
    "OUT_CSV":   "5.g.csv",
    "OUT_JSONL": "5.g.jsonl",

    # Davranış ayarları
    "PAGELOAD_WAIT_SEC": 15,
    "SLEEP_MIN_MAX": (0.5, 1.1),
    "SKIP_PATTERNS": [
        "#", "mailto:", "tel:",
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".zip", ".rar", ".7z", ".xlsx", ".xls", ".doc", ".docx", ".ppt", ".pptx", ".pdf"
    ],

    # Sadece bu ağacın altındaki linkleri takip et
    "ALLOWED_PREFIX": "/destek/4-5g",

    # URL segment indeksleri: /destek/4-5g/<category>/<slug>
    "CATEGORY_IDX": 2,
    "SUBCATEGORY_IDX": 3,
}

if __name__ == "__main__":
    logger.warning("RUN: Turkcell Destek > 4.5G (generic) crawl")
    run_crawl(CONFIG)
    logger.warning("DONE: Outputs -> 5.g.csv, 5.g.jsonl")
