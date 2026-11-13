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
    // the shown rows by tag (a code line and a name / description change are no counted change) and how many of
    // them are not in the notes — for a band's banner and for each ability's head alike
    function countRows(rows, onlyHidden) {
      var counts = {}, hidden = 0;
      rows.forEach(function (r) {
        if (r.classList.contains('f-out') || r.classList.contains('st-code') || r.classList.contains('st-text') ||
            r.classList.contains('st-fix') || r.classList.contains('model-row') ||
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
      return { counts: counts, hidden: hidden };
    }
    function setPips(pips, counts) {
      pips.forEach(function (p) {
        if (!p.lastChild || p.lastChild.nodeType !== 3) return;
        if (p.__n === undefined) p.__n = p.lastChild.nodeValue;
        var n = counts[p.classList[1]] || 0;
        p.lastChild.nodeValue = n;
        p.classList.toggle('n0', !n);
      });
    }
    // the banner's counters while a filter is on, and each ability head's; the eye's count; the built numbers
    // come back when the filters clear
    function recount(b, active, onlyHidden) {
      var bc = b.querySelector('summary .bc');
      if (!bc) return;
      var pips = bc.querySelectorAll('.tsum .pip'), eye = bc.querySelector('.ec-n');
      // an ability's own counters (its head) follow its shown rows too: Haze's Bullet Dance read 10 over 1 row.
      // The head only: a link row's own "+N" pip (inside .vv) is not one of them
      var gpips = b.querySelectorAll('.hgroup > .hg-b > .esub > .tsum .pip');
      // "+34 for all heroes": only while its link row is shown (a tag or the eye never keeps it)
      var shr = bc.querySelectorAll('.shr-chip');
      if (!active) {
        if (!b.__rc) return;
        b.__rc = false;
        [pips, gpips].forEach(function (ps) {
          ps.forEach(function (p) { if (p.__n !== undefined) p.lastChild.nodeValue = p.__n; p.classList.remove('n0'); });
        });
        if (eye) { eye.textContent = eye.__t; eye.parentNode.classList.remove('n0'); named(eye); }
        shr.forEach(function (c) { c.classList.remove('n0'); });
        return;
      }
      b.__rc = true;
      var allShown = !!b.querySelector('.erow.shr-all:not(.f-out)');
      shr.forEach(function (c) { c.classList.toggle('n0', !allShown); });
      var got = countRows(b.querySelectorAll('.erow'), onlyHidden);
      var counts = got.counts, hidden = got.hidden;
      setPips(pips, counts);
      b.querySelectorAll('.hgroup').forEach(function (g) {
        var gp = g.querySelectorAll(':scope > .hg-b > .esub > .tsum .pip');
        if (gp.length) setPips(gp, countRows(g.querySelectorAll('.erow'), onlyHidden).counts);
      });
      if (eye) {
        if (eye.__t === undefined) eye.__t = eye.textContent;
        // the built wording (history_view._banner): "all N" when every shown row is out of the notes and N > 1; an
        // update with no patch notes at all keeps saying so (a filter turned it into "all 2 not in notes", review
        // 2026-10-17)
        var shown = 0;
        for (var t in counts) shown += counts[t];
        var none = eye.__t === 'no patch notes';
        var words = none ? eye.__t : (hidden > 1 && hidden === shown && b.classList.contains('all-hidden') ? 'all ' : '') +
          hidden + ' not in patch notes';
        if (eye.textContent !== words) { eye.textContent = words; named(eye); }
        eye.parentNode.classList.toggle('n0', !hidden);
      }
    }
    // the chip that links its proof (history_view._eye_chip) is named "count — words": its name follows the count
    function named(eye) {
      var a = eye.parentNode;
      if (a.tagName === 'A' && a.hasAttribute('data-tooltip')) {
        a.setAttribute('aria-label', eye.textContent + ' — ' + a.getAttribute('data-tooltip'));
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
          // a merged group carries every member's id ("a b"): it matches when one of them is chosen
          var gok = (!state.area || (' ' + g.getAttribute('data-area') + ' ').indexOf(' ' + state.area + ' ') >= 0) &&
                    (!state.ab || (g.getAttribute('data-ab') || '').split(' ').some(function (id) {
                      return id && (' ' + state.ab + ' ').indexOf(' ' + id + ' ') >= 0;
                    }));
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
    // the bar is sticky on a desktop (styles.css): its height lets a jump to a band land below it
    function barHeight() {
      var stuck = getComputedStyle(bar).position === 'sticky';
      document.documentElement.style.setProperty('--hist-bar-h', (stuck ? bar.offsetHeight : 0) + 'px');
      return stuck ? bar.getBoundingClientRect().bottom : 0;
    }
    barHeight();
    window.addEventListener('resize', barHeight, { passive: true });
    // a filter chosen deep in the page: its first match starts just below the bar, not under it
    function underBar() {
      var bottom = barHeight();
      var first = box.querySelector('details.pblock:not(.f-out)');
      if (!first || !bottom) return;
      var top = first.getBoundingClientRect().top;
      if (top < bottom) window.scrollBy(0, top - bottom - 8);
    }
    // back to the top of a long history: a button past one screen (a passive listener; the class only on change)
    var up = document.createElement('button');
    up.type = 'button';
    up.className = 'back-to-top';
    up.setAttribute('aria-label', 'Back to top');
    up.textContent = '↑';
    up.addEventListener('click', function () { window.scrollTo({ top: 0 }); });
    document.body.appendChild(up);
    // a touch screen shows it only while the page goes up: the rest of the time it sat on the right-hand values
    var upOn = false, lastY = window.scrollY, touch = window.matchMedia && window.matchMedia('(hover: none)').matches;
    window.addEventListener('scroll', function () {
      var y = window.scrollY, on = y > window.innerHeight;
      if (touch && on) {
        if (Math.abs(y - lastY) < 6) return;          // a jitter of the finger is no direction
        on = y < lastY;
      }
      lastY = y;
      if (on !== upOn) { upOn = on; up.classList.toggle('on', on); }
    }, { passive: true });
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
      // no chip and no group or band of the page names the id (a Game page has no chips): a filter nothing could
      // clear would empty the history, so the link just opens the page
      if (!chip && !Array.prototype.some.call(box.querySelectorAll('[data-ab], [data-abs]'), function (el) {
        return ((el.getAttribute('data-ab') || '') + ' ' + (el.getAttribute('data-abs') || '')).split(' ').indexOf(id) >= 0;
      })) return;
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
      setTimeout(function () { apply(); underBar(); }, 0);
    });
  });

  /* ---------- --stick-h: how tall the toolbar stuck under the site bar is, for the anchored targets' scroll-margin
     (styles.css: a patch page's cards and tab panels). The home page's "12 not in patch notes" landed Deadman Danny's
     card head under a patch page's filter bar, the rows without their hero (review 2026-10-17). Several bars stick at
     one top (a patch page's tabs and its panel's own bar): the tallest one shown counts. `window.__stickH` re-measures
     at once — the tabs module calls it when it opens a panel, before it scrolls to a card ---------- */
  safe('sticky-h', function () {
    var bars = document.querySelectorAll('.toolbar');
    if (!bars.length) return;
    var root = document.documentElement, last = null, pending = false;
    function measure() {
      pending = false;
      var h = 0;
      bars.forEach(function (b) {
        if (b.getClientRects().length && getComputedStyle(b).position === 'sticky') h = Math.max(h, b.offsetHeight);
      });
      if (h !== last) { last = h; root.style.setProperty('--stick-h', h + 'px'); }
    }
    function later() { if (!pending) { pending = true; requestAnimationFrame(measure); } }
    measure();
    window.__stickH = measure;
    window.addEventListener('resize', later, { passive: true });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(later);
  });

  /* ---------- #p-<patch>: a history band named in the address — or clicked on this page (a strip tile,
     an ability card's trail square or its last change) — opens and comes into view, even when a filter
     or "Before release" hid it and even when the address already names it ---------- */
  safe('patch-anchor', function () {
    if (!document.querySelector('[id^="p-"]')) return;     // no history bands here: no listeners
    // a band or group a filter (or "Before release") hides: clear the filters; still hidden and work before
    // release -> show that too. The band can show while the group is filtered out (another ability's rows
    // kept it): the group is checked on its own, or the square scrolled nowhere and lit a hidden group
    function reveal(x) {
      if (!x || x.offsetParent !== null) return;
      var reset = window.__histReset;
      if (reset) reset();
      // a band of rules for every hero waits behind "For all heroes" (history_view.toolbar): show them
      var only = x.closest('.every-only');
      if (only && x.offsetParent === null) {
        var hb = only.closest('.hblocks');
        if (hb) hb.classList.add('show-every');
        var eb = document.querySelector('.hist-bar .hf-every');
        if (eb) { eb.classList.add('on'); eb.setAttribute('aria-pressed', 'true'); }
      }
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
        return (g.getAttribute('data-ab') || '').split(' ').indexOf(ab) >= 0;
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
      // a touch screen's first tap on a strip tile only shows its card (dyn-tip): no jump
      if (!a || ev.defaultPrevented || ev.button !== 0 || ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.altKey) return;
      var href = a.getAttribute('href');
      if (!document.getElementById(href.slice(1))) return;
      ev.preventDefault();
      if (location.hash !== href) {
        try { history.pushState(null, '', href); } catch (e) { location.hash = href; return; }
      }
      go(a.getAttribute('data-ab'));
    });
  });

  /* ---------- a build page's rows (builders/evidence.py row_source): #r-<hash> — the eye on an entity page —
     opens that row's source and brings it into view, out of a closed fold too; an opened source's "file diff ↗"
     takes the URL of the head's link of that file (the page writes each URL once) ---------- */
  safe('build-src', function () {
    if (!document.querySelector('details.src')) return;      // not a build page: no listeners
    function fill(d) {
      var a = d.querySelector('a.src-d');
      var h = a && a.getAttribute('href');
      if (!h || h.charAt(0) !== '#') return;
      var t = document.getElementById(h.slice(1));
      if (t && t.href) { a.href = t.href; a.rel = 'noopener'; }
    }
    document.addEventListener('toggle', function (ev) {
      var d = ev.target;
      if (d.open && d.classList && d.classList.contains('src')) fill(d);
    }, true);
    function go() {
      if (location.hash.indexOf('#r-') !== 0) return;
      var el = document.getElementById(location.hash.slice(1));
      if (!el || el.tagName !== 'DETAILS') return;
      for (var p = el.parentElement; p; p = p.parentElement) if (p.tagName === 'DETAILS') p.open = true;
      el.open = true;
      fill(el);
      el.scrollIntoView({ block: 'start' });
    }
    go();
    window.addEventListener('hashchange', go);
  });

