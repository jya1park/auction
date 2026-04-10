"""
ChromeDriver 설정 및 초기화 모듈
"""
import os
import re
import subprocess
import time

# ── webdriver-manager 한국어 Windows 인코딩 패치 ──────────────────────────
# webdriver_manager/core/utils.py의 read_version_from_cmd / determine_powershell이
# subprocess 출력을 .decode() (UTF-8 고정)로 읽는다.
# 한국어 Windows에서 PowerShell 출력은 CP949이므로 UnicodeDecodeError 발생.
# 해당 함수 두 개를 errors='ignore' 버전으로 직접 교체한다.
import webdriver_manager.core.utils as _wdm_utils

def _read_version_from_cmd(cmd, pattern):
    with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            shell=True,
    ) as stream:
        stdout = stream.communicate()[0].decode('utf-8', errors='ignore')
        version = re.search(pattern, stdout)
        return version.group(0) if version else None

def _determine_powershell():
    cmd = "(dir 2>&1 *`|echo CMD);&<# rem #>echo powershell"
    with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            shell=True,
    ) as stream:
        stdout = stream.communicate()[0].decode('utf-8', errors='ignore')
    return "" if stdout.strip() == "powershell" else "powershell"

_wdm_utils.read_version_from_cmd = _read_version_from_cmd
_wdm_utils.determine_powershell  = _determine_powershell
# ─────────────────────────────────────────────────────────────────────────────

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

    # webdriver-manager 버그: install()이 chromedriver.exe 대신
    # THIRD_PARTY_NOTICES 파일 경로를 반환하는 경우가 있음 (WinError 193 원인)
    # → 반환된 경로의 디렉터리에서 chromedriver.exe를 직접 탐색해 보정
    raw_path = ChromeDriverManager().install()
    driver_dir = os.path.dirname(raw_path)
    exe_path = os.path.join(driver_dir, "chromedriver.exe")
    if not os.path.isfile(exe_path):
        # 한 단계 위 디렉터리도 탐색
        exe_path = os.path.join(os.path.dirname(driver_dir), "chromedriver.exe")
    if not os.path.isfile(exe_path):
        exe_path = raw_path  # 보정 실패 시 원래 경로 사용

    service = Service(exe_path)
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
