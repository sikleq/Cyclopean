"""The rest of the data pipeline (no tracker clone needed): entity kinds, localization, the hero table
history, returned entities, cosmetics."""
from pipeline import semantics


def test_unit_kind_reads_the_id_before_the_class():
    from pipeline.classify import unit_kind
    # neutral camps and Guardians are npc_trooper subclasses in the data
    assert unit_kind('neutral_lantern_weak', {'_class': 'npc_trooper'}) == 'neutral'
    assert unit_kind('npc_boss_tier1', {'_class': 'npc_trooper_boss'}) == 'building'
    assert unit_kind('npc_super_neutral', {}) == 'neutral'
    assert unit_kind('trooper_medic', {'_class': 'npc_trooper'}) == 'trooper'


def test_weapon_name_comes_from_the_owning_hero():
    from pipeline import loc
    tok = {'citadel_weapon_atlas_set': 'Case Closed', 'citadel_weapon_atlas_set_desc': 'Reloads single shells'}
    assert loc.entity_name(tok, 'citadel_weapon_bull_set', 'hero_atlas') == 'Case Closed'
    assert loc.loc_base(tok, 'citadel_weapon_bull_set', 'hero_atlas') == 'citadel_weapon_atlas_set'
    assert loc.entity_name(tok, 'citadel_weapon_bull_set') == 'citadel_weapon_bull_set'   # no owner: id
    assert loc.entity_name({'x': 'Own'}, 'x', 'hero_atlas') == 'Own'                      # own name first
    tok = {'citadel_weapon_shiv_set': 'Busted Flush'}
    assert loc.entity_name(tok, 'citadel_weapon_shiv_alt', 'hero_shiv') == 'citadel_weapon_shiv_alt'  # alt fire


def test_loc_pairs_without_a_gap_are_read():
    from pipeline import loc
    text = ('"lang" { "Tokens" {\n\t\t"viscous_gootapult""Splatapult"\n'
            '\t\t"MaxBounces_label"\t"Bounces"\n\t\t"x_desc" "a \\"q\\" b"\n} }')
    tok = loc.parse(text)
    # Valve sometimes writes "key""value" with no whitespace; the game reads it, so do we
    assert tok['viscous_gootapult'] == 'Splatapult'
    assert tok['maxbounces_label'] == 'Bounces' and tok['x_desc'] == 'a "q" b'


def test_units_without_a_loc_name_take_the_games_other_strings():
    from pipeline import loc
    tok = {'titan_unit': 'Patron', 'citadel_attackerclass_class_trooper_medic': 'Medic Trooper', 'guardian_unit': 'Guardian'}
    assert loc.unit_name(tok, 'alt_npc_boss_tier3', {}) == 'Patron'
    assert loc.unit_name(tok, 'trooper_medic', {}) == 'Medic Trooper'
    assert loc.unit_name(tok, 'npc_boss_tier1', {'m_sLocUnitName': '#guardian_unit'}) == 'Guardian'
    assert loc.unit_name(tok, 'npc_neutral_bug', {}) == 'npc_neutral_bug'     # never named: the site prettifies it


def test_history_bridges_only_holes_in_the_data():
    from pipeline.hero_table import MISSING, history_changes
    # Billy's weapon was cut from the files on 2025-08-18..08-20: one change 11.26 -> 11.62, not two
    pts = [[5700, '2025-08-01', 11.26], [5747, '2025-08-18', MISSING], [5789, '2025-08-20', 11.62]]
    assert history_changes(pts) == [[5789, '2025-08-20', 11.26, 11.62]]
    assert history_changes([[1, 'a', 5.0], [2, 'b', MISSING], [3, 'c', 5.0]]) == []
    # a stat REMOVED and later restored (an absent field, None) is two real changes with their dates
    assert history_changes([[1, 'a', 16.0], [2, 'b', None], [3, 'c', 15.0]]) == [[2, 'b', 16.0, None], [3, 'c', None, 15.0]]
    # gone at the end stays a removal; a later start is a first value
    assert history_changes([[1, 'a', 5.0], [2, 'b', MISSING]]) == [[2, 'b', 5.0, None]]
    assert history_changes([[1, 'a', None], [2, 'b', 3.0]]) == [[2, 'b', None, 3.0]]


def test_old_builds_bullet_speed_and_dash():
    from pipeline.hero_table import _dash, bullet_speed, burst_cycle
    curve = {'m_BulletSpeedCurve': {'m_spline': [{'x': 0, 'y': 39370}, {'x': 100, 'y': 39370}]}}
    assert round(bullet_speed({}, curve, None)) == 1000             # a flat curve is the speed (before 5747)
    assert burst_cycle({}, {'m_flCycleTime': 0.1}, None) == 0.0      # omitted = the game's default
    hero = {'m_mapBoundAbilities': {'ESlot_Ability_Innate_1': 'citadel_ability_dash'}}
    abil = {'citadel_ability_dash': {'m_mapAbilityProperties': {'AbilityDuration': {'m_strValue': '0.6'}}}}
    assert _dash('EGroundDashDuration', 'AbilityDuration')(hero, {}, abil) == 0.6   # before 5706: the shared dash


def test_returned_entity_diffs_against_its_last_version(monkeypatch):
    from pipeline import cache, history, tracker
    path = tracker.VDATA_PATHS[0]
    blobs = {'b1': {'x': {'dmg': 10, 'cd': 5}}, 'b2': {}, 'b3': {'x': {'dmg': 12, 'cd': 5}}}
    monkeypatch.setattr(tracker, 'VDATA_PATHS', (path,))
    monkeypatch.setattr(tracker, 'blob_id', lambda commit, p: commit if p == path else None)
    monkeypatch.setattr(cache, 'vdata_blob', lambda blob: blobs[blob])
    builds = [tracker.Build(c, '2025-01-0' + c[1], int(c[1]), (path,)) for c in ('b1', 'b2', 'b3')]
    known: dict = {}
    history.entity_changes(builds[0], builds[0], known)                     # baseline
    gone = history.entity_changes(builds[0], builds[1], known)
    back = history.entity_changes(builds[1], builds[2], known)
    assert [e['status'] for e in gone] == ['removed']
    # Valve cut it and put it back: "dmg 10 -> 12", not "everything added"
    assert [(e['status'], [(c['path'], c['old'], c['new']) for c in e['changes']]) for e in back] == \
        [('returned', [('dmg', 10, 12)])]


def test_hero_table_audit_cases():
    from pipeline.hero_table import _lvl, borrowed_guns
    hero = {'m_mapStandardLevelUpUpgrades': {'MODIFIER_VALUE_TECH_RESIST': 0.625, 'MODIFIER_VALUE_BONUS_ATTACK_RANGE': 59}}
    assert _lvl('MODIFIER_VALUE_TECH_ARMOR_DAMAGE_RESIST', 'MODIFIER_VALUE_TECH_RESIST')(hero, {}, {}) == 0.625
    assert round(_lvl('MODIFIER_VALUE_BONUS_ATTACK_RANGE', meters=True)(hero, {}, {}), 2) == 1.5
    gun = {'m_mapBoundAbilities': {'ESlot_Weapon_Primary': 'citadel_weapon_inferno_set'}}
    assert borrowed_guns({'hero_inferno': gun, 'hero_baba': gun, 'hero_atlas':
                          {'m_mapBoundAbilities': {'ESlot_Weapon_Primary': 'citadel_weapon_bull_set'}}}) == {'hero_baba'}


def test_npc_abilities_belong_to_their_unit():
    from pipeline.classify import unit_bound_abilities
    units = {'npc_boss_tier2': {'m_mapBoundAbilities': {'ESlot_Signature_1': 'citadel_ability_tier2boss_stomp'}},
             'alt_npc_boss_tier2': {'m_mapBoundAbilities': {'ESlot_Signature_1': 'citadel_ability_tier2boss_stomp'}},
             'trooper_zipline_container': {'m_mapBoundAbilities': {'ESlot_Ability_ZipLine': 'citadel_ability_zip_line'}}}
    bound = unit_bound_abilities(units, {'citadel_ability_zip_line': 'hero_base'})
    assert bound == {'citadel_ability_tier2boss_stomp': ['alt_npc_boss_tier2', 'npc_boss_tier2']}
    # judged as the unit: Walker's laser 150 -> 125 DPS is DOWN, not a player's NERF
    assert semantics.direction('m_mapAbilityProperties.DPS.m_strValue', 150, 125, 'unit')[0] == 'down'


def test_readable_names_for_ids_and_stand_ins():
    from builders.common import pretty_id
    assert pretty_id('slork_ability_invis', 'hero_slork') == 'Invis'
    assert pretty_id('citadel_ability_tier2boss_aoe_wave') == 'AoE wave'
    assert pretty_id('hero_airheart') == 'Airheart'
    assert semantics.show('20%', semantics.FRACTION) == '20%'            # already a percent: not ×100
    fencer = semantics.describe('m_vecAbilityUpgrades[2].m_vecPropertyUpgrades{DashSpeed}.m_strBonus', {},
                                'ability_fencer_lunge', 'ability')
    assert semantics.show('550', fencer['meters']) == '13.97m/s'
    assert not semantics.prop_speed('DistanceForMaxProjSpeed') and not semantics.prop_speed('CameraPreviewSpeed')


def test_cosmetic_files_name_their_heroes():
    """2026-10-02: news of "underwear textures" for Paige and Victor — the files had them since 6711."""
    from pipeline.cosmetics import ASSET_KINDS, hero_codes, subject_of
    heroes = {'hero_bookworm': {'m_strModelName': 'models/heroes_wip/bookworm/bookworm.vmdl'},
              'hero_nano': {'m_strModelName': 'models/heroes_staging/nano/nano_v2/nano.vmdl'},
              'hero_krill': {'m_strModelName': 'models/heroes_staging/digger/digger.vmdl'},
              'hero_priest': {'m_strModelName': 'models/heroes_wip/priest/priest.vmdl'}}
    codes = hero_codes(heroes, {'hero_nano': 'Calico', 'hero_krill': 'Mo & Krill'})
    assert subject_of('bookworm', codes) == 'hero_bookworm'
    assert subject_of('calico', codes) == 'hero_nano' and subject_of('mo_krill', codes) == 'hero_krill'
    assert subject_of('priest_crossbow', codes) == 'hero_priest'           # a variant of the hero's graph
    assert subject_of('ratking', codes) == 'ratking'                      # unknown: kept as is
    kind = lambda p: next((k for k, rx in ASSET_KINDS if rx.match(p)), None)     # noqa: E731
    assert kind('models/heroes_wip/bookworm/materials/bookworm_basebody_color_png_1eb21a27.vtex_c') == 'base body'
    assert kind('animgraphs/animgraph2/hero/hero_cosmetic.vnmgraph+abrams.vnmgraph_c') == 'cosmetic animation'
    assert kind('models/heroes_wip/bookworm/materials/bookworm_head.vmat_c') is None
