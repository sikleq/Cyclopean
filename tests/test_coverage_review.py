"""Review of the coverage track (2026-10-05): the shared blocks and counts it brought onto the entity pages.

- Channel Move Speed went from engine units to m/s on 2025-08-18 ("50 → 1.3m" read a −97.4% NERF on 93 abilities)
  and every ability's was rewritten at once (491 + 93 + 6 targets: one rule for all, measured together).
- heroes.vdata moved "Player Selectable" into "Hero Development State" on 2026-09-29: no change for a released hero.
- An inline alias whose entity did not move ("dash", "heavy melee") no longer hides the line's pair from the rest of
  the patch: "Stamina bucket 3 heroes … ground dash time 0.7s to 0.72s" is documented.
- Console variables read in the game's units on the Game pages ("citadel_bounty_aoe_radius 2165.35" is 55m), map
  object ids in values read as names, a misspelt glyph fails the build, the console snapshot is one line."""
import re

import pytest

from pipeline.match import MChange, annotate_line, change_json, count_statuses, mark_availability_moves

WINDOW = ((200, '2026-05-01'), (201, '2026-05-02'))


def _mc(path, old, new, op='change', eid='hero_haze', file='heroes.vdata', cat='availability', kind='hero',
        label='X', **kw) -> MChange:
    return MChange(file, eid, path, op, old, new, cat, kind, None, label, False, **kw)


# ---- metres on one side ----------------------------------------------------------------------------------------------

def test_a_bare_side_against_metres_is_engine_units():
    from pipeline import semantics
    assert semantics.metres_pair('50', '1.3m') == ('1.27m', '1.3m')
    assert semantics.metres_pair('1.3m', 50) == ('1.3m', '1.27m')
    assert semantics.metres_pair('20m', '-1') == ('20m', '-1')            # "no limit" stays
    assert semantics.metres_pair('50', '-1') == ('50', '-1')              # no metres on either side
    assert semantics.metres_pair('0', '2m') == ('0', '2m')


def test_channel_move_speed_in_units_then_metres_is_a_small_change_not_a_97_percent_nerf():
    c = _mc('m_mapAbilityProperties.ChannelMoveSpeed.m_strValue', '50', '1.3m', file='abilities.vdata',
            eid='ability_x', cat='balance', kind='ability', label='Channel Move Speed', speed_m=True)
    j = change_json(c)
    assert (j['old_s'], j['new_s']) == ('1.27m/s', '1.3m/s')
    assert j['dir'] != 'nerf' and j['pct'] == pytest.approx(2.4, abs=0.1)


def test_blocks_on_one_ability_field_are_measured_together():
    """491 + 93 + 6 abilities and items rewrote Channel Move Speed with three pairs of values: one rule for all of
    them, each block 'all' (each alone was 'some': three "shared ×491" rows on 268 pages)."""
    from pipeline.shared_groups import SharedGroups
    cat = {f'abilities.vdata:ab_{i}': {'file': 'abilities.vdata', 'id': f'ab_{i}', 'kind': 'ability',
                                       'first': [100, '2025-01-01'], 'last': [300, '2026-10-01']} for i in range(20)}
    path = 'm_mapAbilityProperties.ChannelMoveSpeed.m_strValue'
    groups = SharedGroups()
    for (old, new), ids in ((('50', '-1'), range(0, 12)), (('50', '1.3m'), range(12, 18))):
        sig = ('abilities.vdata', path, old, new, False)
        for i in ids:
            groups.add(sig, {'path': path, 'status': 'hidden'} if sig not in groups else None, f'A{i}',
                       f'abilities.vdata:ab_{i}', 'hidden')
    ents = groups.entities(cat, WINDOW, {})
    assert len(ents) == 2 and {e['scope'] for e in ents} == {'all'}


def test_hero_base_stats_by_archetype_stay_some():
    """The heroes' file is not measured by field: Max Health 740 → 730 for some, 790 → 780 for the others is each
    hero's own stat (its page shows it as a row, not a link)."""
    from pipeline.shared_groups import SharedGroups
    cat = {f'heroes.vdata:hero_{i}': {'file': 'heroes.vdata', 'id': f'hero_{i}', 'kind': 'hero',
                                      'first': [100, '2025-01-01'], 'last': [300, '2026-10-01']} for i in range(10)}
    groups = SharedGroups()
    path = 'm_mapStartingStats.EMaxHealth'
    for (old, new), ids in ((('740', '730'), range(0, 5)), (('790', '780'), range(5, 10))):
        sig = ('heroes.vdata', path, old, new, False)
        for i in ids:
            groups.add(sig, {'path': path, 'status': 'hidden'} if sig not in groups else None, f'H{i}',
                       f'heroes.vdata:hero_{i}', 'hidden')
    assert {e['scope'] for e in groups.entities(cat, WINDOW, {})} == {'some'}


# ---- availability written in another field ----------------------------------------------------------------------------

def test_a_released_heros_availability_moved_to_another_field_is_no_change():
    from builders.cards import player_facing
    flag = _mc('m_bPlayerSelectable', True, None, op='remove', label='Player Selectable')
    state = _mc('m_eHeroDevelopmentState', None, 'EHeroDevState_Release', op='add', label='Hero Development State')
    lab_flag = _mc('m_bPlayerSelectable', True, None, op='remove', eid='hero_boho', label='Player Selectable')
    mark_availability_moves([flag, state, lab_flag])
    assert flag.moved and state.moved and not lab_flag.moved           # no state came for the hero lab one
    assert change_json(flag)['same'] and change_json(state)['same'] and not change_json(lab_flag)['same']
    assert player_facing([change_json(flag), change_json(state)]) == []
    assert count_statuses([flag, state, lab_flag], [])['hidden'] == 1


def test_a_hero_that_became_unselectable_keeps_both_rows():
    flag = _mc('m_bPlayerSelectable', True, None, op='remove')
    state = _mc('m_eHeroDevelopmentState', None, 'EHeroDevState_InDevelopment', op='add')
    mark_availability_moves([flag, state])
    assert not flag.moved and not state.moved


# ---- an alias that names nothing that moved --------------------------------------------------------------------------

def test_a_line_whose_alias_moved_nothing_finds_its_pair_in_the_whole_patch():
    """"Heavy melee" is the Parry ability's alias; the Parry did not move, every hero's melee did (one '@shared'
    block): the line stayed unmatched and the rows carried the eye."""
    melee = [MChange('abilities.vdata', f'ability_melee_{h}', 'm_mapAttacks.EAttackType_Heavy.m_flCooldownOnHit',
                     'change', 0.9, 1.0, 'balance', 'melee', f'hero_{h}', 'Heavy melee › Cooldown On Hit', False,
                     shared=True) for h in ('a', 'b', 'c')]
    other = MChange('abilities.vdata', 'ability_x', 'm_flRange', 'change', 0.9, 1.0, 'balance', 'ability', 'hero_a',
                    'Range', False)
    res = annotate_line('Heavy Melee cooldown increased from 0.9s to 1.0s', melee + [other], {}, {}, {}, {})
    assert res['status'] == 'documented'
    assert all(c.status == 'documented' for c in melee) and other.status == 'hidden'


# ---- the Game pages ---------------------------------------------------------------------------------------------------

def test_console_variables_read_in_the_games_units():
    from builders.game_systems import convar_change, convar_value
    assert convar_value('citadel_bounty_aoe_radius', '2165.35') == '55m'
    assert convar_value('citadel_player_spawn_time_max_ramp_1', '38') == '38s'
    assert convar_value('citadel_comeback_redirect_fraction', '0.7') == '70%'
    assert convar_value('citadel_neutral_player_range_normal_meters', '30') == '30m'
    assert convar_value('citadel_movespeed_bonus_max', '472.441') == '12m/s'
    # a multiplier, a bare "_time" and the game's "no limit" stay numbers; a switch stays a word
    assert convar_value('citadel_street_brawl_ability_range_multiplier', '0.9') == '0.9'
    assert convar_value('citadel_trooper_spawn_interval_late_time', '20') == '20'
    assert convar_value('citadel_neutral_vault_minigame_force_speed', '-1') == '-1'
    assert convar_value('citadel_koth_enabled', 'true') == 'true'
    row = convar_change('citadel_player_spawn_time_max_ramp_1', 'change', '35', '38', 'documented', [1])
    assert (row['old_s'], row['new_s']) == ('35s', '38s') and row['pct'] == pytest.approx(8.6, abs=0.1)


def test_the_game_rules_table_shows_units_and_its_history_on_the_same_scale():
    from builders.game_rules import _cell
    html = _cell('citadel_bounty_aoe_radius', {'value': '2165.35', 'hist': [[6500, '2026-04-01', 1771.65, 2165.35]]})
    assert '>55m</td>' in html and 'data-unit="m"' in html and '[[6500,"2026-04-01",45,55]]' in html


def test_map_object_and_effect_ids_read_as_names():
    """Game › Breakables read "Pickup spirit_permanent_pickup → small_gold_pickup" (79 rows of ids)."""
    from builders.common import ids_to_names
    s = ids_to_names('spirit_permanent_pickup → small_gold_pickup')
    assert '_' not in s and 'Permanent buff' in s
    assert ids_to_names('modifier_streetbrawl_trooper_overtime') == 'Streetbrawl trooper overtime'
    assert ids_to_names('some_unknown_word') == 'some_unknown_word'       # not an id the catalog knows


def test_a_misspelt_glyph_fails_the_build(monkeypatch):
    from builders import game_systems
    fake = (game_systems.System('x', 'X', 'glyph:rulez', (), ()), game_systems.System('y', 'Y', 'glyph:rules', (), ()))
    monkeypatch.setattr(game_systems, 'systems', lambda: fake)
    assert game_systems.missing_icons() == ['glyph:rulez']


def test_the_urns_biased_pickups_variable_is_shown():
    """The Urn part names it; a 'biased' word in the hide list made that rule dead."""
    from builders.game_systems import convar_place
    assert convar_place({'name': 'citadel_allow_biased_urn_pickups', 'flags': 'gamedll'}) == ('urn', 'urn')


def test_the_snapshot_that_starts_console_tracking_is_one_line(monkeypatch):
    """Build 6395 lists all 1,365 variables: one line, out of the tab's number (20.8k elements on 2026-03-10)."""
    from builders import game_systems, patches_pages
    monkeypatch.setattr(game_systems, 'convar_start', lambda: 6395)
    cv = [{'name': f'citadel_x{i}', 'op': 'add', 'new': '1', 'build': 6395} for i in range(5)]
    cv.append({'name': 'citadel_y', 'op': 'change', 'old': '1', 'new': '2', 'build': 6396, 'status': 'hidden'})
    p = {'extras': {'convars': cv}, 'builds': [], 'entities': []}
    [(key, _, n, html)] = patches_pages._extras_parts(p, '../')
    assert key == 'console' and n == 1
    assert 'starts here: 5 variables in build 6395' in html and html.count('<li') == 2
    assert not re.search(r'citadel_x\d', html)
