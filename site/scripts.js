/* CYCLOPEAN — page behaviour. Each feature is isolated in its own try block
   so one failure cannot take down the rest (a Sloppy lesson). Colours are
   never hardcoded here: styling happens through classes in styles.css. */
(function () {
  'use strict';

  function safe(name, fn) {
    try { fn(); } catch (e) { console.error('[cyclopean] ' + name + ' failed', e); }
  }

  function fmtNum(v, digits) {
    if (v === null || v === undefined || v === '') return '—';
    if (typeof v !== 'number') return String(v);
    var d = digits === undefined ? 2 : digits;
    var s = v.toFixed(d);
    if (s.indexOf('.') >= 0) s = s.replace(/0+$/, '').replace(/\.$/, '');
    return s;
  }

  /* ---------- sortable stats table (3-state: desc -> asc -> neutral) ---------- */
  safe('table-sort', function () {
    document.querySelectorAll('table.stats').forEach(function (table) {
      var tbody = table.tBodies[0];
      var original = Array.prototype.slice.call(tbody.rows);
      var state = { col: null, dir: 0 };
      table.querySelectorAll('thead tr.cols th[data-col]').forEach(function (th) {
        th.addEventListener('click', function () {
          var col = th.getAttribute('data-col');
          if (state.col !== col) { state.col = col; state.dir = 1; }
          else { state.dir = state.dir === 1 ? -1 : (state.dir === -1 ? 0 : 1); }
          table.querySelectorAll('thead th.sorted').forEach(function (x) { x.classList.remove('sorted'); x.removeAttribute('data-arrow'); });
          var rows;
          if (state.dir === 0) {
            rows = original.slice();
          } else {
            th.classList.add('sorted');
            th.setAttribute('data-arrow', state.dir === 1 ? '▼' : '▲');
            rows = original.slice().sort(function (a, b) {
              var ca = a.querySelector('td[data-col="' + col + '"]');
              var cb = b.querySelector('td[data-col="' + col + '"]');
              var va = ca ? ca.getAttribute('data-sort') : '';
              var vb = cb ? cb.getAttribute('data-sort') : '';
              var na = parseFloat(va), nb = parseFloat(vb);
              var ea = isNaN(na), eb = isNaN(nb);
              if (ea && eb) return String(va).localeCompare(String(vb));
              if (ea) return 1;
              if (eb) return -1;
              return state.dir === 1 ? nb - na : na - nb;
            });
          }
          rows.forEach(function (r) { tbody.appendChild(r); });
        });
      });
      // row marking
      tbody.addEventListener('click', function (ev) {
        if (ev.target.closest('a')) return;
        var tr = ev.target.closest('tr');
        if (tr) tr.classList.toggle('marked');
      });
      // sticky second header row sits below the category row
      var cats = table.querySelector('thead tr.cats');
      if (cats) table.style.setProperty('--cat-row-h', cats.getBoundingClientRect().height + 'px');
    });
  });

  /* ---------- history tooltip for cells with data-hist ---------- */
  safe('hist-tip', function () {
    var tip = document.createElement('div');
    tip.className = 'hist-tip px-frame bright';
    document.body.appendChild(tip);
    function show(td) {
      var hist;
      try { hist = JSON.parse(td.getAttribute('data-hist')); } catch (e) { return; }
      if (!hist || !hist.length) return;
      var pol = parseInt(td.getAttribute('data-pol') || '1', 10);
      var digits = parseInt(td.getAttribute('data-digits') || '2', 10);
      var head = td.getAttribute('data-title') || '';
      var esc = document.createElement('span');
      esc.textContent = head;                                  // names come from game text: never as HTML
      var html = '<div class="t-head">' + esc.innerHTML + '</div>';
      var first = hist[0][2], last = hist[hist.length - 1][3];
      if (hist.length > 1 && typeof first === 'number' && typeof last === 'number' && first !== 0) {
        var p = (last - first) / Math.abs(first) * 100;
        html += '<div class="t-overall">Overall: ' + fmtNum(first, digits) + ' → ' + fmtNum(last, digits) +
          ' <span class="' + dirClass(first, last, pol) + '">(' + (p > 0 ? '+' : '') + p.toFixed(1) + '%)</span></div>';
      }
      html += '<ol>';
      for (var i = hist.length - 1; i >= 0; i--) {
        var h = hist[i];
        var cls = dirClass(h[2], h[3], pol);
        var pct = '';
        if (typeof h[2] === 'number' && typeof h[3] === 'number' && h[2] !== 0) {
          var q = (h[3] - h[2]) / Math.abs(h[2]) * 100;
          pct = (q > 0 ? '+' : '') + q.toFixed(1) + '%';
        }
        html += '<li><span class="d">' + h[1] + '</span><span>' + fmtNum(h[2], digits) +
          '<span class="arrow">→</span><span class="' + cls + '">' + fmtNum(h[3], digits) + '</span></span>' +
          '<span class="' + cls + ' pct">' + pct + '</span></li>';
      }
      html += '</ol>';
      tip.innerHTML = html;
      tip.classList.add('on');
      var r = td.getBoundingClientRect();
      var tw = tip.offsetWidth, th = tip.offsetHeight;
      var x = Math.min(Math.max(8, r.left + r.width / 2 - tw / 2), window.innerWidth - tw - 8);
      var y = r.bottom + 8;
      if (y + th > window.innerHeight - 8) y = r.top - th - 8;
      tip.style.left = x + 'px';
      tip.style.top = Math.max(8, y) + 'px';
    }
    function dirClass(a, b, pol) {
      if (typeof a !== 'number' || typeof b !== 'number' || a === b || pol === 0) return 'dir-changed';
      var better = pol > 0 ? Math.abs(b) > Math.abs(a) : Math.abs(b) < Math.abs(a);
      return better ? 'dir-buff' : 'dir-nerf';
    }
    document.addEventListener('mouseover', function (ev) {
      var td = ev.target.closest('[data-hist]');
      if (td) show(td);
    });
    document.addEventListener('mouseout', function (ev) {
      var td = ev.target.closest('[data-hist]');
      if (td && !td.contains(ev.relatedTarget)) tip.classList.remove('on');
    });
    window.addEventListener('scroll', function () { tip.classList.remove('on'); }, true);
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
      var x = Math.min(Math.max(edge, r.left + r.width / 2 - tw / 2), window.innerWidth - tw - edge);
      var y = r.top - th - gap;
      if (y < edge) y = r.bottom + gap;                       // no room above: below the marker
      if (y + th > window.innerHeight - edge) y = Math.max(edge, window.innerHeight - th - edge);
      tip.style.left = Math.round(x) + 'px';
      tip.style.top = Math.round(y) + 'px';
    }
    function show(el) {
      var text = el.getAttribute('data-tooltip');
      if (!text) return;
      current = el;
      tip.textContent = text;
      tip.classList.add('on');
      place(el);
    }
    function hide() { current = null; tip.classList.remove('on'); }
    document.addEventListener('mouseover', function (ev) {
      var el = ev.target.closest && ev.target.closest('[data-tooltip]');
      if (el && el !== current) show(el);
    });
    document.addEventListener('mouseout', function (ev) {
      var el = ev.target.closest && ev.target.closest('[data-tooltip]');
      if (el && !el.contains(ev.relatedTarget)) hide();
    });
    document.addEventListener('focusin', function (ev) {
      var el = ev.target.closest && ev.target.closest('[data-tooltip]');
      if (el) show(el);
    });
    document.addEventListener('focusout', hide);
    // touch: a tap fires mouseover and then click — the tap shows the text (never hides
    // it again), a tap anywhere else hides it
    document.addEventListener('click', function (ev) {
      var el = ev.target.closest && ev.target.closest('[data-tooltip]');
      if (el) { if (el !== current) show(el); } else if (current) hide();
    });
    window.addEventListener('scroll', hide, true);
    window.addEventListener('resize', hide);
  });

  /* ---------- toolbar toggles: [data-toggle-class] on a button toggles a class on its target ---------- */
  safe('toggles', function () {
    document.querySelectorAll('[data-toggle-class]').forEach(function (btn) {
      var target = document.querySelector(btn.getAttribute('data-target') || 'body');
      var cls = btn.getAttribute('data-toggle-class');
      btn.addEventListener('click', function () {
        var on = !target.classList.contains(cls);
        target.classList.toggle(cls, on);
        btn.classList.toggle('on', on);
      });
    });
  });

  /* ---------- wide tables: hide the right-edge fade once scrolled to the end ---------- */
  safe('table-fade', function () {
    document.querySelectorAll('.table-fade > .table-scroll').forEach(function (sc) {
      function check() {
        sc.parentNode.classList.toggle('at-end', sc.scrollLeft + sc.clientWidth >= sc.scrollWidth - 2);
      }
      sc.addEventListener('scroll', check, { passive: true });
      // the Details button widens the table: watch sizes, not only window resizes
      if (window.ResizeObserver) {
        var ro = new ResizeObserver(check);
        ro.observe(sc);
        ro.observe(sc.firstElementChild);
      } else {
        window.addEventListener('resize', check);
      }
      check();
    });
  });

  /* ---------- a clamped REWORK value line opens on click ---------- */
  safe('rework-lines', function () {
    document.addEventListener('click', function (ev) {
      var v = ev.target.closest && ev.target.closest('.erow.rw .vals.wrap');
      if (v) v.classList.toggle('open');
    });
  });

  /* ---------- heatmap toggle for the stats table ---------- */
  safe('heatmap', function () {
    var btn = document.querySelector('[data-heatmap]');
    if (!btn) return;
    var table = document.querySelector('table.stats');
    btn.addEventListener('click', function () {
      var on = !btn.classList.contains('on');
      btn.classList.toggle('on', on);
      table.querySelectorAll('td.hm-hi, td.hm-lo').forEach(function (td) { td.classList.remove('hm-hi', 'hm-lo'); });
      if (!on) return;
      var cols = {};
      table.querySelectorAll('tbody td[data-col]').forEach(function (td) {
        var v = parseFloat(td.getAttribute('data-sort'));
        if (isNaN(v)) return;
        (cols[td.getAttribute('data-col')] = cols[td.getAttribute('data-col')] || []).push([v, td]);
      });
      Object.keys(cols).forEach(function (k) {
        var list = cols[k];
        var uniq = Array.from(new Set(list.map(function (x) { return x[0]; }))).sort(function (a, b) { return a - b; });
        if (uniq.length < 3) return;
        list.forEach(function (x) {
          var td = x[1];
          var pol = parseInt(td.getAttribute('data-pol') || '1', 10);
          if (pol === 0) return;
          var rank = uniq.indexOf(x[0]) / (uniq.length - 1);
          if (pol < 0) rank = 1 - rank;
          if (rank >= 0.6) td.classList.add('hm-hi');
          else if (rank <= 0.4) td.classList.add('hm-lo');
        });
      });
    });
  });

  /* ---------- tabs: <button data-tab="id"> shows #id.tab-panel, hides its siblings ---------- */
  safe('tabs', function () {
    var buttons = document.querySelectorAll('[data-tab]');
    function open(id) {
      buttons.forEach(function (b) { b.classList.toggle('on', b.getAttribute('data-tab') === id); });
      document.querySelectorAll('.tab-panel').forEach(function (p) { p.classList.toggle('on', p.id === id); });
    }
    buttons.forEach(function (b) {
      b.addEventListener('click', function () {
        open(b.getAttribute('data-tab'));
        try { history.replaceState(null, '', '#' + b.getAttribute('data-tab')); } catch (e) { /* file:// */ }
      });
    });
    var start = location.hash.replace('#', '');
    var startEl = start && document.getElementById(start);
    if (startEl && startEl.classList.contains('tab-panel')) open(start);
    else if (startEl && startEl.closest('.tab-panel')) {    // arrived from another page at a card
      open(startEl.closest('.tab-panel').id);
      startEl.scrollIntoView({ block: 'start' });
    }
    // a link to a card inside another tab (the hero strip -> "#c-hero_atlas"): open that tab, then scroll
    document.addEventListener('click', function (ev) {
      var a = ev.target.closest && ev.target.closest('a[href^="#"]');
      if (!a) return;
      var target = document.getElementById(a.getAttribute('href').slice(1));
      var panel = target && target.closest('.tab-panel');
      if (!panel || panel.classList.contains('on')) return;
      ev.preventDefault();
      open(panel.id);
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  /* ---------- search: filters elements with data-search ---------- */
  safe('search', function () {
    document.querySelectorAll('input[data-search-target]').forEach(function (input) {
      var sel = input.getAttribute('data-search-target');
      input.addEventListener('input', function () {
        var q = input.value.trim().toLowerCase();
        document.querySelectorAll(sel).forEach(function (el) {
          var hay = (el.getAttribute('data-search') || el.textContent).toLowerCase();
          el.classList.toggle('hidden-el', q !== '' && hay.indexOf(q) < 0);
        });
      });
    });
  });
})();
