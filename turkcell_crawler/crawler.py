import time
from collections import deque

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException, WebDriverException

from logManager import logger
from my_driver import get_driver

from extractors import (
    set_globals, rnd_sleep, extract_links_from_listing, extract_article_fields,
    write_csv_header_if_missing, append_csv_row, append_jsonl
)

# ---- Genel küçük yardımcılar ----
def accept_cookies_if_any(driver):
    wait = WebDriverWait(driver, 6)
    try:
        btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(., 'Kabul') or contains(., 'Kabul Et') or contains(., 'Tamam') or contains(., 'Accept')]")
        ))
        btn.click()
        rnd_sleep(0.3, 0.7)
        logger.info("Cookies accepted.")
    except TimeoutException:
        pass

def expand_all_accordions(driver):
    selectors = [
        "button[aria-expanded='false'][role='button']",
        "button.accordion-toggle",
        "button[data-testid*='accordion']",
        "button[class*='toggle']",
    ]
    total = 0
    for sel in selectors:
        try:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in elems:
                try:
                    if el.is_displayed():
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                        rnd_sleep(0.15, 0.35)
                        el.click()
                        total += 1
                        rnd_sleep(0.1, 0.25)
                except (ElementClickInterceptedException, NoSuchElementException):
                    continue
        except Exception:
            continue
    if total:
        logger.info(f"Expanded {total} accordion/toggle element(s).")
    return total

def gentle_scroll(driver):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.3);")
    rnd_sleep(0.2, 0.4)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    rnd_sleep(0.3, 0.6)

# ---- Çekirdek akış ----
def collect_links(driver, start_url: str, pageload_wait_sec: int, allowed_prefix: str):
    logger.info(f"Opening seed: {start_url}")
    driver.get(start_url)
    WebDriverWait(driver, pageload_wait_sec).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    rnd_sleep(0.5, 1.0)
    accept_cookies_if_any(driver)
    expand_all_accordions(driver)
    gentle_scroll(driver)

    html = driver.page_source
    links = extract_links_from_listing(html, allowed_prefix)
    logger.info(f"Found {len(links)} candidate link(s) under {allowed_prefix}")
    return sorted(links)

def crawl_article(driver, url: str, pageload_wait_sec: int, category_idx=2, subcategory_idx=3):
    logger.info(f"Visiting: {url}")
    driver.get(url)
    WebDriverWait(driver, pageload_wait_sec).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    rnd_sleep(0.6, 1.2)
    expand_all_accordions(driver)
    gentle_scroll(driver)

    html = driver.page_source
    data = extract_article_fields(html, url, category_idx, subcategory_idx)

    ts = time.time()
    data["last_crawled_ts"] = int(ts)
    data["last_crawled_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    return data

def run_crawl(config: dict):
    """
    config beklenen alanlar:
      BASE_URL, SEED_PATH, START_URL, OUT_CSV, OUT_JSONL,
      PAGELOAD_WAIT_SEC, SLEEP_MIN_MAX, SKIP_PATTERNS,
      ALLOWED_PREFIX, CATEGORY_IDX(=2), SUBCATEGORY_IDX(=3)
    """
    # extractor global’larını ayarla
    set_globals(
        base_url=config["BASE_URL"],
        skip_patterns=config.get("SKIP_PATTERNS"),
        sleep_min_max=config.get("SLEEP_MIN_MAX"),
    )

    start_url = config["START_URL"]
    out_csv   = config["OUT_CSV"]
    out_jsonl = config["OUT_JSONL"]
    pageload  = config.get("PAGELOAD_WAIT_SEC", 15)
    allowed   = config["ALLOWED_PREFIX"]
    cat_idx   = config.get("CATEGORY_IDX", 2)
    sub_idx   = config.get("SUBCATEGORY_IDX", 3)

    logger.info("Generic crawler starting...")
    driver = get_driver(start_url)

    # CSV hızlı kontrol başlıkları
    write_csv_header_if_missing(out_csv, ["url", "title", "breadcrumb", "content_len", "excerpt"])

    try:
        links = collect_links(driver, start_url, pageload, allowed)
        seen = set()
        q = deque(links)

        while q:
            url = q.popleft()
            if url in seen or url == start_url:
                continue
            seen.add(url)

            try:
                data = crawl_article(driver, url, pageload, cat_idx, sub_idx)
                excerpt = (data["content_text"][:180] + "…") if len(data["content_text"]) > 180 else data["content_text"]
                append_csv_row(out_csv, [data["url"], data["title"], data["breadcrumb"], len(data["content_text"]), excerpt])
                append_jsonl(out_jsonl, data)
                logger.info(f"Saved: {data['title'][:70]} ...")
            except Exception as e:
                logger.error(f"Error on {url}: {e}")
            rnd_sleep()
    finally:
        try:
            driver.quit()
        except WebDriverException:
            pass
        logger.info("Generic crawler finished.")
