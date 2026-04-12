"""
매각결과 페이지 탐색 모듈
courtauction.go.kr 매각결과조회 페이지를 Selenium으로 조작합니다.
"""
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)

import config


class ResultNavigator:
    """매각결과 조회 페이지 탐색기."""

    def __init__(self, driver, debug: bool = False):
        self.driver = driver
        self.debug = debug
        self.wait = WebDriverWait(driver, config.WAIT_TIMEOUT)

    def log(self, msg: str):
        if self.debug:
            print(f"[ResultNavigator] {msg}")

    def go_to_result_page(self):
        """매각결과 조회 페이지로 이동합니다."""
        self.log(f"매각결과 페이지 이동: {config.RESULT_URL}")
        self.driver.get(config.RESULT_URL)
        time.sleep(3)
        self._close_popups()

    def _close_popups(self):
        try:
            alert = self.driver.switch_to.alert
            alert.accept()
        except Exception:
            pass
        for sel in ["//button[contains(text(),'닫기')]", "//button[contains(text(),'확인')]"]:
            try:
                btns = self.driver.find_elements(By.XPATH, sel)
                for btn in btns:
                    if btn.is_displayed():
                        btn.click()
                        time.sleep(0.3)
            except Exception:
                pass

    def switch_to_iframe(self) -> bool:
        """메인 iframe으로 전환합니다."""
        self.driver.switch_to.default_content()
        for candidate in [{"name": "indexFrame"}, {"id": "indexFrame"}]:
            try:
                key, val = list(candidate.items())[0]
                frame = self.driver.find_element(By.NAME if key == "name" else By.ID, val)
                self.driver.switch_to.frame(frame)
                self.log("iframe 전환 성공")
                return True
            except NoSuchElementException:
                continue
        # 인덱스로 첫 번째 내용 있는 iframe 시도
        for iframe in self.driver.find_elements(By.TAG_NAME, "iframe"):
            try:
                self.driver.switch_to.frame(iframe)
                if len(self.driver.find_element(By.TAG_NAME, "body").text) > 10:
                    return True
                self.driver.switch_to.default_content()
            except Exception:
                self.driver.switch_to.default_content()
        return False

    def _js_select(self, elem_id: str, text: str) -> bool:
        """JS로 select에서 텍스트 기반 옵션 선택 (인코딩 안전)."""
        codes = [str(ord(c)) for c in text]
        js = f"""
        var sel = document.getElementById('{elem_id}');
        if(!sel) return 'no-element';
        var codes = [{','.join(codes)}];
        var target = String.fromCharCode.apply(null, codes);
        for(var i=0; i<sel.options.length; i++){{
            if(sel.options[i].text.indexOf(target)>=0 || sel.options[i].value.indexOf(target)>=0){{
                sel.selectedIndex = i;
                sel.dispatchEvent(new Event('change', {{bubbles:true}}));
                return 'ok:' + sel.options[i].text;
            }}
        }}
        return 'not-found';
        """
        try:
            r = self.driver.execute_script(js)
            self.log(f"  JS select ({elem_id}/{text}): {r}")
            return r and r.startswith("ok:")
        except Exception as e:
            self.log(f"  JS select 오류: {e}")
            return False

    def _js_select_any(self, target_text: str) -> bool:
        """
        페이지의 모든 select 요소를 순회하며 대상 텍스트를 가진 옵션을 선택합니다.
        특정 ID를 몰라도 동작하는 범용 fallback.
        """
        codes = [str(ord(c)) for c in target_text]
        js = f"""
        var codes = [{','.join(codes)}];
        var target = String.fromCharCode.apply(null, codes);
        var sels = document.querySelectorAll('select');
        for(var j=0; j<sels.length; j++){{
            var sel = sels[j];
            for(var i=0; i<sel.options.length; i++){{
                if(sel.options[i].text.indexOf(target)>=0){{
                    sel.selectedIndex = i;
                    sel.dispatchEvent(new Event('change',{{bubbles:true}}));
                    return 'ok:id=' + sel.id + ',text=' + sel.options[i].text;
                }}
            }}
        }}
        return 'not-found';
        """
        try:
            r = self.driver.execute_script(js)
            self.log(f"  범용 select ({target_text}): {r}")
            return r and r.startswith("ok:")
        except Exception as e:
            self.log(f"  범용 select 오류: {e}")
            return False

    def save_debug_source(self, filename: str = "result_debug.html"):
        """디버그용 페이지 소스 저장."""
        import os
        try:
            path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", filename)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            self.log(f"페이지 소스 저장: {path}")
        except Exception as e:
            self.log(f"소스 저장 실패: {e}")

    def select_court(self, court_name: str = None) -> bool:
        """법원 선택 - 알려진 ID → 범용 자동탐색 순으로 시도."""
        court_name = court_name or config.TARGET_COURT
        known_ids = [
            "mf_wfm_mainFrame_sbx_rletCortOfc",
            "mf_wfm_mainFrame_sbx_cortOfc",
            "mf_wfm_mainFrame_sbx_jiwonNm",
            "idJiwonNm", "jiwonNm",
        ]
        for cid in known_ids:
            if self._js_select(cid, court_name):
                time.sleep(1)
                return True
        # 범용 자동탐색 (페이지의 모든 select 순회)
        if self._js_select_any(court_name):
            time.sleep(1)
            return True
        self.log("법원 선택 실패")
        return False

    def select_property_type(self, prop_type: str = None) -> bool:
        """물건종류 3단계 선택: 건물 > 주거용건물 > 아파트"""
        prop_type = prop_type or config.TARGET_TYPE
        CATEGORY_MAP = {
            "아파트":   ("건물", "주거용건물", "아파트"),
            "다세대":   ("건물", "주거용건물", "다세대주택"),
            "오피스텔": ("건물", "주거용건물", "오피스텔"),
            "상가":     ("건물", "상업용건물", None),
            "토지":     ("토지", None, None),
        }
        large, mid, small = CATEGORY_MAP.get(prop_type, ("건물", "주거용건물", prop_type))

        # 알려진 ID 후보 + 범용 자동탐색 혼합
        lcl_ids = ["mf_wfm_mainFrame_sbx_rletLclLst", "mf_wfm_mainFrame_sbx_lclLst", "mulGbnCd"]
        mcl_ids = ["mf_wfm_mainFrame_sbx_rletMclLst", "mf_wfm_mainFrame_sbx_mclLst", "mulKindCd"]
        scl_ids = ["mf_wfm_mainFrame_sbx_rletSclLst", "mf_wfm_mainFrame_sbx_sclLst"]

        def try_select(id_list, text):
            for eid in id_list:
                if self._js_select(eid, text):
                    return True
            # 범용 자동탐색 fallback
            return self._js_select_any(text)

        ok1 = try_select(lcl_ids, large)
        if ok1:
            time.sleep(3)
        ok2 = False
        if mid:
            for _ in range(3):
                ok2 = try_select(mcl_ids, mid)
                if ok2:
                    break
                time.sleep(1.5)
            if ok2:
                time.sleep(3)
        ok3 = False
        if small:
            for _ in range(3):
                ok3 = try_select(scl_ids, small)
                if ok3:
                    break
                time.sleep(1.5)
        return ok1 or ok2 or ok3

    def click_search_button(self) -> bool:
        """검색 버튼 클릭."""
        for sel in [
            "//button[contains(text(),'검색')]",
            "//input[@type='button' and contains(@value,'검색')]",
            "//*[@id='btnSearch']",
            "//*[contains(@id,'search') or contains(@id,'Search')]",
        ]:
            try:
                btn = self.driver.find_element(By.XPATH, sel)
                if btn.is_displayed() and btn.is_enabled():
                    btn.click()
                    self.log(f"검색 버튼 클릭: {sel}")
                    return True
            except NoSuchElementException:
                continue
        for js in [
            "if(typeof fnSearch==='function'){fnSearch();return true;}",
            "if(typeof scwin!=='undefined'&&scwin.fnSearch){scwin.fnSearch();return true;}",
        ]:
            try:
                if self.driver.execute_script(js):
                    return True
            except Exception:
                pass
        self.log("검색 버튼 클릭 실패")
        return False

    def wait_for_results(self) -> bool:
        """결과 테이블 로드 대기."""
        for by, sel in [
            (By.XPATH, "//tbody/tr[td]"),
            (By.CSS_SELECTOR, "tbody tr"),
        ]:
            try:
                self.wait.until(EC.presence_of_element_located((by, sel)))
                rows = self.driver.find_elements(by, sel)
                if rows:
                    self.log(f"결과 {len(rows)}행 발견")
                    return True
            except TimeoutException:
                continue
        return False

    def _click_next_block(self) -> bool:
        """'다음' 블록 이동 버튼 클릭 (navigator.py와 동일한 패턴)."""
        next_selectors = [
            "//a[normalize-space(text())='다음']",
            "//button[normalize-space(text())='다음']",
            "//a[contains(text(),'다음')]",
            "//button[contains(text(),'다음')]",
            "//img[@alt='다음']/..",
            "//a[@title='다음 페이지']",
            "//a[contains(@onclick,'next') or contains(@onclick,'Next')]",
            "//*[contains(@class,'next') or contains(@id,'next')]",
        ]
        for sel in next_selectors:
            try:
                btn = self.driver.find_element(By.XPATH, sel)
                if btn.is_displayed() and btn.is_enabled():
                    cls = btn.get_attribute("class") or ""
                    aria_disabled = btn.get_attribute("aria-disabled") or ""
                    if "disabled" in cls or "dim" in cls or aria_disabled.lower() == "true":
                        self.log("다음 버튼 비활성화 (마지막 블록)")
                        return False
                    btn.click()
                    self.log(f"다음 블록 버튼 클릭: {sel}")
                    time.sleep(config.PAGE_DELAY)
                    return True
            except (NoSuchElementException, StaleElementReferenceException):
                continue
            except Exception as e:
                self.log(f"  다음 블록 버튼 오류: {e}")
        self.log("다음 페이지 버튼 없음 (마지막 페이지)")
        return False

    def go_to_next_page(self, current_page: int = 0) -> bool:
        """다음 페이지 이동 (staleness_of + 페이지번호 클릭 방식)."""
        next_page = current_page + 1

        def _try_click_page(page_num):
            xpaths = [
                f"//a[normalize-space(text())='{page_num}']",
                f"//button[normalize-space(text())='{page_num}']",
                f"//span[normalize-space(text())='{page_num}']",
                f"//td[normalize-space(text())='{page_num}']",
            ]
            for xpath in xpaths:
                try:
                    els = self.driver.find_elements(By.XPATH, xpath)
                    for el in els:
                        if el.is_displayed() and el.text.strip() == str(page_num):
                            try:
                                old_el = self.driver.find_element(By.XPATH, "//tbody/tr[1]")
                            except Exception:
                                old_el = None
                            el.click()
                            if old_el:
                                try:
                                    WebDriverWait(self.driver, 10).until(EC.staleness_of(old_el))
                                except Exception:
                                    pass
                            time.sleep(config.PAGE_DELAY + 1)
                            self.log(f"페이지 {page_num} 클릭 성공")
                            return True
                except Exception:
                    continue
            return False

        if _try_click_page(next_page):
            return True

        if not self._click_next_block():
            return False

        time.sleep(2)
        if _try_click_page(next_page):
            return True

        return False

    def run_search(self) -> bool:
        """매각결과 전체 검색 시퀀스."""
        self.go_to_result_page()
        self.switch_to_iframe()
        time.sleep(2)

        # 현재 페이지에 select 요소가 있는지 확인
        selects = self.driver.find_elements(By.TAG_NAME, "select")
        self.log(f"페이지 select 수: {len(selects)}")
        if self.debug:
            for s in selects:
                self.log(f"  select id={s.get_attribute('id')}")

        self.select_court()
        self.select_property_type()
        search_ok = self.click_search_button()
        if not search_ok:
            self.log("검색 버튼 클릭 실패 - 디버그 소스 저장")
            self.save_debug_source("result_debug_no_button.html")
            return False
        time.sleep(config.PAGE_DELAY)
        found = self.wait_for_results()
        if not found:
            self.save_debug_source("result_debug_no_data.html")
        return found
