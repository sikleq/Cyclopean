"""Home page: the latest update first (how big, which way, who was hit, biggest moves),
the site's totals, recent patches, all heroes."""
from __future__ import annotations

from .common import (EYE_SVG, esc, plural, glyph_for, hero_icon, load_json, mark, page, patch_name, patch_parts,
                     patch_title_html, visual, write)
from .patches_pages import GAMEPLAY, _summary, hero_names
from .render import tag_html, vals_html

RECENT_PATCHES = 20       # the column beside the hero grid (8 rows of faces): 6 left most of it empty
BIGGEST = 8


def _biggest(p: dict) -> str:
    """The biggest balance moves as small cards: icon, entity (+ its hero), tag, field, values."""
    from .common import entity_icon
    names = hero_names()
    cards = []
    # one card per ability: three rows of the same ultimate crowded out the rest
    seen: set[str] = set()
    picked = []
    for r in p.get('key_changes') or []:
        if r['entity'] not in seen:
            seen.add(r['entity'])
            picked.append(r)
    picked = picked[:BIGGEST]
    if len(picked) > 1:
        picked = picked[:len(picked) // 2 * 2]      # two columns: full rows only, no stretched last card
    for r in picked:
        file, _, eid = r['entity'].partition(':')
        ic = entity_icon(file, eid, r.get('kind') or '', '', r.get('name'), r.get('owner'))
        who = names.get(r.get('owner') or '', '')
        c = r['change']
        cards.append(f'<div class="mini"><span class="mi">{visual(ic, glyph_for(file, eid))}</span>'
                     f'<div class="mt"><div class="mn">{esc(r["name"])}'
                     f'{"<span class=own>" + esc(who) + "</span>" if who and who != r["name"] else ""}</div>'
                     f'<div class="ml">{tag_html(c)}<span>{esc(c["label"])}</span></div></div>'
                     f'<div class="mv">{vals_html(c)}</div></div>')
    return f'<div class="minis">{"".join(cards)}</div>' if cards else ''


def _latest(row: dict | None) -> str:
    if not row:
        return ''
    p = load_json(f'patches/{row["id"]}.json.gz')
    from .cards import gameplay_entities
    gameplay = gameplay_entities(p['entities'])
    href = f'patches/{esc(row["id"])}.html'
    c = p.get('counts', {})
    # notes that only touch the interface say nothing about balance: say so next to the date
    quiet = (' · <span class="no-notes">no balance notes</span>'
             if p.get('sections') and not c.get('documented') and not c.get('described') else '')
    return (f'<section class="latest px-frame hero-frame">'
            f'<div class="banner{" named" if patch_name(row["title"]) else ""}"><span class="bt"><a href="{href}">'
            f'{patch_title_html(row)}</a></span><span class="bd">latest update{quiet}</span>'
            f'<span class="bc"><a class="px-btn" href="{href}">Open the patch →</a></span></div>'
            f'{_summary(p, gameplay, "", link_base=href).replace("summary px-frame", "summary")}'
            f'<h3 class="mini-h">Biggest changes</h3>{_biggest(p)}</section>')


def _recent_name(r: dict) -> str:
    """The date is in its own column: the row shows the update's name, or a quiet 'update'."""
    name, _, follow = patch_parts(r)
    fu = ' <span class="pfu">follow-up</span>' if follow else ''
    return (f'<span class="pname">{esc(name)}</span>' if name else '<span class="pkind">update</span>') + fu


def _recent(patches: list[dict]) -> str:
    rows = []
    for r in list(reversed(patches))[:RECENT_PATCHES]:
        c, lc = r['counts'], r['line_counts']
        if r.get('has_notes'):
            chips = (f'<span class="au">{mark("documented")}<b>{c.get("documented", 0)}</b></span>'
                     f'<span class="au au-hidden">{mark("hidden")}<b>{c.get("hidden", 0)}</b></span>')
        else:
            chips = f'<span class="au au-hidden">{mark("hidden")}<b>{c.get("unannounced", 0)}</b> no notes</span>'
        if lc.get('mismatch'):
            chips += f'<span class="au au-mismatch">{mark("mismatch")}<b>{lc["mismatch"]}</b></span>'
        rows.append(f'<a class="rp" href="patches/{esc(r["id"])}.html"><span class="rd">{esc(r["date"])}</span>'
                    f'<span class="rt">{_recent_name(r)}</span><span class="rb">{plural(r["builds"], "build")}</span>'
                    f'<span class="rc">{chips}</span></a>')
    return '<div class="recent px-frame">' + ''.join(rows) + '</div>'


def build_all() -> int:
    patches = load_json('patches/index.json')
    builds = load_json('builds/index.json')
    heroes = load_json('tables/heroes.json')['heroes']
    latest = patches[-1] if patches else None
    total_hidden = sum(p['counts'].get('hidden', 0) for p in patches)
    total_doc = sum(p['counts'].get('documented', 0) for p in patches)
    total_mis = sum(p['line_counts'].get('mismatch', 0) for p in patches)
    last_build = builds[-1] if builds else None
    strip = ''.join(f'<a class="hp" href="heroes/{esc(h["id"].removeprefix("hero_"))}.html">'
                    f'<img class="px" src="{esc(hero_icon(h["id"], "") or "")}" alt="" loading="lazy">'
                    f'<span>{esc(h["name"])}</span></a>' for h in heroes)
    body = f'''
<div class="home-top">
  <div class="home-brand"><span class="mark hidden">{EYE_SVG}</span><h1>Cyclopean</h1></div>
  <div class="home-stats">
    <div class="hs"><span class="n">{len(builds)}</span><span class="l">builds compared</span></div>
    <div class="hs documented"><span class="n">{total_doc}</span><span class="l">documented</span></div>
    <div class="hs hidden"><span class="n">{total_hidden}</span><span class="l">hidden</span></div>
    <div class="hs mismatch"><span class="n">{total_mis}</span><span class="l">notes ≠ files</span></div>
  </div>
</div>
{_latest(latest)}
<div class="home-grid">
  <div><div class="banner"><span class="bt">Recent patches</span><span class="bc"><a href="patches/index.html">all →</a></span></div>
  {_recent(patches)}</div>
  <div><div class="banner"><span class="bt">Heroes</span><span class="bc">{len(heroes)}</span></div>
  <div class="hgrid">{strip}</div></div>
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
