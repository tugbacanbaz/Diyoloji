from logManager import logger
from crawler import run_crawl

# Hedef: https://www.turkcell.com.tr/destek/kampanya
CONFIG = {
    "BASE_URL":  "https://www.turkcell.com.tr",
    "SEED_PATH": "/destek/kampanya",
    "START_URL": "https://www.turkcell.com.tr/destek/kampanya",

    # Çıktılar
    "OUT_CSV":   "8.campaign.csv",
    "OUT_JSONL": "8.campaign.jsonl",

    # Davranış ayarları
    "PAGELOAD_WAIT_SEC": 15,
    "SLEEP_MIN_MAX": (0.5, 1.1),
    "SKIP_PATTERNS": [
        "#", "mailto:", "tel:",
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".zip", ".rar", ".7z", ".xlsx", ".xls", ".doc", ".docx", ".ppt", ".pptx", ".pdf"
    ],

    # Yalnızca bu ağacın altını gez
    "ALLOWED_PREFIX": "/destek/kampanya",

    # URL segment indeksleri: /destek/kampanya/<category>/<slug>
    "CATEGORY_IDX": 2,
    "SUBCATEGORY_IDX": 3,
}

if __name__ == "__main__":
    logger.warning("RUN: Turkcell Destek > Kampanya (generic) crawl")
    run_crawl(CONFIG)
    logger.warning("DONE: Outputs -> 8.campaign.csv, 8.campaign.jsonl")
