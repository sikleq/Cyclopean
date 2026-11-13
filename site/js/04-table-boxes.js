  /* ---------- a table's box fits the room under the stuck bars: its header row is never scrolled away ---------- */
  /* the box scrolls inside (its header row sticks to the box's top) and the page around it scrolls too: a box as tall
     as the screen took its header under the site bar once the page scrolled on (Hero Stats: 270px down, 820px tall,
     its header at -64px at the page's end; review 2026-10-17). So a box is never taller than the room under the site
     bar and a stuck toolbar; the page's last table also leaves room for what follows it (the footer), so at the
     page's end its header row sits right under the bars; on a desktop the page's first table also ends on the first
     screen, its sideways scrollbar in sight without scrolling the page (review 2026-10-06). A resize refits it: a new
     width always, a new height on a desktop only (a phone's URL bar comes and goes while the page scrolls) */
  safe('table-fit', function () {
    var boxes = Array.prototype.slice.call(document.querySelectorAll('.table-fade > .table-scroll'));
    if (!boxes.length) return;
    var GAP = 16, MIN_H = 300, DESK_W = 760;
    function stuckTop() {                       // the bottom of what stays stuck at the top: the site bar, a toolbar
      var nav = document.querySelector('.top-nav'), bar = document.querySelector('main > .toolbar');
      var top = nav ? nav.offsetHeight : 0;
      if (bar && getComputedStyle(bar).position === 'sticky') top += bar.offsetHeight;
      return top;
    }
    function fitAll() {
      boxes.forEach(function (sc) { sc.style.maxHeight = ''; });
      var vh = window.innerHeight, top = stuckTop(), docH = document.documentElement.scrollHeight;
      var desk = window.innerWidth >= DESK_W;
      // every height read before any is written: one layout
      var hs = boxes.map(function (sc, i) {
        var r = sc.getBoundingClientRect(), y = r.top + window.scrollY, after = docH - (y + r.height);
        var h = vh - top - GAP, c;
        if (after < vh / 3 && (c = vh - top - after) >= MIN_H) h = Math.min(h, c);
        if (desk && i === 0 && (c = vh - y - GAP) >= MIN_H) h = Math.min(h, c);
        return sc.scrollHeight + sc.offsetHeight - sc.clientHeight > h ? Math.round(Math.max(h, MIN_H)) : 0;
      });
      boxes.forEach(function (sc, i) { if (hs[i]) sc.style.maxHeight = hs[i] + 'px'; });
    }
    fitAll();
    // the bars above settle once the fonts and images are in: the box's top moves, so fit it again then
    if (document.readyState !== 'complete') window.addEventListener('load', fitAll, { once: true });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitAll);
    var pending = false, lastW = window.innerWidth;
    window.addEventListener('resize', function () {
      if (pending || (window.innerWidth === lastW && window.innerWidth < DESK_W)) return;
      pending = true;
      requestAnimationFrame(function () { pending = false; lastW = window.innerWidth; fitAll(); });
    });
  });

  /* ---------- change matrices: the row icons load once the page has loaded, not one by one under a scroll ---------- */
  /* a lazy icon arriving mid-scroll cost a layout, a repaint and a new layering of the ~200 sticky name cells:
     scrolling inside items/changes.html ran at p95 50 ms on a 4x slower CPU, 17 ms with the icons in (perf
     2026-10-05, tools/perf_probe.py --throttle 4). The first screen keeps its lazy start: the rest follow at `load` */
  /* a patch page's note cards too: they sit in CSS columns, and each icon arriving mid-scroll re-balanced the columns
     of up to ~2,000 elements — patches/2024-10-10.html spent 1.4 s in 14 layouts while scrolling, p95 83 ms; with
     the icons in after `load`, 0 layouts (2026-10-06) */
  safe('dyn-icons', function () {
    var imgs = document.querySelectorAll('table.dyn td.name img[loading="lazy"], .ecards img[loading="lazy"]');
    if (!imgs.length) return;
    function all() { imgs.forEach(function (i) { i.loading = 'eager'; }); }
    if (document.readyState === 'complete') all(); else window.addEventListener('load', all, { once: true });
  });

  /* ---------- wide tables: hide the right-edge fade once scrolled to the end ---------- */
  safe('table-fade', function () {
    document.querySelectorAll('.table-fade > .table-scroll').forEach(function (sc) {
      var wrap = sc.parentNode, edges = '';
      function check() {
        wrap.classList.toggle('at-end', sc.scrollLeft + sc.clientWidth >= sc.scrollWidth - 2);
      }
      // the shadow sits on the content's edge, not on the box's scrollbars (sizes change on a resize only)
      function sized() {
        var r = sc.offsetWidth - sc.clientWidth - sc.clientLeft, b = sc.offsetHeight - sc.clientHeight - sc.clientTop;
        if (r + ',' + b !== edges) {
          edges = r + ',' + b;
          wrap.style.setProperty('--fade-r', r + 'px');
          wrap.style.setProperty('--fade-b', b + 'px');
        }
        check();
      }
      sc.addEventListener('scroll', check, { passive: true });
      // the Details button widens the table: watch sizes, not only window resizes
      if (window.ResizeObserver) {
        var ro = new ResizeObserver(sized);
        ro.observe(sc);
        ro.observe(sc.firstElementChild);
      } else {
        window.addEventListener('resize', sized);
      }
      sized();
    });
  });

  /* ---------- a phone's folded table bar says how many of its options differ from the page's start ---------- */
  /* (tables_pages.filters_fold; styles.css shows the fold at ≤ 600px only): "Filters (2 active)" — a switch turned on,
     a button pressed that was not, a number changed. Counted after the other modules' handlers ran (a timeout), and
     on "back", when the browser restores the boxes */
  safe('tb-fold', function () {
    document.querySelectorAll('.toolbar > .tb-fold').forEach(function (fold) {
      var bar = fold.parentNode, opts = bar.querySelector('.tb-opts'), n = fold.querySelector('.tb-n');
      if (!opts || !n) return;
      var pressed = Array.prototype.filter.call(opts.querySelectorAll('[aria-pressed]'), function (b) {
        return b.getAttribute('aria-pressed') !== 'true';            // only what starts unpressed can count
      });
      function count() {
        var k = 0;
        opts.querySelectorAll('input').forEach(function (inp) {
          if (inp.type === 'checkbox' ? inp.checked && !inp.defaultChecked : inp.value !== inp.defaultValue) k++;
        });
        pressed.forEach(function (b) { if (b.getAttribute('aria-pressed') === 'true') k++; });
        var txt = k ? '(' + k + ' active)' : '';
        if (n.textContent !== txt) n.textContent = txt;
      }
      function later() { setTimeout(count, 0); }
      ['click', 'change', 'input'].forEach(function (ev) { opts.addEventListener(ev, later); });
      window.addEventListener('pageshow', later);
      count();
    });
  });

