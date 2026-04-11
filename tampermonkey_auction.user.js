// ==UserScript==
// @name         법원경매 사건번호 자동검색
// @namespace    https://www.courtauction.go.kr/
// @version      3.0
// @description  경매지도에서 사건번호 클릭 시 법원·연도·종류·번호 자동입력 및 검색 실행
// @author       courtauction-crawler
// @match        https://www.courtauction.go.kr/*
// @grant        none
// @run-at       document-end
// ==/UserScript==

(function () {
    'use strict';

    /* ── 확인된 DOM ID ──────────────────────────────────────────────
       법원   : mf_wfm_mainFrame_sbx_dspslRsltSrchCortOfc
       연도   : mf_wfm_mainFrame_sbx_auctnCsSrchCsYear
       종류   : mf_wfm_mainFrame_sbx_auctnCsSrchCsKnd  (추정 – 타경/타임 등)
       번호   : mf_wfm_mainFrame_ibx_auctnCsSrchCsNo
    ─────────────────────────────────────────────────────────────── */
    var ID = {
        court  : 'mf_wfm_mainFrame_sbx_dspslRsltSrchCortOfc',
        year   : 'mf_wfm_mainFrame_sbx_auctnCsSrchCsYear',
        kind   : 'mf_wfm_mainFrame_sbx_auctnCsSrchCsKnd',   // 사건종류 (추정)
        num    : 'mf_wfm_mainFrame_ibx_auctnCsSrchCsNo',
        btnCandidates: [
            'mf_wfm_mainFrame_btn_auctnCsSrch',
            'mf_wfm_mainFrame_btn_auctnCsSrchGo',
            'mf_wfm_mainFrame_btn_auctnCsInqr',
            'mf_wfm_mainFrame_btn_dspslRsltSrch',
            'mf_wfm_mainFrame_btnSearch',
        ]
    };

    /* ── URL hash 파라미터 파싱 ────────────────────────────────── */
    function getHashParams() {
        var raw = decodeURIComponent(window.location.hash.replace(/^#/, ''));
        var params = {};
        raw.split('&').forEach(function (kv) {
            var idx = kv.indexOf('=');
            if (idx > 0) params[kv.slice(0, idx)] = kv.slice(idx + 1);
        });
        return params;
    }

    var p            = getHashParams();
    var TARGET_CASE  = p['caseNo'];   // 예: "2024타경10001"
    var TARGET_COURT = p['court'] || '';

    if (!TARGET_CASE) return;

    /* ── 사건번호 파싱: "2024타경10001" → { year, kind, num } ─── */
    function parseCaseNo(raw) {
        // 법원명 접두어 제거 후 파싱 (예: "수원2024타경10001" → 제거 불필요하지만 대비)
        var m = raw.match(/(\d{4})([가-힣]+)(\d+)/);
        if (!m) return null;
        return { year: m[1], kind: m[2], num: m[3] };
    }

    var parsed = parseCaseNo(TARGET_CASE);
    console.log('[경매자동검색] 파싱 결과:', parsed, '/ 법원:', TARGET_COURT);

    /* ── 이벤트 헬퍼 ───────────────────────────────────────────── */
    function trigger(el, events) {
        (events || ['input', 'change', 'blur']).forEach(function (ev) {
            el.dispatchEvent(new Event(ev, { bubbles: true }));
        });
    }

    /* select 요소에서 text 또는 value가 일치하는 옵션 선택 */
    function selectByText(sel, text) {
        if (!sel || !text) return false;
        for (var i = 0; i < sel.options.length; i++) {
            var t = sel.options[i].text.trim();
            var v = sel.options[i].value.trim();
            if (t === text || v === text || t.includes(text) || text.includes(t.replace(/\s*(지방법원|지원|법원)\s*$/, ''))) {
                sel.selectedIndex = i;
                trigger(sel, ['change']);
                return true;
            }
        }
        return false;
    }

    /* ── 1. 법원 선택 ──────────────────────────────────────────── */
    function fillCourt() {
        if (!TARGET_COURT) return;
        var sel = document.getElementById(ID.court)
               || document.querySelector('select[title="법원 선택"]');
        if (!sel) return;
        if (selectByText(sel, TARGET_COURT)) {
            console.log('[경매자동검색] 법원 선택 완료:', TARGET_COURT);
        } else {
            console.warn('[경매자동검색] 법원 매칭 실패:', TARGET_COURT);
        }
    }

    /* ── 2. 연도 선택 ──────────────────────────────────────────── */
    function fillYear() {
        if (!parsed) return;
        var sel = document.getElementById(ID.year)
               || document.querySelector('select[title="연도 선택"]');
        if (!sel) { console.warn('[경매자동검색] 연도 select 없음'); return; }
        if (selectByText(sel, parsed.year)) {
            console.log('[경매자동검색] 연도 선택:', parsed.year);
        } else {
            console.warn('[경매자동검색] 연도 매칭 실패:', parsed.year);
        }
    }

    /* ── 3. 사건종류 선택 (타경 등) ───────────────────────────── */
    function fillKind() {
        if (!parsed) return;
        /* 추정 ID 먼저, 없으면 title로 탐색 */
        var sel = document.getElementById(ID.kind)
               || document.querySelector('select[title*="종류"], select[title*="구분"]');
        if (!sel) {
            /* 연도 select 바로 다음 select 시도 */
            var yearSel = document.getElementById(ID.year);
            if (yearSel) {
                var next = yearSel.parentElement && yearSel.parentElement.nextElementSibling;
                if (next) sel = next.querySelector('select');
            }
        }
        if (!sel) { console.log('[경매자동검색] 종류 select 없음 (스킵)'); return; }
        if (selectByText(sel, parsed.kind)) {
            console.log('[경매자동검색] 사건종류 선택:', parsed.kind);
        } else {
            console.warn('[경매자동검색] 사건종류 매칭 실패:', parsed.kind);
        }
    }

    /* ── 4. 번호 입력 ──────────────────────────────────────────── */
    function fillNum() {
        if (!parsed) return false;
        var inp = document.getElementById(ID.num)
               || document.querySelector('input[title="번호 입력"]');
        if (!inp) { console.warn('[경매자동검색] 번호 input 없음'); return false; }
        inp.value = parsed.num;
        trigger(inp, ['input', 'change', 'blur']);
        inp.focus();
        console.log('[경매자동검색] 번호 입력:', parsed.num);
        return true;
    }

    /* ── 5. 검색 버튼 클릭 ─────────────────────────────────────── */
    function clickSearch() {
        var btn = null;

        /* 확인된 ID 후보 순서대로 시도 */
        for (var i = 0; i < ID.btnCandidates.length; i++) {
            btn = document.getElementById(ID.btnCandidates[i]);
            if (btn) break;
        }

        /* 텍스트가 "검색"/"조회"인 버튼 */
        if (!btn) {
            document.querySelectorAll('button, input[type="button"], input[type="submit"]').forEach(function (el) {
                if (btn) return;
                var txt = (el.textContent || el.value || '').trim();
                if (txt === '검색' || txt === '조회' || txt === '검  색') btn = el;
            });
        }

        /* 이미지 버튼 */
        if (!btn) {
            var img = document.querySelector('img[alt="검색"], img[alt="조회"], img[title="검색"]');
            if (img) btn = img.closest('button, a') || img.parentElement;
        }

        /* Enter 키 폴백 */
        if (!btn) {
            var numInp = document.getElementById(ID.num);
            if (numInp) {
                numInp.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true }));
                console.log('[경매자동검색] Enter 키로 검색');
                return;
            }
        }

        if (btn) {
            btn.click();
            console.log('[경매자동검색] 검색 클릭:', btn.id || btn.textContent.trim());
        } else {
            console.warn('[경매자동검색] 검색 버튼 못 찾음');
        }
    }

    /* ── 메인 루프 ─────────────────────────────────────────────── */
    var MAX_WAIT_MS = 25000;
    var startAt     = Date.now();

    function run() {
        if (Date.now() - startAt > MAX_WAIT_MS) {
            alert('[법원경매 자동검색] 시간 초과.\n수동으로 입력해주세요: ' + TARGET_CASE);
            return;
        }

        /* 연도 select가 로딩될 때까지 대기 */
        var yearSel = document.getElementById(ID.year)
                   || document.querySelector('select[title="연도 선택"]');
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

    window.addEventListener('load', function () { setTimeout(run, 1500); });

})();
