"""
대법원 경매 사이트 탐색 모듈
WebSquare(w2x) 프레임워크 기반 사이트를 Selenium으로 조작합니다.
"""
import time
from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    NoSuchFrameException,
    StaleElementReferenceException,
    ElementNotInteractableException,
)

import config


class Navigator:
    def __init__(self, driver: webdriver.Chrome, debug: bool = False):
        self.driver = driver
        self.debug = debug
        self.wait = WebDriverWait(driver, config.WAIT_TIMEOUT)
        self.in_iframe = False

    def log(self, msg: str):
        if self.debug:
            print(f"[Navigator] {msg}")

    # ──────────────────────────────────────────────
    # 1. 팝업 닫기
    # ──────────────────────────────────────────────
    def close_popups(self):
        """공지/팝업 창을 자동으로 닫습니다."""
        self.log("팝업 확인 중...")
        # alert 처리
        try:
            alert = self.driver.switch_to.alert
            self.log(f"Alert 발견: {alert.text}")
            alert.accept()
        except Exception:
            pass

        # 닫기 버튼 탐색 (여러 패턴)
        close_selectors = [
            "//button[contains(text(),'닫기')]",
            "//button[contains(text(),'확인')]",
            "//a[contains(text(),'닫기')]",
            "//*[@class='close']",
            "//*[contains(@id,'close')]",
            "//*[contains(@onclick,'close')]",
        ]
        for sel in close_selectors:
            try:
                btns = self.driver.find_elements(By.XPATH, sel)
                for btn in btns:
                    if btn.is_displayed():
                        btn.click()
                        self.log(f"팝업 닫기: {sel}")
                        time.sleep(0.5)
            except Exception:
                pass

    # ──────────────────────────────────────────────
    # 2. iframe 전환
    # ──────────────────────────────────────────────
    def switch_to_main_iframe(self) -> bool:
        """
        indexFrame iframe으로 전환합니다.
        실패 시 다른 iframe을 시도합니다.
        """
        self.driver.switch_to.default_content()
        self.in_iframe = False

        # 시도할 iframe 식별자 목록
        iframe_candidates = [
            {"name": "indexFrame"},
            {"id": "indexFrame"},
            {"name": "mainFrame"},
            {"id": "mainFrame"},
        ]

        for candidate in iframe_candidates:
            try:
                if "name" in candidate:
                    frame = self.driver.find_element(By.NAME, candidate["name"])
                else:
                    frame = self.driver.find_element(By.ID, candidate["id"])
                self.driver.switch_to.frame(frame)
                self.log(f"iframe 전환 성공: {candidate}")
                self.in_iframe = True
                return True
            except NoSuchElementException:
                continue

        # 인덱스로 첫 번째 iframe 시도
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        self.log(f"발견된 iframe 수: {len(iframes)}")
        for i, iframe in enumerate(iframes):
            try:
                name = iframe.get_attribute("name") or iframe.get_attribute("id") or f"index_{i}"
                self.log(f"  iframe[{i}]: name={iframe.get_attribute('name')}, id={iframe.get_attribute('id')}, src={iframe.get_attribute('src')[:80] if iframe.get_attribute('src') else 'N/A'}")
                self.driver.switch_to.frame(iframe)
                # 전환 후 내용이 있는지 확인
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
                if len(body_text) > 10:
                    self.log(f"iframe[{i}] 선택 (내용 있음)")
                    self.in_iframe = True
                    return True
                self.driver.switch_to.default_content()
            except Exception as e:
                self.log(f"  iframe[{i}] 전환 실패: {e}")
                self.driver.switch_to.default_content()

        self.log("경고: 모든 iframe 전환 실패 - default_content 사용")
        return False

    # ──────────────────────────────────────────────
    # 3. 검색 페이지 이동
    # ──────────────────────────────────────────────
    def go_to_search_page(self):
        """물건일반검색 페이지로 이동합니다."""
        self.log(f"검색 페이지 이동: {config.SEARCH_URL}")
        self.driver.get(config.SEARCH_URL)
        time.sleep(3)
        self.close_popups()

    # ──────────────────────────────────────────────
    # 4. DOM 디버깅
    # ──────────────────────────────────────────────
    def print_dom_structure(self):
        """현재 DOM 구조를 출력합니다 (디버그용)."""
        print("\n" + "="*60)
        print("[DEBUG] 현재 URL:", self.driver.current_url)
        print("[DEBUG] 페이지 제목:", self.driver.title)

        # iframe 목록
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        print(f"[DEBUG] iframe 수: {len(iframes)}")
        for i, f in enumerate(iframes):
            print(f"  [{i}] name={f.get_attribute('name')}, id={f.get_attribute('id')}, src={str(f.get_attribute('src'))[:80]}")

        # 현재 컨텍스트의 select/input/button
        selects = self.driver.find_elements(By.TAG_NAME, "select")
        print(f"[DEBUG] select 수: {len(selects)}")
        for s in selects:
            print(f"  select id={s.get_attribute('id')}, name={s.get_attribute('name')}")

        inputs = self.driver.find_elements(By.TAG_NAME, "input")
        print(f"[DEBUG] input 수: {len(inputs)}")
        for inp in inputs[:20]:
            print(f"  input type={inp.get_attribute('type')}, id={inp.get_attribute('id')}, value={inp.get_attribute('value')}")

        buttons = self.driver.find_elements(By.TAG_NAME, "button")
        print(f"[DEBUG] button 수: {len(buttons)}")
        for btn in buttons[:10]:
            print(f"  button text={btn.text[:30]}, id={btn.get_attribute('id')}")

        # WebSquare 커스텀 컴포넌트
        w2_elements = self.driver.find_elements(By.XPATH, "//*[starts-with(@id, 'w2')]")
        print(f"[DEBUG] w2* 요소 수: {len(w2_elements)}")
        for el in w2_elements[:20]:
            print(f"  {el.tag_name} id={el.get_attribute('id')}, class={el.get_attribute('class')[:50] if el.get_attribute('class') else ''}")

        print("="*60 + "\n")

    # ──────────────────────────────────────────────
    # 5. 드롭다운 선택 (WebSquare 호환)
    # ──────────────────────────────────────────────
    def select_dropdown(self, element_id: str, value_text: str) -> bool:
        """
        드롭다운에서 특정 텍스트를 선택합니다.
        WebSquare 커스텀 컴포넌트와 일반 <select> 모두 처리합니다.
        """
        self.log(f"드롭다운 선택: id={element_id}, value={value_text}")

        # 방법 1: 일반 <select> 시도
        try:
            el = self.driver.find_element(By.ID, element_id)
            select = Select(el)
            # 텍스트로 선택 시도
            try:
                select.select_by_visible_text(value_text)
                self.log(f"  select_by_visible_text 성공")
                return True
            except Exception:
                pass
            # 부분 텍스트 매칭
            for option in select.options:
                if value_text in option.text:
                    select.select_by_visible_text(option.text)
                    self.log(f"  부분 매칭 선택: {option.text}")
                    return True
        except NoSuchElementException:
            self.log(f"  일반 select 없음: {element_id}")
        except Exception as e:
            self.log(f"  select 오류: {e}")

        # 방법 2: JavaScript로 WebSquare 컴포넌트 값 변경
        js_methods = [
            # w2ui combobox 패턴
            f"var el = scwin['{element_id}']; if(el && el.setValue) {{ el.setValue('{value_text}'); return true; }}",
            f"var el = w2.getObject('{element_id}'); if(el && el.setValue) {{ el.setValue('{value_text}'); return true; }}",
            # 직접 DOM 조작
            f"""
            var sel = document.getElementById('{element_id}');
            if(sel) {{
                var opts = sel.options;
                for(var i=0; i<opts.length; i++) {{
                    if(opts[i].text.indexOf('{value_text}') >= 0) {{
                        sel.selectedIndex = i;
                        sel.dispatchEvent(new Event('change', {{bubbles:true}}));
                        return i;
                    }}
                }}
            }}
            return -1;
            """,
        ]
        for js in js_methods:
            try:
                result = self.driver.execute_script(js)
                if result and result != -1:
                    self.log(f"  JavaScript 선택 성공: result={result}")
                    time.sleep(0.5)
                    return True
            except Exception as e:
                self.log(f"  JS 실행 오류: {e}")

        # 방법 3: 드롭다운 클릭 후 옵션 선택 (커스텀 UI)
        try:
            trigger = self.driver.find_element(By.XPATH,
                f"//*[@id='{element_id}' or contains(@id,'{element_id}')]")
            trigger.click()
            time.sleep(0.5)
            option = self.driver.find_element(By.XPATH,
                f"//*[contains(text(),'{value_text}')]")
            option.click()
            self.log(f"  클릭 방식 선택 성공")
            return True
        except Exception as e:
            self.log(f"  클릭 방식 실패: {e}")

        self.log(f"  경고: 드롭다운 선택 실패 ({element_id}={value_text})")
        return False

    def _find_select_by_options(self, target_text: str) -> Optional[object]:
        """텍스트로 해당 옵션을 포함하는 select 요소를 찾습니다."""
        selects = self.driver.find_elements(By.TAG_NAME, "select")
        for sel in selects:
            try:
                s = Select(sel)
                for opt in s.options:
                    if target_text in opt.text:
                        return sel
            except Exception:
                continue
        return None

    # ──────────────────────────────────────────────
    # 6. 법원 선택
    # ──────────────────────────────────────────────
    def select_court(self, court_name: str = None) -> bool:
        """법원 드롭다운에서 지정 법원을 선택합니다."""
        court_name = court_name or config.TARGET_COURT
        self.log(f"법원 선택: {court_name}")

        # 실제 확인된 element ID 우선 시도
        real_court_id = "mf_wfm_mainFrame_sbx_rletCortOfc"

        # JavaScript로 텍스트 기반 선택 (인코딩 안전)
        # 유니코드 코드포인트로 전달하여 인코딩 문제 회피
        unicode_vals = [str(ord(c)) for c in court_name]
        js = f"""
        var sel = document.getElementById('{real_court_id}');
        if(!sel) return 'no-element';
        var codes = [{','.join(unicode_vals)}];
        var target = String.fromCharCode.apply(null, codes);
        for(var i=0; i<sel.options.length; i++){{
            var t = sel.options[i].text;
            var v = sel.options[i].value;
            if(t.indexOf(target)>=0 || v.indexOf(target)>=0){{
                sel.selectedIndex = i;
                sel.dispatchEvent(new Event('change', {{bubbles:true}}));
                return 'ok:' + t;
            }}
        }}
        return 'not-found:' + sel.options.length;
        """
        try:
            result = self.driver.execute_script(js)
            self.log(f"  법원 JS 선택 결과: {result}")
            if result and result.startswith("ok:"):
                time.sleep(1)
                return True
        except Exception as e:
            self.log(f"  법원 JS 오류: {e}")

        # 폴백: 알려진 ID 후보
        court_ids = ["idJiwonNm", "jiwonNm", "courtNm", "selCourt"]
        for cid in court_ids:
            if self.select_dropdown(cid, court_name):
                time.sleep(1)
                return True

        # 마지막 폴백: 옵션 텍스트로 select 요소 자동 탐색
        sel_el = self._find_select_by_options(court_name)
        if sel_el:
            try:
                s = Select(sel_el)
                for opt in s.options:
                    if court_name in opt.text:
                        s.select_by_visible_text(opt.text)
                        self.log(f"법원 선택 성공 (자동 탐색): {opt.text}")
                        time.sleep(1)
                        return True
            except Exception as e:
                self.log(f"법원 자동 탐색 실패: {e}")

        self.log(f"경고: 법원 선택 실패")
        return False

    # ──────────────────────────────────────────────
    # 7. 물건종류 선택
    # ──────────────────────────────────────────────
    def select_property_type(self, prop_type: str = None) -> bool:
        """
        물건종류 드롭다운에서 지정 유형을 선택합니다.
        대법원 경매 사이트는 대분류(LclLst) → 중분류(MclLst) 2단계 구조입니다.
        아파트의 경우: 대분류='건물', 중분류='아파트'
        """
        prop_type = prop_type or config.TARGET_TYPE
        self.log(f"물건종류 선택: {prop_type}")

        # 대분류 → 중분류 → 소분류 3단계 매핑
        # (대분류, 중분류, 소분류) - 소분류 없으면 None
        CATEGORY_MAP = {
            "아파트":    ("건물", "주거용건물", "아파트"),
            "다세대":    ("건물", "주거용건물", "다세대주택"),
            "오피스텔":  ("건물", "주거용건물", "오피스텔"),
            "상가":      ("건물", "상업용건물", None),
            "토지":      ("토지", None, None),
            "임야":      ("토지", None, None),
        }
        large_cat, mid_cat, small_cat = CATEGORY_MAP.get(prop_type, ("건물", "주거용건물", prop_type))

        lcl_id = "mf_wfm_mainFrame_sbx_rletLclLst"
        mcl_id = "mf_wfm_mainFrame_sbx_rletMclLst"
        scl_id = "mf_wfm_mainFrame_sbx_rletSclLst"

        def js_select_by_text(elem_id: str, target_text: str) -> bool:
            """JS로 select에서 텍스트 기반 옵션 선택 (인코딩 안전)."""
            codes = [str(ord(c)) for c in target_text]
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
            var opts=[]; for(var i=0;i<sel.options.length;i++) opts.push(sel.options[i].value);
            return 'not-found:' + opts.join(',');
            """
            try:
                r = self.driver.execute_script(js)
                self.log(f"  JS 선택 ({elem_id}/{target_text}): {r}")
                return r and r.startswith("ok:")
            except Exception as e:
                self.log(f"  JS 오류: {e}")
                return False

        # 1단계: 대분류 선택
        ok1 = js_select_by_text(lcl_id, large_cat)
        if not ok1:
            self.log(f"  대분류 선택 실패 ({large_cat})")
        else:
            time.sleep(3)  # 중분류 AJAX 로드 충분히 대기

        # 2단계: 중분류 선택 - 재시도 포함
        ok2 = False
        if mid_cat:
            for attempt in range(3):
                ok2 = js_select_by_text(mcl_id, mid_cat)
                if ok2:
                    break
                self.log(f"  중분류 선택 재시도 {attempt+1}/3")
                time.sleep(1.5)
            if ok2:
                time.sleep(3)  # 소분류 AJAX 로드 대기

        # 3단계: 소분류 선택 - 재시도 포함
        ok3 = False
        if small_cat:
            for attempt in range(3):
                ok3 = js_select_by_text(scl_id, small_cat)
                if ok3:
                    break
                self.log(f"  소분류 선택 재시도 {attempt+1}/3")
                time.sleep(1.5)
            if ok3:
                time.sleep(1)
                return True

        # 소분류 없는 경우 중분류까지만 선택해도 성공
        if ok2 and not small_cat:
            time.sleep(1)
            return True

        # 폴백: 기존 방식
        type_ids = ["mulGbnCd", "mulKindCd", "propType", "selMulGbn"]
        for tid in type_ids:
            if self.select_dropdown(tid, prop_type):
                time.sleep(1)
                return True

        # 대분류만 선택된 경우도 부분 성공으로 처리
        if ok1:
            self.log(f"  대분류만 선택됨 (중/소분류 실패)")
            return True

        self.log(f"경고: 물건종류 선택 실패")
        return False

    # ──────────────────────────────────────────────
    # 8. 검색 버튼 클릭
    # ──────────────────────────────────────────────
    def click_search_button(self) -> bool:
        """검색 버튼을 클릭합니다."""
        self.log("검색 버튼 클릭 시도...")

        search_selectors = [
            "//button[contains(text(),'검색')]",
            "//input[@type='button' and contains(@value,'검색')]",
            "//input[@type='submit' and contains(@value,'검색')]",
            "//a[contains(text(),'검색')]",
            "//*[contains(@onclick,'search') and contains(text(),'검색')]",
            "//*[@id='btnSearch']",
            "//*[contains(@id,'search') or contains(@id,'Search')]",
            "//*[contains(@class,'btn-search') or contains(@class,'searchBtn')]",
        ]

        for sel in search_selectors:
            try:
                btn = self.driver.find_element(By.XPATH, sel)
                if btn.is_displayed() and btn.is_enabled():
                    btn.click()
                    self.log(f"검색 버튼 클릭 성공: {sel}")
                    return True
            except NoSuchElementException:
                continue
            except Exception as e:
                self.log(f"  버튼 클릭 오류 ({sel}): {e}")

        # JavaScript로 검색 함수 직접 호출
        js_search = [
            "if(typeof fnSearch === 'function') { fnSearch(); return true; }",
            "if(typeof doSearch === 'function') { doSearch(); return true; }",
            "if(typeof gfnSearch === 'function') { gfnSearch(); return true; }",
            "if(typeof scwin !== 'undefined' && scwin.fnSearch) { scwin.fnSearch(); return true; }",
        ]
        for js in js_search:
            try:
                result = self.driver.execute_script(js)
                if result:
                    self.log(f"JavaScript 검색 함수 호출 성공")
                    return True
            except Exception:
                pass

        self.log("경고: 검색 버튼 클릭 실패")
        return False

    # ──────────────────────────────────────────────
    # 9. 결과 대기
    # ──────────────────────────────────────────────
    def wait_for_results(self) -> bool:
        """검색 결과 테이블이 로드될 때까지 대기합니다."""
        self.log("검색 결과 대기 중...")
        result_selectors = [
            (By.XPATH, "//tbody/tr[td]"),
            (By.CSS_SELECTOR, "tbody tr"),
            (By.XPATH, "//table//tr[contains(@class,'data')]"),
            (By.XPATH, "//*[contains(@id,'grid')]//tr"),
        ]

        for by, sel in result_selectors:
            try:
                self.wait.until(EC.presence_of_element_located((by, sel)))
                rows = self.driver.find_elements(by, sel)
                if rows:
                    self.log(f"결과 로드 완료: {len(rows)}행 발견")
                    return True
            except TimeoutException:
                continue

        # "결과 없음" 메시지 확인
        no_result_texts = ["조회된 데이터가 없습니다", "검색 결과가 없습니다", "데이터가 없습니다"]
        for txt in no_result_texts:
            try:
                el = self.driver.find_element(By.XPATH, f"//*[contains(text(),'{txt}')]")
                if el.is_displayed():
                    self.log(f"검색 결과 없음: {txt}")
                    return False
            except NoSuchElementException:
                pass

        self.log("경고: 결과 대기 타임아웃")
        return False

    # ──────────────────────────────────────────────
    # 10. 페이지 이동
    # ──────────────────────────────────────────────
    def _get_current_page(self) -> Optional[int]:
        """현재 활성 페이지 번호를 DOM에서 탐색합니다."""
        active_selectors = [
            "//*[contains(@class,'active') and (self::a or self::span or self::strong or self::b)]",
            "//*[contains(@class,'current') and (self::a or self::span or self::strong or self::b)]",
            "//*[contains(@class,'on') and (self::a or self::span or self::strong or self::b)]",
            "//*[contains(@class,'selected') and (self::a or self::span or self::strong or self::b)]",
            "//strong[parent::*[contains(@class,'paging') or contains(@class,'page')]]",
            "//span[contains(@class,'num') and contains(@class,'on')]",
        ]
        for sel in active_selectors:
            try:
                els = self.driver.find_elements(By.XPATH, sel)
                for el in els:
                    text = el.text.strip()
                    if text.isdigit():
                        return int(text)
            except Exception:
                continue
        return None

    def go_to_next_page(self) -> bool:
        """다음 페이지로 이동합니다."""
        self.log("다음 페이지 이동 시도...")

        # 현재 활성 페이지 번호를 찾아 current+1 번호 버튼을 직접 클릭
        # "다음" 텍스트 버튼은 페이지 블록 이동(예: 1~10 → 11~20)이므로 사용 금지
        current_page = self._get_current_page()
        if current_page is not None:
            next_page = current_page + 1
            self.log(f"현재 페이지: {current_page}, 다음 페이지: {next_page}")
            if self.go_to_page(next_page):
                return True
            self.log(f"페이지 {next_page} 버튼 없음 - 다음 블록 버튼으로 폴백")

        # 폴백: 다음 페이지 블록 버튼 (페이지 번호 버튼이 없는 경우)
        next_block_selectors = [
            "//img[@alt='다음']/..",
            "//a[@title='다음 페이지']",
            "//a[contains(@onclick,'next') or contains(@onclick,'Next')]",
            "//*[contains(@class,'next') or contains(@id,'next')]",
            "//a[normalize-space(text())='다음']",
            "//button[normalize-space(text())='다음']",
        ]

        for sel in next_block_selectors:
            try:
                btn = self.driver.find_element(By.XPATH, sel)
                if btn.is_displayed() and btn.is_enabled():
                    cls = btn.get_attribute("class") or ""
                    if "disabled" in cls or "dim" in cls:
                        self.log("다음 페이지 버튼 비활성화 (마지막 페이지)")
                        return False
                    btn.click()
                    self.log(f"다음 블록 클릭: {sel}")
                    time.sleep(config.PAGE_DELAY)
                    return True
            except (NoSuchElementException, StaleElementReferenceException):
                continue
            except Exception as e:
                self.log(f"  페이지 이동 오류: {e}")

        self.log("다음 페이지 버튼 없음 (마지막 페이지)")
        return False

    def go_to_page(self, page_num: int) -> bool:
        """특정 페이지 번호로 이동합니다."""
        self.log(f"페이지 {page_num} 이동...")
        try:
            page_link = self.driver.find_element(
                By.XPATH, f"//a[text()='{page_num}'] | //button[text()='{page_num}']"
            )
            page_link.click()
            time.sleep(config.PAGE_DELAY)
            return True
        except NoSuchElementException:
            return False

    # ──────────────────────────────────────────────
    # 11. 전체 검색 시퀀스
    # ──────────────────────────────────────────────
    def run_search(self, debug_dom: bool = False) -> bool:
        """
        전체 검색 시퀀스를 실행합니다.
        1. 페이지 이동 → 2. iframe 전환 → 3. 법원/종류 선택 → 4. 검색
        """
        # 1. 페이지 이동
        self.go_to_search_page()

        # 2. DOM 디버깅 (기본 컨텍스트)
        if debug_dom:
            print("\n[DEBUG] === 기본 컨텍스트 DOM ===")
            self.print_dom_structure()

        # 3. iframe 전환
        iframe_ok = self.switch_to_main_iframe()

        if debug_dom:
            print("\n[DEBUG] === iframe 전환 후 DOM ===")
            self.print_dom_structure()

        if not iframe_ok:
            self.log("iframe 전환 실패 - 기본 컨텍스트에서 계속 진행")

        # 4. 잠시 대기 (페이지 완전 로드)
        time.sleep(2)

        # 5. 법원 선택
        court_ok = self.select_court()
        if not court_ok:
            self.log("법원 선택 실패 - 계속 진행")

        # 6. 물건종류 선택
        type_ok = self.select_property_type()
        if not type_ok:
            self.log("물건종류 선택 실패 - 계속 진행")

        # 7. 검색 버튼 클릭
        search_ok = self.click_search_button()
        if not search_ok:
            self.log("검색 버튼 클릭 실패")
            return False

        # 8. 결과 대기
        time.sleep(config.PAGE_DELAY)
        result_ok = self.wait_for_results()

        return result_ok
