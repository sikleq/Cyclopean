"""The hero page's game panels (pipeline/hero_panels.py, builders/hero_panels.py; owner 2026-10-22): the stats each
panel lists come from the hero's m_ShopStatDisplay, values read the game's way (checked against the game's own Warden
panels), and every per-boon number is of its own build's boon count."""
from __future__ import annotations

import json
from pathlib import Path

from pipeline import hero_panels as hp

ROOT = Path(__file__).resolve().parent.parent

WARDEN = {
    'm_mapStartingStats': {'EMaxMoveSpeed': 6.3, 'EReloadSpeed': 1, 'ECritDamageReceivedScale': 1.0,
                           'ECritDamageBonusScale': 1.0, 'ETechDuration': 1, 'ETechRange': 1,
                           'EHeroSpiritLifestealEffectiveness': 1.0, 'EStaminaRegenPerSecond': 0.222222,
                           'EOOCHealthRegen': 0},
    'm_mapScalingStats': {'ERoundsPerSecond': {'eScalingStat': 'ETechPower', 'flScale': 0.008},
                          'EFireRate': {'eScalingStat': 'ETechPower', 'flScale': 0.21}},
    'm_ShopStatDisplay': {
        'm_eWeaponStatsDisplay': {
            'm_vecDisplayStats': ['EBulletDamage', 'ERoundsPerSecond', 'EFireRate', 'EReloadSpeed', 'ECritDamageBonusScale'],
            'm_vecOtherDisplayStats': ['ELightMeleeDamage'],
            'm_eWeaponAttributes': 'EWeaponAttribute_MediumRange | EWeaponAttribute_Projectile',
            'm_strWeaponImage': 'panorama:"file://{images}/heroes/guns/warden_gun.psd"'},
        'm_eVitalityStatsDisplay': {
            'm_vecDisplayStats': ['EMaxHealth', 'EHeroSpiritLifestealEffectiveness', 'ECritDamageReceivedScale'],
            'm_vecOtherDisplayStats': ['EMaxMoveSpeed', 'EStaminaCooldown']},
        'm_eSpiritStatsDisplay': {'m_vecDisplayStats': ['ETechCooldown', 'ETechDuration', 'ETechRange']},
    },
}


def test_panels_are_the_heros_own_lists_in_order():
    p = hp.panels(WARDEN)
    assert p['weapon'] == {'stats': ['EBulletDamage', 'ERoundsPerSecond', 'EFireRate', 'EReloadSpeed',
                                     'ECritDamageBonusScale'], 'other': ['ELightMeleeDamage']}
    assert p['vitality']['other'] == ['EMaxMoveSpeed', 'EStaminaCooldown']
    assert p['spirit'] == {'stats': ['ETechCooldown', 'ETechDuration', 'ETechRange'], 'other': []}


def test_gun_tags_and_picture():
    assert hp.gun(WARDEN) == {'attrs': ['EWeaponAttribute_MediumRange', 'EWeaponAttribute_Projectile'],
                              'image': 'warden_gun'}
    assert hp.gun({}) == {'attrs': [], 'image': None}


def test_values_read_the_games_way():
    """Warden's panels in the game: Fire Rate 0%, Reload Reduction 0%, Crit Bonus Scale 0%, Lifesteal Effectiveness
    100%, Crit Reduction 0%, Stamina Cooldown 4.5s, Ability Duration / Range 0% — from 1.0 scales and 0.222/s."""
    v = hp.own_values(WARDEN)
    assert v['EFireRate'] == 0 and v['EReloadSpeed'] == 0 and v['ECritDamageBonusScale'] == 0
    assert v['EHeroSpiritLifestealEffectiveness'] == 100 and v['ECritDamageReceivedScale'] == 0
    assert round(v['EStaminaCooldown'], 2) == 4.5
    assert v['ETechDuration'] == 0 and v['ETechRange'] == 0 and v['ETechCooldown'] == 0
    # a stat a Hero Stats column holds is not repeated here: the tile reads the column (and its history)
    assert 'EBulletDamage' not in v and 'EMaxMoveSpeed' not in v and 'ERoundsPerSecond' not in v


def test_a_scale_stat_the_hero_lacks_reads_neutral():
    assert hp.start_value('ECritDamageBonusScale', {}) == 0          # missing 1.0 scale: no bonus
    assert hp.start_value('EHeroSpiritLifestealEffectiveness', {}) == 100
    assert round(hp.start_value('EReloadSpeed', {'EReloadSpeed': 0.8}), 6) == 20   # a 0.8 scale: 20% reduction
    assert hp.start_value('EDebuffResist', {}) == 0


def test_every_stat_name_comes_from_the_games_words():
    t = json.loads((ROOT / 'data' / 'tables' / 'heroes.json').read_text(encoding='utf-8'))
    labels = t['panel_labels']
    assert all(labels['stats'].values()), [k for k, v in labels['stats'].items() if not v]
    assert all(labels['attrs'].values()) and all(labels['text'].values())
    assert labels['stats']['EFireRate'] == 'Fire Rate' and labels['stats']['ERoundsPerSecond'] == 'Bullets per sec'
    assert labels['stats']['EClipSize'] == 'Ammo' and labels['stats']['EStaminaCooldown'] == 'Stamina Cooldown'


def test_boons_are_counted_per_build_in_the_history():
    """Owner 2026-10-22: a per-boon sum in the history uses that moment's boons. Haze had 11 boons until build 5201
    and 35 since 2025-11-21; its Max Bullet DMG step of 2025-05-27 (5648) is a boon count change alone."""
    t = json.loads((ROOT / 'data' / 'tables' / 'heroes.json').read_text(encoding='utf-8'))
    haze = next(h for h in t['heroes'] if h['id'] == 'hero_haze')
    steps = {s[0]: (s[2], s[3]) for s in haze['history']['boons']}
    assert steps[5201] == (11, 14) and steps[5648] == (19, 20) and steps[5983] == (33, 35)
    assert haze['values']['boons'] == 35
    lvl = {s[0] for s in haze['history']['bullet_dmg_lvl']}
    assert 5648 not in lvl and 5648 in {s[0] for s in haze['history']['bullet_dmg_max']}


def _warden_row() -> dict:
    t = json.loads((ROOT / 'data' / 'tables' / 'heroes.json').read_text(encoding='utf-8'))
    return next(h for h in t['heroes'] if h['id'] == 'hero_warden'), t['columns']


def test_a_tile_is_dim_at_zero_and_framed_when_spirit_raises_it():
    from builders import hero_panels as bp
    row, cols = _warden_row()
    by_key = {c['key']: c for c in cols}
    fire = bp.tile(row, 'EFireRate', by_key, 'Warden', '../')
    assert 'zero' in fire and 'spirit' in fire and '× 0.21' in fire and '>Fire Rate<' in fire
    bps = bp.tile(row, 'ERoundsPerSecond', by_key, 'Warden', '../')
    assert 'zero' not in bps and '× 0.008' in bps and 'data-hist' in bps         # the column's history stays
    life = bp.tile(row, 'EHeroSpiritLifestealEffectiveness', by_key, 'Warden', '../')
    assert '100<span class="u">%</span>' in life and 'zero' not in life


def test_spirit_power_impact_lists_the_gun_then_the_abilities():
    from builders import hero_panels as bp
    row, _ = _warden_row()
    cards = [{'slot': 'Signature_2', 'important': [{'label': 'Barrier', 'value': '125', 'scale': 0.8, 'scale_by': None,
                                                     'css': 'combat_barrier'}]},
             {'slot': 'Signature_1', 'important': [{'label': 'Damage', 'value': '60', 'scale': 0.63, 'scale_by': None,
                                                     'css': 'tech_damage'},
                                                    {'label': 'Heal', 'value': '75%', 'scale': 1, 'scale_by': 'Healing',
                                                     'css': 'healing'}]},
             {'slot': 'Weapon_Primary', 'important': [{'label': 'X', 'value': '1', 'scale': 1, 'scale_by': None}]}]
    rows = bp.impact_rows(row, cards, '../')
    names = [r.split('class="l">')[1].split('<')[0] for r in rows]
    assert names == ['Bullets per sec', 'Fire Rate', 'Damage', 'Barrier']


def test_boon_card_says_its_own_builds_count():
    from builders import hero_panels as bp
    row, cols = _warden_row()
    html = bp.boon_card(row, {c['key']: c for c in cols}, 'Warden', '../')
    assert 'At each threshold, Warden gains:' in html and '>35</b>' in html
    assert 'Base Bullet Damage' in html and 'Base Health' in html and 'Weapon Range' not in html   # 0 gains left out
