"""Patch notes in (Steam, forum, the update page) and builds grouped into patch windows."""
from pipeline.news import bbcode_lines, parse_lines


# ---- notes parsing & matching -------------------------------------------------

def test_bbcode_sections_and_bullets():
    text = '[p][b]\\[ Heroes ][/b][/p][list][*]Lash: Flog heal reduced from 50% to 40%[/list]'
    secs = parse_lines(bbcode_lines(text))
    assert secs[-1].title == 'Heroes'
    assert secs[-1].lines == ['Lash: Flog heal reduced from 50% to 40%']
    # a rule is no line: Steam's feed writes [hr] as "------" (Ranked - Beta Season 2, 2026-11-05)
    assert bbcode_lines('[p]A ranked change.[/p]\n\n------\n\n[p]Beta Season 2 begins today![/p]') \
        == ['A ranked change.', 'Beta Season 2 begins today!']


def test_same_notes_from_steam_and_forum_become_one_patch():
    from pipeline.news import Notes, Section
    from pipeline.patches import group
    lines = [f'Hero{i}: Damage increased from {i} to {i + 1}' for i in range(6)]
    steam = Notes('Minor Update - 09-16-2026', '2026-09-17', 'u1', 'steam', [Section('Heroes', lines)])
    forum = Notes('09-16-2026 Update', '2026-09-16', 'u2', 'forum', [Section('Heroes', lines + ['Extra line'])])
    teaser = Notes('City Never Sleeps', '2026-09-16', 'u3', 'steam', [Section('General', ['New map', 'Six heroes', 'Spooky'])])
    builds = [{'build': 1, 'date': '2026-09-16T20:00:00+00:00', 'file': 'x', 'fields': {'balance': 5}}]
    ps = group([steam, forum, teaser], builds)
    assert len(ps) == 1
    p = ps[0]
    assert p.title == '09-16-2026 Update' and p.builds == builds
    assert [s.title for s in p.notes.sections] == ['Heroes']      # the teaser is not a changelog


def test_big_build_without_notes_gets_its_own_patch():
    from pipeline.news import Notes, Section
    from pipeline.patches import group
    notes = Notes('01-01-2026 Update', '2026-01-01', 'u', 'forum',
                  [Section('Heroes', [f'H{i}: X increased from 1 to 2' for i in range(5)])])
    builds = [{'build': 1, 'date': '2026-01-01T20:00:00+00:00', 'file': 'a', 'fields': {'balance': 5}},
              {'build': 2, 'date': '2026-01-20T20:00:00+00:00', 'file': 'b', 'fields': {'balance': 900}}]
    ps = group([notes], builds)
    assert [p.id for p in ps] == ['2026-01-01', 'build-2']
    assert [b['build'] for b in ps[1].builds] == [2]


def test_a_post_without_text_only_names_a_window():
    """2026-10-02 "Listen up, Crumbums! Your King is here." (Rat King) came without text: it names the
    notes-less build of its day, but opens no window and drops no follow-up of that date."""
    from pipeline.news import TITLE_ONLY, Notes, Section
    from pipeline.patches import group
    reveal = Notes('Listen up, Crumbums! Your King is here.', '2026-01-20', 'u', TITLE_ONLY, [])
    notes = Notes('01-01-2026 Update', '2026-01-01', 'n', 'forum',
                  [Section('Heroes', [f'H{i}: X increased from 1 to 2' for i in range(5)])])
    builds = [{'build': 1, 'date': '2026-01-01T20:00:00+00:00', 'file': 'a', 'fields': {'balance': 5}},
              {'build': 2, 'date': '2026-01-20T20:00:00+00:00', 'file': 'b', 'fields': {'balance': 200}}]
    ps = group([notes, reveal], builds)
    assert [p.title for p in ps] == ['01-01-2026 Update', 'Listen up, Crumbums! Your King is here.']
    # beside a changelog, a small build stays in its window: the title-only post makes no new one
    small = [builds[0], {'build': 2, 'date': '2026-01-02T20:00:00+00:00', 'file': 'b', 'fields': {'balance': 200}}]
    reveal2 = Notes('Reveal', '2026-01-02', 'u', TITLE_ONLY, [])
    assert [p.id for p in group([notes, reveal2], small)] == ['2026-01-01']


def test_forum_follow_ups_become_separate_notes(tmp_path, monkeypatch):
    from pipeline import news
    (tmp_path / '2025-08-18.txt').write_text(
        '08-18-2025 Update\nhttps://x/t\n[ Heroes ]\n- A: X from 1 to 2\n[ Follow-up 2025-08-20 ]\n- Billy: Health per boon reduced from 44 to 43\n',
        encoding='utf-8')
    monkeypatch.setattr(news, 'FORUM_DIR', tmp_path)
    ns = news.forum_notes()
    assert [(n.date, n.title) for n in ns] == [('2025-08-18', '08-18-2025 Update'),
                                               ('2025-08-20', '08-18-2025 Update · follow-up 2025-08-20')]
    assert ns[1].sections[0].lines == ['Billy: Health per boon reduced from 44 to 43']


def test_notes_less_window_implementing_a_changelog_is_merged(monkeypatch):
    from pipeline import match
    from pipeline.patches import Patch
    monkeypatch.setattr(match, 'ABSORB_MIN', 2)
    monkeypatch.setattr(match, 'build_patch', lambda p, cat: {'rebuilt': [b['build'] for b in p.builds]})
    lines = [{'text': f'Kevlar: Stat{w} increased from {i} to {i + 1}', 'subject': 'Kevlar', 'status': 'unmatched',
              'changes': []} for w, i in (('alpha', 1), ('beta', 5))]
    notes = match.Patch('2024-12-06', 'A', '2024-12-06', notes=object(), builds=[{'build': 1, 'date': '2024-12-06'}])
    later = Patch('build-2', 'B', '2024-12-14', notes=None, builds=[{'build': 2, 'date': '2024-12-14'}])
    changes = [{'label': f'Stat{w}', 'old_s': str(i), 'new_s': str(i + 1), 'cat': 'balance', 'status': 'unannounced'}
               for w, i in (('alpha', 1), ('beta', 5))]
    results = [(notes, {'sections': [{'lines': lines}]}),
               (later, {'sections': [], 'entities': [{'name': 'Kevlar', 'owner': None, 'changes': changes}]})]
    merged, absorbed = match.absorb_late_windows(results, {})
    assert absorbed == ['build-2'] and len(merged) == 1 and merged[0][1] == {'rebuilt': [1, 2]}


def test_date_titled_changelog_takes_the_announcement_name():
    from pipeline.news import Notes
    from pipeline.patches import _titled
    ann = Notes('City Never Sleeps', '2026-09-29T17:00:00+00:00', 'https://x', 'forum', [])
    notes = Notes('09-29-2026', '2026-09-29', 'https://y', 'forum', [])
    assert _titled(notes, [ann]) == 'City Never Sleeps · 09-29-2026'
    assert _titled(Notes('09-16-2026 Update', '2026-09-16', 'u', 'forum', []), [ann]) == '09-16-2026 Update'


def test_inline_images_are_not_note_lines():
    assert bbcode_lines('[img]{STEAM_CLAN_IMAGE}/45164767/8b22ee.jpg[/img]\n[*] Real line') == ['Real line']


def test_update_page_keeps_changes_drops_lore():
    from pipeline import update_page
    text = {'X_Blue_Name': 'Broadway', 'X_Landmark_1_Title': 'Uptown', 'X_Landmark_1_Body': 'Our first stop on the tour.',
            'X_MustDo_Crates_Kicker': 'Smash open', 'X_MustDo_Crates_Title': 'Tough Crates',
            'X_MustDo_Crates_Body': 'Require a <1>Heavy Melee</1> to break.', 'X_Notes_1': '<1>Improved anti-cheat</1>',
            'X_Notes_2': 'And many other misc changes...'}
    rules = {'title': 'T', 'date': '2026-01-01', 'skip': '^And many other', 'sections': [
        {'title': 'Map', 'items': [{'line': 'Lane names — Blue Lane is {X_Blue_Name}'},
                                   {'list': 'Landmarks', 'keys': r'^X_Landmark_\d+_Title$'}]},
        {'title': 'Gameplay', 'items': [{'cards': '^X_MustDo_'}]},
        {'title': 'Additional Update Notes', 'items': [{'verbatim': r'^X_Notes_\d+$'}]}]}
    lines = update_page.to_lines(text, rules)
    assert lines == ['[ Map ]', '- Lane names — Blue Lane is Broadway', '- Landmarks — Uptown',
                     '[ Gameplay ]', '- Tough Crates: Require a Heavy Melee to break.',
                     '[ Additional Update Notes ]', '- Improved anti-cheat']
    assert not any('first stop' in ln for ln in lines)          # lore is never republished


def test_a_steam_post_the_notes_do_not_hold_starts_a_data_run():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('nsp', Path(__file__).resolve().parent.parent / 'tools' / 'new_steam_posts.py')
    nsp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nsp)
    feed = {'appnews': {'newsitems': [{'gid': '1'}, {'gid': '2'}]}}
    assert nsp.new_ids(feed, [{'gid': '1'}]) == ['2']
    assert nsp.new_ids({}, []) == []                                  # an outage starts nothing


def test_release_window_prefers_the_post_that_names_the_hero_and_counts_heroes_added_released():
    """2026-11-15: a release window took the nearest post within two days unchecked; a hero that arrived already
    released (a new entry with the state Release) had no window at all."""
    from pipeline.history import released_heroes
    from pipeline.news import Notes, Section
    from pipeline.patches import release_windows
    other = Notes('Another hero arrives', '2026-01-10T21:00:00+00:00', 'u1', 'steam', [Section('', ['Meet Haze'])])
    own = Notes('A new face', '2026-01-09T12:00:00+00:00', 'u2', 'steam', [Section('', ['Violet joins the fight'])])
    build = {'build': 1, 'date': '2026-01-10T21:00:00Z', 'released': ['hero_artist']}
    got = release_windows([build], [], [other, own], {'hero_artist': 'Violet', 'hero_haze': 'Haze'})
    assert [p.link for p in got] == ['u2']
    rec = {'entities': [{'file': 'heroes.vdata', 'id': 'hero_new', 'status': 'added', 'changes': [
        {'path': 'm_eHeroDevelopmentState', 'op': 'add', 'old': None, 'new': 'EHeroDevState_Release'}]}]}
    assert released_heroes(rec) == ['hero_new']
