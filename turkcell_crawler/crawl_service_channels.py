from logManager import logger
from crawler import run_crawl

# Hedef: https://www.turkcell.com.tr/destek/hizmet-kanallarimiz
CONFIG = {
    "BASE_URL":  "https://www.turkcell.com.tr",
    "SEED_PATH": "/destek/hizmet-kanallarimiz",
    "START_URL": "https://www.turkcell.com.tr/destek/hizmet-kanallarimiz",

    # Çıktılar
    "OUT_CSV":   "11.service_channel.csv",
    "OUT_JSONL": "11.service_channel.jsonl",

    # Davranış ayarları
    "PAGELOAD_WAIT_SEC": 15,
    "SLEEP_MIN_MAX": (0.5, 1.1),
    "SKIP_PATTERNS": [
        "#", "mailto:", "tel:",
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".zip", ".rar", ".7z", ".xlsx", ".xls", ".doc", ".docx", ".ppt", ".pptx", ".pdf"
    ],

    # Yalnızca bu ağacın altını gez
    "ALLOWED_PREFIX": "/destek/hizmet-kanallarimiz",

    # URL parça indeksleri: /destek/hizmet-kanallarimiz/<category>/<slug>
    "CATEGORY_IDX": 2,
    "SUBCATEGORY_IDX": 3,
}

if __name__ == "__main__":
    logger.warning("RUN: Turkcell Destek > Hizmet Kanallarımız (generic) crawl")
    run_crawl(CONFIG)
    logger.warning("DONE: Outputs -> 11.service_channel.csv, 11.service_channel.jsonl")
