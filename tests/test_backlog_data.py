"""Data / pipeline backlog of the review rounds (2026-10-06).

- The matcher reaches what Valve announced about the Game: a game system the line names ("Jump Pad", "Zip Line",
  "Urn", "Bounty") brings its entries no page claims and its console variables, an added variable included; a number
  list matches a line that gives it element by element ("1/0.65/0.28 → 1/0.54/0.36"); an interface word next to an
  entity whose files moved no longer ends the line before it is matched (#47.2)."""
from pipeline import game_map
from pipeline.match import MChange, annotate_line, list_match, names_other_stat, system_pools, words


def _mc(file, eid, path, old, new, label, op='change', kind='global', **kw) -> MChange:
    return MChange(file, eid, path, op, old, new, 'balance', kind, None, label, False, **kw)


def _by_ent(changes):
    out = {}
    for c in changes:
        out.setdefault(f'{c.file}:{c.eid}', []).append(c)
    return out


def _cat(*keys_kinds):
    return {k: {'file': k.split(':', 1)[0], 'id': k.split(':', 1)[1], 'kind': kind} for k, kind in keys_kinds}


# ---- 1. game systems, lists, added console variables --------------------------------------------------------------

def test_a_line_naming_a_game_system_reaches_its_nameless_entry():
    """"Jump Pad stun window increased from 0.6s to 0.9s" (2025-11-21) is the catapult watcher's Duration: the entry
    has no name and its label shares no word with the line — it kept the eye."""
    watcher = _mc('modifiers.vdata', 'modifier_citadel_catapult_damage_watcher', 'm_flDuration', 0.6, 0.9, 'Duration',
                  kind='modifier')
    other = _mc('abilities.vdata', 'ability_x', 'm_flSomething', 0.6, 0.9, 'Something', kind='ability')
    changes = [watcher, other]
    cat = _cat(('modifiers.vdata:modifier_citadel_catapult_damage_watcher', 'modifier'),
               ('abilities.vdata:ability_x', 'ability'))
    by_ent = _by_ent(changes)
    pools = system_pools(by_ent, cat)
    assert 'modifiers.vdata:modifier_citadel_catapult_damage_watcher' in pools['combat']
    res = annotate_line('Jump Pad stun window increased from 0.6s to 0.9s', changes, by_ent, {}, cat, {}, None, pools)
    assert res['status'] == 'documented' and res['changes'] == [watcher.key]
    assert watcher.status == 'documented' and other.status == 'hidden'


def test_a_system_entry_that_names_another_stat_is_not_the_lines():
    """"Movement Speed powerup movespeed reduced from 2 to 1" is not the stamina powerup's Extra Stamina 2 -> 1."""
    stamina = _mc('misc.vdata', 'extra_stamina_pickup', 'm_sModifer.m_vecScriptValues{X}.m_value', 2, 1,
                  'Effect › Extra Stamina')
    assert names_other_stat(stamina, words('Movement Speed powerup movespeed reduced from 2 to 1'))
    assert not names_other_stat(stamina, words('Stamina powerup reduced from 2 to 1'))
    by_ent = _by_ent([stamina])
    cat = _cat(('misc.vdata:extra_stamina_pickup', 'global'))
    pools = system_pools(by_ent, cat)
    res = annotate_line('Movement Speed powerup movespeed reduced from 2 to 1', [stamina], by_ent, {}, cat, {}, None,
                        pools)
    assert res['status'] == 'unmatched' and stamina.status == 'hidden'


def test_a_line_without_numbers_links_no_system_entry_by_a_word():
    """A system holds dozens of entries: "Added Dash Speed to the Vitality stat screen" took the zipline's Latch
    End Speed when words could reach them."""
    latch = _mc('abilities.vdata', 'citadel_ability_zip_line', 'm_mapAbilityProperties.LatchEndSpeed.m_strValue',
                None, 5, 'Latch End Speed', op='add', kind='shared')
    by_ent = _by_ent([latch])
    cat = _cat(('abilities.vdata:citadel_ability_zip_line', 'shared'))
    pools = system_pools(by_ent, cat)
    assert pools, 'the zipline is a Movement & combat entry'
    res = annotate_line('Added Dash Speed to the Vitality stat screen', [latch], by_ent, {}, cat, {}, None, pools)
    assert res['status'] != 'described' and latch.status == 'hidden'


def test_a_number_list_matches_the_line_that_lists_it():
    split = _mc('generic_data.vdata', 'm_flTrooperKillGoldShareFrac', 'value', (1, 0.65, 0.28, 0.15, 0.12, 0.08),
                (1, 0.54, 0.36, 0.25, 0.2, 0.16), 'value')
    pairs = [(1, 1), (0.65, 0.54), (0.28, 0.36), (0.15, 0.25), (0.12, 0.2), (0.08, 0.16)]
    assert list_match(split, pairs)
    assert not list_match(split, pairs[:5])                     # another length is another list
    # percents for fractions, rounded by the notes: "100/70/45/33%" for 1 / 0.7 / 0.45 / 0.333
    share = _mc('generic_data.vdata', 'm_flPostLanePhaseGoldShareFrac', 'value', (1, 0.7, 0.45, 0.333),
                (1, 0.6, 0.35, 0.25), 'value')
    assert list_match(share, [(100, 100), (70, 60), (45, 35), (33, 25)], rel=0.1)
    # an entry the notes skip because it stayed (0 enemies: 0%)
    walker = _mc('npc_units.vdata', 'npc_boss_tier2', 'm_NearbyEnemyResist.m_flResistValues', (0, 0, 8, 16),
                 (0, 0, 0, 20), 'Nearby Enemy Resist › Resist Values')
    assert list_match(walker, [(0, 0), (8, 0), (16, 20)])


def test_the_bounty_split_line_is_the_list_of_its_system():
    split = _mc('generic_data.vdata', 'm_flTrooperKillGoldShareFrac', 'value', (1, 0.65, 0.28, 0.15, 0.12, 0.08),
                (1, 0.54, 0.36, 0.25, 0.2, 0.16), 'value')
    by_ent = _by_ent([split])
    cat = _cat(('generic_data.vdata:m_flTrooperKillGoldShareFrac', 'global'))
    pools = system_pools(by_ent, cat)
    res = annotate_line('Trooper bounty split ratios updated from 1/0.65/0.28/0.15/0.12/0.08 to '
                        '1/0.54/0.36/0.25/0.2/0.16', [split], by_ent, {}, cat, {}, None, pools)
    assert res['status'] == 'documented' and res['changes'] == [split.key]


def test_an_added_console_variable_of_a_named_system_matches():
    """"Unstable Rift spawn interval increased from every 6 minutes to every 7 minutes" (2026-06-30) is
    citadel_koth_respawn_interval, added at 420 seconds."""
    cv = MChange('convars', 'citadel_koth_respawn_interval', 'citadel_koth_respawn_interval', 'add', None, '420',
                 'balance', 'global', None, 'koth respawn interval', False)
    assert game_map.convar_system(cv.eid) == 'urn'
    by_ent = _by_ent([cv])
    pools = system_pools(by_ent, {})
    res = annotate_line('Unstable Rift spawn interval increased from every 6 minutes to every 7 minutes', [cv],
                        by_ent, {}, {}, {}, None, pools)
    assert res['status'] in ('documented', 'rounded') and cv.status == 'documented'


def test_system_phrases_prefer_the_longer_name():
    assert game_map.phrases_in('Jump Pads now launch higher')[0] == ('jump pad', 'combat')
    assert ('urn', 'urn') in game_map.phrases_in('Soul Urn bounty') or ('soul urn', 'urn') in game_map.phrases_in(
        'Soul Urn bounty')
    assert all(p != 'soul' for p, _ in game_map.phrases_in('Soul Urn bounty'))


def test_an_interface_line_about_a_moved_ability_is_matched():
    """#47.2: "Added keybinds for "Fly Up" and "Fly Down". Used for flying abilities like Ivy's Air Drop" names an
    ability whose flight controls came in that window; the interface word ended the line as untracked."""
    fly = _mc('abilities.vdata', 'citadel_ability_tengu_airlift', 'm_bUsesFlightControls', None, True,
              'Uses Flight Controls', op='add', kind='ability')
    fly.cat = 'mechanic'
    idx = {'air drop': ['abilities.vdata:citadel_ability_tengu_airlift']}
    cat = {'abilities.vdata:citadel_ability_tengu_airlift': {'file': 'abilities.vdata', 'id': 'citadel_ability_tengu_airlift',
                                                              'kind': 'ability', 'owner': 'hero_tengu'}}
    res = annotate_line('Added keybinds for "Fly Up" and "Fly Down". Used for flying abilities like Ivy\'s Air Drop '
                        'and its flight', [fly], _by_ent([fly]), idx, cat, {})
    assert res['status'] == 'described' and fly.status == 'described'
    # an interface line about nothing that moved still ends early (annotate() calls it untracked)
    res = annotate_line('Added keybinds for the scoreboard', [fly], _by_ent([fly]), idx, cat, {})
    assert res['status'] == 'unmatched' and not res['changes']


# ---- 2. engine-unit speeds ----------------------------------------------------------------------------------------

def test_capped_and_killer_plane_speeds_read_in_metres_per_second():
    """#13: Air / Fall Speed Max, the soul orbs' Killer Plane speeds, a modifier's speed bonus, the hook's return
    speed and a growing value's base were engine units ("Air Speed Max 150 → 161.42" is the notes' 3.8 → 4.1 m/s)."""
    from pipeline import semantics as s

    def shown(path, v, kind='ability', eid='ability_x'):
        d = s.describe(path, {}, eid, kind)
        meters = s.M_SPEED if d.get('speed_m') and not d['meters'] else d['meters']
        return s.show(v, meters, d.get('unit', ''))
    assert shown('m_mapAbilityProperties.AirSpeedMax.m_strValue', '161.42') == '4.1m/s'
    assert shown('m_mapAbilityProperties.FallSpeedMax.m_strValue', '30') == '0.762m/s'
    assert shown('m_mapAbilityProperties.FallSpeedMax.m_strValue', '1m') == '1m/s'       # written in m: m/s
    assert shown('m_flKillerPlaneHorizontalSpeedX', 65, 'global', 'xp_orb_spawner') == '1.65m/s'
    assert shown('m_flKillerPlaneVerticalSpeed', 50, 'global', 'xp_orb_trooper') == '1.27m/s'
    assert shown('m_sModifer.m_vecScriptValues{MODIFIER_VALUE_SPRINT_SPEED_BONUS}.m_value', 118.11, 'global',
                 'movement_powerup_pickup') == '3m/s'
    assert shown('m_SpeedBonusModifier.m_vecScriptValues{MODIFIER_VALUE_MOVEMENT_SPEED_MAX}.m_value', 118.11,
                 'modifier', 'citadel_modifier_teleporter') == '3m/s'
    assert shown('m_TargetModifier.m_flReturnSpeed', 2200) == '55.88m/s'
    assert shown('m_flMaxMovespeed', 600) == '15.24m/s'
    assert shown('m_flPickupRadius.m_flBase', 85, 'global', 'small_gold_pickup') == '2.16m'
    assert shown('m_flPickupExpirationDuration.m_flBase', 30, 'global', 'small_gold_pickup') == '30s'
    # still not travel: a percent, a slow, a decay rate, a start minute
    assert shown('m_sModifer.m_vecScriptValues{MODIFIER_VALUE_ZIP_LINE_SPEED_PERCENTAGE}.m_value', 30, 'global',
                 'movement_powerup_pickup') == '30%'
    assert shown('m_flKillerPlaneHorizontalDecayRate', 15, 'global', 'xp_orb_trooper') == '15'
    assert shown('m_flPickupRadius.m_flStartMinute', 10, 'global', 'small_gold_pickup') == '10'
    assert s.engine_unit('m_flInitialOffsetLerpBias') is False and s.engine_unit('m_flTurnRate') is False
