"""Ability cards, generated patch lines, technical-field classification."""
from pipeline.abilities import fill, fmt_prop
from pipeline.classify import category
from pipeline.match import sentence


def test_tooltip_text_filled_like_the_game():
    text = 'Apply <span class="highlight">-{s:EnemySlowPct}%</span> Move speed for {s:EnemySlowDuration}s'
    assert fill(text, {'EnemySlowPct': '28', 'EnemySlowDuration': '3'}) == 'Apply -28% Move speed for 3s'
    assert fill("Strike, {g:citadel_inline_attribute:'Healing'} for a portion", {}) == 'Strike, Healing for a portion'
    assert fill('a<br>b', {}) == 'a\nb'


def test_property_prefix_and_units():
    tok = {'enemyslowpct_prefix': '-', 'enemyslowpct_postfix': '%', 'bonushealth_prefix': '{s:sign}',
           'abilitycastrange_postfix': 'm'}
    assert fmt_prop(tok, 'EnemySlowPct', '28', 'a') == '-28%'
    assert fmt_prop(tok, 'BonusHealth', '125', 'a') == '+125'
    assert fmt_prop(tok, 'BonusHealth', '-50', 'a') == '-50'
    assert fmt_prop(tok, 'AbilityCastRange', '20m', 'a') == '20m'


def test_valve_style_sentences():
    base = {'label': 'Health', 'op': 'change', 'old_s': '780', 'new_s': '800', 'path': 'x'}
    assert sentence('Abrams', base) == 'Abrams: Health increased from 780 to 800'
    assert sentence('Abrams', {**base, 'old_s': '800', 'new_s': '780'}).endswith('reduced from 800 to 780')
    assert sentence('Mina', {'path': '@add', 'op': 'add'}) == 'Mina: added to the game'


def test_engine_plumbing_is_technical_not_balance():
    assert category('m_mapAbilityProperties.Damage.m_subclassScaleFunction._class', 'a', 'b') == 'technical'
    assert category('m_mapWeaponInfos.primary.m_BulletSpeedCurve.m_spline[3].x', 1, 2) == 'technical'
    assert category('m_bitsPreCastEnabledStateMask', 'a', 'b') == 'technical'
    assert category('m_mapItemDraftWeights.upgrade_x', 1, 2) == 'streetbrawl'
    # real values stay gameplay
    assert category('m_mapAbilityProperties.Damage.m_strValue', 65, 80) == 'balance'
    assert category('m_mapAbilityProperties.Damage.m_subclassScaleFunction.m_flStatScale', 0.8, 0.85) == 'balance'
    assert category('m_mapWeaponInfos.primary.m_flBulletSpeed', 1, 2) == 'balance'
