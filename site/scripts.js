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
        // the pill only when there is a real change to measure: a first value or a 0.0% step gets none
        var pill = '';
        if (typeof h[2] === 'number' && typeof h[3] === 'number' && h[2] !== 0) {
          var q = (h[3] - h[2]) / Math.abs(h[2]) * 100;
          if (Math.abs(q) >= 0.05) {
            pill = '<span class="' + cls + ' pct" data-g="' + pctGrade(q) + '">' + (q > 0 ? '+' : '') + q.toFixed(1) + '%</span>';
          }
        }
        // fixed columns: date | was | → | now | % — a first value sits under "now" like every other row
        var first = (h[2] === null || h[2] === undefined);
        html += '<li><span class="d">' + h[1] + '</span>' +
          '<span class="o">' + (first ? '' : fmtNum(h[2], digits)) + '</span>' +
          '<span class="arrow">' + (first ? '' : '→') + '</span>' +
          '<span class="n ' + (first ? 'dir-changed' : cls) + '">' + fmtNum(h[3], digits) + '</span>' +
          '<span class="p">' + pill + '</span></li>';
      }
      html += '</ol>';
      tip.innerHTML = html;
      tip.classList.add('on');
      var r = td.getBoundingClientRect();
      var tw = tip.offsetWidth, th = tip.offsetHeight;
      var x = Math.min(Math.max(8, r.left + r.width / 2 - tw / 2), document.documentElement.clientWidth - tw - 8);
      var y = r.bottom + 8;
      if (y + th > window.innerHeight - 8) y = r.top - th - 8;
      tip.style.left = x + 'px';
      tip.style.top = Math.max(8, y) + 'px';
    }
    function pctGrade(q) {
      var a = Math.abs(q);
      return a < 5 ? 1 : a < 15 ? 2 : a < 30 ? 3 : a < 60 ? 4 : 5;     // same steps as render.pct_grade
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
      var x = Math.min(Math.max(edge, r.left + r.width / 2 - tw / 2), document.documentElement.clientWidth - tw - edge);   // the page width without its scrollbar
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
  /* ---------- change matrices: a hover card per cell (who, which patch, counts, the biggest changes) ---------- */
  safe('dyn-tip', function () {
    var blobs = document.querySelectorAll('script.dyn-data');
    if (!blobs.length) return;
    var data = {};
    blobs.forEach(function (b) { data[b.getAttribute('data-for')] = JSON.parse(b.textContent); });
    var tip = document.createElement('div');
    tip.className = 'dyn-tip px-frame';
    document.body.appendChild(tip);
    function txt(s) { var e = document.createElement('span'); e.textContent = s == null ? '' : String(s); return e.innerHTML; }
    function show(a) {
      var table = a.closest('table.dyn');
      var d = table && data[table.id];
      var k = a.getAttribute('data-k');
      if (!d || k === null) return;
      var c = d.cells[+k], p = d.patches[c[0]], tr = a.closest('tr');
      var counts = c[1], samples = c[2], order = ['new', 'rework', 'buff', 'nerf', 'del', 'on', 'off', 'up', 'down', 'mech', 'changed'];
      var part = table.getAttribute('data-part') || 'all';
      if (part !== 'all' && c[3]) {             // the filter: only this part's counts and changes
        counts = c[3][part] || {};
        samples = samples.filter(function (s) { return s[5] === part; });
      }
      var total = 0;
      Object.keys(counts).forEach(function (t) { total += counts[t]; });
      var icon = tr.getAttribute('data-icon');
      var html = '<div class="dt-head">' + (icon ? '<img src="' + txt(icon) + '" alt="">' : '') +
        '<span class="dt-name">' + txt(tr.getAttribute('data-name')) + '</span>' +
        '<span class="dt-patch' + (p[2] ? ' named' : '') + '">' + txt(p[1]) + '</span></div>';
      html += '<div class="dt-counts">' + order.filter(function (t) { return counts[t]; }).map(function (t) {
        var word = (counts[t] === 1 && d.word1 && d.word1[t]) || d.words[t] || t;     // "1 buff", "2 buffs"
        return '<span class="pip ' + t + '">' + (d.icons[t] || '') + counts[t] + '<em>' + txt(word) + '</em></span>';
      }).join('') + '</div>';
      if (samples.length) {
        // the biggest changes; a hero's are grouped by part (base stats, weapon, abilities) and name
        // the ability — an item's or unit's are about the row itself
        var hero = !!c[3], lastPart = null, rowsHtml = '';
        samples.forEach(function (s) {
          if (hero && s[5] !== lastPart && d.parts && d.parts[s[5]] && part === 'all') {
            lastPart = s[5];
            rowsHtml += '<tr class="dt-part p-' + s[5] + '"><td colspan="3">' + txt(d.parts[s[5]]) + '</td></tr>';
          }
          var vals = s[2] && s[3] ? txt(s[2]) + '<i>→</i><b class="t-' + s[4] + '">' + txt(s[3]) + '</b>'
            : '<b class="t-' + s[4] + '">' + txt(s[3] || s[2]) + '</b>';
          rowsHtml += '<tr>' + (hero ? '<td class="dt-what">' + txt(s[0]) + '</td>' : '') +
            '<td class="dt-field">' + txt(s[1]) + '</td><td class="dt-vals">' + vals + '</td></tr>';
        });
        html += '<table class="dt-rows">' + rowsHtml + '</table>';
      }
      var more = total - samples.length;
      html += '<div class="dt-foot">' + (more > 0 ? '+' + more + ' more · ' : '') + 'click to open the patch</div>';
      tip.innerHTML = html;
      tip.classList.add('on');
      var r = a.getBoundingClientRect(), tw = tip.offsetWidth, th = tip.offsetHeight;
      var x = Math.min(Math.max(8, r.left + r.width / 2 - tw / 2), document.documentElement.clientWidth - tw - 8);
      var y = r.bottom + 8;
      if (y + th > window.innerHeight - 8) y = r.top - th - 8;
      tip.style.left = x + 'px';
      tip.style.top = Math.max(8, y) + 'px';
    }
    document.addEventListener('mouseover', function (ev) {
      var a = ev.target.closest && ev.target.closest('table.dyn .dsq');
      if (a) show(a); else tip.classList.remove('on');
    });
    window.addEventListener('scroll', function () { tip.classList.remove('on'); }, true);
  });

  /* ---------- hero changes: a filter narrows every tile to one part (stats / weapon / abilities) ---------- */
  /* the tiles follow both filters: the hero part (All / Stats / Weapon / Abilities) and the hidden
     tags — hiding BUFF used to drop the stripe but keep the tile's number */
  safe('dyn-parts', function () {
    var tables = document.querySelectorAll('table.dyn');
    if (!tables.length) return;
    var order = ['new', 'rework', 'buff', 'nerf', 'del', 'on', 'off', 'up', 'down', 'mech', 'changed'];
    var parsed = {};
    function redraw(table) {
      var blob = document.querySelector('script.dyn-data[data-for="' + table.id + '"]');
      if (!blob) return;
      var d = parsed[table.id] || (parsed[table.id] = JSON.parse(blob.textContent));
      var part = table.getAttribute('data-part') || 'all';
      table.querySelectorAll('a.dsq[data-k]').forEach(function (a) {
          var c = d.cells[+a.getAttribute('data-k')];
          var counts = part === 'all' ? c[1] : ((c[3] || {})[part] || {});
          var tags = order.filter(function (t) { return counts[t] && !table.classList.contains('hide-' + t); }), total = 0;
          tags.forEach(function (t) { total += counts[t]; });
          a.classList.toggle('part-out', !total);
          if (!total) return;
          a.innerHTML = tags.map(function (t) {
            return '<span class="st t-' + t + '" style="flex:' + counts[t] + '"></span>';
          }).join('') + '<span class="dn">' + total + '</span>';
          var good = (counts.buff || 0) + (counts['new'] || 0) + (counts.on || 0);
          var bad = (counts.nerf || 0) + (counts.del || 0) + (counts.off || 0);
          a.classList.remove('net-buff', 'net-nerf', 'net-mix');
          a.classList.add(good > bad ? 'net-buff' : bad > good ? 'net-nerf' : 'net-mix');
      });
    }
    document.querySelectorAll('[data-part]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var table = document.querySelector(btn.getAttribute('data-target'));
        if (!table) return;
        document.querySelectorAll('[data-part]').forEach(function (b) { b.classList.toggle('on', b === btn); });
        table.setAttribute('data-part', btn.getAttribute('data-part'));
        redraw(table);
      });
    });
    // tag buttons toggle "hide-<tag>" on the table (generic toggle): redraw after it ran
    document.querySelectorAll('.dyn-tags [data-toggle-class]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var table = document.querySelector(btn.getAttribute('data-target'));
        if (table) setTimeout(function () { redraw(table); }, 0);
      });
    });
  });

  /* ---------- change matrices open at the newest patches (the right end); older columns re-scroll ---------- */
  safe('dyn-scroll', function () {
    document.querySelectorAll('table.dyn').forEach(function (t) {
      var sc = t.closest('.table-scroll');
      if (!sc) return;
      function toEnd() { sc.scrollLeft = sc.scrollWidth; }
      toEnd();
      new MutationObserver(toEnd).observe(t, { attributes: true, attributeFilter: ['class'] });
    });
  });

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
  /* ---------- the game's shop: tabs, hover (dim / light up / pulse), item tooltip, the game's UI sounds ---------- */
  safe('gshop', function () {
    var root = document.querySelector('.gshop');
    if (!root) return;
    var tabs = root.querySelectorAll('.gs-tab'), pages = root.querySelectorAll('.gs-page');
    var HASH = { all: 'all', w: 'weapon', s: 'spirit', v: 'vitality' }, TAB_KEY = 'cyclopean.shopTab', SND_KEY = 'cyclopean.shopSound';
    function store(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode: not remembered */ } }
    function stored(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }

    /* sounds: decoded on demand once the page got a click or a key (browsers allow audio only then) */
    var base = root.getAttribute('data-sfx'), ctx = null, bufs = {}, unlocked = false;
    var muted = stored(SND_KEY) === 'off';
    var hoverN = {};
    (root.getAttribute('data-hover') || '').split(' ').forEach(function (p) { var kv = p.split(':'); hoverN[kv[0]] = +kv[1]; });
    // ui.vsndevts: hover -14 / -12 / -15 dB at pitch 1.2, tab clicks -6 dB plus a page flip -3 dB under it
    var HOVER_GAIN = { w: 0.35, s: 0.44, v: 0.31 };
    function audio() {
      if (!ctx) { var C = window.AudioContext || window.webkitAudioContext; if (!C) return null; ctx = new C(); }
      return ctx;
    }
    function load(name) {
      if (!bufs[name]) {
        bufs[name] = fetch(base + name + '.mp3').then(function (r) { return r.arrayBuffer(); }).then(function (b) {
          return new Promise(function (ok, bad) { audio().decodeAudioData(b, ok, bad); });
        });
      }
      return bufs[name];
    }
    function play(name, gain, rate) {
      if (muted || !unlocked || !audio()) return;
      load(name).then(function (buf) {
        var src = ctx.createBufferSource(), g = ctx.createGain();
        src.buffer = buf;
        src.playbackRate.value = rate || 1;
        g.gain.value = gain;
        src.connect(g);
        g.connect(ctx.destination);
        src.start();
      }).catch(function () { /* a sound that fails to load stays silent */ });
    }
    function pick(n) { var i = 1 + Math.floor(Math.random() * n); return (i < 10 ? '0' : '') + i; }
    // every gesture tries again: iOS Safari takes a touchend or a click, not a pointerdown
    function unlock() {
      unlocked = true;
      if (audio() && ctx.state !== 'running') ctx.resume();
    }
    ['pointerup', 'touchend', 'click', 'keydown'].forEach(function (ev) {
      document.addEventListener(ev, unlock, { passive: true });
    });
    var sound = root.querySelector('.gs-sound');
    function soundState() {
      sound.classList.toggle('on', !muted);
      sound.setAttribute('aria-pressed', muted ? 'false' : 'true');
    }
    if (sound) {
      soundState();
      sound.addEventListener('click', function () { muted = !muted; store(SND_KEY, muted ? 'off' : 'on'); soundState(); });
    }

    // a name too long for its two lines shrinks until it fits (the game's text-overflow: shrink)
    function fit(page) {
      // a hidden page measures nothing: it fits when its tab opens
      if (!page || page.hidden || page.getAttribute('data-fit')) return;
      page.setAttribute('data-fit', '1');
      page.querySelectorAll('.gc-nm').forEach(function (n) {
        for (var k = 14.5; n.scrollHeight > n.clientHeight + 1 && k >= 10; k -= 0.5) {
          n.style.fontSize = 'calc(' + k + ' * var(--u))';
        }
      });
    }
    function show(key, byUser) {
      if (!HASH[key]) key = 'w';
      pages.forEach(function (p) { p.hidden = p.getAttribute('data-page') !== key; });
      var page = root.querySelector('.gs-page[data-page="' + key + '"]');
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { fit(page); });
      else fit(page);
      tabs.forEach(function (t) { t.classList.toggle('on', t.getAttribute('data-gs') === key); });
      root.setAttribute('data-gs-tab', key);     // not data-tab: the site's generic tabs would take it
      if (!byUser) return;
      store(TAB_KEY, key);
      if (history.replaceState) history.replaceState(null, '', '#' + HASH[key]);
      var tab = root.querySelector('.gs-tab[data-gs="' + key + '"]');
      unlock();
      play('panel_' + tab.getAttribute('data-panel'), 0.5);
      play('page_' + pick(6), 0.35);
    }
    tabs.forEach(function (t) { t.addEventListener('click', function () { show(t.getAttribute('data-gs'), true); }); });
    function hashTab() { return Object.keys(HASH).filter(function (k) { return '#' + HASH[k] === location.hash; })[0]; }
    show(hashTab() || stored(TAB_KEY) || 'w', false);
    window.addEventListener('hashchange', function () { if (hashTab()) show(hashTab(), false); });

    /* hover: the tooltip sits left of the card (the game's tooltip-position: left), right when no room */
    var tip = document.createElement('div');
    tip.className = 'gs-tip';
    tip.hidden = true;
    document.body.appendChild(tip);
    var nav = document.querySelector('.top-nav');
    function place(card) {
      var r = card.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight, gap = 10;
      var left = r.left - w - gap;
      if (left < 8) left = r.right + gap;
      left = Math.max(8, Math.min(left, window.innerWidth - w - 8));
      // below the sticky top bar (it sits above tooltips), else its name and price hide under it
      var min = (nav ? nav.offsetHeight : 0) + 8;
      var top = Math.max(min, Math.min(r.top + r.height / 2 - h / 2, window.innerHeight - h - 8));
      tip.style.left = left + 'px';
      tip.style.top = top + 'px';
    }
    root.querySelectorAll('.gs-board').forEach(function (board) {
      var cat = board.closest('.gs-page').getAttribute('data-page');
      var byId = {}, cur = null;
      board.querySelectorAll('.gcard[data-id]').forEach(function (c) { byId[c.getAttribute('data-id')] = c; });
      function mark(ids, cls) {
        (ids || '').split(' ').forEach(function (id) { if (byId[id]) byId[id].classList.add(cls); });
      }
      function clear() {
        cur = null;
        tip.hidden = true;
        board.classList.remove('hovering');
        board.querySelectorAll('.is-me, .is-comp, .is-up').forEach(function (c) { c.classList.remove('is-me', 'is-comp', 'is-up'); });
      }
      board.addEventListener('mouseover', function (ev) {
        var card = ev.target.closest('.gcard');
        if (card === cur) return;
        clear();
        if (!card) return;
        cur = card;
        board.classList.add('hovering');
        card.classList.add('is-me');
        mark(card.getAttribute('data-comp'), 'is-comp');
        mark(card.getAttribute('data-up'), 'is-up');
        var tpl = document.getElementById('gt-' + card.getAttribute('data-id'));
        if (tpl) {
          tip.textContent = '';
          tip.appendChild(tpl.content.cloneNode(true));
          tip.hidden = false;
          place(card);
        }
        play('hover_' + cat + '_' + pick(hoverN[cat] || 1), HOVER_GAIN[cat] || 0.35, 1.2);
      });
      board.addEventListener('mouseleave', clear);
    });
    // the card moves with the page: the tooltip follows it
    window.addEventListener('scroll', function () {
      var on = root.querySelector('.gcard.is-me');
      if (on && !tip.hidden) place(on);
    }, { passive: true });
  });

  /* ---------- items shop, All Items tab: hover lights up components and upgrades ---------- */
  safe('shop', function () {
    var shops = document.querySelectorAll('.shop');
    if (!shops.length) return;
    shops.forEach(function (shop) {
      var byId = {};
      shop.querySelectorAll('.icard[data-id]').forEach(function (c) { byId[c.getAttribute('data-id')] = c; });
      function mark(ids, cls) {
        (ids || '').split(' ').forEach(function (id) { if (byId[id]) byId[id].classList.add(cls); });
      }
      function clear() {
        shop.classList.remove('hovering');
        shop.querySelectorAll('.is-me, .is-comp, .is-up').forEach(function (c) { c.classList.remove('is-me', 'is-comp', 'is-up'); });
      }
      shop.addEventListener('mouseover', function (ev) {
        var card = ev.target.closest('.icard');
        if (!card || card.classList.contains('is-me')) return;
        clear();
        var comp = card.getAttribute('data-comp'), up = card.getAttribute('data-up');
        if (!comp && !up) return;
        shop.classList.add('hovering');
        card.classList.add('is-me');
        mark(comp, 'is-comp');
        mark(up, 'is-up');
      });
      shop.addEventListener('mouseleave', clear);
    });
  });

  /* ---------- Hero Stats at N boons (Sloppy's LVL box): base + N x per-boon, shown in its own colour ---------- */
  safe('boons', function () {
    document.querySelectorAll('input[data-boons]').forEach(function (inp) {
      var table = document.querySelector(inp.getAttribute('data-boons'));
      if (!table) return;
      var cells = table.querySelectorAll('td[data-per]');
      cells.forEach(function (td) { td.setAttribute('data-base', td.getAttribute('data-sort')); });
      function fmt(v, digits) {
        var s = v.toFixed(Math.max(0, digits));
        return s.indexOf('.') >= 0 ? s.replace(/0+$/, '').replace(/\.$/, '') : s;
      }
      function apply() {
        var n = Math.max(0, Math.min(+inp.max || 35, parseInt(inp.value || '0', 10) || 0));
        cells.forEach(function (td) {
          var base = parseFloat(td.getAttribute('data-base')), per = parseFloat(td.getAttribute('data-per'));
          if (isNaN(base) || isNaN(per)) return;
          var v = base + per * n;
          td.textContent = fmt(v, parseInt(td.getAttribute('data-digits') || '2', 10));
          td.setAttribute('data-sort', v);
          td.classList.toggle('boosted', n > 0);
        });
      }
      inp.addEventListener('input', apply);
    });
  });

  /* ---------- Hero Stats: one role at a time (Sloppy's Melee / Ranged buttons) ---------- */
  safe('role-filter', function () {
    var btns = document.querySelectorAll('[data-role-filter]');
    btns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var table = document.querySelector(btn.getAttribute('data-target'));
        var role = btn.classList.contains('on') ? '' : btn.getAttribute('data-role-filter');
        btns.forEach(function (b) { b.classList.toggle('on', b === btn && !!role); });
        table.querySelectorAll('tbody tr[data-role]').forEach(function (tr) {
          tr.classList.toggle('role-out', !!role && tr.getAttribute('data-role') !== role);
        });
      });
    });
  });

  /* ---------- calendar: year buttons show that year's grid ---------- */
  safe('calendar', function () {
    var btns = document.querySelectorAll('[data-year].px-btn');
    btns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var y = btn.getAttribute('data-year');
        btns.forEach(function (b) { b.classList.toggle('on', b === btn); });
        document.querySelectorAll('.cal-year').forEach(function (s) { s.classList.toggle('on', s.getAttribute('data-year') === y); });
      });
    });
  });

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
    // every table on the page (items and units come as one table per category), ranked within itself
    btn.addEventListener('click', function () {
      var on = !btn.classList.contains('on');
      btn.classList.toggle('on', on);
      document.querySelectorAll('table.stats').forEach(function (table) { heat(table, on); });
    });
    function heat(table, on) {
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
    }
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
        var tables = [];
        document.querySelectorAll(sel).forEach(function (el) {
          var hay = (el.getAttribute('data-search') || el.textContent).toLowerCase();
          el.classList.toggle('hidden-el', q !== '' && hay.indexOf(q) < 0);
          var t = el.closest && el.closest('table');
          if (t && tables.indexOf(t) < 0) tables.push(t);
        });
        // a section row (a tier, a unit group) with nothing left under it goes too
        tables.forEach(function (t) {
          var secs = t.querySelectorAll('tbody tr.sec');
          secs.forEach(function (sec) {
            var r = sec.nextElementSibling, any = false;
            while (r && !r.classList.contains('sec')) {
              if (!r.classList.contains('hidden-el')) { any = true; break; }
              r = r.nextElementSibling;
            }
            sec.classList.toggle('hidden-el', q !== '' && !any);
          });
        });
      });
    });
  });
})();
