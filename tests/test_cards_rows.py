"""The rows of a patch's cards (builders/cards.py): what folds, what counts, what a row says."""
from tests.helpers import ch


def test_zero_added_or_removed_is_no_change():
    from builders.cards import is_noop
    assert is_noop({'op': 'add', 'path': 'p', 'new_s': '0'})            # Sleep Dagger's Explosion Radius 0
    assert is_noop({'op': 'remove', 'path': 'p', 'old_s': '0m'})
    assert is_noop({'op': 'change', 'old_s': '1.5', 'new_s': '1.5'})
    assert not is_noop({'op': 'add', 'path': 'p', 'new_s': '5'})
    assert not is_noop({'op': 'change', 'old_s': '20', 'new_s': '0'})   # tuned TO zero is a change
    assert not is_noop({'op': 'add', 'path': '@add', 'new_s': ''})       # an entity added to the game
    # the same value spelled two ways is not a change ("LOS Check: Bounds → Bounds")
    assert is_noop({'op': 'change', 'old_s': 'ELOSCheck_Bounds', 'new_s': 'Bounds'})
    assert is_noop({'op': 'change', 'old_s': 'Head Ignore Obscure Blockers', 'new_s': 'Head_IgnoreObscureBlockers'})
    assert not is_noop({'op': 'change', 'old_s': '1.5', 'new_s': '15'})


def test_entity_rows_name_once_with_counters():
    """The ability's header (cards.sub_head) names it once with its counters; its rows do not repeat it.
    (render.entity_rows, the table version, had no caller left besides these tests.)"""
    from builders.cards import entity_rows, sub_head
    rows = [ch(label='a', key='abilities.vdata:x:a'), ch(label='b', dir='buff', key='abilities.vdata:x:b'),
            ch(label='c', key='abilities.vdata:x:c')]
    html = sub_head('Seismic Impact', None, 'abilities', rows, hidden=True) + entity_rows(rows)
    assert html.count('Seismic Impact') == 1
    assert '<span class="pip nerf">2</span>' in html and '<span class="pip buff">1</span>' in html
    assert 'esub has-hidden' in html


def test_unreleased_rows_marked_but_not_counted_as_not_in_notes():
    """Work on a hero in development keeps its mark; it is not "not in patch notes" (render.NOT_IN_NOTES)."""
    from builders.cards import change_row
    html = change_row(ch(status='unreleased'))
    assert 'mark unreleased' in html and 'st-unreleased' in html and 'is-hidden' not in html


def test_change_row_escapes_and_marks_hidden():
    from builders.cards import change_row
    html = change_row(ch(label='<b>x</b>'))
    assert '&lt;b&gt;' in html and 'mark hidden' in html and 'st-hidden' in html


def test_replaced_tier_row_gets_full_width_line():
    from builders.cards import change_rows
    html = change_rows([ch(op='remove', label='T2: Fire Rate', old_s='14', new_s=None),
                        ch(op='add', label='T2: Stun Duration', old_s=None, new_s='0.6')])
    assert 'erow st-hidden is-hidden rw' in html and 'T2 upgrade' in html


def test_player_facing_is_the_one_counting_rule():
    from builders.cards import player_facing
    engine = ch(key='heroes.vdata:hero_atlas:m_x', label='Roster Background Layout', old_s='A', new_s='B')
    swap = [ch(key='abilities.vdata:a:t2a', op='remove', label='T2: Fire Rate', old_s='14', new_s=None),
            ch(key='abilities.vdata:a:t2b', op='add', label='T2: Stun Duration', old_s=None, new_s='0.6')]
    other = [ch(key='abilities.vdata:b:t2c', op='add', label='T2: Range', old_s=None, new_s='3')]
    out = player_facing([engine] + swap + other)
    # engine plumbing out; ability a's swapped tier is one REWORK; ability b's T2 is not folded into a's
    assert [c['op'] for c in out] == ['rework', 'add']


def test_added_entity_shows_a_summary_not_every_field():
    from builders.cards import change_rows
    rows = [ch(op='add', path='m_mapStartingStats.EMaxHealth', label='Max Health', old_s=None, new_s='780'),
            ch(op='add', path='m_mapBoundAbilities.ESlot_Signature_1', label='Bound Abilities › Signature 1', old_s=None,
               new_s='Splatter')]
    rows += [ch(op='add', path=f'm_mapLevelInfo.{i}.m_unRequiredGold', label=f'{i} › Required Gold', old_s=None,
                new_s=str(i * 100)) for i in range(1, 30)]
    html = change_rows(rows, added=True)
    assert 'Added to the game files · 31 fields' in html and 'Max Health' in html and 'Splatter' in html
    assert 'All fields (29)' in html


def test_renamed_field_is_judged_and_unit_only_renames_drop():
    from builders.cards import merge_renames
    rows = merge_renames([ch(op='remove', label='Weapon Damage', old_s='45', new_s=None, dir='changed',
                             path='m_mapAbilityProperties.WeaponDamage.m_strValue'),
                          ch(op='add', label='Weapon Damage', old_s=None, new_s='40', dir='changed',
                             path='m_mapAbilityProperties.BonusWeaponDamage.m_strValue')])
    assert len(rows) == 1 and rows[0]['op'] == 'change' and rows[0]['dir'] == 'nerf'
    same = merge_renames([ch(op='remove', label='Radius', old_s='100', new_s=None),
                          ch(op='add', label='Radius', old_s=None, new_s='2.54m')])
    assert same == []


def test_table_edited_row_by_row_folds_into_one_summary():
    from builders.cards import change_rows
    rows = [ch(label=f'Level {n}: souls needed', old_s=str(n * 1000), new_s=str(n * 950), dir='buff', pct=-5.0)
            for n in range(19, 25)]
    html = change_rows(rows)
    assert 'details class="fam' in html and 'Level 19–24: souls needed' in html and '6 rows' in html
    assert html.count('class="erow') == 7          # the summary + the 6 rows behind it
    few = change_rows([ch(label='T1: Cooldown'), ch(label='T2: Cooldown')])
    assert 'fam' not in few


def test_whole_level_added_is_one_row_and_moved_fields_drop():
    from builders.cards import change_rows, merge_renames
    rows = [ch(op='add', label='Level 35: souls needed', old_s=None, new_s='47000'),
            ch(op='add', label='Level 35: gives a boon', old_s=None, new_s='yes'),
            ch(op='add', label='Level 35: ability points', old_s=None, new_s='1')]
    html = change_rows(rows)
    assert html.count('class="erow') == 1 and 'Level 35 added' in html and '47000 souls' in html
    assert merge_renames([ch(op='remove', label='Pickup Radius', old_s='85', new_s=None),
                          ch(op='add', label='Pickup Radius › Base', old_s=None, new_s='85')]) == []


def test_engine_vocabulary_stays_off_the_pages_unless_the_notes_spoke():
    """2026-10-03 advisor: 452 'Behaviour' flag rows, pellet offsets, Walker's weak-point joints read as
    noise; a flag change a note line covers ("No longer interrupts sliding") stays."""
    from builders.cards import is_engine
    flags = {'cat': 'mechanic', 'label': 'Behaviour', 'status': 'hidden',
             'old_s': 'CITADEL_ABILITY_BEHAVIOR_A', 'new_s': 'CITADEL_ABILITY_BEHAVIOR_A | CITADEL_ABILITY_BEHAVIOR_B'}
    assert is_engine(flags) and not is_engine({**flags, 'status': 'described'})
    assert is_engine({'cat': 'mechanic', 'label': 'Projectile › Behaviour', 'old_s': 'PBF_StickToWorld', 'new_s': None})
    assert is_engine({'cat': 'mechanic', 'label': 'Scatter Offsets[3]', 'path': 'm_mapWeaponInfos.primary.m_vecScatterOffsets[3]',
                      'old_s': '2, 0', 'new_s': None})
    assert not is_engine({'cat': 'balance', 'label': 'Silence Duration', 'old_s': None, 'new_s': '0.3'})


def test_two_fields_under_one_label_get_told_apart():
    """Advisor round 3, 2026-10-03: 104 pairs like "Healing Reduction" (receive / regen penalty)."""
    from builders.cards import disambiguate
    rows = disambiguate([{'label': 'Healing Reduction', 'path': 'm_mapAbilityProperties.HealAmpReceivePenaltyPercent.m_strValue'},
                         {'label': 'Healing Reduction', 'path': 'm_mapAbilityProperties.HealAmpRegenPenaltyPercent.m_strValue'},
                         {'label': 'Cooldown', 'path': 'm_mapAbilityProperties.AbilityCooldown.m_strValue'}])
    assert [r['label'] for r in rows] == ['Healing Reduction · receive', 'Healing Reduction · regen', 'Cooldown']


def test_a_bare_namesake_gets_a_word_too():
    """Advisor round 4: Puddle Punch's T3 "Damage −50 → −40" beside "Damage · heavy melee 50 → 40" read as
    one stat; "Spirit Power · tech" said nothing (Tech is Spirit); a scale function's switch is plumbing."""
    from builders.cards import disambiguate, is_engine
    up = 'm_vecAbilityUpgrades[2].m_vecPropertyUpgrades{%s}.m_strBonus'
    rows = disambiguate([{'label': 'T3: Damage', 'path': up % 'Damage'},
                         {'label': 'T3: Damage', 'path': up % 'DamageHeavyMelee'}])
    assert [r['label'] for r in rows] == ['T3: Damage · base', 'T3: Damage · heavy melee']
    prop = 'm_mapAbilityProperties.%s.m_strValue'
    rows = disambiguate([{'label': 'Spirit Power', 'path': prop % 'TechPower'},
                         {'label': 'Spirit Power', 'path': prop % 'BonusSpirit'}])
    assert [r['label'] for r in rows] == ['Spirit Power · base', 'Spirit Power · bonus']
    rows = disambiguate([{'label': 'Spirit Power', 'path': prop % 'TechPower', 'op': 'change', 'new_s': '0'},
                         {'label': 'Spirit Power', 'path': prop % 'SpiritPower', 'op': 'add', 'new_s': '8'}])
    assert [r['label'] for r in rows] == ['Spirit Power · old field', 'Spirit Power · new field']
    spread = 'm_mapWeaponInfos.primary.m_ShootSpreadPenaltyPerShotNormalization.%s'
    rows = disambiguate([{'label': 'Spread Normalization', 'path': spread % 'm_SpreadPerShotFactor'},
                         {'label': 'Spread Normalization', 'path': spread % 'm_FireRatePctRange'}])
    assert [r['label'] for r in rows] == ['Spread Normalization · per shot factor', 'Spread Normalization · fire rate range']
    # the same row reads alike in a patch where its namesake did not move
    from builders.history_view import history_table
    p1 = {'id': 'p1', 'date': '2026-03-21', 'title': '03-21-2026 Update'}
    p2 = {'id': 'p2', 'date': '2025-07-04', 'title': '07-04-2025 Update'}
    key = 'abilities.vdata:viscous_telepunch'
    by_ent = {key: [(p1, [ch(key='a', label='T3: Damage', path=up % 'Damage'),
                          ch(key='b', label='T3: Damage', path=up % 'DamageHeavyMelee')]),
                    (p2, [ch(key='c', label='T3: Damage', path=up % 'Damage', old_s='-35', new_s='-30')])]}
    html = history_table([(key, 'Puddle Punch', None)], ['Viscous'], by_ent, {}, '../')
    bands = html.split('id="history"')[1]            # the strip's hover-card data repeats the labels
    assert bands.count('T3: Damage · base') == 2 and bands.count('T3: Damage · heavy melee') == 1
    switch = {'cat': 'mechanic', 'label': 'Cooldown · Function Disabled', 'status': 'hidden', 'old_s': 'no', 'new_s': 'yes',
              'path': 'm_mapAbilityProperties.AbilityCooldown.m_subclassScaleFunction.m_bFunctionDisabled'}
    assert is_engine(switch)
    assert not is_engine({**switch, 'path': 'm_mapAbilityProperties.AbilityCooldown.m_subclassScaleFunction.m_flStatScale'})


def test_a_namesake_hint_is_never_a_unit_word():
    """Review 2026-10-05: "Incoming Damage Deferred · pct", "… · value" — hints made of property words."""
    from builders.cards import _hint
    assert _hint('Incoming Damage Deferred', 'IncomingDamageDeferredPct', skip=frozenset()) == ''
    assert _hint('Healing Reduction', 'HealAmpRegenPenaltyPercent') == 'regen'          # the default skip list
