/**
 * Survey searchable dropdown for choice questions with > 3 options.
 *
 * Key design decisions:
 *  - List opens on FOCUS and on INPUT/KEYUP (belt-and-suspenders for input event).
 *  - Options use MOUSEDOWN (fires before the input's blur) so selection wins.
 *  - cancelClose() called in focus AND input handlers to stop any pending
 *    blur-triggered close from wiping the list mid-type.
 *  - Filter uses data-label with textContent fallback so it works even if the
 *    attribute is absent or empty.
 */
(function () {
    'use strict';

    // ── Utility ────────────────────────────────────────────────────────────────

    function esc(str) {
        var d = document.createElement('div');
        d.appendChild(document.createTextNode(str || ''));
        return d.innerHTML;
    }

    function optLabel(opt) {
        // data-label is the canonical source; fall back to last <span> text content
        if (opt.dataset.label) return opt.dataset.label;
        var spans = opt.querySelectorAll('span');
        if (spans.length) return (spans[spans.length - 1].textContent || '').trim();
        return (opt.textContent || '').trim();
    }

    // ── Core initialiser (one per .o_survey_dd_search input) ──────────────────

    function initDropdown(searchInput) {
        var dd       = searchInput.closest('.o_survey_dd');
        var wrapper  = searchInput.closest('.o_survey_answer_wrapper');
        var list     = dd.querySelector('.o_survey_dd_list');
        var empty    = dd.querySelector('.o_survey_dd_empty');
        var chipsRow = dd.querySelector('.o_survey_dd_chips');
        var isMulti  = searchInput.dataset.isMulti === '1';

        var closeTimer = null;

        // ── Open / Close ───────────────────────────────────────────────────────

        function openList() {
            list.style.display = 'block';
        }

        function scheduleClose() {
            closeTimer = setTimeout(function () {
                list.style.display = 'none';
                searchInput.value  = '';
                showAll();
            }, 200);
        }

        function cancelClose() {
            if (closeTimer) { clearTimeout(closeTimer); closeTimer = null; }
        }

        // ── Filter ─────────────────────────────────────────────────────────────

        function getOptions() {
            return list.querySelectorAll('.o_survey_dd_opt');
        }

        function showAll() {
            // removeProperty restores d-flex; never use style.display='' here
            // because Bootstrap's d-flex !important would still win over 'none'.
            getOptions().forEach(function (o) { o.style.removeProperty('display'); });
            if (empty) empty.style.display = 'none';
        }

        function filterOptions(q) {
            var lq  = (q || '').toLowerCase();
            var any = false;
            getOptions().forEach(function (o) {
                var label = optLabel(o).toLowerCase();
                var match = !lq || label.includes(lq);
                if (match) {
                    o.style.removeProperty('display'); // let d-flex take effect
                    any = true;
                } else {
                    // must use !important — Bootstrap's d-flex !important wins over
                    // a plain inline display:none
                    o.style.setProperty('display', 'none', 'important');
                }
            });
            if (empty) empty.style.display = any ? 'none' : '';
        }

        // ── Hidden input sync ──────────────────────────────────────────────────

        function setHidden(val, checked) {
            if (!wrapper) return;
            var inp = wrapper.querySelector(
                'input.o_survey_form_choice_item[value="' + val + '"]'
            );
            if (!inp) return;
            inp.checked = checked;
            inp.classList.toggle('o_survey_form_choice_item_selected', checked);
            inp.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function clearAllHidden() {
            if (!wrapper) return;
            wrapper.querySelectorAll('input.o_survey_form_choice_item').forEach(function (inp) {
                inp.checked = false;
                inp.classList.remove('o_survey_form_choice_item_selected');
            });
        }

        // ── "Other" textarea ───────────────────────────────────────────────────

        function setOther(show) {
            if (!wrapper) return;
            var box = wrapper.querySelector('.o_survey_comment_container');
            var ta  = box && box.querySelector('textarea');
            if (!box || !ta) return;
            if (show) {
                box.classList.remove('d-none');
                ta.removeAttribute('disabled');
            } else {
                box.classList.add('d-none');
                ta.setAttribute('disabled', 'disabled');
            }
        }

        // ── Icon helper ────────────────────────────────────────────────────────

        function updateIcon(optEl, active) {
            var icon = optEl.querySelector('.o_survey_dd_icon');
            if (!icon) return;
            icon.innerHTML = isMulti
                ? (active ? '&#9745;' : '&#9744;')
                : (active ? '&#9679;' : '&#9675;');
        }

        // ── Single-choice select ───────────────────────────────────────────────

        function selectSingle(val, label) {
            clearAllHidden();
            getOptions().forEach(function (o) {
                var active = String(o.dataset.value) === String(val);
                o.classList.toggle('o_survey_dd_opt_active', active);
                updateIcon(o, active);
            });
            setHidden(val, true);
            if (String(val) === '-1') {
                searchInput.value = '';
                setOther(true);
            } else {
                searchInput.value = label;
                setOther(false);
            }
            list.style.display = 'none';
            showAll();
        }

        // ── Multiple-choice toggle ─────────────────────────────────────────────

        function toggleMulti(val, label, optEl) {
            var wasActive = optEl.classList.contains('o_survey_dd_opt_active');
            if (wasActive) {
                optEl.classList.remove('o_survey_dd_opt_active');
                updateIcon(optEl, false);
                setHidden(val, false);
                removeChip(val);
                if (String(val) === '-1') setOther(false);
            } else {
                optEl.classList.add('o_survey_dd_opt_active');
                updateIcon(optEl, true);
                setHidden(val, true);
                addChip(val, label);
                if (String(val) === '-1') setOther(true);
            }
            searchInput.value = '';
            showAll();
            searchInput.focus();
        }

        // ── Chips ──────────────────────────────────────────────────────────────

        function addChip(val, label) {
            if (!chipsRow) return;
            if (chipsRow.querySelector('[data-chip="' + val + '"]')) return;
            var chip = document.createElement('span');
            chip.className = 'badge rounded-pill bg-primary text-white d-inline-flex align-items-center gap-1 px-2 py-1';
            chip.dataset.chip = val;
            chip.innerHTML =
                '<span>' + esc(label) + '</span>' +
                '<button type="button" class="btn-close btn-close-white ms-1" style="font-size:10px;" aria-label="Remove"></button>';
            chipsRow.appendChild(chip);
            chip.querySelector('button').addEventListener('mousedown', function (e) {
                e.preventDefault();
                var optEl = list.querySelector('.o_survey_dd_opt[data-value="' + val + '"]');
                if (optEl) toggleMulti(val, optLabel(optEl), optEl);
            });
        }

        function removeChip(val) {
            var chip = chipsRow && chipsRow.querySelector('[data-chip="' + val + '"]');
            if (chip) chip.remove();
        }

        // ── Event wiring ───────────────────────────────────────────────────────

        searchInput.addEventListener('focus', function () {
            cancelClose();   // cancel any pending blur-timer
            openList();
        });

        function handleInput() {
            cancelClose();   // stop a stale blur-timer from closing the list
            openList();
            filterOptions(searchInput.value);
        }

        searchInput.addEventListener('input', handleInput);
        searchInput.addEventListener('keyup', handleInput);  // belt-and-suspenders

        searchInput.addEventListener('blur', scheduleClose);

        // Wire up option clicks with mousedown (fires before input blur)
        list.addEventListener('mousedown', function (e) {
            e.preventDefault(); // prevents input from losing focus
            cancelClose();
            var opt = e.target.closest('.o_survey_dd_opt');
            if (!opt) return;
            var val   = opt.dataset.value;
            var label = optLabel(opt);
            if (isMulti) {
                toggleMulti(val, label, opt);
            } else {
                selectSingle(val, label);
            }
        });

        // ── Pre-selected state (server-side answer) ────────────────────────────

        if (isMulti) {
            list.querySelectorAll('.o_survey_dd_opt_active').forEach(function (opt) {
                addChip(opt.dataset.value, optLabel(opt));
            });
        } else {
            var active = list.querySelector('.o_survey_dd_opt_active');
            if (active) searchInput.value = optLabel(active);
        }
    }

    // ── Entry point ────────────────────────────────────────────────────────────

    function init() {
        document.querySelectorAll('.o_survey_dd_search:not([data-dd-init])').forEach(function (el) {
            el.dataset.ddInit = '1';
            initDropdown(el);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    window.addEventListener('load', init);

})();
