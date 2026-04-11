// ==UserScript==
// @name         법원경매 사건번호 자동검색
// @namespace    https://www.courtauction.go.kr/
// @version      2.0
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

    var p            = getHashParams();
    var TARGET_CASE  = p['caseNo'];
    var TARGET_COURT = p['court'] || '';

    if (!TARGET_CASE) return;

    console.log('[경매자동검색] 사건번호:', TARGET_CASE, '/ 법원:', TARGET_COURT);

    /* ── 이벤트 발생 헬퍼 ──────────────────────────────────────────── */
    function trigger(el, events) {
        (events || ['input', 'change', 'blur']).forEach(function (ev) {
            el.dispatchEvent(new Event(ev, { bubbles: true }));
        });
    }

    /* ────────────────────────────────────────────────────────────────
       1. 법원 선택
    ──────────────────────────────────────────────────────────────── */
    function fillCourt() {
        if (!TARGET_COURT) return true;

        /* 정확한 DOM ID 직접 타겟 (확인된 ID) */
        var sel = document.getElementById('mf_wfm_mainFrame_sbx_dspslRsltSrchCortOfc');

        /* fallback: title 속성으로 찾기 */
        if (!sel) sel = document.querySelector('select[title="법원 선택"]');

        /* fallback: 전체 select 순회 */
        if (!sel) {
            var all = document.querySelectorAll('select.w2selectbox_select, select');
            for (var i = 0; i < all.length; i++) {
                if (all[i].options.length > 3) { sel = all[i]; break; }
            }
        }

        if (!sel) return false;

        /* option text 매칭 (완전일치 → 포함 → 약칭 포함 순) */
        var matched = -1;
        for (var j = 0; j < sel.options.length; j++) {
            var txt = sel.options[j].text.trim();
            if (txt === TARGET_COURT)                          { matched = j; break; }
            if (txt.includes(TARGET_COURT))                   { matched = j; break; }
            var short = TARGET_COURT.replace(/\s*(지방법원|지원|법원)\s*$/, '');
            if (txt.includes(short) && short.length > 1)      { matched = j; }
        }

        if (matched >= 0) {
            sel.selectedIndex = matched;
            trigger(sel, ['change']);
            console.log('[경매자동검색] 법원 선택:', sel.options[matched].text);
            return true;
        }

        console.warn('[경매자동검색] 법원 매칭 실패:', TARGET_COURT);
        return false;
    }

    /* ────────────────────────────────────────────────────────────────
       2. 사건번호 입력
    ──────────────────────────────────────────────────────────────── */
    function fillCaseNo() {
        var found = null;

        /* ① 패턴 기반 ID 후보 (법원 select ID 네이밍 패턴 적용) */
        var candidateIds = [
            'mf_wfm_mainFrame_inp_dspslRsltSrchCaseNo',   // 가장 유력
            'mf_wfm_mainFrame_inp_dspslRsltSrchCasNo',
            'mf_wfm_mainFrame_edt_dspslRsltSrchCaseNo',
            'mf_wfm_mainFrame_txt_dspslRsltSrchCaseNo',
            'mf_wfm_mainFrame_inp_dspslRsltSrchCaseNum',
        ];
        for (var i = 0; i < candidateIds.length; i++) {
            var el = document.getElementById(candidateIds[i]);
            if (el) { found = el; break; }
        }

        /* ② id/name/placeholder에 'case' 또는 '사건' 포함 */
        if (!found) {
            document.querySelectorAll('input[type="text"], input:not([type])').forEach(function (inp) {
                if (found) return;
                var ph = (inp.placeholder || '').toLowerCase();
                var id = (inp.id   || '').toLowerCase();
                var nm = (inp.name || '').toLowerCase();
                if (ph.includes('사건') || ph.includes('case') ||
                    id.includes('caseno') || id.includes('casenum') || id.includes('사건') ||
                    nm.includes('caseno') || nm.includes('사건')) {
                    found = inp;
                }
            });
        }

        /* ③ 라벨 텍스트 '사건번호' 인접 input */
        if (!found) {
            document.querySelectorAll('label, th, td, span, div').forEach(function (lbl) {
                if (found) return;
                if (lbl.textContent.trim() === '사건번호') {
                    if (lbl.htmlFor) { found = document.getElementById(lbl.htmlFor); return; }
                    var sib = lbl.nextElementSibling;
                    if (sib && sib.tagName === 'INPUT') { found = sib; return; }
                    var cell = lbl.closest('td, th');
                    if (cell && cell.nextElementSibling) {
                        found = cell.nextElementSibling.querySelector('input');
                    }
                }
            });
        }

        /* ④ 마지막 수단: 첫 번째 visible·enabled text input */
        if (!found) {
            document.querySelectorAll('input[type="text"], input:not([type])').forEach(function (inp) {
                if (found) return;
                if (inp.offsetParent !== null && !inp.disabled && !inp.readOnly) found = inp;
            });
        }

        if (found) {
            found.value = TARGET_CASE;
            trigger(found, ['input', 'change', 'blur']);
            found.focus();
            console.log('[경매자동검색] 사건번호 입력:', found.id || '(id 없음)');
            return true;
        }

        console.warn('[경매자동검색] 사건번호 input 못 찾음');
        return false;
    }

    /* ────────────────────────────────────────────────────────────────
       3. 검색 버튼 클릭
    ──────────────────────────────────────────────────────────────── */
    function clickSearch() {
        var btn = null;

        /* ① 패턴 기반 ID 후보 */
        var btnIds = [
            'mf_wfm_mainFrame_btn_dspslRsltSrch',
            'mf_wfm_mainFrame_btn_dspslRsltSrchGo',
            'mf_wfm_mainFrame_btn_dspslRsltInqr',
            'mf_wfm_mainFrame_btn_srch',
            'mf_wfm_mainFrame_btnSearch',
        ];
        for (var i = 0; i < btnIds.length; i++) {
            var el = document.getElementById(btnIds[i]);
            if (el) { btn = el; break; }
        }

        /* ② 텍스트가 "검색" or "조회"인 버튼 */
        if (!btn) {
            document.querySelectorAll('button, input[type="button"], input[type="submit"]').forEach(function (el) {
                if (btn) return;
                var txt = (el.textContent || el.value || '').trim();
                if (txt === '검색' || txt === '조회' || txt === '검  색') btn = el;
            });
        }

        /* ③ 이미지 버튼 alt/title */
        if (!btn) {
            var img = document.querySelector('img[alt="검색"], img[alt="조회"], img[title="검색"]');
            if (img) btn = img.closest('button, a') || img.parentElement;
        }

        /* ④ Enter 키 폴백 */
        if (!btn) {
            document.querySelectorAll('input[type="text"]').forEach(function (inp) {
                if (btn) return;
                if (inp.value === TARGET_CASE) {
                    inp.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true }));
                    btn = true;
                }
            });
        }

        if (btn && btn !== true) {
            btn.click();
            console.log('[경매자동검색] 검색 버튼 클릭:', btn.id || btn.textContent);
        }
    }

    /* ────────────────────────────────────────────────────────────────
       메인 루프 – WebSquare 초기화 대기 후 실행
    ──────────────────────────────────────────────────────────────── */
    var MAX_WAIT_MS  = 25000;
    var startAt      = Date.now();
    var caseInputted = false;

    function run() {
        if (Date.now() - startAt > MAX_WAIT_MS) {
            alert('[법원경매 자동검색] 시간 초과.\n수동으로 입력해주세요: ' + TARGET_CASE);
            return;
        }

        /* 법원 select가 렌더링될 때까지 대기 */
        var courtSel = document.getElementById('mf_wfm_mainFrame_sbx_dspslRsltSrchCortOfc')
                    || document.querySelector('select[title="법원 선택"]')
                    || document.querySelector('select.w2selectbox_select');

        if (!courtSel || courtSel.options.length < 2) {
            setTimeout(run, 400);
            return;
        }

        if (!caseInputted) {
            fillCourt();
            caseInputted = fillCaseNo();
        }

        if (caseInputted) {
            setTimeout(clickSearch, 700);
        } else {
            setTimeout(run, 500);
        }
    }

    window.addEventListener('load', function () { setTimeout(run, 1500); });

})();
