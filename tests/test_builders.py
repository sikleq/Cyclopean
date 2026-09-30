"""Rendering helpers: tags, order, escaping."""
from builders.render import change_li, sort_changes, tag_of


def ch(**kw):
    base = {'op': 'change', 'cat': 'balance', 'label': 'Cooldown', 'old_s': '27', 'new_s': '29',
            'dir': 'nerf', 'pct': 7.4, 'grad': 2, 'status': 'hidden', 'path': 'x'}
    base.update(kw)
    return base


def test_tags():
    assert tag_of(ch()) == ('nerf', 'NERF 7%')
    assert tag_of(ch(op='add'))[0] == 'new'
    assert tag_of(ch(op='remove'))[0] == 'del'
    assert tag_of(ch(cat='availability', new='true')) == ('del', 'DISABLED')
    assert tag_of(ch(cat='mechanic', dir='changed', pct=None)) == ('changed', 'MECH')


def test_order_new_buff_nerf_del_changed():
    order = [tag_of(c)[0] for c in sort_changes([
        ch(cat='mechanic', dir='changed', label='a'), ch(op='remove', label='b'), ch(dir='nerf', label='c'),
        ch(dir='buff', label='d'), ch(op='add', label='e')])]
    assert order == ['new', 'buff', 'nerf', 'del', 'changed']


def test_change_li_escapes_and_marks_hidden():
    html = change_li(ch(label='<b>x</b>'))
    assert '&lt;b&gt;' in html and 'mark hidden' in html and 'st-hidden' in html
