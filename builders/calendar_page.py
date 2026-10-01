"""Patch calendar (Sloppy's Calendar): per year, months by days. A day's shade = how many game builds
landed that day (the tracker sees every build); a patch day carries its marker (a named update in
gold, a follow-up smaller). Below: the year's numbers (patches, the longest and shortest stretch
between them, the median) and the cadence of all years by month."""
from __future__ import annotations

import calendar
from collections import Counter
from datetime import date
from statistics import median

from .common import esc, load_json, page, patch_name, patch_parts, patch_title_text

BUILD_STEPS = (1, 3, 6, 10)      # builds per day -> shade 1..4
MONTHS = [calendar.month_abbr[m].upper() for m in range(1, 13)]


def _shade(n: int) -> int:
    return 0 if not n else 1 + sum(n >= s for s in BUILD_STEPS[1:])


def _year_grid(year: int, patches: list[dict], builds: Counter) -> str:
    by_day = {}
    for p in patches:
        by_day.setdefault(p['date'][:10], []).append(p)
    rows = []
    for m in range(1, 13):
        cells = []
        days = calendar.monthrange(year, m)[1]
        for d in range(1, 32):
            if d > days:
                cells.append('<span class="cd none"></span>')
                continue
            iso = f'{year}-{m:02d}-{d:02d}'
            nb = builds.get(iso, 0)
            ps = by_day.get(iso, [])
            cls = f'cd s{_shade(nb)}'
            if iso == date.today().isoformat():
                cls += ' today'
            if ps:
                main = next((p for p in ps if ' · follow-up ' not in p['title']), ps[0])
                name, _, follow = patch_parts(main)
                cls += ' patch' + (' named' if name else '') + (' fu' if follow else '')
                label = (name or 'update')[:12] if not follow else 'f-up'
                tip = ' / '.join(patch_title_text(p) for p in ps) + (f' · {nb} builds' if nb else '')
                cells.append(f'<a class="{cls}" href="{esc(main["id"])}.html" data-tooltip="{esc(tip)}">'
                             f'<b>{d}</b><span class="pl">{esc(label)}</span></a>')
            else:
                tip = f' data-tooltip="{nb} build{"s" if nb != 1 else ""}"' if nb else ''
                cells.append(f'<span class="{cls}"{tip}>{d}</span>')
        rows.append(f'<div class="cal-row"><span class="cm">{MONTHS[m - 1]}</span>{"".join(cells)}</div>')
    return '<div class="cal-grid">' + ''.join(rows) + '</div>'


def _gaps(patches: list[dict]) -> list[tuple[int, dict, dict]]:
    """Days between consecutive patches (follow-ups count: each shipped something)."""
    ps = sorted(patches, key=lambda p: p['date'])
    out = []
    for a, b in zip(ps, ps[1:]):
        out.append(((date.fromisoformat(b['date'][:10]) - date.fromisoformat(a['date'][:10])).days, a, b))
    return out


def _stats(year_patches: list[dict], all_patches: list[dict], n_builds: int) -> str:
    named = sum(1 for p in year_patches if patch_name(p['title']) and ' · follow-up ' not in p['title'])
    follow = sum(1 for p in year_patches if ' · follow-up ' in p['title'])
    # a stretch belongs to the year it starts in; the one crossing into the next year counts too
    gaps = [g for g in _gaps(all_patches) if g[1]['date'][:4] == year_patches[0]['date'][:4]] if year_patches else []
    cells = [('patches', len(year_patches)), ('named updates', named), ('follow-ups', follow), ('game builds', n_builds)]
    if gaps:
        longest = max(gaps, key=lambda g: g[0])
        shortest = min(gaps, key=lambda g: g[0])
        cells.append(('median days apart', f'{median(g[0] for g in gaps):g}'))
    out = ''.join(f'<div class="cs"><b>{esc(v)}</b><span>{esc(k)}</span></div>' for k, v in cells)
    if gaps:
        out += (f'<div class="cs wide"><b>{longest[0]}</b><span>days, longest: {esc(longest[1]["date"][:10])} → '
                f'{esc(longest[2]["date"][:10])}</span></div>'
                f'<div class="cs wide"><b>{shortest[0]}</b><span>days, shortest: {esc(shortest[1]["date"][:10])} → '
                f'{esc(shortest[2]["date"][:10])}</span></div>')
    return f'<div class="cal-stats">{out}</div>'


def _cadence(patches: list[dict]) -> str:
    """Patches per month over every year: a bar per month (named updates in gold on top)."""
    years = sorted({p['date'][:4] for p in patches})
    per = Counter(p['date'][5:7] for p in patches)
    named = Counter(p['date'][5:7] for p in patches if patch_name(p['title']) and ' · follow-up ' not in p['title'])
    top = max(per.values()) if per else 1
    bars = ''.join(
        f'<div class="cb" data-tooltip="{esc(MONTHS[m - 1])}: {per.get(f"{m:02d}", 0)} patches'
        f'{", " + str(named[f"{m:02d}"]) + " named" if named.get(f"{m:02d}") else ""}">'
        f'<span class="bar" style="height:{per.get(f"{m:02d}", 0) / top * 100:.0f}%">'
        f'<span class="nb" style="height:{(named.get(f"{m:02d}", 0) / per[f"{m:02d}"] * 100) if per.get(f"{m:02d}") else 0:.0f}%"></span>'
        f'</span><span class="n">{per.get(f"{m:02d}", 0)}</span><span class="m">{MONTHS[m - 1][:1]}</span></div>'
        for m in range(1, 13))
    return (f'<section class="cadence px-frame"><div class="cad-h"><b>Patch cadence</b>'
            f'<span>{esc(years[0])} – {esc(years[-1])} · {len(patches)} patches</span></div>'
            f'<div class="cad-bars">{bars}</div></section>')


def calendar_page(sub_tabs: str) -> str:
    rel = '../'
    patches = load_json('patches/index.json')
    builds = Counter(b['date'][:10] for b in load_json('builds/index.json'))
    years = sorted({p['date'][:4] for p in patches}, reverse=True)
    switch = '<div class="flex cal-years">' + ''.join(
        f'<button class="px-btn{" on" if i == 0 else ""}" data-year="{y}">{y}</button>' for i, y in enumerate(years)) + '</div>'
    blocks = []
    for i, y in enumerate(years):
        yp = [p for p in patches if p['date'][:4] == y]
        nb = sum(n for d, n in builds.items() if d[:4] == y)
        blocks.append(f'<section class="cal-year px-frame{" on" if i == 0 else ""}" data-year="{y}">'
                      f'{_year_grid(int(y), yp, builds)}{_stats(yp, patches, nb)}</section>')
    legend = ('<div class="cal-legend"><span>builds a day</span>' + ''.join(
        f'<i class="cd s{s}"></i>' for s in range(5)) + '<span class="sep"></span>'
        '<i class="cd patch"></i><span>update</span><i class="cd patch named"></i><span>named update</span></div>')
    body = '<h1>Calendar</h1>' + sub_tabs + switch + legend + ''.join(blocks) + _cadence(patches)
    return page('Patch calendar', body, rel, 'patches', description='Deadlock patches and game builds by day')
