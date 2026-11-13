"""Helpers shared by the tests: a change row (`ch`), a matcher change (`mc`), the site's CSS and JS, a page opened in
the `browser` fixture (inline or as a file next to the site's assets), and element boxes measured in it."""
from __future__ import annotations

from pathlib import Path

from builders.common import site_parts, site_source, site_text
from pipeline.match import MChange

ROOT = Path(__file__).resolve().parents[1]

_CH_BASE = {'op': 'change', 'cat': 'balance', 'label': 'Cooldown', 'old_s': '27', 'new_s': '29', 'dir': 'nerf',
            'pct': 7.4, 'grad': 2, 'status': 'hidden', 'path': 'x'}


def make_ch(**defaults):
    """A `ch(**kw)` whose rows start from the base row with `defaults` over it (new keys go last)."""
    def ch(**kw):
        base = {**_CH_BASE, **defaults}
        base.update(kw)
        return base
    return ch


ch = make_ch()                                      # one change row of a patch archive, a hidden nerf by default


def mc(file, eid, path, old, new, label, op='change', cat='balance', kind='ability', owner=None, **kw) -> MChange:
    """One matcher change (pipeline.match.MChange), not yet weighed (`flag` False)."""
    return MChange(file, eid, path, op, old, new, cat, kind, owner, label, False, **kw)


# ---- the site's CSS and JS ---------------------------------------------------------------------------------------

def site_css() -> str:
    """The site's stylesheet (site/css/*.css joined) as the build reads it for dist/styles.css."""
    return site_text('styles.css')


def site_js() -> str:
    """The site's script (site/js/*.js joined) as the build reads it for dist/scripts.js."""
    return site_text('scripts.js')


def site_files() -> list[Path]:
    """Every part file of the site's stylesheet and script (site/css, site/js)."""
    return site_parts('styles.css') + site_parts('scripts.js')


def js_files() -> list[Path]:
    """The part files of the site's script (site/js)."""
    return site_parts('scripts.js')


def write_site_assets(folder: Path) -> None:
    """styles.css and scripts.js into `folder`, as a built site has them (unminified)."""
    (folder / 'styles.css').write_bytes(site_source('styles.css'))
    (folder / 'scripts.js').write_bytes(site_source('scripts.js'))


# ---- pages in the browser ----------------------------------------------------------------------------------------

def open_file(browser, tmp_path: Path, html: str, ctx_args: dict, hash_: str = '', settle_ms: int = 0):
    """`html` as tmp_path/x/page.html with the site's CSS and JS one level up (rel '../'), opened at `hash_`,
    offline. Returns (context, page, page errors)."""
    write_site_assets(tmp_path)
    (tmp_path / 'x').mkdir(exist_ok=True)
    f = tmp_path / 'x' / 'page.html'
    f.write_text(html, encoding='utf-8')
    ctx = browser.new_context(**ctx_args)
    pg = ctx.new_page()
    pg.route('**/*', lambda r: r.continue_() if r.request.url.startswith('file:') else r.abort())
    errors: list[str] = []
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.goto(f.as_uri() + hash_)
    if settle_ms:
        pg.wait_for_timeout(settle_ms)
    return ctx, pg, errors


def open_page(browser, tmp_path: Path, html: str, width: int = 1440, height: int = 900, phone: bool = False,
              hash_: str = '', settle_ms: int = 0):
    """open_file at a window size; `phone`: a touch phone at device scale 2."""
    opts = {'viewport': {'width': width, 'height': height}}
    if phone:
        opts.update(is_mobile=True, has_touch=True, device_scale_factor=2)
    return open_file(browser, tmp_path, html, opts, hash_=hash_, settle_ms=settle_ms)


def open_inline(browser, body: str, width: int = 1440, height: int = 900, touch: bool = False, head: str = '',
                main: str | None = 'page', viewport_meta: bool = True):
    """A page of `body` (inside <main class=`main`> unless `main` is None) with the site's CSS and JS inline; `head`
    goes after the stylesheet; `touch`: a phone (is_mobile, has_touch: hover is none). Returns (context, page,
    page errors)."""
    opts = {'viewport': {'width': width, 'height': height}}
    if touch:
        opts.update(is_mobile=True, has_touch=True)
    ctx = browser.new_context(**opts)
    page = ctx.new_page()
    errors: list[str] = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    meta = '<meta name="viewport" content="width=device-width, initial-scale=1">' if viewport_meta else ''
    inner = f'<main class="{main}">{body}</main>' if main is not None else body
    page.set_content(f'<!doctype html><html><head><meta charset="utf-8">{meta}<style>{site_css()}</style>{head}</head>'
                     f'<body>{inner}<script>{site_js()}</script></body></html>')
    return ctx, page, errors


def box(pg, sel: str) -> dict:
    """The first `sel` element's box: l, r, t, b, w, h."""
    return pg.evaluate(f"(() => {{ const r = document.querySelector({sel!r}).getBoundingClientRect();"
                       " return {l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height}; })()")


def boxes(pg, sel: str) -> list[dict]:
    """Every `sel` element's box."""
    return pg.evaluate(f"[...document.querySelectorAll({sel!r})].map(e => {{ const r = e.getBoundingClientRect();"
                       " return {l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height}; })")


def no_side_scroll(pg) -> bool:
    """The page does not scroll sideways."""
    return pg.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth')
