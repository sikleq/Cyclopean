"""Data-quality track, review fixes (2026-10-04): renames that were other fields, internal weapon codes,
empty flag cells, units Valve dropped, a home for the abilities every hero has, and the smaller wording
fixes. No tracker clone needed."""
from builders import dynamics_page
from builders.cards import is_noop, merge_renames
from builders.common import pretty_id
from builders.render import flags_html, vals_html
from pipeline import flags, labels, semantics
from pipeline.match import MChange, change_json


def _ch(op, label, path, v, key='abilities.vdata:a'):
    side = 'new_s' if op == 'add' else 'old_s'
    return {'op': op, 'label': label, 'path': path, side: v, 'key': f'{key}:{path}', 'status': 'hidden',
            'cat': 'balance'}


def _prop(name: str, rest: str = 'm_strValue') -> str:
    return f'm_mapAbilityProperties.{name}.{rest}'


# ---- a removed and an added field are one renamed field only when the names say so ---------------------

def test_moved_investment_thresholds_stay_removed_and_added():
    # 2026-05-22: the 9,600 step (70) went, a 6,400 step (54) came — not "6,400: 70 → 54 −22.9%"
    inv = 'm_MapModCostBonuses.EItemSlotType_WeaponMod{%d}.flBonus'
    rows = [_ch('remove', 'Weapon investment at 9,600 souls: bonus', inv % 9600, '70', key='heroes.vdata:h'),
            _ch('add', 'Weapon investment at 6,400 souls: bonus', inv % 6400, '54', key='heroes.vdata:h')]
    assert [c['op'] for c in merge_renames(rows)] == ['remove', 'add']
    # the same number at another threshold is a moved step too, not "no change"
    rows = [_ch('remove', 'Vitality investment at 7,200 souls: bonus', inv % 7200, '42', key='heroes.vdata:h'),
            _ch('add', 'Vitality investment at 6,400 souls: bonus', inv % 6400, '42', key='heroes.vdata:h')]
    assert len(merge_renames(rows)) == 2


def test_a_word_more_or_another_word_is_another_field():
    scale = 'm_subclassScaleFunction.m_flStatScale'
    pairs = [
        # Aura of Suffering 2025-08-29: damage taken → damage, not "BUFF −0.1395 → 1.1 +688.5%"
        (('Damage Taken (spirit scaling)', _prop('IncomingDamagePercent', scale), '-0.1395'),
         ('Damage (spirit scaling)', _prop('Damage', scale), '1.1')),
        # Djinn's Mark 2024-09-26
        (('Spirit Damage (spirit scaling)', _prop('ProcBonusMagicDamage', scale), '0.2'),
         ('Base Damage (spirit scaling)', _prop('ProcDamageBase', scale), '0.4')),
        (('Wall Turn Ratio', 'm_flWallTurnRatio', '1000'), ('Wall Turn Ratio Max', 'm_flWallTurnRatioMax', '1200')),
        (('Killer Plane Horizontal Speed', 'm_flKillerPlaneHorizontalSpeed', '90'),
         ('Killer Plane Horizontal Speed X', 'm_flKillerPlaneHorizontalSpeedX', '65')),
        (('value #1 › Lane', 'value[0].iLane', '0'), ('value #5 › Lane', 'value[4].iLane', '-1')),
        (('Imbued Ability Cooldown Reduction', _prop('ImbuedCooldownReduction'), '32%'),
         ('Ability Cooldown Reduction', _prop('CooldownReduction'), '27%')),
    ]
    for (l1, p1, v1), (l2, p2, v2) in pairs:
        out = merge_renames([_ch('remove', l1, p1, v1), _ch('add', l2, p2, v2)])
        assert [c['op'] for c in out] == ['remove', 'add'], l1


def test_a_true_respelling_with_a_new_value_is_still_one_change():
    rows = [_ch('remove', 'Picup Expiration Duration', 'm_flPicupExpirationDuration', '30s'),
            _ch('add', 'Pickup Expiration Duration', 'm_flPickupExpirationDuration', '300s')]
    out = merge_renames(rows)
    assert len(out) == 1 and out[0]['op'] == 'change' and (out[0]['old_s'], out[0]['new_s']) == ('30s', '300s')


def test_a_bare_engine_leaf_names_no_property():
    # Gutter Ghoul passive 2026-05-31: two script values on m_value, one number, two effects
    base = 'm_vecIntrinsicModifiers{strong_neutral_bullet_armor}.m_vecScriptValues{%s}.m_value'
    rows = [_ch('remove', 'Passive › Melee Damage Increase Percent', base % 'MODIFIER_VALUE_MELEE_DAMAGE_INCREASE_PERCENT',
                '20', key='npc_units.vdata:n'),
            _ch('add', 'Passive › Melee Resist Reduction', base % 'MODIFIER_VALUE_MELEE_RESIST_REDUCTION', '20',
                key='npc_units.vdata:n')]
    assert len(merge_renames(rows)) == 2
    # an ability property inside another's name still is the same one (FlameAuraDPS → DPS)
    p1 = 'm_vecAbilityUpgrades[1].m_vecPropertyUpgrades{FlameAuraDPS}.m_strBonus'
    p2 = 'm_vecAbilityUpgrades[1].m_vecPropertyUpgrades{DPS}.m_strBonus'
    assert merge_renames([_ch('remove', 'T2: DPS', p1, '40'), _ch('add', 'T2: Damage Per Second', p2, '40')]) == []


def test_a_number_and_a_percent_are_one_value_only_when_the_name_says_percent():
    # Blood Bomb 2026-03-06: a flat 30 became 30% of health — two rows, not none
    rows = [_ch('remove', 'Self Damage', _prop('SelfDamage'), '30'),
            _ch('add', 'Health Cost', _prop('SelfDamagePct'), '30%')]
    assert len(merge_renames(rows)) == 2
    rows = [_ch('remove', 'Outgoing Ability Damage Penalty Percent', _prop('OutgoingAbilityDamagePenaltyPercent'), '-35'),
            _ch('add', 'Damage Penalty', _prop('OutgoingDamagePenaltyPercent'), '-35%')]
    assert merge_renames(rows) == []


# ---- internal weapon codes ---------------------------------------------------------------------------

def test_a_weapon_id_says_only_what_follows_its_owners_code():
    assert pretty_id('citadel_weapon_bull_set', 'hero_atlas') == 'Weapon'
    assert pretty_id('citadel_weapon_digger_set', 'hero_krill') == 'Weapon'
    assert pretty_id('citadel_weapon_gunslinger2_set', 'hero_gunslinger') == 'Weapon'
    assert pretty_id('citadel_weapon_astro_set_shotgun', 'hero_astro') == 'Weapon (shotgun)'
    assert pretty_id('citadel_weapon_astro_hand_cannon', 'hero_astro') == 'Weapon (hand cannon)'
    assert pretty_id('citadel_weapon_astro_set_shotgun_shared_base', 'hero_astro') == 'Weapon (shotgun)'
    assert pretty_id('citadel_weapon_astro_set_shotgun_shared_weapon_info', 'hero_astro') == 'Weapon (shotgun)'
    assert pretty_id('citadel_weapon_frank_set', 'hero_frank') == 'Weapon'
    assert pretty_id('citadel_weapon_doorman_alt', 'hero_doorman') == 'Alt weapon'


# ---- flag fields ------------------------------------------------------------------------------------

def test_a_flag_change_of_unlisted_bits_still_shows_its_bits():
    old = 'CITADEL_ABILITY_BEHAVIOR_NO_TARGET'
    new = 'CITADEL_ABILITY_BEHAVIOR_NO_TARGET | CITADEL_ABILITY_BEHAVIOR_CAN_SET_QUICK_CAST'
    html = flags_html(old, new, 'm_AbilityBehaviorsBits')
    assert html and 'quick cast' in html and html != '<span class="vals flags"></span>'


def test_flag_chips_take_the_colour_of_their_side():
    html = vals_html({'op': 'change', 'path': 'm_bitsInterruptingStates', 'cat': 'mechanic',
                      'old_s': 'MODIFIER_STATE_IMMOBILIZED', 'new_s': 'MODIFIER_STATE_STUNNED'})
    assert 'flag add bad">+stunned' in html and 'flag rem good">−rooted' in html
    html = vals_html({'op': 'change', 'path': 'm_AbilityBehaviorsBits', 'cat': 'mechanic', 'old_s': 'A | B',
                      'new_s': 'A | B | CITADEL_ABILITY_BEHAVIOR_INTERRUPT_MELEE_ON_CAST'})
    assert 'flag add bad">+interrupts your melee' in html
    html = vals_html({'op': 'add', 'path': 'm_X.m_nEnabledStateMask', 'cat': 'mechanic', 'old_s': '—',
                      'new_s': 'MODIFIER_STATE_DISARMED'})
    assert 'flag add even">+disarmed' in html


def test_the_disabled_state_mask_reads_as_immunities():
    d = flags.diff('m_X.m_nDisabledStateMask', None,
                   'MODIFIER_STATE_DASH_DISABLED_DEBUFF | MODIFIER_STATE_DISARMED | MODIFIER_STATE_SLOWED')
    assert d == ([('dash lockouts', 1), ('disarm', 1), ('slows', 1)], [])
    assert flags.direction('m_X.m_nDisabledStateMask', None, 'MODIFIER_STATE_SILENCED') == 'buff'


def test_an_invalid_enum_value_is_no_value():
    assert flags.enum_words('m_eItemSlotType', 'EItemSlotType_Invalid') is None
    assert not flags.is_gameplay('m_eItemSlotType', 'EItemSlotType_Invalid', None)
    assert flags.is_gameplay('m_eItemSlotType', 'EItemSlotType_Invalid', 'EItemSlotType_Tech')


def test_the_same_bits_in_another_order_are_no_change():
    a = 'CITADEL_ABILITY_BEHAVIOR_CANNOT_CANCEL_DURING_CHANNEL | CITADEL_ABILITY_BEHAVIOR_DEACTIVATE_CROUCH_TOGGLE_ON_CAST'
    b = 'CITADEL_ABILITY_BEHAVIOR_DEACTIVATE_CROUCH_TOGGLE_ON_CAST | CITADEL_ABILITY_BEHAVIOR_CANNOT_CANCEL_DURING_CHANNEL'
    assert is_noop({'op': 'change', 'path': 'm_AbilityBehaviorsBits', 'old_s': a, 'new_s': b})


def test_matrix_hover_rows_read_a_flag_change_as_words():
    row = {'path': 'm_nAbilityTargetTypes', 'old_s': 'CITADEL_UNIT_TARGET_HERO',
           'new_s': 'CITADEL_UNIT_TARGET_HERO | CITADEL_UNIT_TARGET_NEUTRAL'}
    assert dynamics_page._sample_values(row) == ('', '+neutrals')
    slot = {'path': 'm_eItemSlotType', 'old_s': 'EItemSlotType_Tech', 'new_s': 'EItemSlotType_Armor'}
    assert dynamics_page._sample_values(slot) == ('Spirit', 'Vitality')
    plain = {'path': _prop('Cooldown'), 'old_s': '20s', 'new_s': '18s'}
    assert dynamics_page._sample_values(plain) == ('20s', '18s')


# ---- numbers ----------------------------------------------------------------------------------------

def test_a_heros_signed_base_stat_has_a_signed_percent():
    # Pocket: "BUFF Bullet Resist −20% → −15% −25.0%" — the pill went against the tag
    assert semantics.direction('m_mapStartingStats.EBulletArmorDamageReduction', -20.0, -15.0) == ('buff', 25.0)
    d, pct = semantics.direction('m_mapStartingStats.EBulletArmorDamageReduction', -6.0, -8.0)
    assert d == 'nerf' and pct < 0
    assert semantics.direction('m_mapStartingStats.EMaxHealth', 500.0, 550.0) == ('buff', 10.0)


def test_a_qualifier_alone_is_no_label():
    tok = {'statuehealth_label': '(Normalized)', 'ava_label': 'Ava (Normalized)'}
    assert semantics._loc_label(tok, 'StatueHealth') is None
    assert semantics._loc_label(tok, 'Ava') == 'Ava (Normalized)'
    assert semantics._prop_label(tok, 'StatueHealth')[1] == 'fallback'


def test_a_unit_valve_dropped_is_each_windows_own():
    # Express Shot's Extra Ammo Consumed: 30% of the clip until 2026-03-06, then 2 bullets
    head = {'label': 'Extra Ammo Consumed', 'src': 'loc', 'unit': ''}
    seen = {'loc_label': 'Extra Ammo Consumed', 'unit': '%', 'steps': [(5000, '%'), (6600, '')]}
    cn = labels.resolve('m_mapAbilityProperties.ProcAmmoConsumed.m_strValue', head, seen)
    assert cn['unit'] is None
    assert labels.display_unit({'unit': '%'}, cn) == '%' and labels.display_unit({'unit': ''}, cn) == ''
    assert labels.unit_switch(cn, [6600]) == ('%', '')
    assert labels.unit_switch(cn, [5500, 5600]) is None and labels.unit_switch(cn, [6700]) is None
    # a unit Valve only ADDED (a bare number, later "%") stays one unit for every row
    seen = {'loc_label': 'Slow', 'unit': '%', 'steps': [(5000, ''), (6000, '%')]}
    cn = labels.resolve(_prop('Slow'), {'label': 'Slow', 'src': 'loc', 'unit': '%'}, seen)
    assert cn['unit'] == '%' and labels.unit_switch(cn, [6000]) is None


def test_a_row_across_a_unit_switch_is_changed_without_a_percent():
    c = MChange('abilities.vdata', 'upgrade_express_shot', _prop('ProcAmmoConsumed'), 'change', '30', '2', 'balance',
                'item', None, 'Extra Ammo Consumed', False, [6600], unit='', old_unit='%')
    js = change_json(c)
    assert (js['old_s'], js['new_s'], js['dir'], js['pct']) == ('30%', '2', 'changed', None) and js['unit_switch']
    html = vals_html({**js, 'status': 'documented'})
    assert '>30%<' in html and '>2<' in html and '2%' not in html


def test_a_folded_table_keeps_thousands_in_its_range():
    from builders.cards import change_rows
    rows = [{'op': 'change', 'cat': 'balance', 'label': f'Vitality investment at {n:,} souls: bonus', 'old_s': '1',
             'new_s': '2', 'dir': 'buff', 'pct': 100.0, 'status': 'hidden', 'path': f'p{n}'}
            for n in (6400, 8000, 11200, 28800)]
    assert 'Vitality investment at 6,400–28,800 souls: bonus' in change_rows(rows)


# ---- the abilities every hero has: a home of their own ----------------------------------------------

def test_shared_abilities_have_a_page_a_matrix_row_and_search_rows(monkeypatch):
    from builders import shared_page
    row = {'id': '2026-09-16', 'date': '2026-09-16', 'title': '09-16-2026 Update'}
    change = {'op': 'change', 'cat': 'balance', 'label': 'Mantle Slow On Hit', 'old_s': '20%', 'new_s': '30%',
              'dir': 'changed', 'status': 'hidden', 'path': _prop('MantleSlow'), 'key': 'k'}
    ents = [{'file': 'abilities.vdata', 'id': 'citadel_ability_mantle', 'name': 'Mantle', 'kind': 'shared'},
            {'file': 'abilities.vdata', 'id': 'citadel_ability_dash', 'name': 'Dash', 'kind': 'shared'},
            {'file': 'abilities.vdata', 'id': 'ability_x', 'name': 'X', 'kind': 'ability', 'owner': 'hero_a'}]
    shared = shared_page.shared_entities(ents)
    assert [e['id'] for e in shared] == ['citadel_ability_dash', 'citadel_ability_mantle']
    by_ent = {'abilities.vdata:citadel_ability_mantle': [(row, [change])]}
    assert shared_page.has_history(shared, by_ent)
    html = shared_page.shared_page(shared, by_ent, {})
    assert 'Mantle Slow On Hit' in html and 'href="index.html">Heroes</a>' in html
    assert shared_page.search_rows(shared, by_ent) == [
        ['Mantle', 'heroes/shared.html#ab-citadel_ability_mantle', 'All heroes · ability', '']]
    assert shared_page.matrix_entry()[0] == dynamics_page.SHARED_KEY

    # the hero matrix counts a shared ability's changes on that row
    patch = {'entities': [{'file': 'abilities.vdata', 'id': 'citadel_ability_mantle', 'kind': 'shared',
                           'key': 'abilities.vdata:citadel_ability_mantle', 'changes': [change]}]}
    data = {'patches/index.json': [row], 'patches/2026-09-16.json.gz': patch, 'entities.json': {'entities': ents}}
    monkeypatch.setattr(dynamics_page, 'load_json', lambda name: data[name])
    dynamics_page._collect.cache_clear()
    try:
        cells = dynamics_page._collect()['cells']
        assert sum(cells[dynamics_page.SHARED_KEY]['2026-09-16'].values()) == 1
    finally:
        dynamics_page._collect.cache_clear()
