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
      // band rows (a category, a unit group) stand aside while the table is sorted by a column
      var data = original.filter(function (r) { return !r.classList.contains('sec'); });
      var state = { col: null, dir: 0 };
      function mark(col) {
        table.querySelectorAll('tbody td.sorted-col').forEach(function (td) { td.classList.remove('sorted-col'); });
        if (col) table.querySelectorAll('tbody td[data-col="' + col + '"]').forEach(function (td) { td.classList.add('sorted-col'); });
      }
      table.querySelectorAll('thead tr.cols th[data-col]').forEach(function (th) {
        if (th.hasAttribute('data-nosort')) return;
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
            // each row's key read once, not by two cell lookups per comparison; the rows move in one fragment
            var keyed = data.map(function (r) {
              var td = r.querySelector('td[data-col="' + col + '"]');
              var v = td ? td.getAttribute('data-sort') : '';
              return [v === null ? '' : v, parseFloat(v), r];
            });
            keyed.sort(function (a, b) {
              var ea = isNaN(a[1]), eb = isNaN(b[1]);
              if (ea && eb) return String(a[0]).localeCompare(String(b[0]));
              if (ea) return 1;
              if (eb) return -1;
              return state.dir === 1 ? b[1] - a[1] : a[1] - b[1];
            });
            rows = keyed.map(function (k) { return k[2]; });
          }
          table.classList.toggle('is-sorted', state.dir !== 0);
          var frag = document.createDocumentFragment();
          rows.forEach(function (r) { frag.appendChild(r); });
          tbody.appendChild(frag);
          mark(state.dir !== 0 ? col : null);
        });
      });
      // cells built later (Item Stats' stat columns) join the marked column
      table.addEventListener('statcols', function () { mark(state.dir !== 0 ? state.col : null); });
      // row marking
      tbody.addEventListener('click', function (ev) {
        if (ev.target.closest('a, .sc')) return;
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
      if (!target) return;
      // a switch the browser restored as ticked on "back" gets its class too (they disagreed)
      if (btn.type === 'checkbox' && btn.checked) target.classList.add(cls);
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
    var data = window.__dyn = window.__dyn || {};     // shared with dyn-parts: parse each blob once
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
      html += '<div class="dt-foot">' + (more > 0 ? '+' + more + ' more · ' : '') + 'click for its history at this patch</div>';
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
    // the same gradient builders/dynamics_page.stripes draws: a stripe per tag, none thinner than 12%
    var COLOUR = { up: 'changed', down: 'changed' };
    function stripes(counts, tags) {
      var total = 0, norm = 0, acc = 0;
      tags.forEach(function (t) { total += counts[t]; });
      var shares = tags.map(function (t) { var s = Math.max(counts[t] / total, 0.12); norm += s; return s; });
      return 'linear-gradient(' + tags.map(function (t, i) {
        var a = acc;
        acc += shares[i] / norm * 100;
        return 'var(--tag-' + (COLOUR[t] || t) + ') ' + a.toFixed(1) + '% ' + acc.toFixed(1) + '%';
      }).join(',') + ')';
    }
    // `onlyTag`: a tag button touches only the tiles that have that tag; tiles out of sight (old columns,
    // hidden rows) wait, marked dirty, until they show (2k tiles took 130 ms each click)
    var tiles = {};
    function redraw(table, onlyTag, onlyDirty) {
      var blob = document.querySelector('script.dyn-data[data-for="' + table.id + '"]');
      if (!blob) return;
      var d = (window.__dyn || {})[table.id] || parsed[table.id] || (parsed[table.id] = JSON.parse(blob.textContent));
      var list = tiles[table.id] || (tiles[table.id] = Array.prototype.map.call(
        table.querySelectorAll('a.dsq[data-k]'), function (a) {
          var td = a.parentNode;
          return [a, d.cells[+a.getAttribute('data-k')], td.classList.contains('old'),
                  td.parentNode.classList.contains('extra'), false];
        }));
      var part = table.getAttribute('data-part') || 'all';
      var sel = table.__sel || [];
      var hidden = sel.length ? order.filter(function (t) { return sel.indexOf(t) < 0; }) : [];
      var showOld = table.classList.contains('show-old'), showExtra = table.classList.contains('show-extra');
      list.forEach(function (pair) {
        var a = pair[0], c = pair[1];
        if (onlyDirty && !pair[4]) return;
        var counts = part === 'all' ? c[1] : ((c[3] || {})[part] || {});
        if (onlyTag && !counts[onlyTag]) return;
        if ((pair[2] && !showOld) || (pair[3] && !showExtra)) { pair[4] = true; return; }
        pair[4] = false;
        var tags = order.filter(function (t) { return counts[t] && hidden.indexOf(t) < 0; }), total = 0;
        tags.forEach(function (t) { total += counts[t]; });
        var good = (counts.buff || 0) + (counts['new'] || 0) + (counts.on || 0);
        var bad = (counts.nerf || 0) + (counts.del || 0) + (counts.off || 0);
        var cls = 'dsq ' + (!total ? 'part-out' : good > bad ? 'net-buff' : bad > good ? 'net-nerf' : 'net-mix');
        // write only what changed: a text or class write re-lays the tile out
        if (a.className !== cls) a.className = cls;
        if (!total) return;
        a.style.background = stripes(counts, tags);
        if (a.firstChild.textContent !== String(total)) a.firstChild.textContent = total;
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
    // tag chips select: only the chosen tags colour the tiles (none chosen = all), as on an entity page
    document.querySelectorAll('.dyn-tags [data-dyn-tag]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var table = document.querySelector(btn.getAttribute('data-target'));
        if (!table) return;
        var sel = table.__sel || (table.__sel = []), tag = btn.getAttribute('data-dyn-tag'), i = sel.indexOf(tag);
        if (i >= 0) sel.splice(i, 1); else sel.push(tag);
        btn.classList.toggle('on', i < 0);
        redraw(table);
      });
    });
    // old columns / hidden rows coming into sight: draw the tiles a filter skipped
    document.querySelectorAll('.dyn-bar input[data-toggle-class="show-old"], .dyn-bar input[data-toggle-class="show-extra"]')
      .forEach(function (inp) {
        inp.addEventListener('click', function () {
          var table = document.querySelector(inp.getAttribute('data-target'));
          if (table && tiles[table.id]) setTimeout(function () { redraw(table, null, true); }, 0);
        });
      });
  });

  /* ---------- change matrices open at the newest patches (the right end); older columns re-scroll ---------- */
  /* the box is as wide as the name column + a whole number of patch columns, so at the right end the
     first visible column starts exactly at the sticky names (it opened with half a column under them) */
  safe('dyn-scroll', function () {
    document.querySelectorAll('table.dyn').forEach(function (t) {
      var sc = t.closest('.table-scroll');
      var box = sc && sc.parentNode;
      if (!sc || !box) return;
      box.classList.add('center');
      function fit() {
        box.style.maxWidth = '';
        var name = t.querySelector('thead tr.cols th.name');
        var col = t.querySelector('thead tr.cols th.dd:not(.old)') || t.querySelector('thead tr.cols th.dd');
        if (!name || !col || sc.scrollWidth <= sc.clientWidth) return;
        var w = col.getBoundingClientRect().width, nw = name.getBoundingClientRect().width;
        var chrome = sc.offsetWidth - sc.clientWidth;          // borders + the vertical scrollbar
        var n = Math.floor((sc.clientWidth - nw) / w);
        if (n > 0) box.style.maxWidth = Math.round(nw + n * w + chrome) + 'px';
      }
      function toEnd() { sc.scrollLeft = sc.scrollWidth; }
      fit();
      toEnd();
      // only "Older patches" changes the width; "Buff vs nerf" and the rest leave the scroll alone
      var old = t.classList.contains('show-old');
      new MutationObserver(function () {
        var now = t.classList.contains('show-old');
        if (now !== old) { old = now; fit(); toEnd(); }
      }).observe(t, { attributes: true, attributeFilter: ['class'] });
      var pending = false;
      window.addEventListener('resize', function () {
        if (pending) return;
        pending = true;
        requestAnimationFrame(function () { pending = false; fit(); toEnd(); });
      });
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

    // a name keeps inside its card (the game's text-overflow: shrink): words never break, a long one —
    // "Sharpshooter", "Enchantment" — shrinks until the text is narrower than the card and fits two lines
    var probe = document.createRange();
    function tooBig(n) {
      probe.selectNodeContents(n);
      var room = n.clientWidth - 2 * parseFloat(getComputedStyle(n).paddingLeft);
      return n.scrollHeight > n.clientHeight + 1 || probe.getBoundingClientRect().width > room * 0.98;
    }
    function fit(page) {
      // a hidden page measures nothing: it fits when its tab opens
      if (!page || page.hidden || page.getAttribute('data-fit')) return;
      page.setAttribute('data-fit', '1');
      page.querySelectorAll('.gc-nm').forEach(function (n) {
        n.style.fontSize = '';
        for (var k = 14.5; tooBig(n) && k >= 9; k -= 0.5) n.style.fontSize = 'calc(' + k + ' * var(--u))';
      });
    }
    function refit() {
      pages.forEach(function (p) { p.removeAttribute('data-fit'); });
      fit(root.querySelector('.gs-page:not([hidden])'));
    }
    var fitT = 0, lastW = window.innerWidth;
    window.addEventListener('resize', function () {
      if (window.innerWidth === lastW) return;           // a phone's address bar changes only the height
      lastW = window.innerWidth;
      clearTimeout(fitT);
      fitT = setTimeout(refit, 200);
    });
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

    /* tooltips: one json (items/shop-tips.json), fetched on the first hover over the shop */
    var tips = null, tipsReq = null;
    function loadTips() {
      if (!tipsReq) {
        tipsReq = fetch(root.getAttribute('data-tips'))
          .then(function (r) { if (!r.ok) throw new Error('tips ' + r.status); return r.json(); })
          .then(function (j) { tips = j; return j; })
          .catch(function () { tipsReq = null; return {}; });   // no tooltips now; the next hover asks again
      }
      return tipsReq;
    }
    root.addEventListener('pointerover', loadTips, { once: true });

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
    var active = null;
    function showTip(card) {
      var id = card.getAttribute('data-id');
      // after a failed load, only the next hover asks again (no retry loop on this card)
      if (!tips) { loadTips().then(function () { if (tips && active === card) showTip(card); }); return; }
      if (!tips[id]) { tip.hidden = true; return; }
      tip.innerHTML = tips[id];                 // built and escaped by builders/game_shop.py
      tip.hidden = false;
      place(card);
    }
    root.querySelectorAll('.gs-board').forEach(function (board) {
      var byId = {}, lit = [], leaveT = 0;
      board.querySelectorAll('.gcard[data-id]').forEach(function (c) { byId[c.getAttribute('data-id')] = c; });
      function mark(ids, cls) {
        (ids || '').split(' ').forEach(function (id) {
          var c = byId[id];
          if (c && c !== active) { c.classList.add(cls); lit.push(c); }
        });
      }
      // only the few cards that change get a class: the rest dims under the board's single layer
      function unlight() {
        lit.forEach(function (c) { c.classList.remove('is-me', 'is-comp', 'is-up'); });
        lit = [];
      }
      function leave() {
        active = null;
        unlight();
        board.classList.remove('hovering');
        tip.hidden = true;
      }
      board.addEventListener('mouseover', function (ev) {
        var card = ev.target.closest('.gcard');
        if (!card) {                            // the gap between cards: let go only if it lasts
          clearTimeout(leaveT);
          if (active) leaveT = setTimeout(leave, 90);
          return;
        }
        clearTimeout(leaveT);
        if (card === active) return;
        unlight();
        active = card;
        card.classList.add('is-me');
        lit.push(card);
        mark(card.getAttribute('data-comp'), 'is-comp');
        mark(card.getAttribute('data-up'), 'is-up');
        if (!board.classList.contains('hovering')) board.classList.add('hovering');
        showTip(card);
        var cat = (card.className.match(/p-([wsv])/) || [])[1] || 'w';
        play('hover_' + cat + '_' + pick(hoverN[cat] || 1), HOVER_GAIN[cat] || 0.35, 1.2);
      });
      board.addEventListener('mouseleave', function () { clearTimeout(leaveT); leave(); });
    });
    // the card moves with the page: the tooltip follows it
    window.addEventListener('scroll', function () {
      if (active && !tip.hidden) place(active);
    }, { passive: true });
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
      // one redraw per frame while the number spins, then the heat re-ranks the new values
      var pending = false;
      inp.addEventListener('input', function () {
        if (pending) return;
        pending = true;
        requestAnimationFrame(function () {
          pending = false;
          apply();
          if (window.__reheat) window.__reheat();
        });
      });
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
    var CLS = ['hm-g1', 'hm-g2', 'hm-g3', 'hm-g4', 'hm-b1', 'hm-b2', 'hm-b3', 'hm-b4'];
    // every table on the page (units come as one table per group), ranked within itself
    function all() {
      document.querySelectorAll('table.stats').forEach(function (table) { heat(table, btn.checked); });
    }
    btn.addEventListener('change', all);
    // values that change in place (Boons, "Souls per point", new cells) re-rank the heat if it is on
    window.__reheat = function () { if (btn.checked) all(); };
    // on by default where the page says so (Item Stats); a box the browser restored on "back" counts too
    if (btn.checked) all();
    /* graded by rank (Sloppy's mana table): each column's distinct values ranked by size, the middle
       fifth left plain, then 4 steps of green (better) or red (worse) — a binary +-14% hid the spread.
       An item's stat chip ranks with its column; bonuses rank by size, so a -8% shred beats a -6% one. */
    function heat(table, on) {
      table.querySelectorAll('.' + CLS.join(', .')).forEach(function (el) { el.classList.remove.apply(el.classList, CLS); });
      if (!on) return;
      var cols = {};
      // the heat's direction: data-hpol when set ("Souls per point": cheaper per point is better; a
      // price column: no heat), else the stat's own data-pol, which the history tooltip reads too
      table.querySelectorAll('tbody td[data-col], tbody .sc[data-col]').forEach(function (el) {
        var v = parseFloat(el.getAttribute('data-sort'));
        var pol = parseInt(el.getAttribute('data-hpol') || el.getAttribute('data-pol') || '1', 10);
        if (isNaN(v) || pol === 0) return;
        (cols[el.getAttribute('data-col')] = cols[el.getAttribute('data-col')] || []).push([Math.abs(v), el, pol]);
      });
      Object.keys(cols).forEach(function (k) {
        var list = cols[k];
        var uniq = Array.from(new Set(list.map(function (x) { return x[0]; }))).sort(function (a, b) { return a - b; });
        if (uniq.length < 3) return;
        var at = {};
        uniq.forEach(function (v, i) { at[v] = i / (uniq.length - 1); });
        list.forEach(function (x) {
          var r = x[2] < 0 ? 1 - at[x[0]] : at[x[0]];
          var off = Math.abs(r - 0.5) - 0.1;
          if (off <= 0) return;
          var step = Math.min(4, Math.ceil(off / 0.4 * 4));
          x[1].classList.add((r > 0.5 ? 'hm-g' : 'hm-b') + step);
        });
      });
    }
  });

  /* ---------- stats tables: a click on a group header folds the group to its first column ---------- */
  /* ONE recount for everything that hides columns (a folded group, the item filter's empty columns,
     Details, Item Stats' stat columns): each group header spans exactly its visible columns, a group
     with none left hides, and a folded group keeps its first column the filter left visible — the item
     filter used to count folded columns too and shifted the headers by one (2026-10-04) */
  safe('col-groups', function () {
    document.querySelectorAll('table.stats').forEach(function (table) {
      var cats = Array.prototype.slice.call(table.querySelectorAll('thead tr.cats th.cat[data-group]'));
      var heads = Array.prototype.slice.call(table.querySelectorAll('thead tr.cols th[data-group]'));
      var allHeads = Array.prototype.slice.call(table.querySelectorAll('thead tr.cols th'));
      if (!cats.length) return;
      function shown(el) { return getComputedStyle(el).display !== 'none'; }
      function ofGroup(g) { return heads.filter(function (h) { return h.getAttribute('data-group') === g; }); }
      function setOff(h, off) {
        h.classList.toggle('grp-off', off);
        table.querySelectorAll('td[data-col="' + h.getAttribute('data-col') + '"]').forEach(function (td) {
          td.classList.toggle('grp-off', off);
        });
      }
      function refold(th) {
        var hs = ofGroup(th.getAttribute('data-group'));
        hs.forEach(function (h) { setOff(h, false); });
        if (!th.classList.contains('folded')) return;
        var keep = hs.filter(function (h) { return !h.classList.contains('col-off') && shown(h); })[0];
        hs.forEach(function (h) { if (h !== keep) setOff(h, true); });
      }
      function recount() {
        cats.forEach(function (th) { if (th.classList.contains('folded')) refold(th); });
        cats.forEach(function (th) {
          var n = ofGroup(th.getAttribute('data-group')).filter(shown).length;
          th.classList.toggle('col-gone', !n);
          if (n) th.colSpan = n;
        });
        // a band row spans the visible columns
        var width = allHeads.filter(shown).length;
        table.querySelectorAll('tbody tr.sec td.sec-fill').forEach(function (td) { td.colSpan = Math.max(1, width - 1); });
      }
      table.__recount = recount;
      cats.forEach(function (th) {
        if (ofGroup(th.getAttribute('data-group')).length < 2) return;      // nothing to fold
        th.classList.add('foldable');
        th.addEventListener('click', function () {
          th.classList.toggle('folded');
          recount();
        });
      });
      // switches that show / hide columns (Details, Stat columns): the spans follow
      document.querySelectorAll('[data-toggle-class]').forEach(function (b) {
        b.addEventListener('click', function () { setTimeout(recount, 0); });
      });
      table.addEventListener('statcols', recount);
      recount();
    });
  });

  /* ---------- Item Stats: chips by category / tier / kind; columns no shown row fills hide; souls per point ---------- */
  safe('item-filter', function () {
    var table = document.getElementById('items-table');
    if (!table) return;
    var bar = document.querySelector('.toolbar');
    var sel = { cat: [], tier: [], kind: [] };
    var all = Array.prototype.slice.call(table.tBodies[0].rows);
    var rows = all.filter(function (r) { return !r.classList.contains('sec'); });
    var bands = all.filter(function (r) { return r.classList.contains('sec'); });
    var heads = Array.prototype.slice.call(table.querySelectorAll('thead tr.cols th[data-col]'))
      .filter(function (th) { return th.getAttribute('data-col') !== 'name'; });
    var lazy = heads.filter(function (th) { return th.hasAttribute('data-cell-cls'); });
    var cells = [];
    function readCells() {          // td per (row, column), read once per layout
      cells = rows.map(function (r) {
        var m = {};
        Array.prototype.forEach.call(r.querySelectorAll('td[data-col]'), function (td) { m[td.getAttribute('data-col')] = td; });
        return m;
      });
    }
    readCells();
    function shown(r) { return !r.classList.contains('f-out') && !r.classList.contains('hidden-el'); }
    function filled(td) { var s = td ? td.getAttribute('data-sort') : null; return s !== null && s !== ''; }
    function columns() {
      heads.forEach(function (th) {
        var key = th.getAttribute('data-col'), any = false;
        for (var i = 0; i < rows.length && !any; i++) any = shown(rows[i]) && filled(cells[i][key]);
        th.classList.toggle('col-off', !any);
        cells.forEach(function (m) { if (m[key]) m[key].classList.toggle('col-off', !any); });
      });
      // a category band with none of its items left goes too
      bands.forEach(function (b) {
        var cat = b.getAttribute('data-cat');
        b.classList.toggle('f-out', !rows.some(function (r) { return r.getAttribute('data-cat') === cat && shown(r); }));
      });
      if (table.__recount) table.__recount();        // the group headers span what is left of them
    }
    function apply() {
      rows.forEach(function (r) {
        var ok = ['cat', 'tier', 'kind'].every(function (k) {
          return !sel[k].length || sel[k].indexOf(r.getAttribute('data-' + k)) >= 0;
        });
        r.classList.toggle('f-out', !ok);
      });
      columns();
    }
    bar.addEventListener('click', function (ev) {
      var b = ev.target.closest('button[data-f]');
      if (!b) return;
      var k = b.getAttribute('data-f'), v = b.getAttribute('data-v'), i = sel[k].indexOf(v);
      if (i >= 0) sel[k].splice(i, 1); else sel[k].push(v);
      b.classList.toggle('on', i < 0);
      apply();
    });
    var search = bar.querySelector('input[type=search]');
    if (search) search.addEventListener('searched', columns);     // the search module ran

    // what one point of a stat costs: cost / value (lower is better), back to the values when off; the
    // heat ranks it lower-is-better (data-hpol) while the history colours keep the stat's own direction
    var per = bar.querySelector('[data-souls-per]');
    function spp(el, on) {
      var cost = parseFloat(el.closest('tr').getAttribute('data-cost'));
      var tgt = el.classList.contains('sc') ? el.querySelector('b') : el;
      if (on && !el.__orig) {
        var v = parseFloat(el.getAttribute('data-sort'));
        if (isNaN(v) || v <= 0 || isNaN(cost)) return;
        el.__orig = [tgt.innerHTML, el.getAttribute('data-sort')];
        var s = cost / v;
        tgt.textContent = s >= 10 ? Math.round(s) : s.toFixed(1);
        el.setAttribute('data-sort', s);
        el.setAttribute('data-hpol', '-1');
      } else if (!on && el.__orig) {
        tgt.innerHTML = el.__orig[0];
        el.setAttribute('data-sort', el.__orig[1]);
        el.removeAttribute('data-hpol');
        el.__orig = null;
      }
    }
    function sppAll() {
      var on = !!(per && per.checked);
      table.querySelectorAll('[data-spp]').forEach(function (el) { spp(el, on); });
    }
    if (per) per.addEventListener('change', function () {
      table.classList.toggle('per-soul', per.checked);
      sppAll();
      if (window.__reheat) window.__reheat();
    });

    /* Stat columns: the always-on stats as one sortable column each (by family). Their cells are not in
       the page — built here from each row's chips the first time the columns open. */
    var sw = bar.querySelector('[data-stat-cols]');
    var built = false;
    function cellFrom(chip, key, cls) {
      var td = document.createElement('td');
      td.className = cls;
      td.setAttribute('data-col', key);
      if (!chip || chip.classList.contains('gone')) {
        td.classList.add('dash');
        td.textContent = '—';
      }
      if (!chip) return td;
      ['data-pol', 'data-digits', 'data-hist', 'data-title'].forEach(function (a) {
        var v = chip.getAttribute(a);
        if (v !== null) td.setAttribute(a, v);
      });
      if (chip.classList.contains('has-hist')) td.classList.add('has-hist');
      if (chip.classList.contains('recent')) td.classList.add('recent');
      if (chip.classList.contains('gone')) return td;
      var raw = chip.__orig ? chip.__orig[1] : chip.getAttribute('data-sort');
      td.setAttribute('data-sort', raw);
      td.setAttribute('data-spp', '');
      td.textContent = fmtNum(parseFloat(raw), parseInt(chip.getAttribute('data-digits') || '0', 10));
      return td;
    }
    function build() {
      if (built) return;
      built = true;
      rows.forEach(function (r) {
        var chips = {};
        r.querySelectorAll('td.sumc .sc[data-col]').forEach(function (c) { chips[c.getAttribute('data-col')] = c; });
        var frag = document.createDocumentFragment();
        lazy.forEach(function (th) {
          var key = th.getAttribute('data-col');
          frag.appendChild(cellFrom(chips[key], key, th.getAttribute('data-cell-cls')));
        });
        r.insertBefore(frag, r.querySelector('td.fxc'));
      });
      readCells();
      sppAll();
      columns();
      table.dispatchEvent(new CustomEvent('statcols'));
      if (window.__reheat) window.__reheat();
    }
    if (sw) {
      sw.addEventListener('change', function () { if (sw.checked) build(); });
      if (sw.checked) {                          // the browser restored the box on "back"
        table.classList.add('cols-open');
        build();
      }
      // the Stats header opens the columns too
      table.querySelectorAll('thead th.sumc').forEach(function (th) {
        th.addEventListener('click', function () { if (!sw.checked) sw.click(); });
      });
      // a chip opens the columns sorted by its stat, biggest first, scrolled into view
      table.addEventListener('click', function (ev) {
        var chip = ev.target.closest('.sc[data-col]');
        if (!chip) return;
        if (!sw.checked) sw.click();
        var th = table.querySelector('thead tr.cols th[data-col="' + chip.getAttribute('data-col') + '"]');
        if (!th) return;
        if (!(th.classList.contains('sorted') && th.getAttribute('data-arrow') === '▼')) {
          th.click();
          if (th.getAttribute('data-arrow') !== '▼') th.click();
        }
        var sc = table.closest('.table-scroll'), name = table.querySelector('thead th.name');
        if (sc && name) sc.scrollLeft = Math.max(0, th.offsetLeft - name.offsetWidth - 40);
      });
    }
  });

  /* ---------- tabs: <button data-tab="id"> shows #id.tab-panel, hides its siblings ---------- */
  /* ---------- entity history: older patches render when opened; the toolbar filters rows ---------- */
  /* (builders/history_view.py) tags are a multi-select, a part (Stats / Weapon / Abilities) and an
     ability one at a time (click again to clear); "Only hidden" and "In development" are classes on
     #history that CSS reads — the filter re-runs after them so a block left empty folds away */
  safe('hist-filter', function () {
    var box = document.getElementById('history');
    if (!box || !box.classList.contains('hblocks')) return;
    var TAGS = ['new', 'rework', 'buff', 'nerf', 'del', 'mech', 'up', 'down', 'changed', 'on', 'off'];
    var state = { tags: [], area: null, ab: null };
    function stamp(d) {
      var t = d.querySelector('template.hp-t');
      if (!t) return;
      t.parentNode.replaceChild(t.content.cloneNode(true), t);
    }
    window.__histStamp = stamp;            // patch-anchor opens a lazy block too
    // <details> fires "toggle" on itself only: listen in the capture phase
    box.addEventListener('toggle', function (ev) {
      if (ev.target.tagName === 'DETAILS' && ev.target.open) stamp(ev.target);
    }, true);
    function tagOf(r) {
      if (r.__t === undefined) {
        var t = r.querySelector('.tg .tag');
        r.__t = '';
        if (t) for (var i = 0; i < TAGS.length; i++) if (t.classList.contains(TAGS[i])) { r.__t = TAGS[i]; break; }
      }
      return r.__t;
    }
    function apply() {
      var active = state.tags.length || state.area || state.ab;
      var onlyHidden = box.classList.contains('only-hidden'), dev = box.classList.contains('show-dev');
      box.classList.toggle('filtering', !!active);
      var blocks = box.querySelectorAll('details.pblock');
      // a band still in its <template> says what it holds (data-tags / -abs / -areas): one that cannot
      // match is folded away unstamped (the first filter stamped all 33 of Calico's)
      function mayMatch(b) {
        var has = function (attr, v) { return (' ' + (b.getAttribute(attr) || '') + ' ').indexOf(' ' + v + ' ') >= 0; };
        return !(state.tags.length && !state.tags.some(function (t) { return has('data-tags', t); })) &&
               !(state.ab && !state.ab.split(' ').some(function (id) { return has('data-abs', id); })) &&
               !(state.area && !has('data-areas', state.area));
      }
      blocks.forEach(function (b) {
        if (active && b.querySelector('template.hp-t') && !mayMatch(b)) { b.classList.add('f-out'); return; }
        if (active) stamp(b);
        if (!active && !b.querySelector('.f-out')) { b.classList.remove('f-out'); return; }
        var any = false;
        b.querySelectorAll('.hgroup').forEach(function (g) {
          // a merged group belongs to several parts ("t1 t2 t3": the same change on every tier)
          var gok = (!state.area || (' ' + g.getAttribute('data-area') + ' ').indexOf(' ' + state.area + ' ') >= 0) &&
                    (!state.ab || (' ' + state.ab + ' ').indexOf(' ' + g.getAttribute('data-ab') + ' ') >= 0);
          var gany = false;
          g.querySelectorAll('.erow').forEach(function (r) {
            if (r.parentNode.tagName === 'SUMMARY') return;      // a family's head follows its rows
            var ok = gok && (!state.tags.length || state.tags.indexOf(tagOf(r)) >= 0) &&
                     (!onlyHidden || r.classList.contains('is-hidden')) &&
                     (dev || !r.classList.contains('st-unreleased'));
            r.classList.toggle('f-out', !ok);
            gany = gany || ok;
          });
          g.querySelectorAll('details.fam').forEach(function (f) {
            f.classList.toggle('f-out', !f.querySelector(':scope > .erow:not(.f-out)'));
          });
          g.classList.toggle('f-out', !gany);
          any = any || gany;
        });
        b.classList.toggle('f-out', !any);
        if (active && any && !b.open) b.open = true;            // a patch with a match opens
      });
    }
    var bar = document.querySelector('.hist-bar');
    if (!bar) return;
    // #ab-<ability id> (an ability card's "History" link, Sloppy's ?ability=) filters to that ability
    function fromHash() {
      if (location.hash.indexOf('#ab-') !== 0) return;
      var id = decodeURIComponent(location.hash.slice(4));
      // the chip that holds this id (one chip may stand for namesakes: "id1 id2")
      var chip = Array.prototype.filter.call(bar.querySelectorAll('[data-f-ab]'), function (b) {
        return b.getAttribute('data-f-ab').split(' ').indexOf(id) >= 0;
      })[0];
      state.ab = chip ? chip.getAttribute('data-f-ab') : id;
      if (chip && chip.classList.contains('gone')) chip.parentNode.classList.add('show-gone');
      bar.querySelectorAll('[data-f-ab]').forEach(function (b) { b.classList.toggle('on', b.getAttribute('data-f-ab') === state.ab); });
      apply();
      box.scrollIntoView({ block: 'start' });
    }
    fromHash();
    window.addEventListener('hashchange', fromHash);
    bar.addEventListener('click', function (ev) {
      var btn = ev.target.closest('button');
      if (!btn) return;
      var tag = btn.getAttribute('data-f-tag'), area = btn.getAttribute('data-f-area'), ab = btn.getAttribute('data-f-ab');
      if (tag) {
        var i = state.tags.indexOf(tag);
        if (i >= 0) state.tags.splice(i, 1); else state.tags.push(tag);
        btn.classList.toggle('on', i < 0);
      } else if (area) {
        state.area = state.area === area ? null : area;
        bar.querySelectorAll('[data-f-area]').forEach(function (b) { b.classList.toggle('on', b.getAttribute('data-f-area') === state.area); });
      } else if (ab) {
        state.ab = state.ab === ab ? null : ab;
        bar.querySelectorAll('[data-f-ab]').forEach(function (b) { b.classList.toggle('on', b.getAttribute('data-f-ab') === state.ab); });
      }
      // "Only hidden" and "In development" toggle a class on #history first (the generic toggle)
      setTimeout(apply, 0);
    });
    bar.addEventListener('change', function () { setTimeout(apply, 0); });
  });

  /* ---------- #p-<patch>: a history block named in the address opens and comes into view ---------- */
  safe('patch-anchor', function () {
    function go() {
      if (location.hash.indexOf('#p-') !== 0) return;
      var el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (!el) return;
      if (el.tagName === 'DETAILS') {
        if (window.__histStamp) window.__histStamp(el);
        el.open = true;
      }
      el.scrollIntoView({ block: 'start' });
    }
    go();
    window.addEventListener('hashchange', go);
  });

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
      var sel = input.getAttribute('data-search-target'), timer = 0;
      // after a pause in typing (one pass, not one per key); "haze, abrams" finds either (Sloppy's search)
      input.addEventListener('input', function () {
        clearTimeout(timer);
        timer = setTimeout(run, 100);
      });
      function run() {
        var q = input.value.trim().toLowerCase();
        var terms = q.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
        var tables = [];
        document.querySelectorAll(sel).forEach(function (el) {
          var hay = (el.getAttribute('data-search') || el.textContent).toLowerCase();
          var hit = !terms.length || terms.some(function (t) { return hay.indexOf(t) >= 0; });
          el.classList.toggle('hidden-el', !hit);
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
        input.dispatchEvent(new CustomEvent('searched'));
      }
    });
  });

  /* ---------- home search: any hero, ability, item or unit by name (search.json on the first key) ---------- */
  safe('site-search', function () {
    var input = document.querySelector('input[data-site-search]');
    if (!input) return;
    var list = input.parentNode.querySelector('.ss-list');
    var rel = input.getAttribute('data-rel') || '', rows = null, asked = false, timer = 0, on = -1;
    var MAX = 12;
    function load(then) {
      if (rows) { then(); return; }
      if (asked) return;
      asked = true;
      fetch(input.getAttribute('data-site-search'))
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (d) { rows = d; then(); })
        .catch(function () { asked = false; });
    }
    function item(r) {
      var a = document.createElement('a');
      a.href = rel + r[1];
      var pic = document.createElement(r[3] ? 'img' : 'span');
      if (r[3]) { pic.src = rel + r[3]; pic.alt = ''; pic.loading = 'lazy'; } else pic.className = 'ss-noimg';
      var nm = document.createElement('span'), what = document.createElement('span');
      nm.className = 'ss-nm'; nm.textContent = r[0];
      what.className = 'ss-what'; what.textContent = r[2];
      a.appendChild(pic); a.appendChild(nm); a.appendChild(what);
      return a;
    }
    function render() {
      var q = input.value.trim().toLowerCase();
      list.textContent = '';
      on = -1;
      if (!q || !rows) { list.hidden = true; return; }
      // names that start with the query first, then any word that does, then anywhere
      var first = [], word = [], any = [];
      for (var i = 0; i < rows.length; i++) {
        var n = rows[i][0].toLowerCase(), at = n.indexOf(q);
        if (at < 0) continue;
        (at === 0 ? first : n.indexOf(' ' + q) >= 0 ? word : any).push(rows[i]);
      }
      var hits = first.concat(word, any).slice(0, MAX);
      if (!hits.length) {
        var none = document.createElement('div');
        none.className = 'ss-none'; none.textContent = 'Nothing by that name';
        list.appendChild(none);
      }
      hits.forEach(function (r) { list.appendChild(item(r)); });
      list.hidden = false;
    }
    function move(d) {
      var links = list.querySelectorAll('a');
      if (!links.length) return;
      if (on >= 0) links[on].classList.remove('on');
      on = (on + d + links.length) % links.length;
      links[on].classList.add('on');
      links[on].scrollIntoView({ block: 'nearest' });
    }
    input.addEventListener('focus', function () { load(function () {}); });
    input.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(function () { load(render); }, 80);
    });
    input.addEventListener('keydown', function (ev) {
      if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') { ev.preventDefault(); move(ev.key === 'ArrowDown' ? 1 : -1); }
      else if (ev.key === 'Enter') {
        var links = list.querySelectorAll('a');
        if (links.length) { ev.preventDefault(); window.location.href = links[Math.max(on, 0)].href; }
      } else if (ev.key === 'Escape') { input.value = ''; render(); }
    });
    document.addEventListener('click', function (ev) {
      if (!input.parentNode.contains(ev.target)) list.hidden = true;
    });
    input.addEventListener('focus', function () { if (list.childNodes.length) list.hidden = false; });
  });
})();
