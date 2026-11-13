  /* ---------- history tooltip for cells with data-hist ---------- */
  /* drawn once per cell (moving between a cell's children redrew it: 2 forced layouts a move), also on
     keyboard focus: the values take the tab order, the tip describes the focused one */
  safe('hist-tip', function () {
    if (!document.querySelector('[data-hist]')) return;
    var tip = document.createElement('div'), current = null;
    tip.className = 'hist-tip px-frame bright';
    tip.id = 'hist-tip';
    tip.setAttribute('role', 'tooltip');
    document.body.appendChild(tip);
    /* a table's values are ONE tab stop (a roving tabindex): Tab enters the table at the value visited last
       (else its first shown one), the arrow keys move between its values — Hero Stats had ~1,100 tab stops,
       Item Stats ~1,000 (review 2026-10-05). A value outside a table is a stop of its own. Item Stats'
       stat-column cells, built later, join their table's moves (item-filter). */
    var grids = [];
    document.querySelectorAll('[data-hist]').forEach(function (el) {
      var t = el.closest('table');
      if (!t) { el.tabIndex = 0; return; }
      if (t.__hist) return;
      t.__hist = el;
      el.tabIndex = 0;
      grids.push(t);
    });
    function shown(el) { return el.getClientRects().length > 0; }
    function enter(t, el) {
      if (t.__hist && t.__hist !== el) t.__hist.tabIndex = -1;
      t.__hist = el;
      el.tabIndex = 0;
    }
    // the stop must be a value one can see: a filter or a folded group may have hidden it since
    function entryOf(t) {
      if (t.__hist && t.contains(t.__hist) && shown(t.__hist)) return t.__hist;
      var all = t.querySelectorAll('[data-hist]');
      for (var i = 0; i < all.length; i++) if (shown(all[i])) return all[i];
      return null;
    }
    // ←/→ the previous / next value in reading order (rows move in the DOM when sorted), ↑/↓ the same
    // column's value in the nearest shown row above / below
    function moveFrom(el, key) {
      var t = el.closest('table');
      if (!t) return null;
      if (key === 'ArrowLeft' || key === 'ArrowRight') {
        var all = Array.prototype.filter.call(t.querySelectorAll('[data-hist]'), shown);
        var i = all.indexOf(el);
        return all[i + (key === 'ArrowRight' ? 1 : -1)] || null;
      }
      var col = el.getAttribute('data-col'), tr = el.closest('tr');
      if (!col || !tr) return null;
      var sel = '[data-hist][data-col="' + col + '"]';
      for (var r = tr; (r = key === 'ArrowDown' ? r.nextElementSibling : r.previousElementSibling);) {
        var c = r.querySelector(sel);
        if (c && shown(c)) return c;
      }
      return null;
    }
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Tab') {
        grids.forEach(function (t) { var e = entryOf(t); if (e && e !== t.__hist) enter(t, e); });
        return;
      }
      if (ev.key !== 'ArrowLeft' && ev.key !== 'ArrowRight' && ev.key !== 'ArrowUp' && ev.key !== 'ArrowDown') return;
      var el = document.activeElement;
      if (!el || !el.hasAttribute || !el.hasAttribute('data-hist')) return;
      var next = moveFrom(el, ev.key);
      if (!next) return;
      ev.preventDefault();
      enter(next.closest('table'), next);
      next.focus();
    });
    function show(td) {
      if (td === current) return;
      var hist;
      try { hist = JSON.parse(td.getAttribute('data-hist')); } catch (e) { return; }
      if (!hist || !hist.length) return;
      current = td;
      var pol = parseInt(td.getAttribute('data-pol') || '1', 10);
      var digits = parseInt(td.getAttribute('data-digits') || '2', 10);
      // a unit after every number (Game rules: "55m", "38s" — builders/game_rules.py), none by default
      var unit = td.getAttribute('data-unit') || '';
      var fmtU = function (v, d) { var s = fmtNum(v, d); return unit && typeof v === 'number' && v !== -1 ? s + unit : s; };
      var head = td.getAttribute('data-title') || '';
      var esc = document.createElement('span');
      esc.textContent = head;                                  // names come from game text: never as HTML
      var html = '<div class="t-head">' + esc.innerHTML + '</div>';
      // two negatives (a penalty, a slow) compare by size, as the item page does: −0.5 → −1 is +100%, not −100%
      // (review 2026-10-05) — the steps and the "Overall" line alike
      var pctOf = function (a, b) {
        return a < 0 && b < 0 ? (Math.abs(b) - Math.abs(a)) / Math.abs(a) * 100 : (b - a) / Math.abs(a) * 100;
      };
      var first = hist[0][2], last = hist[hist.length - 1][3];
      if (hist.length > 1 && typeof first === 'number' && typeof last === 'number' && first !== 0) {
        var p = pctOf(first, last);
        var odir = td.getAttribute('data-odir');
        html += '<div class="t-overall">Overall: ' + fmtU(first, digits) + ' → ' + fmtU(last, digits) +
          ' <span class="' + (odir ? 'dir-' + odir : dirClass(first, last, pol)) + '">(' + (p > 0 ? '+' : '') +
          p.toFixed(1) + '%)</span></div>';
      }
      html += '<ol>';
      for (var i = hist.length - 1; i >= 0; i--) {
        var h = hist[i];
        // a step that carries its direction (Item Stats: the item page's own, drawbacks and signed
        // penalties included) wins over the column's polarity
        var cls = h[4] ? 'dir-' + h[4] : dirClass(h[2], h[3], pol);
        // the pill only when there is a real change to measure: a first value or a 0.0% step gets none
        var pill = '';
        if (typeof h[2] === 'number' && typeof h[3] === 'number' && h[2] !== 0) {
          var q = pctOf(h[2], h[3]);
          if (Math.abs(q) >= 0.05) {
            pill = '<span class="' + cls + ' pct" data-g="' + pctGrade(q) + '">' + (q > 0 ? '+' : '') + q.toFixed(1) + '%</span>';
          }
        }
        // fixed columns: date | was | → | now | % — a first value sits under "now" like every other row, "added"
        // where the value was; a value that went says "removed" (a bare "—" read as no value)
        var firstStep = (h[2] === null || h[2] === undefined);
        var gone = (h[3] === null || h[3] === undefined);
        // a step the patch notes left out (a sixth element 1: builders/stat_eyes.py) carries the site's eye
        var eye = h[5] ? '<span class="mark hidden" role="img" aria-label="not in patch notes"></span>' : '';
        esc.textContent = h[1];
        html += '<li><span class="d">' + esc.innerHTML + '</span>' +
          '<span class="o">' + (firstStep ? '<i>added</i>' : fmtU(h[2], digits)) + '</span>' +
          '<span class="arrow">' + (firstStep ? '' : '→') + '</span>' +
          '<span class="n ' + (firstStep ? 'dir-changed' : cls) + '">' + (gone ? '<i>removed</i>' : fmtU(h[3], digits)) +
          '</span><span class="p">' + pill + eye + '</span></li>';
      }
      html += '</ol>';
      tip.innerHTML = html;
      tip.classList.add('on');
      td.setAttribute('aria-describedby', tip.id);
      place(td);
    }
    function place(td) {
      var r = td.getBoundingClientRect();
      var tw = tip.offsetWidth, th = tip.offsetHeight;
      var x = Math.min(Math.max(8, r.left + r.width / 2 - tw / 2), document.documentElement.clientWidth - tw - 8);
      var y = r.bottom + 8;
      if (y + th > window.innerHeight - 8) y = r.top - th - 8;
      tip.style.left = x + 'px';
      tip.style.top = Math.max(8, y) + 'px';
    }
    function hide() {
      if (current) current.removeAttribute('aria-describedby');
      current = null;
      tip.classList.remove('on');
    }
    function pctGrade(q) {
      var a = Math.abs(q);
      return a < 5 ? 1 : a < 15 ? 2 : a < 30 ? 3 : a < 60 ? 4 : 5;     // same steps as render.pct_grade
    }
    // with the sign, as the entity pages' tags (pipeline/semantics.direction): a hero's bullet resist
    // −20% → −15% is a buff and −6% → −8% a nerf; by size they read the other way (frontend audit 10-04)
    function dirClass(a, b, pol) {
      if (typeof a !== 'number' || typeof b !== 'number' || a === b || pol === 0) return 'dir-changed';
      return (pol > 0 ? b > a : b < a) ? 'dir-buff' : 'dir-nerf';
    }
    document.addEventListener('mouseover', function (ev) {
      var td = ev.target.closest && ev.target.closest('[data-hist]');
      if (td) show(td);
    });
    document.addEventListener('mouseout', function (ev) {
      var td = ev.target.closest && ev.target.closest('[data-hist]');
      if (td && !td.contains(ev.relatedTarget)) hide();
    });
    document.addEventListener('focusin', function (ev) {
      var td = ev.target.closest && ev.target.closest('[data-hist]');
      if (td) show(td); else if (current) hide();
    });
    document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape' && current) hide(); });
    // a scroll hides it — except the one the keyboard focused (focusing scrolls the cell into view)
    window.addEventListener('scroll', function () {
      if (current && current === document.activeElement) place(current); else if (current) hide();
    }, true);
  });

  /* ---------- short tooltips for [data-tooltip]: one element, kept inside the viewport ---------- */
  safe('tooltip', function () {
    var tip = document.createElement('div');
    tip.className = 'tip';
    tip.setAttribute('role', 'tooltip');
    document.body.appendChild(tip);
    var current = null;
    function place(el) {
      var r = el.getBoundingClientRect();
      var tw = tip.offsetWidth, th = tip.offsetHeight, gap = 8, edge = 8;
      var x = Math.min(Math.max(edge, r.left + r.width / 2 - tw / 2), document.documentElement.clientWidth - tw - edge);   // the page width without its scrollbar
      var y = r.top - th - gap;
      if (y < edge) y = r.bottom + gap;                       // no room above: below the marker
      if (y + th > window.innerHeight - edge) y = Math.max(edge, window.innerHeight - th - edge);
      tip.style.left = Math.round(x) + 'px';
      tip.style.top = Math.round(y) + 'px';
    }
    function show(el) {
      // an eye that links its proof writes its words once, as its aria-label (common.mark: data-tooltip is empty)
      var text = el.getAttribute('data-tooltip') || el.getAttribute('aria-label');
      if (!text) return;
      // the words were written for a mouse: on a touch screen the first tap shows them, the second opens the build
      if (noHover) text = text.replace('click to open', 'tap again to open');
      current = el;
      tip.textContent = text;
      tip.classList.add('on');
      place(el);
      var r = el.getBoundingClientRect();
      shownAt = [r.left, r.top];
    }
    // a scroll hides the words only when it moved their marker (dyn-tip's rule: a late scroll event of the tap that
    // showed them is not a leave)
    var shownAt = null;
    function scrolled() {
      if (!current) return;
      var r = current.getBoundingClientRect();
      if (shownAt && Math.abs(r.left - shownAt[0]) < 4 && Math.abs(r.top - shownAt[1]) < 4) return;
      hide();
    }
    // (a hidden tip disarms an eye link: its next tap shows the words again before it follows)
    function hide() { current = null; upBefore = null; tip.classList.remove('on'); }
    document.addEventListener('mouseover', function (ev) {
      var el = ev.target.closest && ev.target.closest('[data-tooltip]');
      if (el && el !== current) show(el);
    });
    // a touch screen has no hover: its taps fire compatibility mouseout / focusout events, which hid the words and
    // disarmed an eye link between its two taps (CI's Linux Chromium, 2026-10-06) — there a tap elsewhere hides them
    document.addEventListener('mouseout', function (ev) {
      if (noHover) return;
      var el = ev.target.closest && ev.target.closest('[data-tooltip]');
      if (el && !el.contains(ev.relatedTarget)) hide();
    });
    document.addEventListener('focusin', function (ev) {
      var el = ev.target.closest && ev.target.closest('[data-tooltip]');
      if (el) show(el);
    });
    document.addEventListener('focusout', function () { if (!noHover) hide(); });
    // touch: a tap fires mouseover and then click — the tap shows the text (never hides
    // it again), a tap anywhere else hides it. An eye that opens its proof (a.mark: the build it came
    // in, builders/evidence.py) shows its words on the first tap and follows the link on the second
    var noHover = window.matchMedia && window.matchMedia('(hover: none)').matches;
    // whether the words were up is read when the touch begins, before the tap's own mouseover shows them: iOS drops
    // the click of a tap whose mouseover showed something, so a flag set at click time took a third tap there (the
    // hover cards' rule, dyn-tip; review 2026-10-17)
    var upBefore = null;
    function touchStart(ev) {
      var el = ev.target.closest && ev.target.closest('[data-tooltip]');
      upBefore = el && el === current ? el : null;
    }
    if (noHover) {
      document.addEventListener('pointerdown', touchStart, true);
      document.addEventListener('touchstart', touchStart, { capture: true, passive: true });
    }
    // (a band's "N not in notes" chip is such a link too: history_view._eye_chip)
    document.addEventListener('click', function (ev) {
      var el = ev.target.closest && ev.target.closest('[data-tooltip]');
      if (el && noHover && el.matches('a.mark[href], a.eye-chip[href]') && upBefore !== el) {
        ev.preventDefault();
        show(el);
        return;
      }
      if (el) { if (el !== current) show(el); } else if (current) hide();
    });
    window.addEventListener('scroll', scrolled, true);
    window.addEventListener('resize', hide);
  });

  /* ---------- toolbar toggles: [data-toggle-class] on a button toggles a class on its target ---------- */
  safe('toggles', function () {
    document.querySelectorAll('[data-toggle-class]').forEach(function (btn) {
      var target = document.querySelector(btn.getAttribute('data-target') || 'body');
      var cls = btn.getAttribute('data-toggle-class');
      if (!target) return;
      if (btn.type === 'checkbox') {
        // a switch: the class follows the box — also when the browser restores a ticked box on "back"
        // (Firefox on a reload too), which left the box on and its class off
        var sync = function () { target.classList.toggle(cls, btn.checked); };
        btn.addEventListener('change', sync);
        window.addEventListener('pageshow', sync);
        sync();
        return;
      }
      btn.addEventListener('click', function () {
        var on = !target.classList.contains(cls);
        target.classList.toggle(cls, on);
        btn.classList.toggle('on', on);
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    });
  });

