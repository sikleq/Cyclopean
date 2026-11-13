/* CYCLOPEAN — page behaviour. Each feature is isolated in its own try block
   so one failure cannot take down the rest (a Sloppy lesson). Colours are
   never hardcoded here: styling happens through classes in styles.css. */
(function () {
  'use strict';

  function safe(name, fn) {
    try { fn(); } catch (e) { console.error('[cyclopean] ' + name + ' failed', e); }
  }

  /* a unit family's member page points to the family's page, keeping the #p-<patch> anchor */
  var redirect = document.body && document.body.getAttribute('data-redirect');
  if (redirect) { location.replace(redirect + location.hash); return; }

  /* a build page's picker (builds_pages.build_page): the list of every build comes from builds/list.json on first
     use; choosing one opens its page */
  safe('build-pick', function () {
    var sel = document.querySelector('select.build-pick[data-list]');
    if (!sel) return;
    var loaded = false;
    function load() {
      if (loaded) return;
      loaded = true;
      fetch(sel.getAttribute('data-list')).then(function (r) { return r.json(); }).then(function (list) {
        var cur = location.pathname.split('/').pop().replace(/\.html$/, '');
        var frag = document.createDocumentFragment();
        list.forEach(function (row) {
          var o = document.createElement('option');
          o.value = row[0] + '.html';
          o.textContent = row[1];
          if (row[0] === cur) o.selected = true;
          frag.appendChild(o);
        });
        sel.textContent = '';
        sel.appendChild(frag);
      }).catch(function (e) { loaded = false; console.error('[cyclopean] build list failed', e); });
    }
    sel.addEventListener('pointerdown', load);
    sel.addEventListener('focus', load);
    sel.addEventListener('change', function () { if (sel.value.slice(-5) === '.html') location.href = sel.value; });
  });

  /* a patch strip shows the newest tiles that fit whole (styles.css .patch-strip: 38px tiles), the older ones
     `ps-out`: a scrolled strip cut its oldest tile in sight at the left edge (owner 2026-10-21); the history below
     has every patch. Again when the strip's column changes width */
  safe('strip-end', function () {
    function fit(s) {
      var tiles = s.children, cs, gap, step, n, i;
      for (i = 0; i < tiles.length; i++) tiles[i].classList.remove('ps-out');
      if (!tiles.length) return;
      cs = getComputedStyle(s);
      gap = parseFloat(cs.columnGap) || 0;
      step = tiles[0].getBoundingClientRect().width + gap;
      n = Math.max(1, Math.floor((s.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) + gap) / step));
      for (i = 0; i < tiles.length - n; i++) tiles[i].classList.add('ps-out');
    }
    document.querySelectorAll('.patch-strip').forEach(function (s) {
      fit(s);
      if (window.ResizeObserver) {
        var w = s.parentNode.clientWidth;
        new ResizeObserver(function () {
          if (s.parentNode.clientWidth !== w) { w = s.parentNode.clientWidth; fit(s); }
        }).observe(s.parentNode);
      }
    });
  });

  /* the fonts' stylesheet arrives as media="print" so it never holds the first paint (builders/common.page):
     switched on once it has loaded */
  safe('fonts', function () {
    document.querySelectorAll('link[data-fonts]').forEach(function (l) {
      function on() { l.media = 'all'; }
      if (l.sheet) on(); else l.addEventListener('load', on);
    });
  });

  /* an element that acts on a click (a sortable header, a foldable group) answers Enter and Space too */
  function pressable(el) {
    if (el.__press) return;
    el.__press = true;
    el.addEventListener('keydown', function (ev) {
      if ((ev.key === 'Enter' || ev.key === ' ') && ev.target === el) { ev.preventDefault(); el.click(); }
    });
  }

  function fmtNum(v, digits) {
    if (v === null || v === undefined || v === '') return '—';
    if (typeof v !== 'number') return String(v);
    var d = digits === undefined ? 2 : digits;
    var s = v.toFixed(d);
    if (s.indexOf('.') >= 0) s = s.replace(/0+$/, '').replace(/\.$/, '');
    return s;
  }

