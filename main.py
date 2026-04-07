"""
대법원 경매 크롤러 메인 실행 파일

사용법:
    python main.py              # 기본 실행 (headless, 전체 페이지)
    python main.py --visible    # 브라우저 창 표시
    python main.py --pages 5    # 5페이지만 수집
    python main.py --watchlist  # 찜한 물건 낙찰 조회
    python main.py --excel      # Excel도 저장
    python main.py --debug      # 디버그 모드 (DOM 구조 출력)
    python main.py --visible --debug --pages 3 --excel
"""
import sys
import time
import argparse

import config
from crawler.driver import create_driver, quit_driver
from crawler.navigator import Navigator
from crawler.list_parser import parse_list_page, get_total_count
from crawler.detail_parser import DetailParser
from crawler.result_navigator import ResultNavigator
from crawler.result_parser import parse_result_page, get_total_count as get_result_count
from storage.exporter import save_csv, save_excel, update_excel, print_summary


def parse_args():
    parser = argparse.ArgumentParser(
        description="대법원 경매 크롤러 - 수원지방법원 아파트 물건 수집",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--visible", action="store_true",
        help="브라우저 창을 표시합니다 (기본: headless)"
    )
    parser.add_argument(
        "--pages", type=int, default=0,
        help="수집할 최대 페이지 수 (0=전체, 기본: 0)"
    )
    parser.add_argument(
        "--excel", action="store_true",
        help="Excel 파일도 저장합니다"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="디버그 모드 - DOM 구조 상세 출력"
    )
    parser.add_argument(
        "--watchlist", action="store_true",
        help="찜한 물건 낙찰 조회 모드"
    )
    parser.add_argument(
        "--detail", action="store_true",
        help="각 물건의 상세 정보(낙찰가 등)도 수집합니다"
    )
    parser.add_argument(
        "--court", type=str, default=config.TARGET_COURT,
        help=f"수집할 법원명 (기본: {config.TARGET_COURT})"
    )
    parser.add_argument(
        "--type", type=str, default=config.TARGET_TYPE,
        dest="prop_type",
        help=f"물건종류 (기본: {config.TARGET_TYPE})"
    )
    return parser.parse_args()


def _parse_case_number(raw: str):
    """
    '2023타경10883' 형식의 사건번호를 (연도, 사건구분, 번호)로 분리합니다.
    예: '2023타경10883' → ('2023', '타경', '10883')
    """
    import re
    m = re.match(r'(\d{4})(타경|타채|강경|강채|타기|경매|임의|강제)(\d+)', raw.strip())
    if m:
        return m.group(1), m.group(2), m.group(3)
    # 숫자만 있는 경우 (연도+번호만)
    m2 = re.match(r'(\d{4})(\d+)', raw.strip())
    if m2:
        return m2.group(1), '타경', m2.group(2)
    return None, None, raw.strip()


def _input_case_number(driver, year: str, case_type: str, number: str, debug: bool = False):
    """
    사건번호 검색 필드에 연도/사건구분/번호를 각각 입력합니다.
    대법원 경매 사이트는 연도 + 사건구분(드롭다운) + 번호 3개 필드 구조입니다.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import Select

    def log(msg):
        if debug:
            print(f"  [CaseInput] {msg}")

    # ── 연도 입력 ──
    year_ids = [
        "mf_wfm_mainFrame_ipt_jiwonYear",
        "mf_wfm_mainFrame_ipt_caseYear",
        "caseYear", "jiwonYear", "searchYear",
    ]
    year_xpath = "//input[contains(@id,'Year') or contains(@id,'year')][@maxlength='4' or @size='4']"
    year_input = None
    for yid in year_ids:
        try:
            el = driver.find_element(By.ID, yid)
            year_input = el
            break
        except Exception:
            pass
    if not year_input:
        try:
            els = driver.find_elements(By.XPATH, year_xpath)
            if els:
                year_input = els[0]
        except Exception:
            pass
    if year_input:
        try:
            year_input.clear()
            year_input.send_keys(year)
            log(f"연도 입력: {year}")
        except Exception as e:
            log(f"연도 입력 오류: {e}")
    else:
        log("연도 입력 필드 없음")

    # ── 사건구분 드롭다운 ──
    type_ids = [
        "mf_wfm_mainFrame_sbx_caseGbn",
        "mf_wfm_mainFrame_sbx_jiwonGbn",
        "caseGbn", "jiwonGbn", "caseType",
    ]
    codes = [str(ord(c)) for c in case_type]
    js_select = f"""
    var ids = {type_ids};
    var codes = [{','.join(codes)}];
    var target = String.fromCharCode.apply(null, codes);
    for(var j=0; j<ids.length; j++){{
        var sel = document.getElementById(ids[j]);
        if(!sel) continue;
        for(var i=0; i<sel.options.length; i++){{
            if(sel.options[i].text.indexOf(target)>=0 || sel.options[i].value.indexOf(target)>=0){{
                sel.selectedIndex = i;
                sel.dispatchEvent(new Event('change',{{bubbles:true}}));
                return 'ok:' + sel.options[i].text;
            }}
        }}
    }}
    return 'not-found';
    """
    try:
        r = driver.execute_script(js_select)
        log(f"사건구분 선택: {r}")
    except Exception as e:
        log(f"사건구분 오류: {e}")

    # ── 번호 입력 ──
    num_ids = [
        "mf_wfm_mainFrame_ipt_jiwonNo",
        "mf_wfm_mainFrame_ipt_caseNo",
        "caseNo", "jiwonNo", "searchNo",
    ]
    num_xpath = "//input[contains(@id,'No') or contains(@id,'no') or contains(@id,'Num') or contains(@id,'num')][@type='text']"
    num_input = None
    for nid in num_ids:
        try:
            el = driver.find_element(By.ID, nid)
            num_input = el
            break
        except Exception:
            pass
    if not num_input:
        try:
            els = driver.find_elements(By.XPATH, num_xpath)
            # 연도 필드가 아닌 것 중 첫 번째
            for el in els:
                maxlen = el.get_attribute("maxlength") or ""
                if maxlen != "4":
                    num_input = el
                    break
        except Exception:
            pass
    if num_input:
        try:
            num_input.clear()
            num_input.send_keys(number)
            log(f"번호 입력: {number}")
        except Exception as e:
            log(f"번호 입력 오류: {e}")
    else:
        log("번호 입력 필드 없음")


def run_watchlist_mode(driver, navigator, debug):
    """찜한 물건 낙찰 조회 모드."""
    print("\n" + "="*60)
    print("찜한 물건 낙찰 조회 모드")
    print("사건번호를 입력하세요 (예: 2023타경10883, 빈 줄 입력 시 종료)")
    print("="*60)

    detail_parser = DetailParser(driver, debug=debug)
    results = []

    while True:
        raw_input = input("사건번호: ").strip()
        if not raw_input:
            break

        year, case_type, number = _parse_case_number(raw_input)
        print(f"  조회 중: {raw_input}  (연도={year}, 구분={case_type}, 번호={number})")

        # 검색 페이지로 이동
        navigator.go_to_search_page()
        navigator.switch_to_main_iframe()
        time.sleep(1)

        # 연도/사건구분/번호 각각 입력
        _input_case_number(driver, year, case_type, number, debug=debug)
        time.sleep(0.5)

        navigator.click_search_button()
        time.sleep(2)

        items = parse_list_page(driver.page_source, debug=debug)
        if items:
            detail = detail_parser.get_detail(items[0], navigator)
            item = {**items[0], **detail}
            results.append(item)
            print(f"  결과: 낙찰가={item.get('낙찰가', '정보없음')}, 상태={item.get('진행상태', '정보없음')}")
        else:
            print(f"  결과: 사건번호 {raw_input} 조회 결과 없음")

    if results:
        save_csv(results)
        print(f"\n총 {len(results)}건 조회 완료")

    return results


def run_result_mode(driver, args) -> list:
    """매각결과 크롤링 모드."""
    debug = args.debug
    max_pages = args.pages

    print(f"\n[Main] 매각결과 크롤링 시작")
    print(f"  대상 법원: {args.court}")
    print(f"  물건종류: {args.prop_type}")
    print()

    result_nav = ResultNavigator(driver, debug=debug)
    search_ok = result_nav.run_search()

    if not search_ok:
        print("[Main] 매각결과 검색 실패 또는 결과 없음")
        return []

    total = get_result_count(driver.page_source)
    if total:
        print(f"[Main] 매각결과 전체: {total}건")

    all_data = []
    page = 1

    while True:
        print(f"\n[Main] 매각결과 페이지 {page} 파싱 중...")
        items = parse_result_page(driver.page_source, debug=debug)

        if not items:
            print(f"[Main] 매각결과 페이지 {page}: 데이터 없음")
            break

        print(f"[Main] 매각결과 페이지 {page}: {len(items)}건")
        all_data.extend(items)

        if max_pages > 0 and page >= max_pages:
            print(f"[Main] 최대 페이지({max_pages}) 도달")
            break

        has_next = result_nav.go_to_next_page()
        if not has_next:
            print("[Main] 매각결과 마지막 페이지")
            break

        page += 1
        time.sleep(config.PAGE_DELAY)

    print(f"\n[Main] 매각결과 수집 완료: {len(all_data)}건")
    return all_data


def run_crawl_mode(driver, navigator, args):
    """일반 크롤링 모드."""
    debug = args.debug
    max_pages = args.pages

    print(f"\n[Main] 크롤링 시작")
    print(f"  대상 법원: {args.court}")
    print(f"  물건종류: {args.prop_type}")
    print(f"  최대 페이지: {'전체' if max_pages == 0 else max_pages}")
    print(f"  상세 수집: {'예' if args.detail else '아니오'}")
    print()

    # 검색 실행
    print("[Main] 검색 실행 중...")
    search_ok = navigator.run_search(debug_dom=debug)

    if not search_ok:
        print("[Main] 검색 결과가 없거나 검색 실패. 현재 페이지 소스를 저장하고 종료합니다.")
        # 디버그용 페이지 소스 저장
        if debug:
            with open("debug_page_source.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("[Main] debug_page_source.html 저장됨")
        return []

    # 전체 결과 수 확인
    total = get_total_count(driver.page_source)
    if total:
        print(f"[Main] 전체 검색 결과: {total}건")

    all_data = []
    detail_parser = DetailParser(driver, debug=debug) if args.detail else None
    page = 1

    while True:
        print(f"\n[Main] 페이지 {page} 파싱 중...")

        items = parse_list_page(driver.page_source, debug=debug)

        if not items:
            print(f"[Main] 페이지 {page}: 데이터 없음")
            break

        print(f"[Main] 페이지 {page}: {len(items)}건 파싱")

        # 상세 정보 수집 (선택적)
        if detail_parser:
            for i, item in enumerate(items):
                case_num = item.get("사건번호", f"item_{i}")
                print(f"  상세 수집 중: {case_num} ({i+1}/{len(items)})")
                detail = detail_parser.get_detail(item, navigator)
                if detail:
                    items[i] = {**item, **detail}

        all_data.extend(items)
        print(f"[Main] 누적 수집: {len(all_data)}건")

        # 페이지 제한 확인
        if max_pages > 0 and page >= max_pages:
            print(f"[Main] 최대 페이지({max_pages}) 도달")
            break

        # 다음 페이지 이동
        has_next = navigator.go_to_next_page()
        if not has_next:
            print("[Main] 마지막 페이지 도달")
            break

        page += 1
        time.sleep(config.PAGE_DELAY)

    return all_data


def main():
    args = parse_args()

    print("="*60)
    print("대법원 경매 크롤러")
    print("="*60)

    headless = not args.visible
    driver = None

    try:
        # 드라이버 초기화
        print(f"[Main] 드라이버 초기화 (headless={headless})...")
        driver = create_driver(headless=headless, debug=args.debug)
        navigator = Navigator(driver, debug=args.debug)

        if args.watchlist:
            # 찜한 물건 조회 모드
            data = run_watchlist_mode(driver, navigator, args.debug)
        else:
            # 일반 크롤링 모드
            # 법원/물건종류 설정 반영
            if args.court != config.TARGET_COURT:
                config.TARGET_COURT = args.court
            if args.prop_type != config.TARGET_TYPE:
                config.TARGET_TYPE = args.prop_type

            data = run_crawl_mode(driver, navigator, args)

        # 매각결과 크롤링 (경매목록과 동일한 조건)
        result_data = []
        try:
            print("\n[Main] 매각결과 수집 시작...")
            result_data = run_result_mode(driver, args)
        except Exception as e:
            print(f"[Main] 매각결과 수집 오류 (경매목록만 저장): {e}")
            if args.debug:
                import traceback
                traceback.print_exc()

        # 결과 저장
        if data or result_data:
            if data:
                print_summary(data)
                csv_path = save_csv(data)
            xlsx_path = update_excel(data, result_data)  # 두 시트 누적 업데이트
        else:
            print("\n[Main] 수집된 데이터가 없습니다.")

    except KeyboardInterrupt:
        print("\n[Main] 사용자 중단 (Ctrl+C)")
    except Exception as e:
        print(f"\n[Main] 예기치 않은 오류: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        # 오류 시에도 수집된 데이터 저장 시도
        try:
            if 'data' in locals() and data:
                print(f"[Main] 오류 발생 전 수집 데이터 저장 시도: {len(data)}건")
                save_csv(data, f"emergency_save_{int(time.time())}.csv")
        except Exception:
            pass
    finally:
        if driver:
            quit_driver(driver, debug=args.debug)
        print("\n[Main] 크롤러 종료")


if __name__ == "__main__":
    main()
