from logManager import logger
from crawler import run_crawl

# Hedef: https://www.turkcell.com.tr/destek/yenilenmis-cihazlar
CONFIG = {
    "BASE_URL":  "https://www.turkcell.com.tr",
    "SEED_PATH": "/destek/yenilenmis-cihazlar",
    "START_URL": "https://www.turkcell.com.tr/destek/yenilenmis-cihazlar",

    # Çıktılar
    "OUT_CSV":   "14.refurbished_devices.csv",
    "OUT_JSONL": "14.refurbished_devices.jsonl",

    # Davranış ayarları
    "PAGELOAD_WAIT_SEC": 15,
    "SLEEP_MIN_MAX": (0.5, 1.1),
    "SKIP_PATTERNS": [
        "#", "mailto:", "tel:",
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".zip", ".rar", ".7z", ".xlsx", ".xls", ".doc", ".docx", ".ppt", ".pptx", ".pdf"
    ],

    # Yalnızca bu ağacın altını gez
    "ALLOWED_PREFIX": "/destek/yenilenmis-cihazlar",

    # URL parça indeksleri: /destek/yenilenmis-cihazlar/<category>/<slug>
    "CATEGORY_IDX": 2,
    "SUBCATEGORY_IDX": 3,
}

if __name__ == "__main__":
    logger.warning("RUN: Turkcell Destek > Yenilenmiş Cihazlar (generic) crawl")
    run_crawl(CONFIG)
    logger.warning("DONE: Outputs -> 14.refurbished_devices.csv, 14.refurbished_devices.jsonl")
