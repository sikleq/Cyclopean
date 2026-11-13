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
    // in rounds: every name that is still too big takes the next size, then all of them are measured — one
    // layout a round instead of one a name a step (a tab switch was one 160 ms task, frontend audit 10-04)
    function fit(page) {
      // a hidden page measures nothing: it fits when its tab opens
      if (!page || page.hidden || page.getAttribute('data-fit')) return;
      page.setAttribute('data-fit', '1');
      var names = Array.prototype.slice.call(page.querySelectorAll('.gc-nm'));
      names.forEach(function (n) { n.style.fontSize = ''; });
      var todo = names.filter(tooBig);
      for (var k = 14.5; todo.length && k >= 9; k -= 0.5) {
        todo.forEach(function (n) { n.style.fontSize = 'calc(' + k + ' * var(--u))'; });
        todo = todo.filter(tooBig);
      }
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
    // the fonts arrive after the first paint (their stylesheet does not block it): names fitted in the
    // fallback font fit again in the real one
    if (document.fonts && document.fonts.addEventListener) document.fonts.addEventListener('loadingdone', refit);
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
    // a touch screen (the tooltip module's rule): the first tap on a card lights it and shows its tooltip, a second tap
    // on it opens the item, a tap elsewhere lets go — a tap sent hover and click together, so the item opened at once
    // and the tooltip was never seen (review 2026-10-17). Whether the card was lit is read when the touch begins,
    // before the tap's own mouseover lights it; the compatibility mouseleave a tap may fire is not a leave.
    var noHover = window.matchMedia && window.matchMedia('(hover: none)').matches;
    var litBefore = null;
    if (noHover) {
      var touchStart = function (ev) {
        var c = ev.target.closest && ev.target.closest('.gcard');
        litBefore = c && c === active ? c : null;
      };
      document.addEventListener('pointerdown', touchStart, true);
      document.addEventListener('touchstart', touchStart, { capture: true, passive: true });
      root.addEventListener('click', function (ev) {
        var c = ev.target.closest && ev.target.closest('.gcard[href]');
        if (c && c !== litBefore && ev.detail !== 0) ev.preventDefault();
      });
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
      if (!noHover) {
        board.addEventListener('mouseleave', function () { clearTimeout(leaveT); leave(); });
        return;
      }
      // touch: a tap outside this board lets its card go (a tap on its gaps does through mouseover)
      document.addEventListener('pointerdown', function (ev) {
        if (active && board.contains(active) && !board.contains(ev.target)) { clearTimeout(leaveT); leave(); }
      }, true);
    });
    // the card moves with the page: the tooltip follows it
    window.addEventListener('scroll', function () {
      if (active && !tip.hidden) place(active);
    }, { passive: true });
  });

