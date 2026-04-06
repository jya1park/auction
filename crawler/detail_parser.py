"""
경매 물건 상세 페이지 파싱 모듈
사건번호로 상세 정보(낙찰가, 낙찰가율, 응찰자수 등)를 추출합니다.
"""
import re
import time
from typing import Dict, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

import config
from crawler.list_parser import parse_amount


class DetailParser:
    def __init__(self, driver: webdriver.Chrome, debug: bool = False):
        self.driver = driver
        self.debug = debug
        self.wait = WebDriverWait(driver, config.WAIT_TIMEOUT)

    def log(self, msg: str):
        if self.debug:
            print(f"[DetailParser] {msg}")

    def click_case_link(self, case_number: str) -> bool:
        """
        목록에서 사건번호 링크를 클릭하여 상세 페이지로 이동합니다.
        """
        self.log(f"사건번호 링크 클릭: {case_number}")
        try:
            link = self.driver.find_element(
                By.XPATH, f"//a[contains(text(),'{case_number}')]"
            )
            link.click()
            time.sleep(2)
            return True
        except NoSuchElementException:
            # onclick으로 탐색
            try:
                link = self.driver.find_element(
                    By.XPATH,
                    f"//*[contains(@onclick,'{case_number}')]"
                )
                link.click()
                time.sleep(2)
                return True
            except NoSuchElementException:
                self.log(f"사건번호 링크 없음: {case_number}")
                return False

    def parse_detail_page(self, page_source: str) -> Dict:
        """
        상세 페이지 HTML에서 추가 정보를 파싱합니다.
        """
        soup = BeautifulSoup(page_source, "lxml")
        detail = {}

        # 낙찰 정보 패턴
        patterns = {
            "낙찰가": [r"낙찰가[액]?\s*[:\s]*([\d,]+)\s*원?", r"매각가[액]?\s*[:\s]*([\d,]+)\s*원?"],
            "낙찰가율": [r"낙찰가율\s*[:\s]*([\d.]+)\s*%?", r"매각가율\s*[:\s]*([\d.]+)\s*%?"],
            "응찰자수": [r"응찰자\s*[:\s]*(\d+)\s*명?", r"입찰자\s*[:\s]*(\d+)\s*명?"],
            "낙찰일": [r"낙찰일\s*[:\s]*(\d{4}[-./]\d{2}[-./]\d{2})", r"매각일\s*[:\s]*(\d{4}[-./]\d{2}[-./]\d{2})"],
        }

        full_text = soup.get_text()

        for field, pats in patterns.items():
            for pat in pats:
                match = re.search(pat, full_text)
                if match:
                    val = match.group(1).strip()
                    if field == "낙찰가":
                        detail[field] = parse_amount(val + "원") or val
                    elif field == "낙찰가율":
                        try:
                            detail[field] = float(val)
                        except ValueError:
                            detail[field] = val
                    elif field == "응찰자수":
                        try:
                            detail[field] = int(val)
                        except ValueError:
                            detail[field] = val
                    else:
                        detail[field] = val
                    break

        # 테이블에서 추가 정보 추출
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                headers = row.find_all("th")
                values = row.find_all("td")
                for h, v in zip(headers, values):
                    h_text = h.get_text(strip=True)
                    v_text = v.get_text(strip=True)
                    if h_text and v_text:
                        # 필요한 필드만 추출
                        if any(kw in h_text for kw in ["낙찰", "매각", "응찰", "입찰자", "임차"]):
                            detail[h_text] = v_text

        self.log(f"상세 정보 파싱: {list(detail.keys())}")
        return detail

    def get_detail(self, item: Dict, navigator) -> Dict:
        """
        목록 아이템의 상세 정보를 가져옵니다.
        현재 목록 페이지에서 링크를 클릭 → 상세 파싱 → 뒤로가기 패턴.
        """
        case_number = item.get("사건번호", "")
        if not case_number:
            return {}

        self.log(f"상세 조회 시작: {case_number}")

        # 뒤로가기를 위해 현재 URL 저장
        current_url = self.driver.current_url

        try:
            # 상세 페이지 이동
            clicked = self.click_case_link(case_number)
            if not clicked:
                return {}

            # 새 페이지 로드 대기
            time.sleep(2)

            # iframe 재전환 필요 여부 확인
            if navigator.in_iframe:
                try:
                    navigator.switch_to_main_iframe()
                except Exception:
                    pass

            # 파싱
            detail = self.parse_detail_page(self.driver.page_source)

            # 뒤로가기
            self.driver.back()
            time.sleep(2)

            # iframe 재전환
            if navigator.in_iframe:
                try:
                    navigator.switch_to_main_iframe()
                except Exception:
                    pass

            return detail

        except Exception as e:
            self.log(f"상세 조회 오류: {e}")
            # 오류 시 원래 URL로 복귀
            try:
                self.driver.get(current_url)
                time.sleep(2)
            except Exception:
                pass
            return {}
