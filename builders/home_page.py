"""Home page: what the site is, the latest patch at a glance, entry points."""
from __future__ import annotations

from .common import EYE_SVG, build_pages, esc, load_json, mark, page, write


def build_all() -> int:
    patches = load_json('patches/index.json')
    builds = load_json('builds/index.json')
    with_notes = [p for p in patches if p.get('has_notes')]
    latest = with_notes[-1] if with_notes else None
    total_hidden = sum(p['counts'].get('hidden', 0) for p in patches)
    total_doc = sum(p['counts'].get('documented', 0) for p in patches)
    total_mis = sum(p['line_counts'].get('mismatch', 0) for p in patches)
    last_build = builds[-1] if builds else None

    latest_html = ''
    if latest:
        c = latest['counts']
        latest_html = (f'<a class="tile px-frame bright" href="patches/{esc(latest["id"])}.html">'
                       f'<div class="d">Latest patch · {esc(latest["date"])}</div>'
                       f'<div class="t">{esc(latest["title"])}</div>'
                       f'<div class="d">{mark("documented")} {c.get("documented", 0)} documented · '
                       f'{mark("hidden")} {c.get("hidden", 0)} hidden · '
                       f'{mark("mismatch")} {latest["line_counts"].get("mismatch", 0)} mismatches</div></a>')
    stems = build_pages()
    recent = []
    for r in reversed(builds):
        f = r.get('fields', {})
        gp = f.get('balance', 0) + f.get('mechanic', 0) + f.get('availability', 0)
        if not (gp or r.get('loc') or r.get('convars')):
            continue
        recent.append(f'<li><span class="date">{esc(r["date"][:10])}</span>'
                      f'<span><a class="ttl" href="builds/{stems[r["file"]]}.html">Build {r["build"]}</a></span>'
                      f'<span class="nums"><span class="chip">{gp} gameplay</span><span class="chip">{r.get("loc", 0)} text</span>'
                      f'<span class="chip">{r.get("convars", 0)} cvars</span></span></li>')
        if len(recent) == 6:
            break
    recent_html = f'<h2>Latest builds</h2><ul class="timeline px-frame">{"".join(recent)}</ul>' if recent else ''
    body = f'''
<div class="home-hero">
  <div>
    <div class="eye-big">{EYE_SVG}</div>
    <h1>Cyclopean</h1>
  </div>
  <div>
    {latest_html}
    <div class="stat-strip">
      <div class="stat-box px-frame"><div class="n">{len(builds)}</div><div class="l">builds tracked</div></div>
      <div class="stat-box px-frame documented"><div class="n">{total_doc}</div><div class="l">documented changes</div></div>
      <div class="stat-box px-frame hidden"><div class="n">{total_hidden}</div><div class="l">hidden changes</div></div>
      <div class="stat-box px-frame mismatch"><div class="n">{total_mis}</div><div class="l">notes vs files mismatches</div></div>
    </div>
  </div>
</div>
{recent_html}
<div class="tiles">
  <a class="tile px-frame" href="patches/index.html"><div class="t">Patches</div><div class="d">{len(patches)} updates, notes vs files</div></a>
  <a class="tile px-frame" href="builds/index.html"><div class="t">Builds</div><div class="d">Latest: {esc(last_build["build"] if last_build else "—")} · {esc(last_build["date"][:10] if last_build else "")}</div></a>
  <a class="tile px-frame" href="heroes/index.html"><div class="t">Heroes</div><div class="d">History of every hero and ability</div></a>
  <a class="tile px-frame" href="items/index.html"><div class="t">Items</div><div class="d">Every item, including removed ones</div></a>
  <a class="tile px-frame" href="units/index.html"><div class="t">Units</div><div class="d">Troopers, guardians, walkers, patron, neutrals</div></a>
  <a class="tile px-frame" href="tables/heroes.html"><div class="t">Hero Stats</div><div class="d">All stats, each cell with its history</div></a>
  <a class="tile px-frame" href="tables/units.html"><div class="t">Units &amp; Buildings</div><div class="d">Troopers, objectives, neutrals — values over time</div></a>
</div>
'''
    write('index.html', page('Deadlock change history', body, '', '', build=last_build['build'] if last_build else None,
                             description='Deadlock patch history from the game files: hidden changes, exact values, hero stats.'))
    write('changelog.html', changelog_page())
    return 2


def changelog_page() -> str:
    entries = load_json('changelog.json')
    parts = ['<h1>Site changelog</h1>']
    for e in sorted(entries, key=lambda x: x['date'], reverse=True):
        items = ''.join(f'<li><span class="lbl">{esc(i)}</span></li>' for i in e['items'])
        parts.append(f'<section class="section px-frame"><h3 class="section-title">{esc(e["title"])}'
                     f'<span class="dimmer">{esc(e["date"])}</span></h3><ul class="change-list">{items}</ul></section>')
    return page('Site changelog', ''.join(parts), '', '')
