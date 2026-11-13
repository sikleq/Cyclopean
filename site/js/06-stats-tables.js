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
        if (!table) return;
        var role = btn.classList.contains('on') ? '' : btn.getAttribute('data-role-filter');
        btns.forEach(function (b) {
          var on = b === btn && !!role;
          b.classList.toggle('on', on);
          b.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
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
        btns.forEach(function (b) { b.classList.toggle('on', b === btn); b.setAttribute('aria-pressed', b === btn ? 'true' : 'false'); });
        document.querySelectorAll('.cal-year').forEach(function (s) { s.classList.toggle('on', s.getAttribute('data-year') === y); });
      });
    });
  });

  safe('rework-lines', function () {
    // a replaced tier's bonus lists stop at two lines; a list the clamp cut gets "more ▾" (its row's `clamped`), and a
    // tap on the list or on that word opens it. Measured after load, after a band opens (a folded band's rows are in a
    // <template> until then) and after a resize: reads first, then the class writes
    function mark() {
      var rows = [], cut = [];
      document.querySelectorAll('.erow.rw .vals.wrap').forEach(function (v) {
        if (v.classList.contains('open') || !v.offsetParent) return;
        rows.push(v.closest('.erow'));
        cut.push(v.scrollHeight > v.clientHeight + 1);
      });
      rows.forEach(function (r, i) { if (r) r.classList.toggle('clamped', cut[i]); });
    }
    var queued = false;
    function later() {
      if (queued) return;
      queued = true;
      requestAnimationFrame(function () { queued = false; mark(); });
    }
    if (document.querySelector('.erow.rw .vals.wrap') || document.querySelector('template.hp-t')) {
      if (document.readyState === 'complete') later(); else window.addEventListener('load', later);
      window.addEventListener('resize', later);
      document.addEventListener('toggle', later, true);
    }
    document.addEventListener('click', function (ev) {
      var vv = ev.target.closest && ev.target.closest('.erow.rw .vv');
      var v = vv && vv.querySelector('.vals.wrap');
      if (!v) return;
      if (vv.closest('details.src > summary')) ev.preventDefault();  // a build page's row: the list opens, not the source
      var open = v.classList.toggle('open');
      vv.parentNode.classList.toggle('open', open);
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
        th.tabIndex = 0;
        th.setAttribute('aria-expanded', 'true');
        pressable(th);
        th.addEventListener('click', function () {
          th.setAttribute('aria-expanded', th.classList.toggle('folded') ? 'false' : 'true');
          recount();
        });
      });
      // switches that show / hide columns (Details, Stat columns): the spans follow
      document.querySelectorAll('[data-toggle-class]').forEach(function (b) {
        b.addEventListener('click', function () { setTimeout(recount, 0); });
      });
      table.addEventListener('statcols', function () { recount(true); });
      recount();
      // a phone's Item Stats hides its Tier column (styles.css): the spans follow a turn of the screen across 760px
      var narrow = window.matchMedia && window.matchMedia('(max-width: 760px)');
      if (narrow && narrow.addEventListener) narrow.addEventListener('change', function () { recount(); });
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
      b.setAttribute('aria-pressed', i < 0 ? 'true' : 'false');
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

