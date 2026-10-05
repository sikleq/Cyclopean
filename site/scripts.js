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
      // back to the table's own order (Item Stats: its stat columns closed while one sorted the rows)
      table.__sortedBy = function () { return state.dir !== 0 ? state.col : null; };
      table.__resetSort = function () {
        state.col = null;
        state.dir = 0;
        table.querySelectorAll('thead th.sorted').forEach(function (x) { x.classList.remove('sorted'); x.removeAttribute('data-arrow'); });
        table.classList.remove('is-sorted');
        var frag = document.createDocumentFragment();
        original.forEach(function (r) { frag.appendChild(r); });
        tbody.appendChild(frag);
        mark(null);
      };
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
      // a unit after every number (Game rules: "55m", "38s" — builders/game_rules.py), none by default
      var unit = td.getAttribute('data-unit') || '';
      var fmtU = function (v, d) { var s = fmtNum(v, d); return unit && typeof v === 'number' && v !== -1 ? s + unit : s; };
      var head = td.getAttribute('data-title') || '';
      var esc = document.createElement('span');
      esc.textContent = head;                                  // names come from game text: never as HTML
      var html = '<div class="t-head">' + esc.innerHTML + '</div>';
      var first = hist[0][2], last = hist[hist.length - 1][3];
      if (hist.length > 1 && typeof first === 'number' && typeof last === 'number' && first !== 0) {
        var p = (last - first) / Math.abs(first) * 100;
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
          var q = (h[3] - h[2]) / Math.abs(h[2]) * 100;
          if (Math.abs(q) >= 0.05) {
            pill = '<span class="' + cls + ' pct" data-g="' + pctGrade(q) + '">' + (q > 0 ? '+' : '') + q.toFixed(1) + '%</span>';
          }
        }
        // fixed columns: date | was | → | now | % — a first value sits under "now" like every other row
        var first = (h[2] === null || h[2] === undefined);
        html += '<li><span class="d">' + h[1] + '</span>' +
          '<span class="o">' + (first ? '' : fmtU(h[2], digits)) + '</span>' +
          '<span class="arrow">' + (first ? '' : '→') + '</span>' +
          '<span class="n ' + (first ? 'dir-changed' : cls) + '">' + fmtU(h[3], digits) + '</span>' +
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

  /* ---------- hover cards: what a patch did. ONE renderer for a change-matrix cell, an entity page's strip
     tile (the whole patch) and an ability card's trail square (that ability in the patch): head, counts by
     tag, "N not in patch notes", the biggest changes grouped by ability, a foot. Each page's JSON is parsed
     on the first hover, not at load (heroes/changes carries 313 KB of it); the older history bands are
     <template>s, so the cards never read the page (builders/history_view.strip_data). ---------- */
  safe('dyn-tip', function () {
    var SEL = 'table.dyn .dsq, .patch-strip .ps-tile[data-k], .trail a.sq[data-p], a.ac-last[data-p], a.lu[data-k]';
    if (!document.querySelector(SEL)) return;
    var ORDER = ['new', 'rework', 'buff', 'nerf', 'del', 'on', 'off', 'up', 'down', 'mech', 'changed'];
    var tip = null, current = null, strip, feed;
    function txt(s) { var e = document.createElement('span'); e.textContent = s == null ? '' : String(s); return e.innerHTML; }
    function matrixData(id) {                   // shared with dyn-parts: each blob parsed once
      var all = window.__dyn = window.__dyn || {};
      if (!all[id]) {
        var b = document.querySelector('script.dyn-data[data-for="' + id + '"]');
        if (b) all[id] = JSON.parse(b.textContent);
      }
      return all[id];
    }
    function stripData() {
      if (strip === undefined) {
        var b = document.querySelector('script.strip-data');
        strip = b ? JSON.parse(b.textContent) : null;
      }
      return strip;
    }
    function feedData() {
      if (feed === undefined) {
        var b = document.querySelector('script.feed-data');
        feed = b ? JSON.parse(b.textContent) : null;
      }
      return feed;
    }
    function countsHtml(counts, d) {
      return '<div class="dt-counts">' + ORDER.filter(function (t) { return counts[t]; }).map(function (t) {
        var word = (counts[t] === 1 && d.word1 && d.word1[t]) || d.words[t] || t;     // "1 buff", "2 buffs"
        return '<span class="pip ' + t + '">' + ((d.icons || {})[t] || '') + counts[t] + '<em>' + txt(word) + '</em></span>';
      }).join('') + '</div>';
    }
    function valsHtml(old, now, tag) {
      return old && now ? txt(old) + '<i>→</i><b class="t-' + tag + '">' + txt(now) + '</b>'
        : '<b class="t-' + tag + '">' + txt(now || old) + '</b>';
    }
    /* one change in an entity card: its tag, the eye when the notes left it out, the field, old → new */
    function rowHtml(d, field, old, now, tag, hidden) {
      return '<tr' + (hidden ? ' class="dt-hid"' : '') + '><td class="dt-tg"><span class="tag ' + tag + '">' +
        txt(tag.toUpperCase()) + '</span></td><td class="dt-field">' + (hidden ? '<span class="dt-e">' + d.eye + '</span>' : '') +
        field + '</td><td class="dt-vals">' + valsHtml(old, now, tag) + '</td></tr>';
    }
    /* o: icon, name, patch, named, counts, hidden, rows (table html), more, foot, d (words / icons / eye) */
    function card(o) {
      var html = '<div class="dt-head">' + (o.icon ? '<img src="' + txt(o.icon) + '" alt="">' : '') +
        (o.name ? '<span class="dt-name">' + txt(o.name) + '</span>' : '') +
        '<span class="dt-patch' + (o.named ? ' named' : '') + '">' + txt(o.patch) + '</span></div>';
      if (o.counts) html += countsHtml(o.counts, o.d);
      if (o.hidden) html += '<div class="dt-eye">' + (o.d.eye || '') + o.hidden + ' not in patch notes</div>';
      if (o.rows) html += '<table class="dt-rows">' + o.rows + '</table>';
      if (o.foot) html += '<div class="dt-foot">' + (o.more > 0 ? '+' + o.more + ' more · ' : '') + txt(o.foot) + '</div>';
      return html;
    }
    function total(counts) { var n = 0; Object.keys(counts).forEach(function (t) { n += counts[t]; }); return n; }

    /* a change-matrix cell: who, which patch, its counts, the biggest changes by part */
    function matrixCard(a) {
      var table = a.closest('table.dyn');
      var d = table && matrixData(table.id);
      var k = a.getAttribute('data-k');
      if (!d || k === null) return null;
      var c = d.cells[+k], p = d.patches[c[0]], tr = a.closest('tr');
      var counts = c[1], samples = c[2];
      var part = table.getAttribute('data-part') || 'all';
      if (part !== 'all' && c[3]) {             // the filter: only this part's counts and changes
        counts = c[3][part] || {};
        samples = samples.filter(function (s) { return s[5] === part; });
      }
      // a hero's changes are grouped by part (base stats, weapon, abilities) and name the ability — an
      // item's or unit's are about the row itself
      // a Game system's row names the entry each change is about too (the Soul Urn's pickup, its aura…)
      var hero = !!c[3], what = hero || table.hasAttribute('data-what'), lastPart = null, rows = '';
      samples.forEach(function (s) {
        if (hero && s[5] !== lastPart && d.parts && d.parts[s[5]] && part === 'all') {
          lastPart = s[5];
          rows += '<tr class="dt-part p-' + s[5] + '"><td colspan="3">' + txt(d.parts[s[5]]) + '</td></tr>';
        }
        rows += '<tr>' + (what ? '<td class="dt-what">' + txt(s[0]) + '</td>' : '') +
          '<td class="dt-field">' + txt(s[1]) + '</td><td class="dt-vals">' + valsHtml(s[2], s[3], s[4]) + '</td></tr>';
      });
      return card({ icon: tr.getAttribute('data-icon'), name: tr.getAttribute('data-name'), patch: p[1], named: p[2],
                    counts: counts, d: d, rows: rows, more: total(counts) - samples.length,
                    foot: 'click for its history at this patch' });
    }

    /* an entity page: a strip tile = the patch's biggest changes by ability; a trail square or an ability
       card's "last change" = that ability's own changes in that patch */
    function rowsHtml(d, groups, pick, limit, heads) {
      var html = '', shown = 0;
      groups.forEach(function (g) {
        var ref = d.g[g[0]];
        var rows = g[3].filter(pick).sort(function (x, y) { return x[5] - y[5]; }).slice(0, limit);
        if (!rows.length) return;
        if (heads && ref[0]) {
          html += '<tr class="dt-grp"><td colspan="3">' + (ref[1] ? '<span class="dt-ic' + (ref[3] ? ' ult' : '') +
            '"><img src="' + txt(ref[1]) + '" alt=""></span>' : '') + txt(ref[0]) + '</td></tr>';
        }
        rows.forEach(function (s) {
          shown++;
          html += rowHtml(d, txt(s[0]), s[1], s[2], s[3], s[4]);
        });
      });
      return { html: html, shown: shown };
    }
    function stripCard(a) {
      var d = stripData();
      if (!d) return null;
      var tile = null, k = a.getAttribute('data-k'), pid = a.getAttribute('data-p'), ab = a.getAttribute('data-ab');
      if (k !== null) tile = d.t[+k];
      else for (var i = 0; i < d.t.length && !tile; i++) if (d.t[i][0] === pid) tile = d.t[i];
      if (!tile) {                               // a band the strip leaves out (work before release)
        var label = a.getAttribute('aria-label');
        return label ? card({ patch: label, d: d }) : null;
      }
      var foot = 'click to open this patch';
      if (!ab) {
        var top = rowsHtml(d, tile[5], function (s) { return s[5] < d.top; }, 99, true);
        var n = total(tile[3]);
        return card({ patch: tile[1], named: tile[2], counts: tile[3], hidden: tile[4], d: d, rows: top.html,
                      more: n - top.shown, foot: foot });
      }
      var mine = tile[5].filter(function (g) { return (' ' + d.g[g[0]][2] + ' ').indexOf(' ' + ab + ' ') >= 0; });
      if (!mine.length) return null;
      var ref = d.g[mine[0][0]], counts = {}, hidden = 0;
      mine.forEach(function (g) {
        Object.keys(g[1]).forEach(function (t) { counts[t] = (counts[t] || 0) + g[1][t]; });
        hidden += g[2];
      });
      var own = rowsHtml(d, mine, function () { return true; }, d.per, false);
      return card({ icon: ref[1], name: ref[0], patch: tile[1], named: tile[2], counts: counts, hidden: hidden, d: d,
                    rows: own.html, more: total(counts) - own.shown, foot: foot });
    }

    /* the home page's feed: an icon = what one update did to that hero / item / unit page */
    function feedCard(a) {
      var d = feedData(), e = d && d.c[+a.getAttribute('data-k')];
      if (!e) return null;
      var u = d.u[e[0]], rows = '', img = a.querySelector('img');
      e[3].forEach(function (s) {
        rows += rowHtml(d, (s[0] ? '<b class="dt-what">' + txt(s[0]) + '</b> · ' : '') + txt(s[1]), s[2], s[3], s[4], s[5]);
      });
      return card({ icon: img && img.getAttribute('src'), name: a.getAttribute('data-name'), patch: u[0], named: u[1],
                    counts: e[1], hidden: e[2], d: d, rows: rows, more: total(e[1]) - e[3].length,
                    foot: 'click for its history at this patch' });
    }

    function place(a) {
      var r = a.getBoundingClientRect(), tw = tip.offsetWidth, th = tip.offsetHeight;
      var nav = document.querySelector('.top-nav');
      var minY = (nav ? nav.getBoundingClientRect().bottom : 0) + 8;       // never under the sticky site bar
      var x = Math.min(Math.max(8, r.left + r.width / 2 - tw / 2), document.documentElement.clientWidth - tw - 8);
      var y = r.bottom + 8;
      if (y + th > window.innerHeight - 8) y = r.top - th - 8;
      tip.style.left = x + 'px';
      tip.style.top = Math.max(minY, y) + 'px';
    }
    function hide() { if (tip) tip.classList.remove('on'); current = null; }
    function over(ev) {
      var a = ev.target.closest && ev.target.closest(SEL);
      if (!a) { if (current) hide(); return; }
      if (a === current) return;                 // moving inside the same tile: nothing to redraw
      var html = a.classList.contains('dsq') ? matrixCard(a) : a.classList.contains('lu') ? feedCard(a) : stripCard(a);
      if (!html) { hide(); return; }
      if (!tip) {
        tip = document.createElement('div');
        tip.className = 'dyn-tip px-frame';
        document.body.appendChild(tip);
      }
      tip.innerHTML = html;
      tip.classList.add('on');
      current = a;
      place(a);
    }
    document.addEventListener('mouseover', over);
    document.addEventListener('focusin', over);              // a tile reached with the keyboard shows it too
    document.addEventListener('focusout', hide);
    window.addEventListener('scroll', hide, true);
  });

  /* ---------- hero changes: a filter narrows every tile to one part (stats / weapon / abilities) ---------- */
  /* the tiles follow both filters: the hero part (All / Stats / Weapon / Abilities) and the hidden
     tags — hiding BUFF used to drop the stripe but keep the tile's number */
  safe('dyn-parts', function () {
    var tables = document.querySelectorAll('table.dyn');
    if (!tables.length) return;
    var order = ['new', 'rework', 'buff', 'nerf', 'del', 'on', 'off', 'up', 'down', 'mech', 'changed'];
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
      var all = window.__dyn = window.__dyn || {};          // shared with dyn-tip's hover card: parsed once
      var d = all[table.id] || (all[table.id] = JSON.parse(blob.textContent));
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
        // chosen = aria-pressed: the class "on" is the ON tag's colour (a chosen NERF turned green)
        btn.setAttribute('aria-pressed', i < 0 ? 'true' : 'false');
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
      // a resize keeps the user's place: a height-only one (a phone's URL bar hiding while the page
      // scrolls) does nothing, a new width keeps the same distance from the newest end — re-scrolling to
      // the end threw a reader of older patches back to the newest ones (review 2026-10-04)
      var pending = false, lastW = window.innerWidth;
      window.addEventListener('resize', function () {
        if (pending || window.innerWidth === lastW) return;
        pending = true;
        requestAnimationFrame(function () {
          pending = false;
          lastW = window.innerWidth;
          var gap = sc.scrollWidth - sc.scrollLeft - sc.clientWidth;
          fit();
          sc.scrollLeft = Math.max(0, sc.scrollWidth - sc.clientWidth - gap);
        });
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
    /* graded by rank (Sloppy's mana table): each column's distinct values ranked, the middle fifth left
       plain, then 4 steps of green (better) or red (worse) — a binary +-14% hid the spread. An item's stat
       chip ranks with its column. Values rank with their sign, as the column sorts: a stat column holds
       bonuses, so a negative one (Spirit Sap's -30 Spirit Power, Weighted Shots' -14% Stamina Recovery
       drawback) is the worst, not the biggest (by size they read deep green, review 2026-10-04).
       A table with data-heat-by="tier" ranks within each row's tier (items of one price); "Souls per
       point" evens the price out and ranks over all. */
    function heat(table, on) {
      table.querySelectorAll('.' + CLS.join(', .')).forEach(function (el) { el.classList.remove.apply(el.classList, CLS); });
      if (!on) return;
      var cols = {};
      var by = table.classList.contains('per-soul') ? null : table.getAttribute('data-heat-by');
      // the heat's direction: data-hpol when set ("Souls per point": cheaper per point is better; a
      // price column: no heat), else the stat's own data-pol, which the history tooltip reads too
      table.querySelectorAll('tbody td[data-col], tbody .sc[data-col]').forEach(function (el) {
        var v = parseFloat(el.getAttribute('data-sort'));
        var pol = parseInt(el.getAttribute('data-hpol') || el.getAttribute('data-pol') || '1', 10);
        if (isNaN(v) || pol === 0) return;
        var key = el.getAttribute('data-col') + (by ? '|' + el.closest('tr').getAttribute('data-' + by) : '');
        (cols[key] = cols[key] || []).push([v, el, pol]);
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
      // a column's cells change only when its state does (or `all`: cells built since, Item Stats' stat
      // columns, take their header's state)
      function setOff(h, off, all) {
        if (!all && h.classList.contains('grp-off') === off) return;
        h.classList.toggle('grp-off', off);
        table.querySelectorAll('td[data-col="' + h.getAttribute('data-col') + '"]').forEach(function (td) {
          td.classList.toggle('grp-off', off);
        });
      }
      function shownUnfolded(h) {        // would the header show if its group were open (header only)
        if (!h.classList.contains('grp-off')) return shown(h);
        h.classList.remove('grp-off');
        var s = shown(h);
        h.classList.add('grp-off');
        return s;
      }
      function refold(th, all) {
        var hs = ofGroup(th.getAttribute('data-group'));
        var folded = th.classList.contains('folded');
        var keep = folded ? hs.filter(function (h) { return !h.classList.contains('col-off') && shownUnfolded(h); })[0] : null;
        hs.forEach(function (h) { setOff(h, folded && h !== keep, all); });
      }
      /* every group, folded or not: a group just unfolded has to drop its grp-off too — refolding only the
         folded ones left an unfolded group's columns hidden for good (review 2026-10-04: Hero Stats 34 ->
         21 -> 21 columns on fold / unfold) */
      function recount(all) {
        cats.forEach(function (th) { refold(th, all === true); });
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
      table.addEventListener('statcols', function () { recount(true); });
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
    function perSoul() {
      table.classList.toggle('per-soul', per.checked);
      sppAll();
      if (window.__reheat) window.__reheat();
    }
    if (per) {
      per.addEventListener('change', perSoul);
      if (per.checked) perSoul();               // the browser restored the box on "back": values follow it
    }

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
      sw.addEventListener('change', function () {
        if (sw.checked) { build(); return; }
        // closed while one of them sorted the rows: no visible header would show or undo that sort
        var col = table.__sortedBy && table.__sortedBy();
        var th = col && table.querySelector('thead tr.cols th[data-col="' + col + '"]');
        if (th && th.hasAttribute('data-cell-cls') && table.__resetSort) table.__resetSort();
      });
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

  /* ---------- entity history: older patches render when opened; the toolbar filters rows ---------- */
  /* (builders/history_view.py) tags are a multi-select, a part (Stats / Weapon / Abilities) and an
     ability one at a time (click again to clear); "Not in patch notes" and "Before release" are classes on
     #history that CSS reads — the filter re-runs after them. Every filter, the eye included, opens the
     bands it matches, folds the empty ones away and recounts each band's counters from its shown rows
     (owner 2026-10-04: the eye left Viscous's 21 bands closed, the counters ignored every filter). */
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
    // a row that stands for changes it does not list (a new unit's "Added to the game" over its 12 key
    // fields) says which in data-n: "tag:changes:hidden …" (cards.entity_rows)
    function behind(r) {
      if (r.__b === undefined) {
        var n = r.getAttribute('data-n');
        r.__b = n ? n.split(' ').map(function (e) { var p = e.split(':'); return [p[0], +p[1], +p[2]]; }) : null;
      }
      return r.__b;
    }
    // a row of a rule for every hero (builders/shared_rows.py: the "All heroes: N changes" link row) is counted
    // apart: no band counter and no "Not in patch notes" count holds it
    function inAll(r) {
      if (r.__all === undefined) r.__all = !!r.closest('.shr-all');
      return r.__all;
    }
    function tagOk(r) {
      if (!state.tags.length) return true;
      var bs = behind(r);
      if (!bs) return state.tags.indexOf(tagOf(r)) >= 0;
      for (var i = 0; i < bs.length; i++) if (state.tags.indexOf(bs[i][0]) >= 0) return true;
      return false;
    }
    // the banner's counters while a filter is on: the shown rows by tag (a code line is no counted change),
    // the eye's count; the built numbers come back when the filters clear
    function recount(b, active, onlyHidden) {
      var bc = b.querySelector('summary .bc');
      if (!bc) return;
      var pips = bc.querySelectorAll('.tsum .pip'), eye = bc.querySelector('.ec-n');
      // "+34 for all heroes": only while its link row is shown (a tag or the eye never keeps it)
      var shr = bc.querySelectorAll('.shr-chip');
      if (!active) {
        if (!b.__rc) return;
        b.__rc = false;
        pips.forEach(function (p) { if (p.__n !== undefined) p.lastChild.nodeValue = p.__n; p.classList.remove('n0'); });
        if (eye) { eye.textContent = eye.__t; eye.parentNode.classList.remove('n0'); }
        shr.forEach(function (c) { c.classList.remove('n0'); });
        return;
      }
      b.__rc = true;
      var allShown = !!b.querySelector('.erow.shr-all:not(.f-out)');
      shr.forEach(function (c) { c.classList.toggle('n0', !allShown); });
      var counts = {}, hidden = 0;
      b.querySelectorAll('.erow').forEach(function (r) {
        // a code line and a name / description change (text_rows) are no counted change
        if (r.classList.contains('f-out') || r.classList.contains('st-code') || r.classList.contains('st-text') ||
            r.parentNode.tagName === 'SUMMARY' || inAll(r)) return;
        var bs = behind(r);
        if (bs) {
          bs.forEach(function (e) {
            if (state.tags.length && state.tags.indexOf(e[0]) < 0) return;
            counts[e[0]] = (counts[e[0]] || 0) + (onlyHidden ? e[2] : e[1]);
            hidden += e[2];
          });
          return;
        }
        var t = tagOf(r);
        counts[t] = (counts[t] || 0) + 1;
        if (r.classList.contains('is-hidden')) hidden++;       // render.NOT_IN_NOTES: hidden or no notes at all
      });
      pips.forEach(function (p) {
        if (!p.lastChild || p.lastChild.nodeType !== 3) return;
        if (p.__n === undefined) p.__n = p.lastChild.nodeValue;
        var n = counts[p.classList[1]] || 0;
        p.lastChild.nodeValue = n;
        p.classList.toggle('n0', !n);
      });
      if (eye) {
        if (eye.__t === undefined) eye.__t = eye.textContent;
        eye.textContent = hidden + ' not in notes';
        eye.parentNode.classList.toggle('n0', !hidden);
      }
    }
    function apply() {
      var onlyHidden = box.classList.contains('only-hidden'), dev = box.classList.contains('show-dev');
      var active = !!(state.tags.length || state.area || state.ab || onlyHidden);
      box.classList.toggle('filtering', active);
      // a tag or the eye picks rows: a name / description change is none (text_rows); a part or ability keeps it
      box.classList.toggle('filtering-rows', !!(state.tags.length || onlyHidden));
      var blocks = box.querySelectorAll('details.pblock');
      // a band still in its <template> says what it holds (data-tags / -abs / -areas, has-hidden): one that
      // cannot match is folded away unstamped (the first filter stamped all 33 of Calico's)
      function mayMatch(b) {
        var has = function (attr, v) { return (' ' + (b.getAttribute(attr) || '') + ' ').indexOf(' ' + v + ' ') >= 0; };
        return !(state.tags.length && !state.tags.some(function (t) { return has('data-tags', t); })) &&
               !(state.ab && !state.ab.split(' ').some(function (id) { return has('data-abs', id); })) &&
               !(state.area && !has('data-areas', state.area)) &&
               !(onlyHidden && !b.classList.contains('has-hidden'));
      }
      blocks.forEach(function (b) {
        if (active && b.querySelector('template.hp-t') && !mayMatch(b)) { b.classList.add('f-out'); return; }
        if (active) stamp(b);
        if (!active && !b.__rc && !b.querySelector('.f-out')) { b.classList.remove('f-out'); return; }
        var any = false;
        b.querySelectorAll('.hgroup').forEach(function (g) {
          // a merged group belongs to several parts ("t1 t2 t3": the same change on every tier)
          var gok = (!state.area || (' ' + g.getAttribute('data-area') + ' ').indexOf(' ' + state.area + ' ') >= 0) &&
                    (!state.ab || (' ' + state.ab + ' ').indexOf(' ' + g.getAttribute('data-ab') + ' ') >= 0);
          var gany = false;
          g.querySelectorAll('.erow').forEach(function (r) {
            if (r.parentNode.tagName === 'SUMMARY') return;      // a family's head follows its rows
            var ok = gok && tagOk(r) &&
                     (!onlyHidden || (r.classList.contains('is-hidden') && !inAll(r))) &&
                     (dev || !r.classList.contains('st-unreleased'));
            r.classList.toggle('f-out', !ok);
            gany = gany || ok;
          });
          // innermost first: a fold may hold folds of its own
          var fams = g.querySelectorAll('details.fam');
          for (var fi = fams.length - 1; fi >= 0; fi--) {
            fams[fi].classList.toggle('f-out',
              !fams[fi].querySelector(':scope > .erow:not(.f-out), :scope > details.fam:not(.f-out)'));
          }
          // a description change (a fold of its own, text_rows) keeps its group under a part or ability filter
          if (!gany && gok && !state.tags.length && !onlyHidden && g.querySelector('details.txt')) gany = true;
          g.classList.toggle('f-out', !gany);
          any = any || gany;
        });
        b.classList.toggle('f-out', !any);
        recount(b, active, onlyHidden);
        if (active && any && !b.open) b.open = true;            // a patch with a match opens
      });
    }
    var bar = document.querySelector('.hist-bar');
    if (!bar) return;
    function pressAll(attr, value) {           // one of the part / ability buttons, or none
      bar.querySelectorAll('[' + attr + ']').forEach(function (b) {
        var on = b.getAttribute(attr) === value;
        b.classList.toggle('on', on);
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    }
    // patch-anchor: a tile or square names a band or group the filters hide — clear them all and show it;
    // dev = also show the work before release (a dev-only band or group)
    window.__histReset = function (dev) {
      state.tags = []; state.area = null; state.ab = null;
      box.classList.remove('only-hidden');
      bar.querySelectorAll('[data-f-tag]').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
      pressAll('data-f-area', null);
      pressAll('data-f-ab', null);
      var eye = bar.querySelector('.hf-hidden');
      if (eye) { eye.classList.remove('on'); eye.setAttribute('aria-pressed', 'false'); }
      if (dev) {
        box.classList.add('show-dev');
        var sw = bar.querySelector('.hf-dev');
        if (sw) { sw.classList.add('on'); sw.setAttribute('aria-pressed', 'true'); }
      }
      apply();
    };
    // #ab-<ability id> (an ability card's "History" link, Sloppy's ?ability=) filters to that ability
    function fromHash() {
      if (location.hash.indexOf('#ab-') !== 0) return;
      var id;
      try { id = decodeURIComponent(location.hash.slice(4)); } catch (e) { return; }
      // the chip that holds this id (one chip may stand for namesakes: "id1 id2")
      var chip = Array.prototype.filter.call(bar.querySelectorAll('[data-f-ab]'), function (b) {
        return b.getAttribute('data-f-ab').split(' ').indexOf(id) >= 0;
      })[0];
      state.ab = chip ? chip.getAttribute('data-f-ab') : id;
      if (chip && chip.classList.contains('gone')) {
        chip.parentNode.classList.add('show-gone');
        var gb = chip.parentNode.querySelector('.hf-gone-btn');
        if (gb) { gb.classList.add('on'); gb.setAttribute('aria-pressed', 'true'); }
      }
      pressAll('data-f-ab', state.ab);
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
        // chosen = aria-pressed: the class "on" is the ON tag's colour (a chosen NERF turned green)
        btn.setAttribute('aria-pressed', i < 0 ? 'true' : 'false');
      } else if (area) {
        state.area = state.area === area ? null : area;
        pressAll('data-f-area', state.area);
      } else if (ab) {
        state.ab = state.ab === ab ? null : ab;
        pressAll('data-f-ab', state.ab);
      }
      // "Not in patch notes" and "Before release" toggle a class on #history first (the generic toggle)
      setTimeout(apply, 0);
    });
  });

  /* ---------- #p-<patch>: a history band named in the address — or clicked on this page (a strip tile,
     an ability card's trail square or its last change) — opens and comes into view, even when a filter
     or "Before release" hid it and even when the address already names it ---------- */
  safe('patch-anchor', function () {
    // a band or group a filter (or "Before release") hides: clear the filters; still hidden and work before
    // release -> show that too. The band can show while the group is filtered out (another ability's rows
    // kept it): the group is checked on its own, or the square scrolled nowhere and lit a hidden group
    function reveal(x) {
      if (!x || x.offsetParent !== null) return;
      var reset = window.__histReset;
      if (reset) reset();
      if (x.offsetParent !== null || !(x.classList.contains('dev-only') || x.closest('.dev-only') ||
          x.querySelector('.st-unreleased'))) return;
      var hist = x.closest('.hblocks');
      if (reset) reset(true);
      else if (hist) hist.classList.add('show-dev');
    }
    function go(ab) {
      if (location.hash.indexOf('#p-') !== 0) return;
      var id;
      try { id = decodeURIComponent(location.hash.slice(1)); } catch (e) { return; }
      var el = document.getElementById(id);
      if (!el) return;
      if (el.tagName === 'DETAILS') {
        reveal(el);
        if (window.__histStamp) window.__histStamp(el);
        el.open = true;
      }
      // an ability's square: its group in the band, lit for a moment
      var group = ab && Array.prototype.filter.call(el.querySelectorAll('.hgroup'), function (g) {
        return g.getAttribute('data-ab') === ab;
      })[0];
      if (group) {
        reveal(group);
        group.classList.add('flash');
        setTimeout(function () { group.classList.remove('flash'); }, 1600);
      }
      (group || el).scrollIntoView({ block: 'start' });
    }
    go();
    window.addEventListener('hashchange', function () { go(); });
    document.addEventListener('click', function (ev) {
      var a = ev.target.closest && ev.target.closest('a[href^="#p-"]');
      if (!a || ev.button !== 0 || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey) return;
      var href = a.getAttribute('href');
      if (!document.getElementById(href.slice(1))) return;
      ev.preventDefault();
      if (location.hash !== href) {
        try { history.pushState(null, '', href); } catch (e) { location.hash = href; return; }
      }
      go(a.getAttribute('data-ab'));
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
