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
      var hero = !!c[3], lastPart = null, rows = '';
      samples.forEach(function (s) {
        if (hero && s[5] !== lastPart && d.parts && d.parts[s[5]] && part === 'all') {
          lastPart = s[5];
          rows += '<tr class="dt-part p-' + s[5] + '"><td colspan="3">' + txt(d.parts[s[5]]) + '</td></tr>';
        }
        rows += '<tr>' + (hero ? '<td class="dt-what">' + txt(s[0]) + '</td>' : '') +
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
  safe('dyn-scroll', function () {
    document.querySelectorAll('table.dyn').forEach(function (t) {
      var sc = t.closest('.table-scroll');
      if (!sc) return;
      function toEnd() { sc.scrollLeft = sc.scrollWidth; }
      toEnd();
      new MutationObserver(toEnd).observe(t, { attributes: true, attributeFilter: ['class'] });
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
    // every table on the page (items and units come as one table per category), ranked within itself
    btn.addEventListener('click', function () {
      var on = !btn.classList.contains('on');
      btn.classList.toggle('on', on);
      document.querySelectorAll('table.stats').forEach(function (table) { heat(table, on); });
    });
    // values that change in place (Boons, "Souls per point") re-rank the heat if it is on
    window.__reheat = function () {
      if (!btn.classList.contains('on')) return;
      document.querySelectorAll('table.stats').forEach(function (table) { heat(table, true); });
    };
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

  /* ---------- stats tables: a click on a group header folds the group to its first column ---------- */
  safe('col-groups', function () {
    document.querySelectorAll('table.stats').forEach(function (table) {
      var cats = Array.prototype.slice.call(table.querySelectorAll('thead tr.cats th.cat[data-group]'));
      var heads = Array.prototype.slice.call(table.querySelectorAll('thead tr.cols th[data-group]'));
      if (cats.length < 2) return;
      function recount() {
        cats.forEach(function (th) {
          var g = th.getAttribute('data-group');
          var n = heads.filter(function (h) {
            return h.getAttribute('data-group') === g && getComputedStyle(h).display !== 'none';
          }).length;
          if (n) th.colSpan = n;
        });
      }
      cats.forEach(function (th) {
        th.classList.add('foldable');
        th.addEventListener('click', function () {
          var g = th.getAttribute('data-group'), off = !th.classList.contains('folded');
          th.classList.toggle('folded', off);
          heads.filter(function (h) { return h.getAttribute('data-group') === g; }).slice(1).forEach(function (h) {
            var key = h.getAttribute('data-col');
            h.classList.toggle('grp-off', off);
            table.querySelectorAll('td[data-col="' + key + '"]').forEach(function (td) { td.classList.toggle('grp-off', off); });
          });
          recount();
        });
      });
      // the Details switch shows / hides a whole group: the spans follow
      document.querySelectorAll('[data-toggle-class="show-details"]').forEach(function (b) {
        b.addEventListener('click', function () { setTimeout(recount, 0); });
      });
    });
  });

  /* ---------- Item Stats: chips by category / tier / kind; columns no shown row fills hide; souls per point ---------- */
  safe('item-filter', function () {
    var table = document.getElementById('items-table');
    if (!table) return;
    var bar = document.querySelector('.toolbar');
    var sel = { cat: [], tier: [], kind: [] };
    var rows = Array.prototype.slice.call(table.tBodies[0].rows);
    var heads = Array.prototype.slice.call(table.querySelectorAll('thead tr.cols th[data-col]'))
      .filter(function (th) { return th.getAttribute('data-col') !== 'name'; });
    var cats = Array.prototype.slice.call(table.querySelectorAll('thead tr.cats th[data-group]'));
    // td per (row, column), read once
    var cells = rows.map(function (r) {
      var m = {};
      Array.prototype.forEach.call(r.querySelectorAll('td[data-col]'), function (td) { m[td.getAttribute('data-col')] = td; });
      return m;
    });
    function shown(r) { return !r.classList.contains('f-out') && !r.classList.contains('hidden-el'); }
    function columns() {
      var count = {};
      heads.forEach(function (th) {
        var key = th.getAttribute('data-col'), any = false;
        for (var i = 0; i < rows.length && !any; i++) {
          var td = cells[i][key];
          any = shown(rows[i]) && td && td.getAttribute('data-sort') !== '';
        }
        th.classList.toggle('col-off', !any);
        cells.forEach(function (m) { if (m[key]) m[key].classList.toggle('col-off', !any); });
        if (any) count[th.getAttribute('data-group')] = (count[th.getAttribute('data-group')] || 0) + 1;
      });
      cats.forEach(function (th) {        // the group headers span what is left of them
        var n = count[th.getAttribute('data-group')] || 0;
        th.classList.toggle('col-off', !n);
        if (n) th.colSpan = n;
      });
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
    // what one point of a stat costs: cost / value (lower is better), back to the values when off
    var per = bar.querySelector('[data-souls-per]');
    if (per) per.addEventListener('change', function () {
      var on = per.checked;
      table.classList.toggle('per-soul', on);
      rows.forEach(function (r, i) {
        var cost = parseFloat(r.getAttribute('data-cost'));
        heads.forEach(function (th) {
          if (th.getAttribute('data-group') !== 'Stats') return;
          var td = cells[i][th.getAttribute('data-col')];
          if (!td) return;
          if (on) {
            var v = parseFloat(td.getAttribute('data-sort'));
            if (isNaN(v) || v <= 0 || isNaN(cost)) return;
            td.__orig = [td.innerHTML, td.getAttribute('data-sort'), td.getAttribute('data-pol')];
            var s = cost / v;
            td.textContent = s >= 10 ? Math.round(s) : s.toFixed(1);
            td.setAttribute('data-sort', s);
            td.setAttribute('data-pol', '-1');
          } else if (td.__orig) {
            td.innerHTML = td.__orig[0];
            td.setAttribute('data-sort', td.__orig[1]);
            td.setAttribute('data-pol', td.__orig[2]);
            td.__orig = null;
          }
        });
      });
      if (window.__reheat) window.__reheat();
    });
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
    // the banner's counters while a filter is on: the shown rows by tag (a code line is no counted change),
    // the eye's count; the built numbers come back when the filters clear
    function recount(b, active) {
      var bc = b.querySelector('summary .bc');
      if (!bc) return;
      var pips = bc.querySelectorAll('.tsum .pip'), eye = bc.querySelector('.ec-n');
      if (!active) {
        if (!b.__rc) return;
        b.__rc = false;
        pips.forEach(function (p) { if (p.__n !== undefined) p.lastChild.nodeValue = p.__n; p.classList.remove('n0'); });
        if (eye) { eye.textContent = eye.__t; eye.parentNode.classList.remove('n0'); }
        return;
      }
      b.__rc = true;
      var counts = {}, hidden = 0;
      b.querySelectorAll('.erow').forEach(function (r) {
        if (r.classList.contains('f-out') || r.classList.contains('st-code') || r.parentNode.tagName === 'SUMMARY') return;
        var t = tagOf(r);
        counts[t] = (counts[t] || 0) + 1;
        if (r.classList.contains('st-hidden')) hidden++;
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
        recount(b, active);
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
    // patch-anchor: a tile or square names a band the filters hide — clear them all and show it
    window.__histReset = function () {
      state.tags = []; state.area = null; state.ab = null;
      box.classList.remove('only-hidden');
      bar.querySelectorAll('[data-f-tag]').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
      pressAll('data-f-area', null);
      pressAll('data-f-ab', null);
      var eye = bar.querySelector('.hf-hidden');
      if (eye) eye.classList.remove('on');
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
      if (chip && chip.classList.contains('gone')) chip.parentNode.classList.add('show-gone');
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
    bar.addEventListener('change', function () { setTimeout(apply, 0); });
  });

  /* ---------- #p-<patch>: a history band named in the address — or clicked on this page (a strip tile,
     an ability card's trail square or its last change) — opens and comes into view, even when a filter
     or "Before release" hid it and even when the address already names it ---------- */
  safe('patch-anchor', function () {
    function reveal(el) {
      if (el.offsetParent !== null) return;
      if (window.__histReset) window.__histReset();
      var hist = el.closest('.hblocks');
      if (el.offsetParent === null && hist && el.classList.contains('dev-only')) {
        hist.classList.add('show-dev');
        var sw = document.querySelector('.hf-dev');
        if (sw) { sw.classList.add('on'); sw.setAttribute('aria-pressed', 'true'); }
      }
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
