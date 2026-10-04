"""Data-quality track, part 2 (audit 2026-10-04): engine plumbing off the pages with the gameplay flags
brought back, BUFF / NERF the notes contradicted, "no limit", renamed fields and rows hidden although
their own note gives both numbers. No tracker clone needed."""
from builders.cards import is_engine, is_noop, merge_renames
from builders.render import _sentinel, fold_tier_swaps, tag_of, vals_html
from pipeline import flags, semantics
from pipeline.classify import category
from pipeline.match import MChange, annotate_line, change_json

D = semantics.direction


def _prop(name: str) -> str:
    return f'm_mapAbilityProperties.{name}.m_strValue'


# ---- directions the notes or the game's logic contradicted ---------------------------------------

def test_names_that_say_the_opposite_go_by_the_notes():
    # Golden Goose Egg: "souls per buff improved from every 200 souls to every 150" (2026-03-10)
    assert D(_prop('BonusBuffsPerGold'), 200, 150, 'item')[0] == 'buff'
    assert D('m_vecAbilityUpgrades[0].m_vecPropertyUpgrades{BonusBuffsPerGold}.m_strBonus', -100, -50, 'item')[0] == 'nerf'
    # Goo Ball: "stun frequency cooldown improved from 1.5s to 1.25s"; "once every 1.5s, up from 1.0s"
    assert D('m_DamagePreventionModifier.m_flDuration', 1.5, 1.25, 'ability')[0] == 'buff'
    assert D('m_DamagePreventionModifier.m_flDuration', 1, 1.5, 'ability')[0] == 'nerf'
    # Malice: "slow reduced from 20% to 15%" — a slow on the enemy
    assert D(_prop('MoveSpeedPenaltyPerStack'), 20, 15, 'ability')[0] == 'nerf'
    # Vampiric Burst: "Added ammo on active increased from +50% to +75%"
    assert D(_prop('ActiveReloadPercent'), 50, 75, 'item')[0] == 'buff'
    # the aim settling faster after recoil (game logic)
    assert D('m_mapWeaponInfos.primary.m_flRecoilRecoverySpeed', 5, 15, 'weapon')[0] == 'buff'
    # Borrowed Decree: "spawn interval improved from every 5s to every 4s"
    assert D(_prop('SummonFrequency'), 5, 4, 'ability')[0] == 'buff'
    # Improved Burst: "Threshold damage increased from 125 to 200"
    assert D(_prop('MinimumDamage'), 125, 200, 'item')[0] == 'nerf'
    # Rising Ram: the negating word comes first
    assert D(_prop('ReduceCooldownOnHitPct'), 0, 50, 'ability')[0] == 'buff'
    assert D(_prop('BonusDamageDecayLockoutDuration'), 3, 5, 'ability')[0] == 'buff'


def test_old_polarities_hold():
    assert D(_prop('AbilityCooldown'), 27, 29, 'ability')[0] == 'nerf'
    assert D(_prop('CooldownReduction'), 10, 12, 'item')[0] == 'buff'
    assert D('m_mapWeaponInfos.primary.m_flReloadTime', 2, 2.5, 'weapon')[0] == 'nerf'
    assert D('m_mapWeaponInfos.primary.m_flRecoilAmount', 2, 3, 'weapon')[0] == 'nerf'


def test_a_heros_own_base_resist_counts_with_its_sign():
    # Pocket 2024-07-18 "Base bullet resistance improved": −20% → −15%; Celeste −6% → −8% a nerf
    assert D('m_mapStartingStats.EBulletArmorDamageReduction', -20, -15, 'hero')[0] == 'buff'
    assert D('m_mapStartingStats.ETechArmorDamageReduction', 0, -15, 'hero')[0] == 'nerf'
    assert D('m_mapStartingStats.EBulletArmorDamageReduction', -6, -8, 'hero')[0] == 'nerf'
    assert D('m_mapStartingStats.EMaxHealth', 550, 600, 'hero')[0] == 'buff'


def test_where_a_thing_sits_has_no_side():
    for path in ('m_flSummonedCardVerticalOffset', 'm_flMaxPitchDown', 'm_GrabModifier.m_flFollowDampingFactor',
                 'flSpringConstant', 'm_flFlatGroundFrictionGraceTime'):
        assert D(path, 15, 22, 'ability')[0] == 'changed', path
    # a shotgun's sideways scatter is a spread: less is better
    assert D('m_mapWeaponInfos.primary.m_flScatterYawScale', 1, 0, 'weapon')[0] == 'buff'


def test_minus_one_is_no_limit_only_against_a_non_negative_value():
    assert semantics.is_sentinel(-1, 50) and semantics.is_sentinel(9999, 5) and semantics.is_sentinel(-1)
    assert not semantics.is_sentinel(-1, -0.5) and not semantics.is_sentinel(-2, 0)
    # Channel Move Speed 50 → −1 has no direction; Sharpshooter's penalty −0.5 → −1 m/s is a nerf
    assert D(_prop('ChannelMoveSpeed'), 50, -1, 'ability') == ('changed', None)
    assert D(_prop('BonusMoveSpeed'), -0.5, -1, 'item', drawback=True)[0] == 'nerf'
    assert D(_prop('BonusMoveSpeed'), -1, -0.7, 'item', drawback=True)[0] == 'buff'
    # −2 is no sentinel: Cheat Death's real −2 m/s slow going away
    assert D(_prop('BonusMoveSpeed'), -2, 0, 'item', drawback=True)[0] == 'buff'


# ---- "no limit": one wording, a real -1 a number, a default a default ------------------------------

def test_minus_one_reads_as_what_the_field_means():
    charge = {'path': _prop('AbilityCooldownBetweenCharge')}
    assert _sentinel('-1s', charge, '0s') == 'default'
    assert _sentinel('-1s', {'path': 'm_BuffModifier.m_flDuration'}, '') == 'permanent'
    assert _sentinel('-1', {'path': _prop('ChannelMoveSpeed')}, '50') == 'no limit'
    html = vals_html({'op': 'change', 'path': _prop('AbilityCooldownBetweenCharge'), 'old_s': '0s', 'new_s': '-1s',
                      'dir': 'changed', 'pct': None})
    assert '>default<' in html and 'no limit' not in html


# ---- engine plumbing off the pages, gameplay flags back ---------------------------------------------

def _row(path, old_s, new_s, op='change', status='hidden', **kw):
    return {'path': path, 'op': op, 'old_s': old_s, 'new_s': new_s, 'status': status, 'cat': 'mechanic',
            'label': 'x', **kw}


def test_known_plumbing_fields_leave_the_pages():
    assert is_engine(_row('m_vecIntrinsicModifiers{midboss_modifier_damage_resistance}.m_bIsForMidBoss', '—', 'yes',
                          'add'))
    assert is_engine(_row('m_mapDependentAbilities.ability_ice_dome_trigger', '', '', 'add'))
    assert is_engine(_row('m_flModelScale', '0.525', '0.6'))
    assert is_engine(_row('m_mapAbilityProperties.WeaponDamagePerKill.m_nRequiredUpgradeBits', '', '', 'add'))
    # what the notes talked about stays
    assert not is_engine(_row('m_flModelScale', '0.525', '0.6', status='documented'))
    # nothing to read: an empty block added or removed
    assert is_noop({'op': 'add', 'path': 'm_nAbilityTargetFlags', 'new_s': '—'})
    assert is_noop({'op': 'remove', 'path': 'x', 'old_s': ''})
    assert not is_noop({'op': 'add', 'path': 'x', 'new_s': '20'})


def test_containers_read_as_words():
    cl = semantics.context_label
    assert cl('m_GrabModifier.m_flDuration') == 'Grab › Duration'
    assert cl('m_GrabModifier.m_bDurationReducibleByCrowdControlDiminish') == 'Grab › Reduced by CC diminishing returns'
    assert cl('m_RebirthModifier.m_flDuration') == 'Rejuvenator buff › Duration'
    assert cl('m_StaggerWatcherModifier.m_BuildUpModifier.m_flDuration') == 'Stagger › Build-up › Duration'
    # a leaf keeps its word: the field IS the modifier
    assert cl('m_vecThings.m_SlowModifier') == 'Things › Slow Modifier'
    assert semantics.describe('m_flInvulModifierRange', {})['label'] == 'Invulnerability aura range'
    assert semantics.describe('m_flSightRangePlayers', {})['label'] == 'Sight range vs heroes'


def test_state_masks_are_a_mechanic():
    assert category('m_UntargetableModifier.m_nEnabledStateMask', None,
                    'MODIFIER_STATE_IGNORED_BY_NPC_TARGETING') == 'mechanic'
    assert category('m_bitsPreCastEnabledStateMask', 'a', 'b') == 'technical'


def test_gameplay_bits_read_as_words_with_a_side():
    trap = 'm_UntargetableModifier.m_nEnabledStateMask'
    assert flags.diff(trap, None, 'MODIFIER_STATE_IGNORED_BY_NPC_TARGETING') == (
        [('ignored by troopers and neutrals', 1)], [])
    assert flags.direction(trap, None, 'MODIFIER_STATE_IGNORED_BY_NPC_TARGETING') == 'buff'
    # a lockout has no side: the holder's own or the enemy's
    assert flags.direction(trap, None, 'MODIFIER_STATE_DISARMED') == 'changed'
    grab = 'm_nAbilityTargetTypes'
    old, new = 'CITADEL_UNIT_TARGET_HERO | CITADEL_UNIT_TARGET_TROOPER_ENEMY', \
        'CITADEL_UNIT_TARGET_HERO | CITADEL_UNIT_TARGET_TROOPER_ENEMY | CITADEL_UNIT_TARGET_NEUTRAL'
    assert flags.diff(grab, old, new) == ([('neutrals', 1)], [])
    assert flags.direction(grab, old, new) == 'buff'
    assert flags.direction('m_bitsInterruptingStates', 'MODIFIER_STATE_IMMOBILIZED',
                           'MODIFIER_STATE_IMMOBILIZED | MODIFIER_STATE_STUNNED') == 'nerf'
    assert flags.direction('m_CurseModifier.m_nAttributes', None, 'MODIFIER_ATTRIBUTE_CANNOT_BE_PURGED') == 'buff'
    assert flags.direction('m_GrabModifier.m_bDurationReducibleByCrowdControlDiminish', None, True) == 'nerf'
    assert flags.enum_words('m_eItemSlotType', 'EItemSlotType_Tech') == 'Spirit'
    # a state renamed to one that reads the same is no change (Dash 2026-09-29)
    assert not flags.is_gameplay('m_bitsInterruptingStates', 'MODIFIER_STATE_MOVEMENT_ABILITY_RESTRICTED',
                                 'MODIFIER_STATE_MOVEMENT_ABILITY_ACTIVATION_RESTRICTED')
    # quick-cast UI and bookkeeping bits are no gameplay
    assert not flags.is_gameplay('m_AbilityBehaviorsBits', 'CITADEL_ABILITY_BEHAVIOR_NO_TARGET',
                                 'CITADEL_ABILITY_BEHAVIOR_NO_TARGET | CITADEL_ABILITY_BEHAVIOR_CAN_SET_QUICK_CAST')
    assert not flags.is_gameplay('m_X.m_nAttributes', None, 'MODIFIER_ATTRIBUTE_MULTIPLE')


def test_gameplay_flag_rows_are_on_the_page_with_their_words_and_tag():
    row = _row('m_nAbilityTargetTypes', 'CITADEL_UNIT_TARGET_HERO', 'CITADEL_UNIT_TARGET_HERO | CITADEL_UNIT_TARGET_NEUTRAL',
               dir='buff', flag=True)
    assert not is_engine(row)
    html = vals_html(row)
    assert '+neutrals' in html and 'hero' not in html.lower().replace('heroes', '')
    assert tag_of(row)[0] == 'buff'
    added = _row('m_CurseModifier.m_nAttributes', '—', 'MODIFIER_ATTRIBUTE_CANNOT_BE_PURGED', 'add', dir='buff', flag=True)
    assert tag_of(added)[0] == 'buff' and '+can&#x27;t be purged' in vals_html(added)
    slot = _row('m_eItemSlotType', 'EItemSlotType_Tech', 'EItemSlotType_Armor')
    assert not is_engine(slot) and '>Spirit<' in vals_html(slot) and '>Vitality<' in vals_html(slot)
    from builders.render import readable_value
    assert readable_value('EItemSlotType_Tech') == 'Spirit'          # the matrices' samples too
    ui = _row('m_AbilityBehaviorsBits', 'CITADEL_ABILITY_BEHAVIOR_NO_TARGET',
              'CITADEL_ABILITY_BEHAVIOR_NO_TARGET | CITADEL_ABILITY_BEHAVIOR_CAN_SET_QUICK_CAST', status='described')
    assert is_engine(ui)


def test_the_matcher_tags_flag_rows():
    c = MChange('abilities.vdata', 'ability_priest_beartrap', 'm_UntargetableModifier.m_nEnabledStateMask', 'add',
                None, 'MODIFIER_STATE_IGNORED_BY_NPC_TARGETING', 'mechanic', 'ability', 'hero_priest', 'x', False)
    js = change_json(c)
    assert js['dir'] == 'buff' and js['flag']
    # a unit's ability has no owner side
    u = MChange('abilities.vdata', 'a', 'm_nAbilityTargetTypes', 'change', 'CITADEL_UNIT_TARGET_HERO',
                'CITADEL_UNIT_TARGET_HERO | CITADEL_UNIT_TARGET_NEUTRAL', 'mechanic', 'unit', None, 'x', False)
    assert change_json(u)['dir'] == 'changed'


def test_scenery_entries_are_no_gameplay_events():
    from pipeline.classify import decor_entity
    from pipeline.match import _gameplay_entity
    for eid in ('vehicle_car_01', 'citadel_base_glass_vert_01', 'm_ColorEnemy', 'm_MiniMapOffsets',
                'm_MapDistrictLocalization', 'm_flNeutralCampRespawnTimerHeight'):
        assert decor_entity(eid), eid
    for eid in ('citadel_breakable_prop_tough_crate', 'm_RejuvParams', 'big_gold_pickup', 'm_ObjectiveParams'):
        assert not decor_entity(eid), eid
    assert not _gameplay_entity({'file': 'misc.vdata', 'id': 'vehicle_car_01', 'status': 'removed', 'changes': []})
    assert _gameplay_entity({'file': 'misc.vdata', 'id': 'citadel_breakable_prop_car', 'status': 'removed',
                             'changes': []})


# ---- renamed fields: one row, or none ----------------------------------------------------------------

def _ch(op, label, path, v, key='abilities.vdata:a'):
    side = 'new_s' if op == 'add' else 'old_s'
    return {'op': op, 'label': label, 'path': path, side: v, 'key': f'{key}:{path}', 'status': 'hidden',
            'cat': 'balance'}


def test_a_field_renamed_with_its_value_leaves_no_row():
    rows = [_ch('remove', 'Grab › Follow Damping Factor', 'm_GrabModifier.m_flFollowDampingFactor', '20'),
            _ch('add', 'Grab › Damping Factor', 'm_GrabModifier.m_flDampingFactor', '20')]
    assert merge_renames(rows) == []
    rows = [_ch('remove', 'Projectile › Vertical Aim Bias', 'm_projectileInfo.m_flVerticalAimBias', '10'),
            _ch('add', 'Vertical Aim Bias', 'm_mapWeaponInfos.primary.m_flVerticalAimBias', '10')]
    assert merge_renames(rows) == []


def test_a_tier_bonus_renamed_is_no_rework():
    p1 = 'm_vecAbilityUpgrades[1].m_vecPropertyUpgrades{FlameAuraDPS}.m_strBonus'
    p2 = 'm_vecAbilityUpgrades[1].m_vecPropertyUpgrades{DPS}.m_strBonus'
    rows = [_ch('remove', 'T2: DPS', p1, '40'), _ch('add', 'T2: Damage Per Second', p2, '40')]
    assert fold_tier_swaps(merge_renames(rows)) == []


def test_a_respelt_field_with_a_new_value_is_one_change():
    rows = [_ch('remove', 'Interupt Cooldown', _prop('InteruptCooldown'), '5s'),
            _ch('add', 'Interrupt Cooldown', _prop('InterruptCooldown'), '6s')]
    out = merge_renames(rows)
    assert len(out) == 1 and out[0]['op'] == 'change' and out[0]['old_s'] == '5s' and out[0]['new_s'] == '6s'


def test_another_stat_with_the_same_number_stays_a_swap():
    rows = [_ch('remove', 'Spirit Resist', _prop('TechResist'), '15%'),
            _ch('add', 'Bullet Resist', _prop('BulletResist'), '15%')]
    assert len(merge_renames(rows)) == 2
    rows = [_ch('remove', 'Sprint Speed', _prop('BonusSprintSpeed'), '2m/s'),
            _ch('add', 'Move Speed', _prop('BonusMoveSpeed'), '2m/s')]
    assert len(merge_renames(rows)) == 2
    # a T1 bonus is not a T2 one, another entity's field is not this one's
    rows = [_ch('remove', 'T1: Cooldown', 'm_vecAbilityUpgrades[0].m_vecPropertyUpgrades{AbilityCooldown}.m_strBonus', '-2s'),
            _ch('add', 'T2: Cooldown', 'm_vecAbilityUpgrades[1].m_vecPropertyUpgrades{AbilityCooldown}.m_strBonus', '-2s')]
    assert len(merge_renames(rows)) == 2
    rows = [_ch('remove', 'Zip Speed', _prop('ZipSpeed'), '17.6m/s'),
            _ch('add', 'Zip Speed Inner', _prop('ZipSpeedInner'), '17.6m/s', key='abilities.vdata:b')]
    assert len(merge_renames(rows)) == 2


# ---- rows hidden although their own note gives both numbers -----------------------------------------

def _item(path, a, b, label):
    return MChange('abilities.vdata', 'upgrade_knockdown', path, 'change', a, b, 'balance', 'item', None, label, False)


def test_a_line_claims_the_twin_field_it_names():
    rng = _item(_prop('TechRangeMultiplier'), 6, 5, 'Ability Range')
    rad = _item(_prop('TechRadiusMultiplier'), 6, 5, 'Radius')
    other = _item(_prop('KillCheckWindow'), 6, 5, 'Kill Check Window')
    pool = [rng, rad, other]
    idx = {'knockdown': ['abilities.vdata:upgrade_knockdown']}
    cat = {'abilities.vdata:upgrade_knockdown': {'id': 'upgrade_knockdown', 'kind': 'item'}}
    res = annotate_line('Knockdown: Ability Range reduced from +6% to +5%', pool,
                        {'abilities.vdata:upgrade_knockdown': pool}, idx, cat, {})
    assert res['status'] == 'documented'
    assert rng.status == rad.status == 'documented'
    assert other.status == 'hidden'


def test_number_pairs_with_numbers_in_between():
    from pipeline.match import parse_pairs
    assert parse_pairs('Power Surge T2 reduced from -15% Spirit Resist for 8s to -10% for 6s') == [(-15, -10), (8, 6)]
    assert parse_pairs('Rallying Charge damage reduced from 150 (+1.2) to 125 (+1.0)') == [(150, 125), (1.2, 1.0)]
    assert parse_pairs('Leaping Slash T2 reduced from "+225s within 4s" to "+200 within 3s"') == [(225, 200), (4, 3)]
    assert parse_pairs('Borrowed Decree spawn interval improved from every 5s to every 4s') == [(5, 4)]
    # the strict pattern still wins, and an uneven list is no pair
    assert parse_pairs('Cooldown reduced from 45s to 37s') == [(45, 37)]
    assert parse_pairs('changed from 2 charges to 3 charges and 10 damage') == [(2, 3)]
    assert parse_pairs('Moved from T4 to T3') == []


def test_a_swap_of_two_properties_is_no_pair():
    from pipeline.match import parse_pairs
    assert parse_pairs('Fire Scarabs T1 changed from "-15s Cooldown" to "+50 Max Health Steal"') == []
    assert parse_pairs('Death Slam T3 changed from -56s Cooldown to Impact Area Stuns for 1s') == []
    assert parse_pairs('Ava T3 changed from -20s Cooldown and +35 Health Regen to a growing damage amp, up to 20% '
                       'for 6s') == []
    # the same words on both sides are one property: "Base health changed from 680 (+41 per boon) to 720 (+39 …)"
    assert parse_pairs('Base health changed from 680 (+41 per boon) to 720 (+39 per boon)') == [(680, 720), (41, 39)]
    assert parse_pairs('resist changed from starting at 70% at 10 min to starting at 60% at 8 minutes') == [
        (70, 60), (10, 8)]


def test_a_modifiers_states_link_by_the_states_not_by_its_name():
    def mask():
        return MChange('abilities.vdata', 'ability_golden_idol', 'm_HoldingIdolModifier.m_nEnabledStateMask', 'change',
                       'MODIFIER_STATE_HOLDING_IDOL | MODIFIER_STATE_DISARMED', 'MODIFIER_STATE_HOLDING_IDOL', 'mechanic',
                       'ability_other', None, 'Holding Idol › Applies', False)
    idx = {'urn': ['abilities.vdata:ability_golden_idol']}
    cat = {'abilities.vdata:ability_golden_idol': {'id': 'ability_golden_idol', 'kind': 'ability_other'}}
    m = mask()
    res = annotate_line('Urn: Please give feedback on the idol as we iterate', [m], {m.key.rsplit(':', 1)[0]: [m]},
                        idx, cat, {})
    assert res['changes'] == [] and m.status == 'hidden'
    m = mask()
    res = annotate_line('Urn: The runner is no longer disarmed', [m], {'abilities.vdata:ability_golden_idol': [m]},
                        idx, cat, {})
    assert res['changes'] == [m.key] and m.status == 'described'


def test_a_twin_is_a_changed_value_of_the_lines_tier():
    rng = _item(_prop('TechRangeMultiplier'), 6, 5, 'Ability Range')
    gone = MChange('abilities.vdata', 'upgrade_knockdown', _prop('RangeOld'), 'remove', 6, None, 'balance', 'item',
                   None, 'Range', False)
    t1 = _item('m_vecAbilityUpgrades[0].m_vecPropertyUpgrades{AbilityCastRange}.m_strBonus', 6, 5, 'T1: Range')
    pool = [rng, gone, t1]
    idx = {'knockdown': ['abilities.vdata:upgrade_knockdown']}
    cat = {'abilities.vdata:upgrade_knockdown': {'id': 'upgrade_knockdown', 'kind': 'item'}}
    annotate_line('Knockdown: Ability Range reduced from +6% to +5%', pool,
                  {'abilities.vdata:upgrade_knockdown': pool}, idx, cat, {})
    assert rng.status == 'documented' and gone.status == 'hidden' and t1.status == 'hidden'


def test_an_item_moved_between_tiers_is_its_tier():
    tier = MChange('abilities.vdata', 'upgrade_shadow_weave', 'm_iItemTier', 'change', 4, 3, 'balance', 'item', None,
                   'Item Tier', False)
    idx = {'shadow weave': ['abilities.vdata:upgrade_shadow_weave']}
    cat = {'abilities.vdata:upgrade_shadow_weave': {'id': 'upgrade_shadow_weave', 'kind': 'item'}}
    res = annotate_line('Shadow Weave: Moved from T4 to T3', [tier], {'abilities.vdata:upgrade_shadow_weave': [tier]},
                        idx, cat, {})
    assert res['status'] == 'documented' and tier.status == 'documented'


def test_a_fix_line_with_both_numbers_covers_its_row():
    regen = MChange('heroes.vdata', 'hero_gigawatt', 'm_mapStartingStats.EBaseHealthRegen', 'change', 3, 1.5,
                    'balance', 'hero', None, 'Health Regen', False)
    idx = {'seven': ['heroes.vdata:hero_gigawatt']}
    cat = {'heroes.vdata:hero_gigawatt': {'id': 'hero_gigawatt', 'kind': 'hero'}}
    res = annotate_line('Seven: Fixed Health Regen being 3 instead of 1.5', [regen],
                        {'heroes.vdata:hero_gigawatt': [regen]}, idx, cat, {})
    assert res['status'] == 'fix' and res['changes'] == [regen.key]
    assert regen.status == 'documented'
