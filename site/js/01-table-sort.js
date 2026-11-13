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
      var sortable = Array.prototype.filter.call(table.querySelectorAll('thead tr.cols th[data-col]'), function (th) {
        return !th.hasAttribute('data-nosort');
      });
      // the keyboard sorts too (Enter / Space on a focused header); aria-sort says the column's order
      function ariaSort(active, dir) {
        sortable.forEach(function (x) {
          x.setAttribute('aria-sort', x === active && dir ? (dir === 1 ? 'descending' : 'ascending') : 'none');
        });
      }
      sortable.forEach(function (th) {
        th.tabIndex = 0;
        pressable(th);
        th.addEventListener('click', function () {
          var col = th.getAttribute('data-col');
          if (state.col !== col) { state.col = col; state.dir = 1; }
          else { state.dir = state.dir === 1 ? -1 : (state.dir === -1 ? 0 : 1); }
          ariaSort(th, state.dir);
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
              // words follow the direction too: a Name column read A→Z on every click while aria-sort
              // announced "descending" (review 2026-10-05)
              if (ea && eb) return String(a[0]).localeCompare(String(b[0])) * -state.dir;
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
      ariaSort(null, 0);
      table.__resetSort = function () {
        state.col = null;
        state.dir = 0;
        ariaSort(null, 0);
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
      // sticky second header row sits below the category row; a group's sticky name keeps clear of the sticky names
      // (measured again once the fonts are in: they change both)
      var cats = table.querySelector('thead tr.cats'), names = table.querySelector('thead tr.cols th.name');
      function pin() {
        if (cats) table.style.setProperty('--cat-row-h', cats.getBoundingClientRect().height + 'px');
        if (names) table.style.setProperty('--name-w', names.getBoundingClientRect().width + 'px');
      }
      pin();
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(pin);
    });
  });

