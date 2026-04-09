"""
대법원 경매 크롤러 메인 실행 파일

사용법:
    python main.py              # 기본 실행 (headless, 전체 페이지)
    python main.py --visible    # 브라우저 창 표시
    python main.py --pages 5    # 5페이지만 수집
    python main.py --watchlist  # 찜한 물건 낙찰 조회
    python main.py --debug      # 디버그 모드 (DOM 구조 출력)
    python main.py --visible --debug --pages 3
"""
import sys
import time
import argparse

import config
from crawler.driver import create_driver, quit_driver
from crawler.navigator import Navigator
from crawler.list_parser import parse_list_page, get_total_count
from crawler.detail_parser import DetailParser
from storage.exporter import save_list_csv, save_result_csv, print_summary


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


def run_watchlist_mode(driver, navigator, debug):
    """찜한 물건 낙찰 조회 모드."""
    print("\n" + "="*60)
    print("찜한 물건 낙찰 조회 모드")
    print("사건번호를 입력하세요 (빈 줄 입력 시 종료)")
    print("="*60)

    detail_parser = DetailParser(driver, debug=debug)
    results = []

    while True:
        case_num = input("사건번호: ").strip()
        if not case_num:
            break

        print(f"  조회 중: {case_num}")
        # 검색 페이지로 이동 후 사건번호로 검색
        navigator.go_to_search_page()
        navigator.switch_to_main_iframe()

        # 사건번호 입력 필드 탐색
        try:
            from selenium.webdriver.common.by import By
            case_inputs = driver.find_elements(By.XPATH,
                "//input[contains(@id,'case') or contains(@id,'Case') or contains(@placeholder,'사건번호')]"
            )
            if case_inputs:
                case_inputs[0].clear()
                case_inputs[0].send_keys(case_num)
        except Exception as e:
            if debug:
                print(f"  사건번호 입력 오류: {e}")

        navigator.click_search_button()
        time.sleep(2)

        items = parse_list_page(driver.page_source, debug=debug)
        if items:
            detail = detail_parser.get_detail(items[0], navigator)
            item = {**items[0], **detail}
            results.append(item)
            print(f"  결과: 낙찰가={item.get('낙찰가', '정보없음')}, 상태={item.get('진행상태', '정보없음')}")
        else:
            print(f"  결과: 사건번호 {case_num} 조회 결과 없음")

    if results:
        save_result_csv(results)
        print(f"\n총 {len(results)}건 조회 완료")

    return results


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

        # 다음 페이지 이동 (current_page 전달로 stale element 방지)
        has_next = navigator.go_to_next_page(page)
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
            # 찜한 물건 조회 모드 → 매각결과 CSV 저장
            data = run_watchlist_mode(driver, navigator, args.debug)
        else:
            # 일반 크롤링 모드
            if args.court != config.TARGET_COURT:
                config.TARGET_COURT = args.court
            if args.prop_type != config.TARGET_TYPE:
                config.TARGET_TYPE = args.prop_type

            data = run_crawl_mode(driver, navigator, args)

        # 결과 저장
        if data:
            print_summary(data)
            save_list_csv(data)
            if args.detail:
                save_result_csv(data)
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
                save_list_csv(data)
        except Exception:
            pass
    finally:
        if driver:
            quit_driver(driver, debug=args.debug)
        print("\n[Main] 크롤러 종료")


if __name__ == "__main__":
    main()
