"""Page performance probe (ported from Sloppy's tools/perf_probe.py, 2026-10-03): measure before and after
any change to a heavy page instead of guessing.

Serves dist/ on a local port, loads each page in headless Chromium (1600 x 900) and records:
  - load: DOMContentLoaded, element count, max DOM depth, counts of box-shadow / filter / sticky elements;
  - a smooth scroll from top to bottom: per-frame times (requestAnimationFrame), long tasks, and the
    layout / recalc-style / script time Chromium spent (CDP Performance metrics);
  - a scroll INSIDE each wide table box (.table-scroll: stats tables, change matrices), across and down:
    its p95 frame and long tasks (columns in-p95 / in-long; reported, not part of the pass budget).

    python tools/perf_probe.py                       # the default pages
    python tools/perf_probe.py --urls heroes/nano.html items/changes.html
    python tools/perf_probe.py --label before        # .cache/perf/<date>_before.json

Exits 1 when a page's p95 frame time is over the budget (default 25 ms).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import functools
import http.server
import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'dist'
OUT_DIR = ROOT / '.cache' / 'perf'
DEFAULT_URLS = [
    'index.html', 'heroes/index.html', 'heroes/nano.html', 'heroes/haze.html', 'heroes/changes.html',
    'items/index.html', 'items/changes.html', 'units/index.html', 'units/npc_boss_tier2.html',
    'units/neutral_dock_creature_weak.html', 'units/changes.html', 'tables/heroes.html', 'tables/items.html',
    'tables/units.html',
]
CDP_METRICS = ('LayoutCount', 'RecalcStyleCount', 'LayoutDuration', 'RecalcStyleDuration', 'ScriptDuration',
               'TaskDuration')

INIT_SCRIPT = """
(() => {
  window.__perfProbe = { frames: [], longTasks: [], collecting: false, _lastTs: null };
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) window.__perfProbe.longTasks.push({ start: e.startTime, duration: e.duration });
    }).observe({ entryTypes: ['longtask'] });
  } catch (e) { /* no longtask support */ }
  function loop(ts) {
    const p = window.__perfProbe;
    if (p.collecting) { if (p._lastTs != null) p.frames.push(ts - p._lastTs); p._lastTs = ts; } else { p._lastTs = null; }
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
})();
"""

DOM_STATS = """
() => {
  const all = document.querySelectorAll('*');
  let maxDepth = 0;
  const stack = [[document.body, 0]];
  while (stack.length) {
    const [el, d] = stack.pop();
    if (d > maxDepth) maxDepth = d;
    for (const c of el.children) stack.push([c, d + 1]);
  }
  let shadow = 0, filter = 0, sticky = 0;
  all.forEach(el => {
    const s = getComputedStyle(el);
    if (s.boxShadow && s.boxShadow !== 'none') shadow++;
    if (s.filter && s.filter !== 'none') filter++;
    if (s.position === 'sticky') sticky++;
  });
  const nav = performance.getEntriesByType('navigation')[0];
  return { elements: all.length, maxDepth, images: document.images.length, boxShadow: shadow, filter, sticky,
           dclMs: nav ? Math.round(nav.domContentLoadedEventEnd) : null,
           htmlKB: nav ? Math.round(nav.decodedBodySize / 1024) : null };
}
"""

SCROLL = """
async () => {
  const p = window.__perfProbe;
  p.frames = []; p.longTasks = [];
  const doc = document.scrollingElement || document.documentElement;
  window.scrollTo(0, 0);
  await new Promise(r => setTimeout(r, 80));
  const end = doc.scrollHeight - window.innerHeight;
  p.collecting = true;
  let pos = 0;
  await new Promise(resolve => {
    function tick() {
      pos = Math.min(pos + 90, Math.max(end, 0));
      window.scrollTo(0, pos);
      if (pos >= end || end <= 0) { resolve(); return; }
      requestAnimationFrame(() => setTimeout(tick, 0));
    }
    tick();
  });
  await new Promise(r => setTimeout(r, 250));
  p.collecting = false;
  return { frames: p.frames.slice(), longTasks: p.longTasks.slice() };
}
"""


# scrolling INSIDE the wide tables (stats tables, change matrices): the window scroll alone missed it, and the
# matrices are heavy exactly there (frontend audit 2026-10-04: items/changes p95 217 ms headless). Each box that
# overflows scrolls to its start, then across and down to its end in 90px steps, like the window
INNER_SCROLL = """
async () => {
  const p = window.__perfProbe;
  const boxes = [...document.querySelectorAll('.table-scroll')]
    .filter(b => b.offsetParent !== null && (b.scrollWidth > b.clientWidth + 2 || b.scrollHeight > b.clientHeight + 2));
  if (!boxes.length) return null;
  p.frames = []; p.longTasks = [];
  const frame = () => new Promise(r => requestAnimationFrame(() => setTimeout(r, 0)));
  for (const b of boxes) {
    b.scrollIntoView({ block: 'start' });
    b.scrollLeft = 0; b.scrollTop = 0;
    await new Promise(r => setTimeout(r, 80));
    p.collecting = true;
    for (const axis of ['scrollLeft', 'scrollTop']) {
      const end = axis === 'scrollLeft' ? b.scrollWidth - b.clientWidth : b.scrollHeight - b.clientHeight;
      for (let pos = 0; pos < end;) {
        pos = Math.min(pos + 90, end);
        b[axis] = pos;
        await frame();
      }
    }
    await new Promise(r => setTimeout(r, 150));
    p.collecting = false;
  }
  return { boxes: boxes.length, frames: p.frames.slice(), longTasks: p.longTasks.slice() };
}
"""


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct / 100
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:               # no line per request
        pass


def serve() -> tuple[http.server.ThreadingHTTPServer, str]:
    handler = functools.partial(_Quiet, directory=str(DIST))
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f'http://127.0.0.1:{srv.server_address[1]}'


def run_one(page, context, url: str, budget: float, inner_scroll: bool = True) -> dict:
    cdp = context.new_cdp_session(page)
    cdp.send('Performance.enable')
    errors: list[str] = []                       # a script error fails the page too
    on_console = lambda m: errors.append(m.text) if m.type == 'error' else None   # noqa: E731
    on_error = lambda e: errors.append(str(e))                                     # noqa: E731
    page.on('console', on_console)
    page.on('pageerror', on_error)
    page.goto(url, wait_until='networkidle', timeout=60000)
    page.wait_for_timeout(200)
    dom = page.evaluate(DOM_STATS)
    before = {m['name']: m['value'] for m in cdp.send('Performance.getMetrics')['metrics']}
    res = page.evaluate(SCROLL)
    after = {m['name']: m['value'] for m in cdp.send('Performance.getMetrics')['metrics']}
    deltas = {n: round((after.get(n, 0) - before.get(n, 0)) * (1000 if 'Duration' in n else 1), 1) for n in CDP_METRICS}
    frames = res['frames']
    p95 = round(percentile(frames, 95), 1)
    inner = page.evaluate(INNER_SCROLL) if inner_scroll else None
    page.remove_listener('console', on_console)
    page.remove_listener('pageerror', on_error)
    # Google Fonts may be unreachable offline: that is the network, not the page
    errors = [e for e in errors if 'fonts.g' not in e and 'ERR_' not in e]
    inner_out = None
    if inner and inner['frames']:
        fr = inner['frames']
        inner_out = {'boxes': inner['boxes'], 'count': len(fr), 'p95_ms': round(percentile(fr, 95), 1),
                     'max_ms': round(max(fr), 1), 'long_tasks': len(inner['longTasks']),
                     'long_ms': round(sum(t['duration'] for t in inner['longTasks']), 1)}
    return {'url': url, 'dom': dom, 'errors': errors,
            'frames': {'count': len(frames), 'p50_ms': round(percentile(frames, 50), 1), 'p95_ms': p95,
                       'max_ms': round(max(frames), 1) if frames else 0.0,
                       'pct_over_16_7': round(100 * sum(f > 16.7 for f in frames) / len(frames), 1) if frames else 0.0},
            'long_tasks': {'count': len(res['longTasks']), 'total_ms': round(sum(t['duration'] for t in res['longTasks']), 1)},
            'inner': inner_out,
            'cdp_ms': deltas, 'pass': p95 <= budget and not errors}


def main() -> int:
    from playwright.sync_api import sync_playwright
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--urls', nargs='*', default=DEFAULT_URLS)
    ap.add_argument('--label', default=None)
    ap.add_argument('--budget-p95', type=float, default=25.0)
    ap.add_argument('--no-inner', action='store_true', help='skip the scroll inside wide tables')
    args = ap.parse_args()
    if not DIST.exists():
        print('build the site first: python build_site.py')
        return 2
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime('%Y-%m-%d_%H%M%S')
    out_path = OUT_DIR / f'{stamp}{"_" + args.label if args.label else ""}.json'
    srv, base = serve()
    results = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(viewport={'width': 1600, 'height': 900})
            context.add_init_script(INIT_SCRIPT)
            page = context.new_page()
            for rel in args.urls:
                try:
                    results.append(run_one(page, context, f'{base}/{rel}', args.budget_p95, not args.no_inner))
                except Exception as exc:                  # keep going, report it
                    results.append({'url': rel, 'error': str(exc), 'pass': False})
            browser.close()
    finally:
        srv.shutdown()
    out_path.write_text(json.dumps({'date': stamp, 'budget_p95_ms': args.budget_p95, 'results': results}, indent=2),
                        encoding='utf-8')
    head = (f"{'page':40} {'elems':>6} {'DCL':>5} {'p95':>6} {'>16.7%':>7} {'long':>5} {'layout':>7} {'style':>7} "
            f"{'script':>7} {'in-p95':>7} {'in-long':>7}")
    print(head)
    print('-' * len(head))
    for r in results:
        if 'error' in r:
            print(f"{r['url']:40} ERROR {r['error'][:60]}")
            continue
        u = r['url'].split('/', 3)[-1]
        inner = r.get('inner') or {}
        print(f"{u:40} {r['dom']['elements']:>6} {r['dom']['dclMs'] or 0:>5} {r['frames']['p95_ms']:>6} "
              f"{r['frames']['pct_over_16_7']:>7} {r['long_tasks']['count']:>5} {r['cdp_ms']['LayoutDuration']:>7} "
              f"{r['cdp_ms']['RecalcStyleDuration']:>7} {r['cdp_ms']['ScriptDuration']:>7} "
              f"{inner.get('p95_ms', '-'):>7} {inner.get('long_tasks', '-'):>7}"
              + ('' if r['pass'] else '  FAIL'))
        for e in r['errors'][:3]:
            print(f'    JS error: {e[:120]}')
    print(f'\nbudget p95 <= {args.budget_p95} ms · {out_path.relative_to(ROOT)}')
    return 0 if all(r['pass'] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
