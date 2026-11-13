  /* a change-matrix cell's rows not in the patch notes (builders/dynamics_page._hidden_tail): counts by tag, by part
     (heroes) and samples. A cell with none hidden is empty; one with every row hidden reads its own counts, parts and
     the samples that carry the eye (s[6]) — the build writes the three only when they differ. `withSamples`: the
     hover card's; a redraw of ~1.5k tiles needs the counts only */
  var NO_HIDDEN = { counts: {}, parts: null, samples: [] };
  function dynHidden(c, withSamples) {
    if (!c[4]) return NO_HIDDEN;
    return { counts: c[6] || c[1], parts: c[7] || c[3],
             samples: withSamples ? c[8] || c[2].filter(function (s) { return s[6]; }) : null };
  }

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
    // a value inside an attribute: its quotes too (innerHTML escapes & < > only)
    function attr(s) { return txt(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }
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
    // `net`: the build's net mark of the patch for this entity (builders/weights.net_of; d.nets its words): one quiet
    // chip at the end of the counts, as on the band's banner — tied to the last count, so it never wraps to a line
    // of its own (review 2026-10-17: "MIXED" alone under the counts)
    function countsHtml(counts, d, net) {
      var pips = ORDER.filter(function (t) { return counts[t]; }).map(function (t) {
        var word = (counts[t] === 1 && d.word1 && d.word1[t]) || d.words[t] || t;     // "1 buff", "2 buffs"
        return '<span class="pip ' + t + '">' + counts[t] + '<em>' + txt(word) + '</em></span>';     // icon: CSS
      });
      if (net && d.nets && d.nets[net]) {
        var chip = '<span class="net-chip net-' + net + '">' + txt(d.nets[net]) + '</span>';
        pips.push('<span class="dt-tail">' + (pips.pop() || '') + chip + '</span>');
      }
      return '<div class="dt-counts">' + pips.join('') + '</div>';
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
    /* o: icon, name, patch, named, counts, net, hidden, rows (table html), more, foot, d (words / icons / eye) */
    function card(o) {
      var html = '<div class="dt-head">' + (o.icon ? '<img src="' + attr(o.icon) + '" alt="">' : '') +
        (o.name ? '<span class="dt-name">' + txt(o.name) + '</span>' : '') +
        '<span class="dt-patch' + (o.named ? ' named' : '') + '">' + txt(o.patch) + '</span></div>';
      if (o.counts) html += countsHtml(o.counts, o.d, o.net);
      if (o.hidden) html += '<div class="dt-eye">' + (o.d.eye || '') + o.hidden + ' not in patch notes</div>';
      if (o.rows) html += '<table class="dt-rows">' + o.rows + '</table>';
      // a touch screen's first tap showed this card: the second opens it (as the tooltip module words an eye's link)
      var foot = o.foot && noHover ? o.foot.replace(/^click/, 'tap again') : o.foot;
      if (foot) html += '<div class="dt-foot">' + (o.more > 0 ? '+' + o.more + ' more · ' : '') + txt(foot) + '</div>';
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
      // "Not in patch notes": the card says what the tile shows — those rows only, their biggest changes
      var only = table.classList.contains('only-hid'), h = only ? dynHidden(c, true) : null;
      var counts = only ? h.counts : c[1], samples = only ? h.samples : c[2], parts = only ? h.parts : c[3];
      var part = table.getAttribute('data-part') || 'all';
      if (part !== 'all' && c[3]) {             // the filter: only this part's counts and changes
        counts = (parts || {})[part] || {};
        samples = samples.filter(function (s) { return s[5] === part; });
      }
      // chosen tags: the card says what the tile shows (the tile kept only BUFF's stripe, the card every tag)
      var sel = table.__sel || [];
      if (sel.length) {
        var kept = {};
        Object.keys(counts).forEach(function (t) { if (sel.indexOf(t) >= 0) kept[t] = counts[t]; });
        counts = kept;
        samples = samples.filter(function (s) { return sel.indexOf(s[4]) >= 0; });
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
        // the eye on a change the notes left out, as in the strip's and the home page's cards (s[6])
        rows += '<tr' + (s[6] ? ' class="dt-hid"' : '') + '>' + (what ? '<td class="dt-what">' + txt(s[0]) + '</td>' : '') +
          '<td class="dt-field">' + (s[6] ? '<span class="dt-e">' + d.eye + '</span>' : '') + txt(s[1]) +
          '</td><td class="dt-vals">' + valsHtml(s[2], s[3], s[4]) + '</td></tr>';
      });
      // how many the notes left out: the whole cell's (a part or tag filter does not split it), so only unfiltered;
      // under "Not in patch notes" every count shown is one
      var whole = part === 'all' && !sel.length;
      return card({ icon: tr.getAttribute('data-icon'), name: tr.getAttribute('data-name'), patch: p[1], named: p[2],
                    counts: counts, net: whole && !only ? c[5] : '', hidden: only ? total(counts) : whole ? c[4] : 0,
                    d: d, rows: rows,
                    more: total(counts) - samples.length,
                    foot: 'click for its history at this patch' });
    }

    /* an entity page: a strip tile = the patch's biggest changes by ability; a trail square or an ability
       card's "last change" = that ability's own changes in that patch */
    function rowsHtml(d, groups, pick, limit, heads, eyeSlot) {
      var html = '', shown = 0;
      groups.forEach(function (g) {
        var ref = d.g[g[0]];
        var all = g[3].filter(pick).sort(function (x, y) { return x[5] - y[5]; });
        var rows = all.slice(0, limit);
        // `eyeSlot`: a group with changes the notes left out shows one of them (history_view.tile_card keeps it)
        if (eyeSlot && g[2] && rows.length && !rows.some(function (s) { return s[4]; })) {
          var h = all.filter(function (s) { return s[4]; })[0];
          if (h) rows[rows.length - 1] = h;
        }
        if (!rows.length) return;
        if (heads && ref[0]) {
          // a rule for all is counted apart from the tile's counts: its group says its own number
          // (history_view.strip_data: the ref's fifth element), as the band's "+38 for all heroes" chip
          var n = ref[4] ? total(g[1]) : 0;
          html += '<tr class="dt-grp"><td colspan="3">' + (ref[1] ? '<span class="dt-ic' + (ref[3] ? ' ult' : '') +
            '"><img src="' + attr(ref[1]) + '" alt=""></span>' : '') + txt(ref[0]) +
            (n ? '<span class="dt-every">' + n + ' ' + (n === 1 ? 'change' : 'changes') + '</span>' : '') + '</td></tr>';
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
        // the rows of rules for all the card lists are not in the tile's counts: "+N more" counts them too
        var n = total(tile[3]);
        tile[5].forEach(function (g) { if (d.g[g[0]][4]) n += total(g[1]); });
        return card({ patch: tile[1], named: tile[2], counts: tile[3], net: tile[6], hidden: tile[4], d: d,
                      rows: top.html, more: n - top.shown, foot: foot });
      }
      var mine = tile[5].filter(function (g) { return (' ' + d.g[g[0]][2] + ' ').indexOf(' ' + ab + ' ') >= 0; });
      if (!mine.length) return null;
      var ref = d.g[mine[0][0]], counts = {}, hidden = 0;
      mine.forEach(function (g) {
        Object.keys(g[1]).forEach(function (t) { counts[t] = (counts[t] || 0) + g[1][t]; });
        hidden += g[2];
      });
      var own = rowsHtml(d, mine, function () { return true; }, d.per, false, true);
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
                    counts: e[1], net: e[4], hidden: e[2], d: d, rows: rows, more: total(e[1]) - e[3].length,
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
      // on a touch screen a mouseover off the tiles is not a finger leaving: the browser sends its own after a tap
      // (to update hover under the last touch point — CI's Linux Chromium hid the card that way, 2026-10-17); there a
      // finger put down elsewhere hides the card (touchStart)
      if (!a) { if (current && !(noHover && ev.type === 'mouseover')) hide(); return; }
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
      var r = a.getBoundingClientRect();
      shownAt = [r.left, r.top];
    }
    // a scroll hides the card only when it moved its tile: a scroll event can land after the tap that drew the card
    // (the scroll that brought the tile into sight, a finger's jitter) and hid it before its second tap (CI's Linux
    // Chromium, 2026-10-17)
    var shownAt = null;
    function scrolled() {
      if (!current) return;
      var r = current.getBoundingClientRect();
      if (shownAt && Math.abs(r.left - shownAt[0]) < 4 && Math.abs(r.top - shownAt[1]) < 4) return;
      hide();
    }
    document.addEventListener('mouseover', over);
    document.addEventListener('focusin', over);              // a tile reached with the keyboard shows it too
    // a touch screen has no hover (the tooltip module's rule): a tap fires mouseover and click together, so a tile
    // opened its link at once and its card was never seen (review 2026-10-17). The first tap shows the card, a second
    // tap on the same tile follows the link, a tap elsewhere hides it (its mouseover). Whether the card was up is
    // read when the touch begins, before the tap's own mouseover draws it — iOS drops the click of a tap whose
    // mouseover showed something, Android sends it. The compatibility focusout a tap may fire is not a leave.
    var noHover = window.matchMedia && window.matchMedia('(hover: none)').matches;
    var upBefore = null;
    function touchStart(ev) {
      var a = ev.target.closest && ev.target.closest(SEL);
      upBefore = a && a === current ? a : null;
      // a finger down anywhere else (not on the card itself) lets the card go
      if (!a && current && !(tip && tip.contains(ev.target))) hide();
    }
    if (noHover) {
      document.addEventListener('pointerdown', touchStart, true);
      document.addEventListener('touchstart', touchStart, { capture: true, passive: true });
      document.addEventListener('click', function (ev) {
        var a = ev.target.closest && ev.target.closest(SEL);
        // the second tap opens the link; so does a key (a click with no pointer: detail 0)
        if (!a || a === upBefore || ev.detail === 0) return;
        ev.preventDefault();
        if (a !== current) over(ev);
      }, true);
    } else {
      document.addEventListener('focusout', hide);
    }
    window.addEventListener('scroll', scrolled, true);
  });

  /* ---------- change matrices: rows by slot / tier (items) or role (heroes) — one choice per group, pressed again
     to clear; a row out is `f-out` (dynamics_page.toolbar `.dyn-rows`, review 2026-10-05) ---------- */
  safe('dyn-rows', function () {
    document.querySelectorAll('.dyn-rows[data-target]').forEach(function (box) {
      var table = document.querySelector(box.getAttribute('data-target'));
      if (!table) return;
      var chosen = {};
      box.addEventListener('click', function (ev) {
        var btn = ev.target.closest('button[data-rowf]');
        if (!btn) return;
        var f = btn.getAttribute('data-rowf'), v = btn.getAttribute('data-v');
        chosen[f] = chosen[f] === v ? null : v;
        // a px-btn shows it is pressed by `.on` (as the part buttons and Item Stats' chips do): with aria-pressed alone
        // a chosen Weapon / Tier 2 looked like the rest while the rows were filtered (2026-10-17)
        box.querySelectorAll('button[data-rowf="' + f + '"]').forEach(function (b) {
          var on = chosen[f] === b.getAttribute('data-v');
          b.setAttribute('aria-pressed', on ? 'true' : 'false');
          b.classList.toggle('on', on);
        });
        table.querySelectorAll('tbody tr').forEach(function (tr) {
          var out = false;
          // "*": a row of any value (a hero with no role yet, dynamics_page.hero_entries) no choice takes out
          for (var k in chosen) {
            var v = tr.getAttribute('data-' + k);
            if (chosen[k] && v !== '*' && v !== chosen[k]) out = true;
          }
          tr.classList.toggle('f-out', out);
        });
      });
    });
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
    // tiles out of sight (old columns, hidden rows) wait, marked dirty, until they show (2k tiles took 130 ms each
    // click); `onlyDirty`: redraw just those once they show
    var tiles = {};
    function redraw(table, onlyDirty) {
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
      // "Not in patch notes" (the bar's eye button): each tile is drawn from its rows the notes left out only
      var only = table.classList.contains('only-hid');
      function pick(counts, parts) { return part === 'all' ? counts : ((parts || {})[part] || {}); }
      function sum(counts) {
        var n = 0;
        order.forEach(function (t) { if (counts[t] && hidden.indexOf(t) < 0) n += counts[t]; });
        return n;
      }
      list.forEach(function (pair) {
        var a = pair[0], c = pair[1];
        if (onlyDirty && !pair[4]) return;
        if ((pair[2] && !showOld) || (pair[3] && !showExtra)) { pair[4] = true; return; }
        pair[4] = false;
        var h = dynHidden(c), hc = pick(h.counts, h.parts);
        var counts = only ? hc : pick(c[1], c[3]);
        var tags = order.filter(function (t) { return counts[t] && hidden.indexOf(t) < 0; }), total = sum(counts);
        var good = (counts.buff || 0) + (counts['new'] || 0) + (counts.on || 0);
        var bad = (counts.nerf || 0) + (counts.del || 0) + (counts.off || 0);
        // unfiltered, the cell's weighed net as the build marked it (builders/weights.net_of: c[5] = 'buff' / 'nerf' /
        // 'mix' / '' — the rule lives there only); a filter falls back to which side has more rows
        var whole = part === 'all' && !sel.length && !only, w = c[5];
        var net = whole && w != null ? 'net-' + (w || 'mix')
          : good > bad ? 'net-buff' : bad > good ? 'net-nerf' : 'net-mix';
        // the orange top: the tile shows a row the notes left out (under any filter: the part's and tags' own)
        var cls = 'dsq ' + (!total ? 'part-out' : net) + (total && sum(hc) ? ' hid' : '');
        // write only what changed: a text or class write re-lays the tile out
        if (a.className !== cls) a.className = cls;
        if (!total) return;
        a.style.background = stripes(counts, tags);
        if (a.firstChild.textContent !== String(total)) a.firstChild.textContent = total;
      });
    }
    // the part buttons of one toolbar (the table itself carries data-part once a part is chosen: a page-wide
    // [data-part] query toggled the class "on" on the table too)
    document.querySelectorAll('.dyn-parts button[data-part]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var table = document.querySelector(btn.getAttribute('data-target'));
        if (!table) return;
        btn.closest('.dyn-parts').querySelectorAll('button[data-part]').forEach(function (b) {
          b.classList.toggle('on', b === btn);
          b.setAttribute('aria-pressed', b === btn ? 'true' : 'false');
        });
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
    // "Not in patch notes": the tiles of the rows the notes left out only (a row with none goes: `tr.nh`, built);
    // pressed = `.on` too, as the part and row buttons
    document.querySelectorAll('.dyn-bar .dyn-hid[data-target]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var table = document.querySelector(btn.getAttribute('data-target'));
        if (!table) return;
        var on = !table.classList.contains('only-hid');
        table.classList.toggle('only-hid', on);
        btn.classList.toggle('on', on);
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
        redraw(table);
      });
    });
    // old columns / hidden rows coming into sight: draw the tiles a filter skipped
    document.querySelectorAll('.dyn-bar input[data-toggle-class="show-old"], .dyn-bar input[data-toggle-class="show-extra"]')
      .forEach(function (inp) {
        inp.addEventListener('click', function () {
          var table = document.querySelector(inp.getAttribute('data-target'));
          if (table && tiles[table.id]) setTimeout(function () { redraw(table, true); }, 0);
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
      // (the box's height: table-fit) only "Older patches" changes the width; "Buff vs nerf" and the rest leave the
      // scroll alone
      var old = t.classList.contains('show-old');
      new MutationObserver(function () {
        var now = t.classList.contains('show-old');
        if (now !== old) { old = now; fit(); toEnd(); }
      }).observe(t, { attributes: true, attributeFilter: ['class'] });
      // a new width keeps the user's place: the same distance from the newest end — re-scrolling to the end threw a
      // reader of older patches back to the newest ones (review 2026-10-04); a height-only resize leaves it alone
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

  /* ---------- change matrices: a month's label is whole, short ("Dec") or out of sight — never cut ---------- */
  /* centred over its whole month, a label sat half under the sticky names and read "025-12" (review 2026-10-17). The
     label is sticky in its header (styles.css `.ml`): the compositor keeps it in the part of its month in sight. Here,
     only where that part is too narrow for it: the short label at the end in sight (`sr` when the month runs off to the
     left, `sl` to the right), or none. Each state is a colour / a visibility, written only when it changes: on this page
     any change in the box costs a frame its paint (~5 ms), so moving the labels from here (a write a frame) was out.
     The headers' places are read once per layout change; a vertical scroll returns at once */
  safe('dyn-months', function () {
    var EDGE = 4, FADE = 22;          // the sticky insets: past the names, short of the right edge's arrow (styles.css)
    document.querySelectorAll('table.dyn').forEach(function (t) {
      var sc = t.closest('.table-scroll');
      var labs = Array.prototype.map.call(t.querySelectorAll('thead tr.cats th.dm > .ml'), function (el) {
        return { el: el, one: el.parentNode.classList.contains('one'), state: '', full: 0, short: 0, l: 0, r: 0, on: false };
      });
      var name = t.querySelector('thead tr.cats th.name');
      if (!sc || !name || !labs.length) return;
      var g = null, lastSl = null;
      function measure() {
        var cs = getComputedStyle(labs[0].el.parentNode);
        var tr = t.getBoundingClientRect(), x0 = t.offsetLeft;
        g = { name: name.getBoundingClientRect().width, cw: sc.clientWidth, sw: sc.scrollWidth,
              padL: parseFloat(cs.paddingLeft) + parseFloat(cs.borderLeftWidth), padR: parseFloat(cs.paddingRight) };
        labs.forEach(function (x) {               // in the box's content coordinates (as at scrollLeft 0)
          var r = x.el.parentNode.getBoundingClientRect();
          x.on = r.width > 0;
          x.l = r.left - tr.left + x0 + g.padL;   // the header's content box
          x.r = r.right - tr.left + x0 - g.padR;
          // the labels' widths as drawn: a canvas measure took another font than the page drew with a fallback face
          // (before the fonts load; CI's Linux), and labels overran their months. A one-patch month's label IS its
          // short form (the span's own text at size 0); else the short form is the absolutely placed ::before
          // (the span is at most its month's width, styles.css: its text's own width is the scroll width)
          var w = Math.max(x.el.getBoundingClientRect().width, x.el.scrollWidth);
          x.full = w;
          x.short = x.one ? w : parseFloat(getComputedStyle(x.el, '::before').width) || 0;
        });
        lastSl = null;
        update();
      }
      function update() {
        var sl = sc.scrollLeft;
        if (!g || sl === lastSl) return;
        lastSl = sl;
        // at the end nothing covers the right edge (the arrow is gone)
        var from = sl + g.name + EDGE, to = sl + g.cw - (sl + g.cw >= g.sw - 2 ? EDGE : FADE);
        labs.forEach(function (x) {
          if (!x.on) return;
          var vl = Math.max(x.l, from), room = Math.min(x.r, to) - vl, st;
          if (x.one) st = room >= x.short - 0.5 ? '' : 'none';
          else st = room >= x.full - 0.5 ? '' : room < x.short - 0.5 ? 'none' : vl > x.l ? 'sr' : 'sl';
          if (st === x.state) return;
          if (x.state) x.el.classList.remove(x.state);
          if (st) x.el.classList.add(st);
          x.state = st;
        });
      }
      var pending = false;
      sc.addEventListener('scroll', function () {
        if (pending) return;
        pending = true;
        requestAnimationFrame(function () { pending = false; update(); });
      }, { passive: true });
      // "Older patches" moves every header; the box's new width (a window's, a scrollbar's) and the fonts change the room
      var old = t.classList.contains('show-old');
      new MutationObserver(function () {
        var now = t.classList.contains('show-old');
        if (now !== old) { old = now; measure(); }
      }).observe(t, { attributes: true, attributeFilter: ['class'] });
      var w0 = sc.clientWidth;
      function resized() {
        if (sc.clientWidth === w0) return;
        w0 = sc.clientWidth;
        requestAnimationFrame(measure);
      }
      if (window.ResizeObserver) new ResizeObserver(resized).observe(sc);
      else window.addEventListener('resize', resized);
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);
      measure();
    });
  });

