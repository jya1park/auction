// ==UserScript==
// @name         법원경매 사건번호 자동검색
// @namespace    https://www.courtauction.go.kr/
// @version      4.0
// @description  경매지도에서 사건번호 클릭 시 법원·연도·종류·번호 자동입력 및 검색 실행 (iframe 대응)
// @author       courtauction-crawler
// @match        https://www.courtauction.go.kr/*
// @grant        none
// @run-at       document-end
// @run-in-frame
// ==/UserScript==

(function () {
    'use strict';

    /* ── URL hash 파라미터 읽기 ──────────────────────────────────
       iframe 내부에서 실행될 때는 부모(top) URL의 hash를 읽는다.
       같은 origin이면 window.top.location.hash에 접근 가능.
    ─────────────────────────────────────────────────────────── */
    function getHashParams() {
        var hashStr = '';
        try {
            // top 프레임 hash 우선 (iframe 안에서 실행 시)
            hashStr = window.top.location.hash
                   || window.parent.location.hash
                   || window.location.hash;
        } catch (e) {
            hashStr = window.location.hash;
        }
        var raw    = decodeURIComponent(hashStr.replace(/^#/, ''));
        var params = {};
        raw.split('&').forEach(function (kv) {
            var idx = kv.indexOf('=');
            if (idx > 0) params[kv.slice(0, idx)] = kv.slice(idx + 1);
        });
        return params;
    }

    var p            = getHashParams();
    var TARGET_CASE  = p['caseNo'];
    var TARGET_COURT = p['court'] || '';

    if (!TARGET_CASE) return;   // 자동검색 대상 아니면 즉시 종료

    /* ── 사건번호 파싱: "2024타경10001" → {year, kind, num} ───── */
    function parseCaseNo(raw) {
        // 앞에 법원명이 붙어있는 경우 제거 후 파싱
        // 예: "수원지방법원2024타경10001" → "2024타경10001"
        var cleaned = raw.replace(/^[가-힣\s]+(?=\d{4})/, '').trim();
        var m = cleaned.match(/(\d{4})([가-힣]+)(\d+)/);
        if (!m) return null;
        return { year: m[1], kind: m[2], num: m[3] };
    }

    var parsed = parseCaseNo(TARGET_CASE);
    console.log('[경매자동검색] v4.0 시작 | 사건번호:', TARGET_CASE,
                '| 파싱:', parsed, '| 법원:', TARGET_COURT);

    /* ── DOM 탐색 헬퍼 ──────────────────────────────────────────
       1) 현재 document에서 직접 탐색
       2) 찾지 못하면 하위 frame/iframe document에서 재귀 탐색
    ─────────────────────────────────────────────────────────── */
    function findInDoc(doc, selector, byId) {
        try {
            return byId ? doc.getElementById(selector)
                        : doc.querySelector(selector);
        } catch (e) { return null; }
    }

    function searchAllFrames(selector, byId) {
        // 현재 문서 먼저
        var el = findInDoc(document, selector, byId);
        if (el) return el;

        // 하위 frame/iframe 순회
        var frames = document.querySelectorAll('frame, iframe');
        for (var i = 0; i < frames.length; i++) {
            try {
                var fd = frames[i].contentDocument || frames[i].contentWindow.document;
                if (!fd) continue;
                el = findInDoc(fd, selector, byId);
                if (el) return el;
                // 2단계 중첩 프레임까지
                var inner = fd.querySelectorAll('frame, iframe');
                for (var j = 0; j < inner.length; j++) {
                    try {
                        var fd2 = inner[j].contentDocument || inner[j].contentWindow.document;
                        if (!fd2) continue;
                        el = findInDoc(fd2, selector, byId);
                        if (el) return el;
                    } catch (e2) { /* cross-origin 무시 */ }
                }
            } catch (e) { /* cross-origin 무시 */ }
        }
        return null;
    }

    /* ── 이벤트 발생 헬퍼 ───────────────────────────────────── */
    function trigger(el, events) {
        (events || ['input', 'change', 'blur']).forEach(function (ev) {
            try { el.dispatchEvent(new Event(ev, { bubbles: true })); } catch (e) {}
        });
    }

    /* select 요소에서 text 또는 value 일치 옵션 선택 */
    function selectByText(sel, text) {
        if (!sel || !text) return false;
        // 완전 일치 우선
        for (var i = 0; i < sel.options.length; i++) {
            var t = (sel.options[i].text  || '').trim();
            var v = (sel.options[i].value || '').trim();
            if (t === text || v === text) {
                sel.selectedIndex = i;
                trigger(sel, ['change']);
                return true;
            }
        }
        // 부분 일치
        for (var i = 0; i < sel.options.length; i++) {
            var t = (sel.options[i].text  || '').trim();
            if (t.includes(text) || text.includes(t.replace(/\s*(지방법원|지원|법원)\s*$/, ''))) {
                sel.selectedIndex = i;
                trigger(sel, ['change']);
                return true;
            }
        }
        return false;
    }

    /* ── 각 필드 채우기 ─────────────────────────────────────── */

    // 법원 ID 후보
    var COURT_IDS = [
        'mf_wfm_mainFrame_sbx_dspslRsltSrchCortOfc',
        'mf_wfm_mainFrame_sbx_auctnCsSrchCortOfc',
    ];
    function fillCourt() {
        if (!TARGET_COURT) return;
        var sel = null;
        for (var i = 0; i < COURT_IDS.length; i++) {
            sel = searchAllFrames(COURT_IDS[i], true);
            if (sel) break;
        }
        if (!sel) sel = searchAllFrames('select[title*="법원"]', false);
        if (!sel) { console.warn('[경매자동검색] 법원 select 없음'); return; }
        if (selectByText(sel, TARGET_COURT)) {
            console.log('[경매자동검색] 법원 선택 완료:', TARGET_COURT);
        } else {
            console.warn('[경매자동검색] 법원 매칭 실패:', TARGET_COURT);
        }
    }

    // 연도 ID 후보
    var YEAR_IDS = [
        'mf_wfm_mainFrame_sbx_auctnCsSrchCsYear',
    ];
    function fillYear() {
        if (!parsed) return;
        var sel = null;
        for (var i = 0; i < YEAR_IDS.length; i++) {
            sel = searchAllFrames(YEAR_IDS[i], true);
            if (sel) break;
        }
        if (!sel) sel = searchAllFrames('select[title*="연도"]', false);
        if (!sel) { console.warn('[경매자동검색] 연도 select 없음'); return; }
        if (selectByText(sel, parsed.year)) {
            console.log('[경매자동검색] 연도 선택:', parsed.year);
        } else {
            console.warn('[경매자동검색] 연도 매칭 실패:', parsed.year);
        }
    }

    // 사건종류 ID 후보
    var KIND_IDS = [
        'mf_wfm_mainFrame_sbx_auctnCsSrchCsKnd',
        'mf_wfm_mainFrame_sbx_auctnCsSrchCsKnd2',
    ];
    function fillKind() {
        if (!parsed) return;
        var sel = null;
        for (var i = 0; i < KIND_IDS.length; i++) {
            sel = searchAllFrames(KIND_IDS[i], true);
            if (sel) break;
        }
        if (!sel) sel = searchAllFrames('select[title*="종류"], select[title*="구분"]', false);
        if (!sel) { console.log('[경매자동검색] 종류 select 없음 (스킵)'); return; }
        if (selectByText(sel, parsed.kind)) {
            console.log('[경매자동검색] 사건종류 선택:', parsed.kind);
        } else {
            console.warn('[경매자동검색] 사건종류 매칭 실패:', parsed.kind);
        }
    }

    // 번호 입력 ID 후보
    var NUM_IDS = [
        'mf_wfm_mainFrame_ibx_auctnCsSrchCsNo',
    ];
    function fillNum() {
        if (!parsed) return false;
        var inp = null;
        for (var i = 0; i < NUM_IDS.length; i++) {
            inp = searchAllFrames(NUM_IDS[i], true);
            if (inp) break;
        }
        if (!inp) inp = searchAllFrames('input[title*="번호"]', false);
        if (!inp) { console.warn('[경매자동검색] 번호 input 없음'); return false; }
        inp.value = parsed.num;
        trigger(inp, ['input', 'change', 'blur']);
        inp.focus();
        console.log('[경매자동검색] 번호 입력:', parsed.num);
        return true;
    }

    /* ── 검색 버튼 클릭 ─────────────────────────────────────── */
    var BTN_CANDIDATES = [
        'mf_wfm_mainFrame_btn_auctnCsSrch',
        'mf_wfm_mainFrame_btn_auctnCsSrchGo',
        'mf_wfm_mainFrame_btn_auctnCsInqr',
        'mf_wfm_mainFrame_btn_dspslRsltSrch',
        'mf_wfm_mainFrame_btnSearch',
    ];
    function clickSearch() {
        var btn = null;

        // ID 후보
        for (var i = 0; i < BTN_CANDIDATES.length; i++) {
            btn = searchAllFrames(BTN_CANDIDATES[i], true);
            if (btn) break;
        }

        // 텍스트 "검색" / "조회" 버튼
        if (!btn) {
            ['frame', 'iframe', ''].forEach(function (tag) {
                if (btn) return;
                var docs = [document];
                document.querySelectorAll('frame, iframe').forEach(function (f) {
                    try { docs.push(f.contentDocument || f.contentWindow.document); } catch (e) {}
                });
                docs.forEach(function (d) {
                    if (btn) return;
                    d.querySelectorAll('button, input[type="button"], input[type="submit"]')
                     .forEach(function (el) {
                        if (btn) return;
                        var txt = (el.textContent || el.value || '').trim().replace(/\s+/g, '');
                        if (txt === '검색' || txt === '조회' || txt === '검색하기') btn = el;
                    });
                });
            });
        }

        // 이미지 버튼
        if (!btn) {
            var img = searchAllFrames('img[alt="검색"], img[alt="조회"], img[title="검색"]', false);
            if (img) btn = img.closest('button, a') || img.parentElement;
        }

        // 엔터 키 폴백
        if (!btn) {
            var numInp = null;
            for (var i = 0; i < NUM_IDS.length; i++) {
                numInp = searchAllFrames(NUM_IDS[i], true);
                if (numInp) break;
            }
            if (numInp) {
                numInp.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true }));
                console.log('[경매자동검색] Enter 키로 검색 시도');
                return;
            }
        }

        if (btn) {
            btn.click();
            console.log('[경매자동검색] 검색 클릭:', btn.id || btn.textContent.trim());
        } else {
            console.warn('[경매자동검색] 검색 버튼을 찾지 못했습니다.');
        }
    }

    /* ── 메인 실행 루프 ─────────────────────────────────────── */
    var MAX_WAIT_MS = 25000;
    var startAt     = Date.now();

    function run() {
        if (Date.now() - startAt > MAX_WAIT_MS) {
            alert('[법원경매 자동검색] 시간 초과.\n수동 입력: ' + TARGET_CASE);
            return;
        }

        // 연도 select가 로딩될 때까지 대기
        var yearSel = null;
        for (var i = 0; i < YEAR_IDS.length; i++) {
            yearSel = searchAllFrames(YEAR_IDS[i], true);
            if (yearSel) break;
        }
        if (!yearSel) yearSel = searchAllFrames('select[title*="연도"]', false);

        if (!yearSel || yearSel.options.length < 2) {
            setTimeout(run, 400);
            return;
        }

        fillCourt();
        fillYear();
        fillKind();
        var ok = fillNum();

        if (ok) {
            setTimeout(clickSearch, 700);
        } else {
            setTimeout(run, 500);
        }
    }

    // 페이지 로드 완료 후 실행
    if (document.readyState === 'complete') {
        setTimeout(run, 1500);
    } else {
        window.addEventListener('load', function () { setTimeout(run, 1500); });
    }

})();
