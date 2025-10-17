from src.logManager import logger

def login(login_data):
    driver = login_data["driver"]
    logger.info("🔑 Giriş zaten açık (manuel oturum kullanılıyor).")
