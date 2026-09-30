"""Home page: latest update at a glance, all heroes, recent builds, entry points."""
from __future__ import annotations

from .common import EYE_SVG, build_pages, esc, hero_icon, load_json, mark, page, write
from .patches_pages import hero_names
from .render import key_change_rows


def _latest_card(latest: dict | None) -> str:
    if not latest:
        return ''
    p = load_json(f'patches/{latest["id"]}.json.gz')
    c = latest['counts']
    lc = latest['line_counts']
    if latest.get('has_notes'):
        nums = (f'<span class="chip">{mark("documented")}{c.get("documented", 0)} documented</span>'
                f'<span class="chip">{mark("hidden")}{c.get("hidden", 0)} hidden</span>'
                f'<span class="chip">{mark("mismatch")}{lc.get("mismatch", 0)} mismatches</span>')
    else:
        nums = f'<span class="chip">{mark("hidden")}{c.get("unannounced", 0)} changes, no official numbers</span>'
    rows = key_change_rows((p.get('key_changes') or [])[:10], '', hero_names())
    table = f'<table class="hist">{rows}</table>' if rows else ''
    return (f'<section class="section px-frame bright"><div class="crumbs">Latest update · {esc(latest["date"])}</div>'
            f'<h2 class="flush"><a href="patches/{esc(latest["id"])}.html">{esc(latest["title"])}</a></h2>'
            f'<div class="chips">{nums}</div>{"<h3>Biggest changes</h3>" + table if table else ""}'
            f'<p><a class="px-btn" href="patches/{esc(latest["id"])}.html">Open the patch →</a></p></section>')


def build_all() -> int:
    patches = load_json('patches/index.json')
    builds = load_json('builds/index.json')
    heroes = load_json('tables/heroes.json')['heroes']
    latest = patches[-1] if patches else None
    total_hidden = sum(p['counts'].get('hidden', 0) for p in patches)
    total_doc = sum(p['counts'].get('documented', 0) for p in patches)
    total_mis = sum(p['line_counts'].get('mismatch', 0) for p in patches)
    last_build = builds[-1] if builds else None
    stems = build_pages()

    recent = []
    for r in reversed(builds):
        f = r.get('fields', {})
        gp = f.get('balance', 0) + f.get('mechanic', 0) + f.get('availability', 0)
        if not (gp or r.get('loc') or r.get('convars')):
            continue
        recent.append(f'<tr><td class="sc"><a href="builds/{stems[r["file"]]}.html">Build {r["build"]}</a></td>'
                      f'<td class="muted">{esc(r["date"][:10])}</td><td class="ov">{gp} gameplay · {r.get("loc", 0)} text · '
                      f'{r.get("convars", 0)} cvars</td></tr>')
        if len(recent) == 8:
            break
    strip = ''.join(f'<a href="heroes/{esc(h["id"].removeprefix("hero_"))}.html" data-tooltip="{esc(h["name"])}">'
                    f'<img class="px" src="{esc(hero_icon(h["id"], "") or "")}" alt="{esc(h["name"])}" loading="lazy"></a>'
                    for h in heroes)
    body = f'''
<div class="home-brand">
  <span class="mark hidden">{EYE_SVG}</span>
  <h1>Cyclopean</h1>
</div>
<div class="home-grid">
  <div>
    {_latest_card(latest)}
    <h2>Latest builds</h2>
    <table class="hist px-frame">{"".join(recent)}</table>
  </div>
  <div>
    <div class="stat-strip">
      <div class="stat-box px-frame"><div class="n">{len(builds)}</div><div class="l">builds compared</div></div>
      <div class="stat-box px-frame documented"><div class="n">{total_doc}</div><div class="l">documented changes</div></div>
      <div class="stat-box px-frame hidden"><div class="n">{total_hidden}</div><div class="l">hidden changes</div></div>
      <div class="stat-box px-frame mismatch"><div class="n">{total_mis}</div><div class="l">notes vs files mismatches</div></div>
    </div>
    <h2>Heroes</h2>
    <div class="hero-strip">{strip}</div>
    <h2>Tables</h2>
    <div class="tiles">
      <a class="tile px-frame" href="tables/heroes.html"><div class="t">Hero Stats</div><div class="d">Every stat with its history</div></a>
      <a class="tile px-frame" href="tables/units.html"><div class="t">Units &amp; Buildings</div><div class="d">Troopers, objectives, neutrals</div></a>
      <a class="tile px-frame" href="tables/items.html"><div class="t">Items</div><div class="d">Cost, tier, stats over time</div></a>
    </div>
  </div>
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
