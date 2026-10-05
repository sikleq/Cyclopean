"""Ability cards, generated patch lines, technical-field classification."""
from pipeline.abilities import fill, fmt_prop
from pipeline.classify import category
from pipeline.match import sentence


def test_tooltip_text_filled_like_the_game():
    text = 'Apply <span class="highlight">-{s:EnemySlowPct}%</span> Move speed for {s:EnemySlowDuration}s'
    assert fill(text, {'EnemySlowPct': '28', 'EnemySlowDuration': '3'}) == 'Apply -28% Move speed for 3s'
    assert fill("Strike, {g:citadel_inline_attribute:'Healing'} for a portion", {}) == 'Strike, Healing for a portion'
    assert fill('a<br>b', {}) == 'a\nb'


def test_inline_attributes_read_like_the_game_and_units_do_not_double():
    tok = {'inlineattribute_spiritdps': 'spirit damage over time', 'inlineattribute_spiriticon': ''}
    # the game prints the attribute's localized words, not its key ("SpiritDPS")
    text = "dealing {g:citadel_inline_attribute:'SpiritDPS'} and {g:citadel_inline_attribute:'Heal'}"
    assert fill(text, {}, tok) == 'dealing spirit damage over time and heal'
    assert fill("x {g:citadel_inline_attribute:'SpiritIcon'}y", {}, tok) == 'x y'
    assert fill("gain {g:citadel_inline_attribute:'AirDash'}", {}, tok) == 'gain air dash'      # unknown: words
    # a key binding is drawn as a key in the game
    assert fill("Hold{g:citadel_binding:'MoveForward'}while active", {}, tok) == 'Hold [Move Forward] while active'
    # a value that already carries the template's unit: "+{s:Radius}m" with "2m" is "+2m", not "+2mm"
    assert fill('<span>+{s:Radius}m</span> Radius', {'Radius': '2m'}) == '+2m Radius'
    assert fill('for {s:D}s', {'D': '5'}) == 'for 5s'
    # the text's own unit after a space: "1.2m m/s" -> "1.2 m/s"; a word starting with m is no unit
    assert fill('Gain {s:S} m/s Move Speed', {'S': '1.2m'}) == 'Gain 1.2 m/s Move Speed'
    assert fill('{s:R} more', {'R': '3m'}) == '3m more'
    # entities in the loc text become characters: the page escapes once ("&amp;amp;")
    assert fill('Bullet, Spirit &amp; Melee Lifesteal', {}) == 'Bullet, Spirit & Melee Lifesteal'


def test_tier_text_uses_the_tooltip_token_names():
    from pipeline.abilities import card
    a = {'m_mapAbilityProperties': {
            'SpeedOnLandDuration': {'m_strValue': '0', 'm_strLocTokenOverride': 'BuffDuration'},
            'MaxBonusBulletDamage': {'m_strValue': '10'}},
         'm_vecAbilityUpgrades': [{'m_vecPropertyUpgrades': [
             {'m_strPropertyName': 'SpeedOnLandDuration', 'm_strBonus': '4'},
             {'m_strPropertyName': 'MaxBonusBulletDamage', 'm_strBonus': '0.5', 'm_eUpgradeType': 'EAddToScale'}]}]}
    tok = {'x_t1_desc': 'Move speed for {s:BuffDuration}s and +{s:MaxBonusBulletDamage_scale}% scaling',
           'x_desc': '{s:hero_name} floats', 'hero_x': 'Paradox'}
    c = card('x', a, tok, 'ability', 'hero_x')
    # the text names the property by its m_strLocTokenOverride; a scale bonus by "<prop>_scale"
    assert c['tiers'][0]['text'] == 'Move speed for 4s and +0.5% scaling'
    assert c['desc'] == 'Paradox floats'


def test_property_prefix_and_units():
    tok = {'enemyslowpct_prefix': '-', 'enemyslowpct_postfix': '%', 'bonushealth_prefix': '{s:sign}',
           'abilitycastrange_postfix': 'm'}
    assert fmt_prop(tok, 'EnemySlowPct', '28', 'a') == '-28%'
    assert fmt_prop(tok, 'BonusHealth', '125', 'a') == '+125'
    assert fmt_prop(tok, 'BonusHealth', '-50', 'a') == '-50'
    assert fmt_prop(tok, 'AbilityCastRange', '20m', 'a') == '20m'
    # a postfix with a space, or "s" after a value in seconds: the unit once
    tok2 = {'bonusmovespeed_postfix': ' m', 'bonusmovespeed_prefix': '{s:sign}', 'slowduration_postfix': 's'}
    assert fmt_prop(tok2, 'BonusMoveSpeed', '3m', 'a') == '+3m'
    assert fmt_prop(tok2, 'SlowDuration', '2s', 'a', bonus=True) == '+2s'
    assert fmt_prop({'fervormovespeed_postfix': ' m/s'}, 'FervorMovespeed', '4m', 'a') == '4m/s'


def test_valve_style_sentences():
    base = {'label': 'Health', 'op': 'change', 'old_s': '780', 'new_s': '800', 'path': 'x'}
    assert sentence('Abrams', base) == 'Abrams: Health increased from 780 to 800'
    assert sentence('Abrams', {**base, 'old_s': '800', 'new_s': '780'}).endswith('reduced from 800 to 780')
    assert sentence('Mina', {'path': '@add', 'op': 'add'}) == 'Mina: added to the game'


def test_values_say_what_they_are():
    # sound events, file paths, loc keys, unix times are not gameplay, whatever the field is called
    assert category('m_strGrappleHitWorld', 'Ability.Bebop.Hook.ImpactGeo', 'Ability.Tengu.Tether.Attach') == 'audio'
    assert category('m_HudSharedStyle', None, 'panorama/styles/Hud elements/abilities_astro.vcss') == 'ui'
    assert category('m_strCastButtonLocToken', None, '#AbilityButtonHint_AltCastStickyBomb') == 'ui'
    assert category('m_unAddedTime', 1737133200, None) == 'meta'
    # "20m" as the records keep it is a number (986 rows were mechanics)
    assert category('m_mapAbilityProperties.VacuumRadius.m_strValue', '8m', '10m') == 'balance'
    # gameplay words that looked visual: light melee, effectiveness, a hero growing, recoil
    assert category('m_mapAbilityProperties.LightMeleeCooldownMult.m_strValue', 1, 2) == 'balance'
    assert category('m_mapAbilityProperties.SlowEffectiveness.m_strValue', 1, 2) == 'balance'
    assert category('m_mapAbilityProperties.ModelScaleGrowth.m_strValue', 1, 2) == 'balance'
    assert category('m_mapWeaponInfos.primary.m_flRecoilSpeed', 1, 2) == 'balance'
    assert category('m_mapAbilityProperties.PunchRadius.m_strValue', 1, 2) == 'balance'
    # what a value scales with: changing it is real, adding the wiring is not
    p = 'm_mapAbilityProperties.Damage.m_subclassScaleFunction.m_eSpecificStatScaleType'
    assert category(p, 'ETechPower', 'ELightMeleeDamage') == 'mechanic'
    assert category(p, None, 'ETechPower') == 'technical'
    assert category('m_flRangeRingAlpha', 0.8, 0.6) == 'visual'                       # build 6728's Walker ring


def test_units_with_only_looks_are_helpers():
    from pipeline.classify import unit_is_helper
    assert unit_is_helper('citadel_cat_animating', {'_class': 'citadel_cat_animating', 'm_sModelName': 'cat.vmdl'})
    assert unit_is_helper('citadel_basketball', {'_class': 'citadel_hideout_ball', 'm_flMass': 3})   # a Hideout toy
    assert unit_is_helper('npc_player_bot_brain', {'m_flSightRange': 900})
    assert not unit_is_helper('npc_necro_skele', {'_class': 'npc_necro_skele', 'm_flRunSpeed': 300})
    assert not unit_is_helper('gone_unit', {})                       # nothing left to judge


def test_screen_flash_sounds_and_offsets_are_not_balance():
    assert category('EFlashType_BulletDamage.m_flCoverage', 1, 0.75) == 'visual'      # damage screen flash
    assert category('m_vecOriginOffsetsLeft[1]', 1, 2) == 'visual'
    assert category('m_NearDeathModifier.m_sSelfDestructEnd', 'a', 'b') == 'audio'
    assert category('m_ImmunityModifier.m_bIsHiddenOverhead', None, True) == 'ui'
    assert category('m_bWarnIfNoAffectedAbilities', None, True) == 'technical'


def test_engine_plumbing_is_technical_not_balance():
    assert category('m_mapAbilityProperties.Damage.m_subclassScaleFunction._class', 'a', 'b') == 'technical'
    assert category('m_mapWeaponInfos.primary.m_BulletSpeedCurve.m_spline[3].x', 1, 2) == 'technical'
    assert category('m_bitsPreCastEnabledStateMask', 'a', 'b') == 'technical'
    assert category('m_mapItemDraftWeights.upgrade_x', 1, 2) == 'streetbrawl'
    # real values stay gameplay
    assert category('m_mapAbilityProperties.Damage.m_strValue', 65, 80) == 'balance'
    assert category('m_mapAbilityProperties.Damage.m_subclassScaleFunction.m_flStatScale', 0.8, 0.85) == 'balance'
    assert category('m_mapWeaponInfos.primary.m_flBulletSpeed', 1, 2) == 'balance'


def test_presentation_fields_are_not_gameplay():
    assert category('m_strVoteSticker', 'a', 'b') == 'visual'
    assert category('m_sAG2VariationName', 'a', 'b') == 'visual'
    assert category('m_nNameOffset', 140, 150) == 'ui'
    assert category('m_strLocUnitName', 'a', 'b') == 'ui'
    assert category('m_flHullCapsuleRadius', 90, 20) == 'technical'
    assert category('m_flSightRangeNPCs', 1500, 1338) == 'technical'
    assert category('m_vecHitReactClips[0].m_ClipID', 1, 2) == 'visual'
    # gameplay stays gameplay
    assert category('m_flSightRangePlayers', 1500, 1338) == 'balance'


def test_look_sound_and_engine_tuning_are_not_gameplay():
    """Review 2026-10-05: 147 rows of looks, sounds, engine tuning and bot wiring sat on the pages as balance
    ("Time Wall Depth Visual Scale 0.04 → 0.16 BUFF +300%"). Narrow names only: the gameplay fields with the same
    words stay."""
    p = 'm_mapAbilityProperties.{}.m_strValue'
    assert category(p.format('TimeWallDepthVisualScale'), 0.04, 0.16) == 'visual'
    assert category(p.format('ProjectileModelScale'), 1, 2) == 'visual'
    assert category('m_flBobHeight', 1, 2) == 'visual'
    assert category('m_flFakeBulletDistanceFudge', None, 500) == 'visual'
    assert category('m_flVelocityVolScaleMin', None, 0.25) == 'audio'
    assert category('m_SpeedToPitchRemap', '1, 2', '1, 3') == 'audio'
    assert category('EResourceType_Heat.m_strHUDSnippetName', None, 'heat') == 'ui'
    assert category('m_flMaxMoveIterationScale', 1, 2) == 'technical'
    assert category('m_NpcAimingSpread', '1, 2', '2, 3') == 'technical'
    assert category('m_flRespawnTimeTest', 10, 20) == 'meta'
    for path in ('m_remapCapturersToCaptureTime', 'm_flDamageFalloffBias', 'm_flTrackingDampingCoefficient',
                 'm_flVerticalAimBias', 'm_flWallJumpPowerBias', p.format('ModelScaleGrowth'), 'm_flSweepingDuration',
                 'm_flGravityScale'):
        assert category(path, 1, 2) in ('balance', 'mechanic'), path
