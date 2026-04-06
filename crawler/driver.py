"""
ChromeDriver 설정 및 초기화 모듈
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def create_driver(headless: bool = True, debug: bool = False) -> webdriver.Chrome:
    """
    Chrome WebDriver를 생성하고 반환합니다.

    Args:
        headless: True면 브라우저 창을 숨김
        debug: True면 상세 로그 출력
    """
    options = Options()

    if headless:
        options.add_argument("--headless=new")

    # 자동화 감지 우회
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # 안정성 옵션
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=ko-KR")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # 팝업 차단 해제 (사이트 팝업 처리를 직접 하기 위해)
    options.add_argument("--disable-popup-blocking")

    if debug:
        print("[Driver] ChromeDriver 초기화 중...")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # navigator.webdriver 속성 숨기기
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    if debug:
        print(f"[Driver] ChromeDriver 초기화 완료 (headless={headless})")

    return driver


def quit_driver(driver: webdriver.Chrome, debug: bool = False):
    """드라이버를 안전하게 종료합니다."""
    try:
        driver.quit()
        if debug:
            print("[Driver] 드라이버 종료 완료")
    except Exception as e:
        if debug:
            print(f"[Driver] 드라이버 종료 중 오류: {e}")
