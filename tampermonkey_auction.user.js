// ==UserScript==
// @name         법원경매 사건번호 자동검색
// @namespace    https://www.courtauction.go.kr/
// @version      1.2
// @description  경매지도에서 사건번호 클릭 시 법원 선택 · 사건번호 입력 · 검색 자동 실행
// @author       courtauction-crawler
// @match        https://www.courtauction.go.kr/*
// @grant        none
// @run-at       document-end
// ==/UserScript==

(function () {
    'use strict';

    /* ── URL hash 파라미터 파싱 ───────────────────────────────────── */
    function getHashParams() {
        var raw = decodeURIComponent(window.location.hash.replace(/^#/, ''));
        var params = {};
        raw.split('&').forEach(function (kv) {
            var idx = kv.indexOf('=');
            if (idx > 0) params[kv.slice(0, idx)] = kv.slice(idx + 1);
        });
        return params;
    }

    var p          = getHashParams();
    var TARGET_CASE  = p['caseNo'];
    var TARGET_COURT = p['court'] || '';   // 예: "수원지방법원"

    if (!TARGET_CASE) return;   // 자동검색 파라미터 없으면 스크립트 종료

    console.log('[경매자동검색] 사건번호:', TARGET_CASE, '/ 법원:', TARGET_COURT);

    /* ── 유틸 ──────────────────────────────────────────────────────── */
    function trigger(el, events) {
        (events || ['input', 'change', 'blur']).forEach(function (ev) {
            el.dispatchEvent(new Event(ev, { bubbles: true }));
        });
    }

    /* ── 법원 콤보박스 채우기 ────────────────────────────────────── */
    function fillCourt() {
        if (!TARGET_COURT) return true;   // 법원 정보 없으면 스킵

        /* 1) <select> 요소 직접 매칭 */
        var selects = document.querySelectorAll('select');
        for (var i = 0; i < selects.length; i++) {
            var sel = selects[i];
            for (var j = 0; j < sel.options.length; j++) {
                var optText = sel.options[j].text;
                if (optText === TARGET_COURT ||
                    optText.includes(TARGET_COURT) ||
                    TARGET_COURT.includes(optText.replace(/\s*(지방법원|지원|법원)\s*$/, ''))) {
                    sel.selectedIndex = j;
                    trigger(sel, ['change']);
                    console.log('[경매자동검색] 법원 선택:', optText);
                    return true;
                }
            }
        }

        /* 2) WebSquare API 시도 (콤보박스 ID 후보) */
        var ws = window.websquare || window.w2 || null;
        if (ws && ws.getComponentById) {
            var courtIds = [
                'sel_courtNm', 'curt_cd', 'courtNm', 'courtCode',
                'court_cd', 'cbo_court', 'sel_court', 'courtCd',
                'selCourtNm', 'selCourt'
            ];
            for (var k = 0; k < courtIds.length; k++) {
                try {
                    var comp = ws.getComponentById(courtIds[k]);
                    if (comp && comp.setValue) {
                        comp.setValue(TARGET_COURT);
                        console.log('[경매자동검색] WebSquare 법원 입력:', courtIds[k]);
                        return true;
                    }
                } catch (e) { /* 없는 ID면 무시 */ }
            }
        }

        /* 법원 선택 실패해도 사건번호 입력은 계속 진행 */
        return false;
    }

    /* ── 사건번호 입력 ──────────────────────────────────────────── */
    function fillCaseNo() {
        /* 1) 속성/플레이스홀더/ID로 input 찾기 */
        var inputs = document.querySelectorAll('input[type="text"], input:not([type])');
        var found  = null;

        inputs.forEach(function (inp) {
            if (found) return;
            var ph = (inp.placeholder || '').toLowerCase();
            var id = (inp.id   || '').toLowerCase();
            var nm = (inp.name || '').toLowerCase();
            if (ph.includes('사건') || ph.includes('case') ||
                id.includes('case') || id.includes('caseNo') || id.includes('사건') ||
                nm.includes('case') || nm.includes('사건')) {
                found = inp;
            }
        });

        /* 2) 라벨 텍스트로 연결된 input 찾기 */
        if (!found) {
            var labels = document.querySelectorAll('label, th, td, span, div');
            labels.forEach(function (lbl) {
                if (found) return;
                if (lbl.textContent.trim() === '사건번호') {
                    /* label for= 연결 */
                    if (lbl.htmlFor) {
                        found = document.getElementById(lbl.htmlFor);
                        return;
                    }
                    /* 인접 sibling/cell input */
                    var sib = lbl.nextElementSibling;
                    if (sib && sib.tagName === 'INPUT') { found = sib; return; }
                    var cell = lbl.closest('td, th');
                    if (cell) {
                        var next = cell.nextElementSibling;
                        if (next) found = next.querySelector('input');
                    }
                }
            });
        }

        /* 3) 마지막 수단 – 첫 번째 visible/enabled text input */
        if (!found) {
            inputs.forEach(function (inp) {
                if (found) return;
                if (inp.offsetParent !== null && !inp.disabled && !inp.readOnly) {
                    found = inp;
                }
            });
        }

        /* 4) WebSquare API 시도 */
        var ws = window.websquare || window.w2 || null;
        if (ws && ws.getComponentById) {
            var caseIds = [
                'inp_caseNo', 'case_no', 'caseNo', 'inp_case',
                'caseNum', 'txt_caseNo', 'inputCaseNo', 'caseNumber'
            ];
            caseIds.forEach(function (cid) {
                try {
                    var comp = ws.getComponentById(cid);
                    if (comp && comp.setValue) {
                        comp.setValue(TARGET_CASE);
                        console.log('[경매자동검색] WebSquare 사건번호 입력:', cid);
                        found = true;   // 플래그 세팅
                    }
                } catch (e) { }
            });
        }

        if (found && found !== true) {
            found.value = TARGET_CASE;
            trigger(found, ['input', 'change', 'blur']);
            found.focus();
            console.log('[경매자동검색] 사건번호 입력 완료');
            return true;
        }
        return false;
    }

    /* ── 검색 버튼 클릭 ─────────────────────────────────────────── */
    function clickSearch() {
        var btn = null;

        /* a) 텍스트/value가 "검색" or "조회" 인 버튼 */
        document.querySelectorAll('button, input[type="button"], input[type="submit"]').forEach(function (el) {
            if (btn) return;
            var txt = (el.textContent || el.value || '').trim();
            if (txt === '검색' || txt === '조회' || txt === '검  색') btn = el;
        });

        /* b) 이미지 버튼 alt="검색" */
        if (!btn) {
            var imgs = document.querySelectorAll('img[alt="검색"], img[alt="조회"], img[title="검색"]');
            if (imgs.length > 0) btn = imgs[0].closest('button, a') || imgs[0].parentElement;
        }

        /* c) WebSquare 버튼 ID 후보 */
        if (!btn) {
            var ws = window.websquare || window.w2 || null;
            var btnIds = ['btn_search', 'btnSearch', 'btn_inq', 'searchBtn', 'btn_srch'];
            if (ws && ws.getComponentById) {
                btnIds.forEach(function (bid) {
                    if (btn) return;
                    try {
                        var comp = ws.getComponentById(bid);
                        if (comp && comp.trigger) { comp.trigger('click'); btn = true; }
                        else if (comp && comp.click) { comp.click(); btn = true; }
                    } catch (e) { }
                });
            }
        }

        /* d) Enter 키 */
        if (!btn) {
            var inputs = document.querySelectorAll('input[type="text"]');
            inputs.forEach(function (inp) {
                if (btn) return;
                if (inp.value === TARGET_CASE) {
                    inp.dispatchEvent(new KeyboardEvent('keydown', {
                        key: 'Enter', keyCode: 13, bubbles: true
                    }));
                    btn = true;
                }
            });
        }

        if (btn && btn !== true) {
            btn.click();
            console.log('[경매자동검색] 검색 버튼 클릭');
        }
    }

    /* ── 메인 실행 루프 ─────────────────────────────────────────── */
    var MAX_WAIT_MS = 25000;
    var startAt    = Date.now();
    var caseInputted = false;

    function run() {
        if (Date.now() - startAt > MAX_WAIT_MS) {
            alert(
                '[법원경매 자동검색] 페이지 로딩 시간 초과.\n' +
                '아래 사건번호를 수동으로 입력해주세요:\n\n' +
                TARGET_CASE
            );
            return;
        }

        /* 폼 요소가 아직 없으면 대기 */
        var hasForm = document.querySelectorAll('select, input[type="text"], input:not([type])').length > 0;
        if (!hasForm) {
            setTimeout(run, 400);
            return;
        }

        if (!caseInputted) {
            fillCourt();
            caseInputted = fillCaseNo();
        }

        if (caseInputted) {
            setTimeout(clickSearch, 700);   // 입력 후 0.7초 뒤 검색 클릭
        } else {
            setTimeout(run, 500);
        }
    }

    /* 페이지 완전 로드 후 1.5초 뒤 시작 (WebSquare 초기화 대기) */
    window.addEventListener('load', function () {
        setTimeout(run, 1500);
    });

})();
