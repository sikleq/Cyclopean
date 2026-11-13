"""The Python / JavaScript twins agree: the scripts redraw what the builders drew, so the two copies of a rule must give
the same answer. A change matrix tile's stripes (builders/dynamics_page.stripes, scripts.js `stripes` in dyn-parts)
and a % pill's strength (builders/render.pct_grade over PCT_STEPS, scripts.js `pctGrade` in hist-tip). The JS
functions live inside the site's one IIFE, so their source is cut out of the joined script and run in Chromium."""
import json
import re

import pytest

from builders.dynamics_page import stripes
from builders.render import PCT_STEPS, TAG_ORDER, pct_grade

from tests.helpers import site_js

STOP = re.compile(r'var\(--tag-([a-z]+)\) ([\d.]+)% ([\d.]+)%')


def _js_function(name: str) -> str:
    """The source of `function <name>(...) {...}` in the site's script, by its braces."""
    js = site_js()
    start = js.index(f'function {name}(')
    depth, i = 0, js.index('{', start)
    while True:
        depth += {'{': 1, '}': -1}.get(js[i], 0)
        i += 1
        if depth == 0:
            return js[start:i]


def _stops(gradient: str) -> list[tuple[str, float, float]]:
    return [(t, float(a), float(b)) for t, a, b in STOP.findall(gradient)]


COUNTS = [
    {'buff': 1},
    {'buff': 2, 'nerf': 1},
    {'nerf': 3, 'new': 1, 'mech': 1},
    {'buff': 1, 'changed': 30},                       # the thin stripe keeps its 12%
    {'up': 2, 'down': 1, 'del': 4, 'rework': 1},     # up / down draw in the CHANGED colour
    {'new': 7, 'buff': 5, 'nerf': 5, 'del': 1, 'on': 2, 'off': 1, 'mech': 3, 'changed': 9},
]


def test_the_matrix_tile_stripes_are_one_rule(browser):
    py_order = sorted(TAG_ORDER, key=lambda t: TAG_ORDER[t])
    js_order = json.loads(re.search(r"var order = (\[[^\]]*\]);", site_js()).group(1).replace("'", '"'))
    # the script's tag order is the builders': ties (on / off, up / down) in either order
    assert [TAG_ORDER[t] for t in js_order] == sorted(TAG_ORDER[t] for t in js_order) and set(js_order) <= set(py_order)
    page = browser.new_page()
    try:
        page.set_content(f"<script>var COLOUR = {{ up: 'changed', down: 'changed' }}; "
                         f"window.stripes = {_js_function('stripes')};</script>")
        for counts in COUNTS:
            tags = [t for t in js_order if counts.get(t)]
            js = page.evaluate('([c, t]) => window.stripes(c, t)', [counts, tags])
            py, got = _stops(stripes(counts)), _stops(js)
            assert [s[0] for s in got] == [s[0] for s in py], counts            # the same stripes, the same colours
            for (_, a1, b1), (_, a2, b2) in zip(py, got):                        # 3 significant digits vs 1 decimal
                assert a1 == pytest.approx(a2, abs=0.06) and b1 == pytest.approx(b2, abs=0.06), (counts, py, got)
    finally:
        page.close()


def test_the_pct_pill_strength_is_one_rule(browser):
    values = [0, 0.4, 4.99, 5, 5.01, 14.9, 15, 29.99, 30, 59.9, 60, 61, 250]
    values += [-v for v in values if v]
    values += [s + d for s in PCT_STEPS for d in (-0.001, 0, 0.001)]
    page = browser.new_page()
    try:
        page.set_content(f'<script>window.pctGrade = {_js_function("pctGrade")};</script>')
        js = page.evaluate('vs => vs.map(v => window.pctGrade(v))', values)
    finally:
        page.close()
    assert js == [pct_grade(v) for v in values]
