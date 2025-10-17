from logManager import logger
from crawler import run_crawl

# Hedef: https://www.turkcell.com.tr/destek/turkcellli-olmak
CONFIG = {
    "BASE_URL":  "https://www.turkcell.com.tr",
    "SEED_PATH": "/destek/turkcellli-olmak",
    "START_URL": "https://www.turkcell.com.tr/destek/turkcellli-olmak",

    # Çıktılar
    "OUT_CSV":   "4.turkcell_member.csv",
    "OUT_JSONL": "4.turkcell_member.jsonl",

    # Davranış ayarları
    "PAGELOAD_WAIT_SEC": 15,
    "SLEEP_MIN_MAX": (0.5, 1.1),
    "SKIP_PATTERNS": [
        "#", "mailto:", "tel:",
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".zip", ".rar", ".7z", ".xlsx", ".xls", ".doc", ".docx", ".ppt", ".pptx", ".pdf"
    ],

    # Sadece bu ağacın altındaki linkleri takip et
    "ALLOWED_PREFIX": "/destek/turkcellli-olmak",

    # URL segment indeksleri: /destek/turkcellli-olmak/<category>/<slug>
    "CATEGORY_IDX": 2,
    "SUBCATEGORY_IDX": 3,
}

if __name__ == "__main__":
    logger.warning("RUN: Turkcell Destek > Turkcell'li Olmak (generic) crawl")
    run_crawl(CONFIG)
    logger.warning("DONE: Outputs -> 4.turkcell_member.csv, 4.turkcell_member.jsonl")
