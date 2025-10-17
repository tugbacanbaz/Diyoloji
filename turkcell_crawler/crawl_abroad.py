from logManager import logger
from crawler import run_crawl

# Hedef: https://www.turkcell.com.tr/destek/yurtdisi
CONFIG = {
    "BASE_URL":  "https://www.turkcell.com.tr",
    "SEED_PATH": "/destek/yurtdisi",
    "START_URL": "https://www.turkcell.com.tr/destek/yurtdisi",

    # Çıktılar
    "OUT_CSV":   "6.abroad.csv",
    "OUT_JSONL": "6.abroad.jsonl",

    # Davranış ayarları
    "PAGELOAD_WAIT_SEC": 15,
    "SLEEP_MIN_MAX": (0.5, 1.1),
    "SKIP_PATTERNS": [
        "#", "mailto:", "tel:",
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".zip", ".rar", ".7z", ".xlsx", ".xls", ".doc", ".docx", ".ppt", ".pptx", ".pdf"
    ],

    # Sadece bu ağacın altındaki linkleri takip et
    "ALLOWED_PREFIX": "/destek/yurtdisi",

    # URL segment indeksleri: /destek/yurtdisi/<category>/<slug>
    "CATEGORY_IDX": 2,
    "SUBCATEGORY_IDX": 3,
}

if __name__ == "__main__":
    logger.warning("RUN: Turkcell Destek > Yurtdışı (generic) crawl")
    run_crawl(CONFIG)
    logger.warning("DONE: Outputs -> 6.abroad.csv, 6.abroad.jsonl")
