from logManager import logger
from crawler import run_crawl

# Bu dosya "config + run" görevini görür.
# Hedef: https://www.turkcell.com.tr/destek/hattiniz

CONFIG = {
    "BASE_URL":  "https://www.turkcell.com.tr",
    "SEED_PATH": "/destek/hattiniz",
    "START_URL": "https://www.turkcell.com.tr/destek/hattiniz",

    # Çıktı dosya isimlerini aynı bırakıyoruz (mevcut pipeline’la uyum için):
    "OUT_CSV":   "1.subscription.csv",
    "OUT_JSONL": "1.subscription.jsonl",

    # Davranış ayarları
    "PAGELOAD_WAIT_SEC": 15,
    "SLEEP_MIN_MAX": (0.5, 1.1),
    "SKIP_PATTERNS": [
        "#", "mailto:", "tel:",
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".zip", ".rar", ".7z", ".xlsx", ".xls", ".doc", ".docx", ".ppt", ".pptx", ".pdf"
    ],

    # Link süzgeci (hangi ağacın altını gezeceğiz?)
    "ALLOWED_PREFIX": "/destek/hattiniz",

    # URL parça indeksleri (…/destek/hattiniz/<category>/<slug>)
    "CATEGORY_IDX": 2,
    "SUBCATEGORY_IDX": 3,
}

if __name__ == "__main__":
    logger.warning("RUN: Turkcell Destek > Hattınız (generic) crawl")
    run_crawl(CONFIG)
    logger.warning("DONE: Outputs -> billing_tool.csv, billing_tool.jsonl")
