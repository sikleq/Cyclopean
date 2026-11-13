"""pipeline/semantics.py: a change's direction, its label, its unit and its printed value."""
from pipeline import semantics
from pipeline.flatten import flatten


# ---- semantics ---------------------------------------------------------------

def test_cooldown_increase_is_a_nerf():
    d, pct = semantics.direction('m_mapAbilityProperties.AbilityCooldown.m_strValue', 27, 29)
    assert d == 'nerf' and round(pct, 1) == 7.4


def test_upgrade_bonus_direction_follows_the_sign():
    # Shoulder Charge T3 "-20s cooldown" -> "-18s": a smaller reduction is a nerf
    p = 'm_vecAbilityUpgrades[2].m_vecPropertyUpgrades{AbilityCooldown}.m_strBonus'
    assert semantics.direction(p, -20, -18)[0] == 'nerf'
    assert semantics.direction(p, -18, -20)[0] == 'buff'


def test_damage_increase_is_a_buff_and_negative_debuff_magnitude():
    assert semantics.direction('m_mapAbilityProperties.Damage.m_strValue', 80, 150)[0] == 'buff'
    # -8% resist shred -> -7%: weaker effect
    assert semantics.direction('m_mapAbilityProperties.BulletResistReduction.m_strValue', -8, -7)[0] == 'nerf'


def test_polarity_reads_the_property_name_not_its_container():
    d = semantics.direction
    # investment bonuses live in m_MapModCostBonuses: "Cost" in the container must not flip the bonus
    assert d('m_MapModCostBonuses.EItemSlotType_Armor[4].flBonus', 22, 34)[0] == 'buff'
    assert d('m_MapModCostBonuses.EItemSlotType_Armor[5].nGoldThreshold', 7200, 6400)[0] == 'buff'
    # "Reduction" / "Refund" / "Decay" after a lower-is-better word turn it around
    assert d('m_mapAbilityProperties.CooldownReduction.m_strValue', 10, 15)[0] == 'buff'
    assert d('m_mapAbilityProperties.StaminaCooldownReduction.m_strValue', 10, 14)[0] == 'buff'
    assert d('m_mapAbilityProperties.CooldownBetweenChargeReduction.m_strValue', 40, 55)[0] == 'buff'
    assert d('m_mapWeaponInfos.primary.m_flShootSpreadPenaltyDecay', 2.5, 5)[0] == 'buff'
    # a lower-is-better value compares with its sign: an enemy healing penalty -65 -> -70 is stronger
    assert d('m_mapAbilityProperties.HealAmpReceivePenaltyPercent.m_strValue', -65, -70)[0] == 'buff'
    assert d('m_mapAbilityProperties.InAirDamageReceived.m_strValue', -40, -60)[0] == 'buff'
    # unchanged: cooldowns, enemy slows, resist shred
    assert d('m_mapAbilityProperties.AbilityCooldown.m_strValue', 27, 29)[0] == 'nerf'
    assert d('m_mapAbilityProperties.SlowPercent.m_strValue', 25, 35)[0] == 'buff'
    assert d('m_mapAbilityProperties.BulletArmorReduction.m_strValue', -10, -12)[0] == 'buff'


def test_shorter_tick_interval_is_a_buff():
    # Rem: Infest Heal Interval 3 -> 2 heals more often
    assert semantics.direction('m_mapAbilityProperties.InfestHealInterval.m_strValue', 3, 2)[0] == 'buff'
    assert semantics.direction('m_mapAbilityProperties.TickInterval.m_strValue', 0.5, 1)[0] == 'nerf'


def test_shared_objects_go_up_or_down_unless_the_player_side_is_plain():
    d = semantics.direction
    assert d('m_nMaxHealth', 4600, 5000, kind='building')[0] == 'up'
    assert d('m_flSightRangePlayers', 1500, 1338.58, kind='building')[0] == 'down'
    # a camp's bounty and a shorter respawn help whoever takes it
    assert d('m_flGoldReward', 275, 220, kind='neutral')[0] == 'nerf'
    assert d('m_iSpawnIntervalInSeconds', 300, 240, kind='global')[0] == 'buff'
    assert d('m_sModifer.m_flDuration', 60, 80, kind='global')[0] == 'buff'


def test_units_have_no_owner_direction():
    # no buff/nerf for a building's health: both teams have it (the tag says UP instead)
    assert semantics.direction('m_nMaxHealth', 5000, 5500, kind='building')[0] not in ('buff', 'nerf')


def test_gradient_steps():
    assert semantics.gradient(3) == 1 and semantics.gradient(33) == 6 and semantics.gradient(500) == 10


def test_meters_display():
    assert semantics.display_value(787.4, meters=True) == '20m'


def test_small_coefficients_keep_decimals():
    assert semantics.display_value(0.005) == '0.005' and semantics.display_value(12.345) == '12.35'


def test_the_holders_own_downside_grows_as_a_nerf():
    from pipeline.enrich import drawbacks
    egg = {'m_mapAbilityProperties': {'OutgoingDamagePenaltyPercent': {'m_strValue': '-15', 'm_bIsNegativeAttribute': True},
                                      'BonusHealth': {'m_strValue': '100'}}}
    assert drawbacks(egg) == {'OutgoingDamagePenaltyPercent'}
    path = 'm_mapAbilityProperties.OutgoingDamagePenaltyPercent.m_strValue'
    # Golden Goose Egg: "Damage Penalty increased from -10% to -15%" is worse for its owner
    assert semantics.direction(path, -10, -15, 'item', drawback=True)[0] == 'nerf'
    assert semantics.direction(path, -15, -10, 'item', drawback=True)[0] == 'buff'


def test_mechanics_audit_cases():
    # investment steps keyed by their souls threshold: a step inserted at 6,400 shifts nothing
    o = {'m_MapModCostBonuses': {'EItemSlotType_Armor': [{'nGoldThreshold': 800, 'flBonus': 8},
                                                         {'nGoldThreshold': 6400, 'flBonus': 34}]}}
    assert 'm_MapModCostBonuses.EItemSlotType_Armor{6400}.flBonus' in flatten(o)
    assert semantics.describe('m_MapModCostBonuses.EItemSlotType_Armor{6400}.flBonus', {})['label'] == \
        'Vitality investment at 6,400 souls: bonus'
    # a % <-> flat HP switch is not an 837% buff
    assert semantics.direction('m_MapModCostBonuses.EItemSlotType_Armor{800}.flBonus', 8, 75, 'hero') == ('changed', None)
    # a placeholder speed curve does not beat the field after build 5747
    w = {'m_flBulletSpeed': 25000, 'm_BulletSpeedCurve': {'m_spline': [{'x': 0, 'y': 22500}, {'x': 1, 'y': 22500}]}}
    assert flatten(w, curve_wins=False) == {'m_flBulletSpeed': 25000}
    assert flatten(w) == {'m_flBulletSpeed': 22500}
    # directions: a longer dash over a fixed distance is slower; a smaller self-slow is better; the
    # parried enemy's damage taken is ours to raise
    assert semantics.direction('m_mapStartingStats.EGroundDashDuration', 0.68, 0.7, 'hero')[0] == 'nerf'
    assert semantics.direction('m_MantleSlowOnHitModifier.m_flPercentageMultiplierStart', 80, 64, 'ability')[0] == 'buff'
    assert semantics.direction('m_mapAbilityProperties.VictimDamageTakenScale.m_strValue', 30, 25, 'ability')[0] == 'nerf'
    # values Valve writes in metres / m/s are not divided again
    assert semantics.display_raw(18, semantics.engine_unit('m_flDashJumpDistanceInMeters')) == '18m'
    assert semantics.display_raw(13, semantics.engine_unit('m_flClimbSpeedUp')) == '13m/s'
    # base stat units: speeds in m/s, times in s, no % on a multiplier
    tok = {'statdesc_runspeed_postfix': 'm', 'statdesc_critdamagebonusscale_postfix': '%'}
    assert semantics.describe('m_mapStartingStats.ERunSpeed', tok)['unit'] == 'm/s'
    assert semantics.describe('m_mapStartingStats.EGroundDashDuration', tok)['unit'] == 's'
    assert semantics.describe('m_mapStartingStats.ECritDamageBonusScale', tok)['unit'] == ''


def test_values_carry_the_tooltip_unit_and_label():
    tok = {'abilitycooldown_postfix': 's', 'buffduration_label': 'Shield Duration', 'buffduration_postfix': 's',
           'enemyslow_postfix': '%'}
    d = semantics.describe('m_mapAbilityProperties.AbilityCooldown.m_strValue', tok, 'x', 'ability')
    assert d['unit'] == 's' and semantics.with_unit('30', d['unit']) == '30s'
    # the tooltip names a property by its m_strLocTokenOverride
    d = semantics.describe('m_mapAbilityProperties.SpeedOnLandDuration.m_strValue', tok, 'x', 'ability', token='BuffDuration')
    assert (d['label'], d['unit']) == ('Shield Duration', 's')
    d = semantics.describe('m_vecAbilityUpgrades[2].m_vecPropertyUpgrades{EnemySlow}.m_strBonus', tok, 'x', 'ability')
    assert semantics.with_unit('-50', d['unit']) == '-50%'
    assert semantics.with_unit('12.19m', 'm') == '12.19m' and semantics.with_unit('—', 's') == '—'


def test_units_and_reencodings():
    assert semantics.engine_unit('m_flRunSpeed') == semantics.SPEED
    assert semantics.engine_unit('m_flSightRangePlayers') is True
    assert semantics.engine_unit('m_flBossDamageScale') == semantics.FRACTION     # a share: 0.5 is 50%
    assert semantics.engine_unit('m_flAbilityDamageScale') is False
    assert semantics.display_raw(18000, semantics.SPEED) == '457.2m/s'
    assert semantics.display_raw('12.19m', True) == '12.19m'               # already metres: not divided again
    p = 'm_mapAbilityProperties.ChannelMoveSpeed.m_strValue'
    assert semantics.reencoded(200, '5.1m', p)                              # 200 units/s is 5.1 m/s
    assert semantics.reencoded(1, 100, 'm_mapAbilityProperties.ImbuedCooldownMultiplier.m_strValue')
    assert not semantics.reencoded(1, 100, 'm_mapAbilityProperties.Damage.m_strValue')
    assert semantics.direction(p, 50, -1, 'ability') == ('changed', None)   # -1 = no cap


def test_shares_speeds_and_curve_corners():
    """Audit 2026-10-02: shares as percents, travel speeds in m/s, a curve's corners named min/max."""
    w = semantics.describe('m_mapWeaponInfos.primary.m_flShootMoveSpeedPercent', {}, 'citadel_weapon_bebop_set', 'weapon')
    assert semantics.show(0.55, w['meters']) == '55%' and semantics.show('0.7', w['meters']) == '70%'
    assert semantics.show(0.1, semantics.FRACTION) == '10%'
    zip_ = semantics.describe('m_mapAbilityProperties.ZipSpeed.m_strValue', {}, 'citadel_ability_zip_line', 'ability')
    assert semantics.show('693', zip_['meters']) == '17.6m/s'
    # a capped speed is a travel speed too (backlog #13: Rain of Arrows' "Air Speed Max 150 → 161.42" = 3.8 → 4.1 m/s)
    for prop in ('TossSpeedUpWall', 'ReturnSpeedNonPlayer', 'AttackingDashSpeed', 'InitialProjectileVelocity',
                 'FallSpeedMax', 'AirSpeedMax'):
        assert semantics.prop_speed(prop), prop
    for prop in ('ChannelMoveSpeed', 'MoveSpeedBonusPct', 'TrackingSpeed', 'ZipMasteryExtraSpeedBonus',
                 'BonusBulletSpeedPercent', 'PostGroundDashSpeed', 'SummonTurnSpeed'):
        assert not semantics.prop_speed(prop), prop
    assert not semantics.prop_speed('ZipSpeed', 'm/s')            # the tooltip's own unit: already m/s
    assert semantics.humanize('m_vDomainMaxs') == 'Domain (max)'
    assert semantics.humanize('m_vDomainMins') == 'Domain (min)'
    assert semantics.humanize('m_iMatchTimeMinsForLevel2Pickups') == 'Match Time (min) For Level2 Pickups'
    # a powerup's modifier value is named by what it changes, not "Modifier Values MODIFIER_VALUE_X › Modifier Value"
    assert semantics.context_label('m_sModifer.m_vecModifierValues{MODIFIER_VALUE_STAMINA}.m_flModifierValue') == \
        'Effect › Stamina'


def test_polarity_audit_cases():
    d = lambda prop, a, b, **kw: semantics.direction(f'm_mapAbilityProperties.{prop}.m_strValue', a, b, 'ability', **kw)[0]
    assert d('AbilityPostCastDuration', 0.5, 0.2) == 'buff'          # busy for less time after the cast
    assert d('ArmTime', 3, 2) == 'buff'
    assert d('RespawnHealthPercent', 40, 50) == 'buff'               # Soul Rebirth: more health on rebirth
    assert d('BonusBaseWeaponDamageTaken', 50, 40) == 'nerf'         # Alchemical Fire: the enemy takes less
    assert d('NonHeroReductionPercent', 40, 50) == 'nerf'            # weaker against non-heroes
    assert d('m_flShootSpreadPenaltyDecayDelay', 0, 0.3) == 'nerf'
    tier = 'm_vecAbilityUpgrades[2].m_vecPropertyUpgrades{GroundDashReductionPercent}.m_strBonus'
    # a bonus to a debuff stored negative: Sleep Dagger T3 -50 -> -45 is weaker ("dash slows -10%")
    assert semantics.direction(tier, -50, -45, 'ability', negative_base=True)[0] == 'nerf'
    assert semantics.direction(tier, -8, -10, 'item', negative_base=True)[0] == 'buff'
    slow = 'm_vecAbilityUpgrades[0].m_vecPropertyUpgrades{EnemyDashSlowPercent}.m_strBonus'
    assert semantics.direction(slow, -25, -22, 'ability')[0] == 'nerf'     # a weaker enemy slow, base 0
    cd = 'm_vecAbilityUpgrades[0].m_vecPropertyUpgrades{AbilityCooldown}.m_strBonus'
    assert semantics.direction(cd, -20, -18, 'ability')[0] == 'nerf'  # a cooldown bonus keeps its sign rule


def test_small_coefficients_keep_their_digits():
    assert semantics.display_value(0.00035) == '0.00035'
    assert semantics.display_value(0.0003) == '0.0003'
    assert semantics.display_value(1e-05) == '0.00001'
    assert semantics.display_value(1.2345) == '1.23'
    assert semantics.scaling_suffix(['EAddToScale', 'EBaseWeaponDamageIncrease']) == ' (weapon damage scaling)'
    assert semantics.scaling_suffix(['EMultiplyScale', 'ETechPower']) == ' (spirit scaling ×)'


def test_plain_labels_for_unlabelled_structures():
    lab = lambda p: semantics.describe(p, {}, 'x', 'hero')['label']   # noqa: E731
    assert lab('m_mapLevelInfo."22".m_unRequiredGold') == 'Level 22: souls needed'
    assert lab('m_mapLevelInfo."14".m_mapBonusCurrencies.EAbilityPoints') == 'Level 14: ability points'
    assert lab('m_MapModCostBonuses.EItemSlotType_Armor[4].flBonus') == 'Vitality investment, step 5: bonus'
    assert lab('m_mapBoundAbilities.ESlot_Signature_3') == 'Kit: Ability 3'
    assert lab('m_sModifer.m_vecModifierValues{MODIFIER_VALUE_FIRE_RATE}.m_valueMin') == 'Powerup: Fire Rate (early game)'
    assert semantics.humanize('m_projectileInfo') == 'Projectile Info'
    assert semantics.humanize('m_flSightRangeNPCs') == 'Sight Range NPCs'
    assert semantics.humanize('m_iSpawnIntervalInSeconds') == 'Spawn Interval (s)'


def test_a_map_key_that_is_an_id_reads_as_words():
    """2026-10-03: 30 Walker rows read 'Intrinsic Modifiers npc_boss_intrinsic › Bullet Armor Damage Resist'."""
    from pipeline import semantics
    label = semantics.context_label('m_sModifer.m_mapThings{npc_boss_intrinsic}.m_flSize')
    assert 'npc_' not in label and 'boss intrinsic' in label
    assert semantics._key_text('EModTier_1') == 'EModTier_1' and semantics._key_text('Value') == 'Value'


def test_labels_use_the_games_words():
    """Advisor round 4 (2026-10-03): labels split from field names said "Tech Armor Damage Resist" (63
    rows) and "Intrinsic Modifiers boss intrinsic › …" — the game says Spirit / Bullet Resist, and a
    unit's intrinsic modifier is its passive."""
    from pipeline import semantics
    assert semantics.humanize('TechArmorDamageReduction') == 'Spirit Resist'
    assert semantics.humanize('MODIFIER_VALUE_TECH_ARMOR_DAMAGE_RESIST_REDUCTION'.title().replace('_', '')) \
        == 'Modifier Value Spirit Resist Reduction'
    assert semantics.humanize('TechPowerPerKill') == 'Spirit Power Per Kill'
    assert semantics.humanize('m_flTechnicalDelay') == 'Technical Delay'       # a word, not a prefix
    path = 'm_vecIntrinsicModifiers{npc_boss_intrinsic}.m_vecScriptValues{MODIFIER_VALUE_BULLET_ARMOR_DAMAGE_RESIST}.m_value'
    assert semantics.context_label(path) == 'Passive › Bullet Resist'
    assert semantics.context_label('m_mapItemSlotInfo.EItemSlotType_Tech.m_arMaxPurchasesForTier').startswith(
        'Item Slot Info › Spirit')


def test_labels_read_without_engine_words():
    """Review 2026-10-05: 1,533 rows on 102 pages read engine words — boss tiers, "Phase01", "Pct", an aura's
    container, CamelCase keys, "Ao E"."""
    from pipeline import semantics
    assert semantics.describe('m_flT1BossDPSMaxResist', {})['label'] == 'Damage Resist at most vs Guardian'
    assert semantics.describe('m_flT2BossDamageResistPct', {})['unit'] == '%'
    assert semantics.describe('m_flAttackT3BossPhase2MaxRange', {})['label'] == 'Max Range vs Patron Phase 2'
    assert semantics.describe('m_flBarrackBossDPS', {})['label'] == 'DPS vs Base Guardian'
    assert semantics.humanize('m_flAttackTimePhase01') == 'Attack Time Phase 1'
    assert semantics.humanize('m_flPounceToTargetDist') == 'Pounce To Target Distance'
    assert semantics.context_label('m_AoEModifier.m_flWaveHeight') == 'AoE Modifier › Wave Height'
    assert semantics.context_label('m_IceDomeModifier.m_EnemyAuraModifier.m_modifierProvidedByAura.m_nEnabledStateMask') \
        == 'Enemy Aura › Applies'
    assert semantics.context_label('m_modifierProvidedByAura.m_flModifierProvidedByAuraDuration').startswith('Lingers')
    assert semantics.context_label('fl_MaxExtraGravityScale') == 'Max Extra Gravity Scale'
    assert semantics.context_label('ECritDamageBonusScale') == 'Crit Damage Bonus Scale'
    d = semantics.describe('m_mapAbilityProperties.NonHeroHealPct.m_strValue', {})
    assert (d['label'], d['unit']) == ('Non Hero Heal', '%')
    assert semantics.describe('m_mapAbilityProperties.DamageGrowthPctPerMin.m_strValue', {})['label'] \
        == 'Damage Growth % Per Min'
    # a coefficient is no percent, a fraction field is shown ×100
    assert not semantics.describe('m_vecAbilityUpgrades[2].m_vecPropertyUpgrades{DealMaxHealthDamagePct|EAddToScale}'
                                  '.m_strBonus', {}, kind='ability').get('unit')
    d = semantics.describe('m_mapAbilityProperties.FourthHitDamagePercentage.m_strValue', {})
    assert d['meters'] == semantics.FRACTION and semantics.show('0.26', d['meters'], d.get('unit', '')) == '26%'
    # a modifier's resist value is a percent (Walker's passive)
    path = 'm_vecIntrinsicModifiers{npc_boss_intrinsic}.m_vecScriptValues{MODIFIER_VALUE_BULLET_ARMOR_DAMAGE_RESIST}.m_value'
    assert semantics.describe(path, {})['unit'] == '%'
    assert not semantics.describe(path.replace('_RESIST}', '_RESIST_REDUCTION_PER_HERO}'), {}).get('unit')


def test_a_bare_channel_move_speed_is_engine_units_whatever_the_other_side():
    """Review 2026-10-05: "Channel Move Speed 50 → no limit" sat next to "1.27m/s → 1.3m/s" in one band (24 rows):
    Valve wrote it in units until 2025-08-18, so a bare side is units even when the other is no number."""
    from pipeline import semantics
    path = 'm_mapAbilityProperties.ChannelMoveSpeed.m_strValue'
    assert semantics.units_when_bare(path, '50', '-1') == ('1.27m', '-1')
    assert semantics.units_when_bare(path, '1.3m', '2m') == ('1.3m', '2m')
    assert semantics.units_when_bare('m_mapAbilityProperties.Radius.m_strValue', '50', '-1') == ('50', '-1')


def test_a_units_tag_and_percent_go_the_same_way():
    """Review 2026-10-05: "T1 Boss DPS Max Resist -35 → -50 DOWN +42.9%" — UP / DOWN say where the number went,
    the percent with its sign; a helper unit (the Hideout's Sinner's Sacrifice) reads UP / DOWN like its family."""
    import pytest
    from pipeline import semantics
    assert semantics.direction('m_flT1BossDPSMaxResist', -35, -50, 'trooper') == ('down', pytest.approx(-42.857, 0.01))
    assert semantics.direction('m_flBulletSpeed', 457.2, 152.4, 'helper')[0] == 'down'


def test_times_carry_seconds_and_metre_speeds_read_per_second():
    """Advisor round 4: Fire Interval / Reload Time / Bullet Lifetime had no unit (1,867 rows), and
    "Channel Move Speed 20m" read as a length. A T1-T3 bonus keeps its own unit."""
    from pipeline import semantics
    assert semantics.describe('m_mapWeaponInfos.primary.m_flCycleTime', {})['unit'] == 's'
    assert semantics.describe('m_mapWeaponInfos.primary.m_reloadDuration', {})['unit'] == 's'
    assert semantics.describe('m_flStunDuration', {})['unit'] == 's'
    assert semantics.describe('m_mapAbilityProperties.AbilityPostCastDuration.m_strValue', {})['unit'] == 's'
    # a plain T1-T3 bonus to a time no tooltip gives a unit is seconds like the time (review 2026-10-05: Doorman's
    # "T3: Late Checkout Cooldown 13 → 15" is the notes' 10s → 13s); a scaling coefficient is not
    assert semantics.describe('m_vecAbilityUpgrades[2].m_vecPropertyUpgrades{AbilityCooldown}.m_strBonus',
                              {}, kind='ability').get('unit') == 's'
    assert not semantics.describe('m_vecAbilityUpgrades[2].m_vecPropertyUpgrades{AbilityDuration|EAddToScale}.m_strBonus',
                                  {}, kind='ability').get('unit')
    assert semantics.describe('m_flCooldownOnHit', {})['unit'] == 's'
    assert semantics.describe('m_flTimeToGiveUp', {})['unit'] == 's'
    assert not semantics.describe('m_flCastDelayMaxDist', {}).get('unit') == 's'
    assert not semantics.describe('m_flGrowthStartTimeInMinutes', {}).get('unit') == 's'
    assert not semantics.describe('m_mapWeaponInfos.primary.m_flBulletDamage', {}).get('unit')
    d = semantics.describe('m_mapAbilityProperties.ChannelMoveSpeed.m_strValue', {})
    assert d['speed_m'] and d['meters'] is False             # the matcher's transforms stay as they were
    assert semantics.show('20m', semantics.M_SPEED) == '20m/s'
    assert semantics.show('50', semantics.M_SPEED) == '50'
    assert semantics.show(-1, semantics.M_SPEED) == '-1'


def test_a_corrupted_bonus_reads_like_a_tier_bonus():
    """Review 2026-10-05: Blood Tribute 'Move Speed +2m' (a speed), Arctic Blast's slow 'Move Speed +30%' (the game
    prints '-30%': an enemy slow), a property named by its tooltip token."""
    p = 'm_CorruptedItemInfo.m_Upgrade.m_vecPropertyUpgrades{%s}.m_strBonus'
    tok = {'slowpercent_label': 'Move Speed', 'slowpercent_prefix': '-', 'slowpercent_postfix': '%',
           'bonusmovespeed_label': 'Move Speed', 'bonusmovespeed_postfix': 'm'}
    d = semantics.describe(p % 'BonusMoveSpeed', tok, 'upgrade_blood_tribute', 'item')
    assert d['speed_m'] and d['unit'] == 'm'
    d = semantics.describe(p % 'SlowPercent', tok, 'upgrade_arctic_blast', 'item')
    assert d['sign'] == '-' and d['label'] == 'Corrupted: Move Speed'
    assert semantics.enemy_label(d['label'], 'SlowPercent') == 'Corrupted: Movement Slow'
