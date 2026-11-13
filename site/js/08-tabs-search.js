  /* ---------- tabs: <button data-tab="id"> shows #id.tab-panel, hides its siblings ---------- */
  safe('tabs', function () {
    var buttons = document.querySelectorAll('[data-tab]');
    if (!buttons.length) return;                     // no tabs on the page: no listeners either
    // a phone's tab bar is one row that scrolls sideways (styles.css): the open tab is brought into sight
    function reveal(b) {
      var bar = b.parentNode;
      if (!bar || bar.scrollWidth <= bar.clientWidth) return;
      var r = b.getBoundingClientRect(), br = bar.getBoundingClientRect();
      if (r.left < br.left || r.right > br.right) bar.scrollLeft += r.left - br.left - 8;
    }
    function open(id) {
      buttons.forEach(function (b) {
        var on = b.getAttribute('data-tab') === id;
        b.classList.toggle('on', on);
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
        if (on) reveal(b);
      });
      document.querySelectorAll('.tab-panel').forEach(function (p) { p.classList.toggle('on', p.id === id); });
      if (window.__stickH) window.__stickH();      // the panel's own bar may be taller: before any scroll to a card
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
      if (!a || ev.defaultPrevented) return;        // a first tap that only showed a hover card (dyn-tip)
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
    var rel = input.getAttribute('data-rel') || '', rows = null, req = null, timer = 0, on = -1;
    var MAX = 12;
    // one request, kept as a promise: what is typed while search.json loads is drawn when it arrives (the
    // keystrokes' callbacks were dropped while the request was in flight, frontend audit 2026-10-04)
    function load() {
      if (!req) {
        req = fetch(input.getAttribute('data-site-search'))
          .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
          .then(function (d) { rows = d; return d; })
          .catch(function (e) { req = null; throw e; });              // the next key asks again
      }
      return req;
    }
    function later(then) { load().then(then, function () { /* offline: nothing to list */ }); }
    function item(r, i) {
      var a = document.createElement('a');
      a.href = rel + r[1];
      a.id = 'ss-o' + i;
      a.setAttribute('role', 'option');
      var pic = document.createElement(r[3] ? 'img' : 'span');
      if (r[3]) { pic.src = rel + r[3]; pic.alt = ''; pic.loading = 'lazy'; } else pic.className = 'ss-noimg';
      var nm = document.createElement('span'), what = document.createElement('span');
      nm.className = 'ss-nm'; nm.textContent = r[0];
      what.className = 'ss-what'; what.textContent = r[2];
      a.appendChild(pic); a.appendChild(nm); a.appendChild(what);
      return a;
    }
    // the list shown or not: the combobox says so (aria-expanded), its active option goes with it
    function shown(open) {
      list.hidden = !open;
      input.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (!open) input.removeAttribute('aria-activedescendant');
    }
    function render() {
      var q = input.value.trim().toLowerCase();
      list.textContent = '';
      on = -1;
      input.removeAttribute('aria-activedescendant');
      if (!q || !rows) { shown(false); return; }
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
      hits.forEach(function (r, k) { list.appendChild(item(r, k)); });
      shown(true);
    }
    function move(d) {
      var links = list.querySelectorAll('a');
      if (!links.length) return;
      if (on >= 0) { links[on].classList.remove('on'); links[on].removeAttribute('aria-selected'); }
      on = (on + d + links.length) % links.length;
      links[on].classList.add('on');
      links[on].setAttribute('aria-selected', 'true');
      input.setAttribute('aria-activedescendant', links[on].id);
      links[on].scrollIntoView({ block: 'nearest' });
    }
    input.addEventListener('focus', function () { later(function () {}); });
    input.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(function () { later(render); }, 80);
    });
    input.addEventListener('keydown', function (ev) {
      if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') { ev.preventDefault(); move(ev.key === 'ArrowDown' ? 1 : -1); }
      else if (ev.key === 'Enter') {
        var links = list.querySelectorAll('a');
        if (links.length) { ev.preventDefault(); window.location.href = links[Math.max(on, 0)].href; }
      } else if (ev.key === 'Escape') { input.value = ''; render(); }
    });
    document.addEventListener('click', function (ev) {
      if (!input.parentNode.contains(ev.target)) shown(false);
    });
    input.addEventListener('focus', function () { if (list.childNodes.length) shown(true); });
  });

  /* ---------- #hidden: "what Valve did not say" in one link (review 2026-10-05: every "N not in patch notes"
     was plain text, the filter sat in the 4th tab or two screens down). The page's eye button is pressed and
     comes into view — on a patch page its tab opens first; pressing the eye writes #hidden, so the filtered
     view survives a reload and can be shared. ---------- */
  safe('hidden-hash', function () {
    var eye = document.querySelector('.hf-hidden');
    // a patch page with notes has a tab of what they left out, as readable lines (patches_pages HIDDEN_TAB): #hidden
    // opens it rather than pressing the raw filter of All changes
    var tabbed = document.querySelector('.tab-panel[data-hidden-tab]');
    if (!eye && !tabbed) return;
    var panel = eye && eye.closest('.tab-panel');
    function show() {
      if (location.hash !== '#hidden') return;
      if (tabbed) {
        var t = document.querySelector('[data-tab="' + tabbed.id + '"]');
        if (t && !tabbed.classList.contains('on')) t.click();
        try { history.replaceState(null, '', '#hidden'); } catch (e) { /* file:// */ }
        (document.querySelector('.tabs') || tabbed).scrollIntoView({ block: 'start' });
        return;
      }
      if (panel) {
        var tab = document.querySelector('[data-tab="' + panel.id + '"]');
        if (tab && !panel.classList.contains('on')) tab.click();
      }
      if (eye.getAttribute('aria-pressed') !== 'true') eye.click();
      try { history.replaceState(null, '', '#hidden'); } catch (e) { /* file:// */ }
      (eye.closest('.toolbar') || eye).scrollIntoView({ block: 'start' });
    }
    if (eye) eye.addEventListener('click', function () {
      setTimeout(function () {
        var on = eye.getAttribute('aria-pressed') === 'true';
        var off = panel ? '#' + panel.id : location.pathname + location.search;
        // where #hidden means the tab of lines, the pressed filter keeps its own tab's hash
        try { history.replaceState(null, '', on && !tabbed ? '#hidden' : off); } catch (e) { /* file:// */ }
      }, 0);
    });
    window.addEventListener('hashchange', show);
    show();
  });

  /* ---------- a change matrix's filters in its address: "#hidden&old&bvn&extra&part=abil&tags=buff,nerf&role=brawler
     &cat=w&tier=3&q=haze". A link opens the matrix so filtered — the home page's "N not in patch notes" opens
     heroes/changes.html#hidden (review 2026-10-17: it opened the plain patch archive) — and every filter chosen here
     is written back, so a reload, "back" from a tile's page and a shared link keep it. The state is set by pressing
     the bar's own controls: their modules (toggles, dyn-parts, dyn-rows, search, tb-fold) do the rest ---------- */
  safe('dyn-url', function () {
    var bar = document.querySelector('.dyn-bar'), table = document.querySelector('table.dyn');
    if (!bar || !table) return;
    var SWITCHES = { old: 'show-old', bvn: 'bvn', extra: 'show-extra' };
    var search = bar.querySelector('input[type=search]');
    function parse() {
      var s = {};
      location.hash.replace(/^#/, '').split('&').forEach(function (kv) {
        if (!kv) return;
        var i = kv.indexOf('=');
        try {
          s[decodeURIComponent(i < 0 ? kv : kv.slice(0, i))] = i < 0 ? '' : decodeURIComponent(kv.slice(i + 1));
        } catch (e) { /* a broken escape: that key is left out */ }
      });
      return s;
    }
    function pressed(b) { return b.getAttribute('aria-pressed') === 'true'; }
    function apply(s) {
      var hid = bar.querySelector('.dyn-hid');
      if (hid && ('hidden' in s) !== pressed(hid)) hid.click();
      Object.keys(SWITCHES).forEach(function (k) {
        var box = bar.querySelector('input[data-toggle-class="' + SWITCHES[k] + '"]');
        if (box && box.checked !== (k in s)) box.click();
      });
      var part = bar.querySelector('.dyn-parts button[data-part="' + (s.part || 'all') + '"]');
      if (part && !pressed(part)) part.click();
      var tags = (s.tags || '').split(',');
      bar.querySelectorAll('[data-dyn-tag]').forEach(function (b) {
        if (pressed(b) !== (tags.indexOf(b.getAttribute('data-dyn-tag')) >= 0)) b.click();
      });
      // one choice per group (dyn-rows): a press clears the group's other button, so each is read again here
      bar.querySelectorAll('.dyn-rows button[data-rowf]').forEach(function (b) {
        if (pressed(b) !== (s[b.getAttribute('data-rowf')] === b.getAttribute('data-v'))) b.click();
      });
      if (search && search.value !== (s.q || '')) {
        search.value = s.q || '';
        search.dispatchEvent(new Event('input'));
      }
    }
    function state() {
      var out = [];
      if (table.classList.contains('only-hid')) out.push('hidden');
      Object.keys(SWITCHES).forEach(function (k) { if (table.classList.contains(SWITCHES[k])) out.push(k); });
      var part = table.getAttribute('data-part');
      if (part && part !== 'all') out.push('part=' + encodeURIComponent(part));
      if ((table.__sel || []).length) out.push('tags=' + table.__sel.map(encodeURIComponent).join(','));
      bar.querySelectorAll('.dyn-rows button[data-rowf][aria-pressed="true"]').forEach(function (b) {
        out.push(encodeURIComponent(b.getAttribute('data-rowf')) + '=' + encodeURIComponent(b.getAttribute('data-v')));
      });
      var q = search ? search.value.trim() : '';
      if (q) out.push('q=' + encodeURIComponent(q));
      return out.join('&');
    }
    var writing = 0;
    function write() {
      clearTimeout(writing);
      writing = setTimeout(function () {
        var h = state();
        if (location.hash.replace(/^#/, '') === h) return;
        try { history.replaceState(null, '', location.pathname + location.search + (h ? '#' + h : '')); }
        catch (e) { /* file:// in some browsers */ }
      }, 0);
    }
    if (location.hash.length > 1) apply(parse());
    bar.addEventListener('click', write);
    bar.addEventListener('change', write);
    if (search) search.addEventListener('searched', write);
    window.addEventListener('hashchange', function () { apply(parse()); });
  });

  /* ---------- Hero Stats opened from a hero page's "Advanced" (builders/hero_panels.adv_link):
     "#details&hero=warden" presses Details (the files' columns live there) and brings that hero's row into view ---- */
  safe('stats-link', function () {
    var table = document.getElementById('hero-stats');
    if (!table || location.hash.length < 2) return;
    var s = {};
    location.hash.slice(1).split('&').forEach(function (kv) {
      var i = kv.indexOf('=');
      s[i < 0 ? kv : kv.slice(0, i)] = i < 0 ? '' : kv.slice(i + 1);
    });
    var box = table.closest('.table-scroll');
    var btn = document.querySelector('[data-toggle-class="show-details"]');
    if ('details' in s && btn && box && !box.classList.contains('show-details')) btn.click();
    if (!s.hero || !/^[a-z0-9_]+$/.test(s.hero)) return;
    var a = table.querySelector('td.name a[href$="heroes/' + s.hero + '.html"]');
    var tr = a && a.closest('tr');
    if (!tr) return;
    tr.classList.add('hl');
    // after the table's own setup (its sticky widths settle a frame later and moved an early scroll): the page to
    // the table, the table's box to the row, centred
    setTimeout(function () {
      if (box) {
        box.scrollIntoView({ block: 'start' });
        var r = tr.getBoundingClientRect(), b = box.getBoundingClientRect();
        box.scrollTop += r.top - b.top - (b.height - r.height) / 2;
      } else {
        tr.scrollIntoView({ block: 'center' });
      }
    }, 120);
  });
})();
