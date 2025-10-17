from datetime import datetime
from pathlib import Path
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys as K
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from src.config_rpa import WEBSITE_URL
from src.my_driver import get_driver
from src.login import login
from src.logManager import logger
from src.rag import ask as rag_ask


# -----------------------------
# PARAMETRELER
# -----------------------------
KEYWORD = "turkcell"
TARGET_HANDLE = "target_X_username"  # Hedef Twitter kullanıcısını giriniz @ olmadan
MAX_SCROLLS = 15
SCROLL_PAUSE_SEC = 2.0


# -----------------------------
# ARAMA VE SCROLL FONKSİYONLARI
# -----------------------------
def open_latest_tab(driver):
    logger.info("🔍 Arama başlatılıyor...")
    WebDriverWait(driver, 20).until(
        EC.visibility_of_element_located((By.XPATH, "//input[@placeholder='Search']"))
    )
    search = driver.find_element(By.XPATH, "//input[@placeholder='Search']")
    search.clear()
    search.send_keys(KEYWORD)
    search.send_keys(K.ENTER)
    time.sleep(3)

    # "Latest" sekmesine geç
    try:
        latest_tab = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//span[text()='Latest']"))
        )
        latest_tab.click()
        logger.info("📄 'Latest' sekmesine geçildi.")
    except TimeoutException:
        logger.warning("⚠️ 'Latest' sekmesi bulunamadı (UI değişmiş olabilir).")
    time.sleep(2)


def parse_tweet_card(card):
    """Tweet kartından kullanıcı, metin ve zaman bilgilerini çıkarır."""
    try:
        author_links = card.find_elements(By.XPATH, ".//div[@data-testid='User-Name']//a")
        author_handle = None
        if len(author_links) > 1:
            href = (author_links[1].get_attribute("href") or "").strip("/")
            author_handle = href.split("/")[-1].lower()

        text = ""
        try:
            text_el = card.find_element(By.XPATH, ".//div[@data-testid='tweetText']")
            text = text_el.text
        except NoSuchElementException:
            pass

        time_el = card.find_element(By.XPATH, ".//time")
        dt_iso = time_el.get_attribute("datetime")
        dt = datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))

        return {"author": author_handle, "text": text, "datetime": dt, "card": card}
    except Exception:
        return None


def find_target_with_scrolling(driver):
    logger.info(f"🔎 @{TARGET_HANDLE} tweetleri aranıyor...")
    best = None
    seen = set()

    for _ in range(MAX_SCROLLS):
        cards = driver.find_elements(By.XPATH, "//div[@data-testid='cellInnerDiv']")
        for c in cards:
            if c.id in seen:
                continue
            seen.add(c.id)

            data = parse_tweet_card(c)
            if not data or not data["author"]:
                continue
            if data["author"] != TARGET_HANDLE.lower():
                continue
            if KEYWORD.lower() not in (data["text"] or "").lower():
                continue

            best = data
        if best:
            return best

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_SEC)

    return best


# -----------------------------
# RAG ve CEVAP GÖNDERİMİ
# -----------------------------
def reply_to_tweet(driver, tweet_card, answer_text):
    """Tweet'e yanıt gönderir."""
    try:
        reply_btn = tweet_card.find_element(By.XPATH, ".//button[@data-testid='reply']")
        driver.execute_script("arguments[0].click();", reply_btn)
        editor = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, "//div[@role='textbox']"))
        )
        editor.send_keys(answer_text)
        send_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@data-testid='tweetButtonInline']"))
        )
        send_btn.click()
        logger.info("💬 Yanıt gönderildi ✅")
    except Exception as e:
        logger.error(f"Yanıt gönderilemedi: {e}")


# -----------------------------
# ANA AKIŞ
# -----------------------------
def run_once():
    logger.info("🚀 Diyoloji otomasyon başlatıldı")
    driver = get_driver(WEBSITE_URL)
    login({"driver": driver})  # sadece bilgi mesajı verir

    open_latest_tab(driver)

    target = find_target_with_scrolling(driver)
    if not target:
        logger.warning("⚠️ Uygun tweet bulunamadı.")
        driver.quit()
        return

    logger.info(f"🎯 Tweet bulundu: {target['text']}")

    # -----------------------------
    # RAG cevabı çekme kısmı
    # -----------------------------
    try:
        agent_out = rag_ask(target["text"])

        # 🔍 Debug için çıktıyı terminalde gör
        print("\n============================")
        print("🔎 agent_out:", agent_out)
        print("============================\n")

        # RAG yanıtı dict mi class mı algıla
        if isinstance(agent_out, dict) and "answer" in agent_out:
            answer_text = agent_out["answer"].strip()
        elif hasattr(agent_out, "answer"):
            answer_text = getattr(agent_out, "answer", "").strip()
        else:
            logger.warning("⚠️ RAG yanıt formatı beklenenden farklı, fallback kullanılacak.")
            answer_text = "Bu konuda bilgi sahibi değilim."

        logger.info(f"🤖 Yanıt üretildi: {answer_text}")
    except Exception as e:
        logger.error(f"RAG hatası: {e}")
        answer_text = "Bu konuda bilgi sahibi değilim."

    # -----------------------------
    # Yanıtı tweet'e gönder
    # -----------------------------
    reply_to_tweet(driver, target["card"], answer_text)
    driver.quit()


if __name__ == "__main__":
    run_once()
