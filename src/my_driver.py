from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time

def get_driver(url: str = None):
    """
    Açık olan Chrome oturumuna bağlanır (manuel giriş yapılmış oturum).
    Sayfayı yenilemez, mevcut sekmeyi olduğu gibi kullanır.
    """

    print("🔗 Var olan Chrome oturumuna bağlanılıyor...")

    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    options.add_argument("--start-maximized")

    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )

        # Eğer URL verilmişse ama zaten o sayfadaysak yönlendirme yapma
        current = driver.current_url
        if url and not current.startswith("http"):
            print(f"🌐 {url} sayfasına gidiliyor (mevcut sayfa boş).")
            driver.get(url)
        elif url and "x.com" not in current:
            print(f"🌐 {url} sayfasına gidiliyor (mevcut sekme x.com değil).")
            driver.get(url)
        else:
            print(f"✅ Tarayıcı hazır, mevcut sayfa korunuyor: {current}")

        time.sleep(1)
        return driver

    except Exception as e:
        print("❌ Chrome oturumuna bağlanılamadı.")
        print("Lütfen önce şu komutu çalıştırarak Chrome'u aç:")
        print(r'& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Temp\chrome_debug_profile"')
        print(f"Hata detayı: {e}")
        raise


if __name__ == "__main__":
    driver = get_driver("https://x.com/home")
    input("ENTER → kapat")
    driver.quit()
