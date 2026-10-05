"""The patch page's written notes ("Not in patch notes", "From the files": builders/written_notes.py).

Review 2026-10-05: the tab every "N not in patch notes" link lands on printed rows through the old sentence() and raw
values — 425 of 5,888 lines dumped flag masks, printed the engine's "-1" where the hero page reads "default", engine
enum words, and took the verb from the sign ("Outgoing Bullet Damage Penalty reduced from -35% to -40%": it grew);
namesakes were not told apart, and the tab's number counted console variables it did not list."""
import html
import re

from builders.cards import change_row
from builders.written_notes import line_text, notes_html, verb


def ch(**kw):
    base = {'op': 'change', 'cat': 'balance', 'label': 'Cooldown', 'old_s': '27', 'new_s': '29',
            'dir': 'nerf', 'pct': 7.4, 'status': 'hidden', 'path': 'x', 'key': 'abilities.vdata:a:x'}
    base.update(kw)
    return base


def _page_values(c: dict) -> list[str]:
    """The value texts the entity page's row prints."""
    return [html.unescape(v) for v in re.findall(r'class="(?:old|new|flag[^"]*)[^"]*">([^<]+)<', change_row(c))]


def test_a_line_reads_the_values_the_entity_page_prints():
    # the engine's -1 for a charge delay: "default" on Kelvin's page, "added (-1s)" in the tab
    sentinel = ch(op='add', old_s=None, new_s='-1s', label='Charge Delay', dir='changed', pct=None,
                  path='m_mapAbilityProperties.AbilityCooldownBetweenCharge.m_strValue')
    assert _page_values(sentinel) == ['default']
    assert line_text(sentinel) == 'Charge Delay added (default)'
    # a flag field: its moved bits in words, not the whole mask
    flag = ch(label='Can target', path='m_nAbilityTargetTypes', old_s='CITADEL_UNIT_TARGET_HERO',
              new_s='CITADEL_UNIT_TARGET_HERO | CITADEL_UNIT_TARGET_NEUTRAL', dir='buff', flag=True, pct=None)
    assert _page_values(flag) == ['+neutrals']
    assert line_text(flag) == 'Can target: +neutrals'
    # an engine enum: the page's word
    slot = ch(label='Item slot', path='m_eItemSlotType', old_s='EItemSlotType_Tech', new_s='EItemSlotType_Armor',
              cat='mechanic', dir='changed', pct=None)
    assert _page_values(slot) == ['Spirit', 'Vitality']
    assert line_text(slot) == 'Item slot changed from Spirit to Vitality'
    # "no limit" for 9999, as the page
    assert line_text(ch(label='Channel Move Speed', old_s='1.27m/s', new_s='9999', dir='changed', pct=None)) == \
        'Channel Move Speed changed from 1.27m/s to no limit'


def test_a_negative_value_takes_its_verb_from_the_rows_percent_or_its_size():
    # a penalty that grew (its pill +14.3%), a slow that got weaker
    assert line_text(ch(label='Outgoing Bullet Damage Penalty', old_s='-35%', new_s='-40%', dir='buff', pct=14.3)) == \
        'Outgoing Bullet Damage Penalty increased from -35% to -40%'
    assert verb('-25%', '-22%') == 'reduced'
    # a resist below zero reads by its sign (its pill −33.3%)
    assert verb('-6%', '-8%', -33.3) == 'reduced'
    # positive values by the numbers, not a percent of the value behind them ("Stamina Cooldown 5s → 6s": −16.7%)
    assert verb('5s', '6s', -16.7) == 'increased'
    assert verb('30%', '-9%') == 'changed' and verb('2', 'words') == 'changed' and verb('30%', '2') == 'changed'


def test_namesakes_and_sections_and_console_variables():
    names = {'hero_kelvin': 'Kelvin'}
    shelter = {'file': 'abilities.vdata', 'id': 'ability_shelter', 'owner': 'hero_kelvin', 'name': 'Frozen Shelter'}
    trigger = {'file': 'abilities.vdata', 'id': 'ability_shelter_trigger', 'owner': 'hero_kelvin',
               'name': 'Frozen Shelter'}
    item = {'file': 'abilities.vdata', 'id': 'upgrade_decay', 'kind': 'item', 'name': 'Decay'}
    urn = {'file': 'misc.vdata', 'id': 'urn', 'kind': 'global', 'name': 'Urn'}
    heal = 'm_mapAbilityProperties.%s.m_strValue'
    convar = ch(label='citadel_urn_time', path='citadel_urn_time', old_s='30', new_s='45', dir='up', pct=50.0,
                convar=True)
    rows = [(shelter, ch(label='Radius', old_s='5m', new_s='6m', dir='buff'), True),
            (trigger, ch(label='Radius', old_s='2m', new_s='3m', dir='buff'), True),
            (item, ch(label='Incoming Healing', path=heal % 'HealAmpReceivePenaltyPercent', old_s='-55%',
                      new_s='-35%', dir='nerf', pct=-36.4), True),
            (item, ch(label='Incoming Healing', path=heal % 'HealAmpRegenPenaltyPercent', old_s='-55%',
                      new_s='-35%', dir='nerf', pct=-36.4), True),
            (urn, ch(label='Bounty', old_s='100', new_s='120', dir='buff'), False),
            (None, convar, False)]
    body, n = notes_html(rows, lambda e: e['name'], names)
    text = html.unescape(re.sub(r'<[^>]+>', ' ', body))
    assert n == len(rows) == body.count('<li>')               # the tab's number is what it lists
    assert 'Kelvin · Frozen Shelter: Radius increased from 5m to 6m' in text
    assert 'Kelvin · Frozen Shelter · trigger: Radius increased from 2m to 3m' in text
    assert 'Decay: Incoming Healing · receive reduced from -55% to -35%' in text
    assert 'Decay: Incoming Healing · regen reduced from -55% to -35%' in text
    heads = re.findall(r'<h3 class="gn-h">([^<]+)<span class="n">(\d+)', body)
    assert heads == [('Heroes', '2'), ('Items', '2'), ('Game rules &amp; map objects', '1'), ('Console variables', '1')]
    assert '<code>citadel_urn_time</code> increased from 30 to 45' in body
    assert body.count('class="tag ') == len(rows)             # every line has its tag badge


def test_the_tab_lists_what_its_number_counts(monkeypatch):
    """The "Not in patch notes" tab of an update with notes: its lines are exactly the rows patch_counts counts, the
    console variables included (City Never Sleeps: 360 on the tab, 353 lines)."""
    from builders import game_systems
    from builders.patch_counts import count
    from builders.patches_pages import _generated_notes
    monkeypatch.setattr(game_systems, 'convar_start', lambda: None)
    monkeypatch.setattr(game_systems, 'convar_place', lambda cv: ('respawn', 'timer'))
    item = {'key': 'abilities.vdata:upgrade_x', 'file': 'abilities.vdata', 'id': 'upgrade_x', 'kind': 'item',
            'name': 'Extra', 'changes': [ch(key='abilities.vdata:upgrade_x:a', label='Range', status='documented'),
                                         ch(key='abilities.vdata:upgrade_x:b', label='Radius', status='hidden')]}
    cv = {'name': 'citadel_respawn_time', 'op': 'change', 'old': '10', 'new': '12', 'build': 5, 'status': 'hidden',
          'flags': 'gamedll'}
    p = {'entities': [item], 'extras': {'convars': [cv]}, 'sections': [{'lines': []}]}
    pages = frozenset({'abilities.vdata:upgrade_x'})
    html_ = _generated_notes(p, only_hidden=True, pages=pages)
    assert html_.count('<li>') == count(p, pages)['not_in_notes'] == 2
    assert 'citadel_respawn_time' in html_ and 'Range' not in html_
