"""Data-quality track (audit 2026-10-04): who owns an ability, one label / unit / sign per field over its
history, enemy slows, units, id-like names and the tracker's upkeep commits. No tracker clone needed."""
from pipeline import labels, semantics, tracker
from pipeline.classify import ability_kind, hero_bound_abilities, shared_abilities, unit_bound_abilities
from pipeline.flatten import flatten


# ---- shared abilities ---------------------------------------------------------------------

def _hero(*bound, **extra):
    return {'m_mapBoundAbilities': {f'ESlot_{i}': ab for i, ab in enumerate(bound)}, **extra}


def test_an_ability_most_heroes_bind_has_no_owner():
    heroes = {
        'hero_base': _hero('citadel_ability_jump', 'citadel_weapon_inferno_set'),
        'hero_inferno': _hero('citadel_ability_jump', 'citadel_weapon_inferno_set', 'ability_melee_inferno'),
        'hero_gigawatt': _hero('citadel_ability_jump', 'citadel_weapon_gigawatt_set'),
        'hero_x': _hero('citadel_ability_jump', 'citadel_weapon_x_set'),
        # a hero in development borrows Infernus' gun as a stand-in: the gun stays his
        'hero_deadpack': _hero('citadel_weapon_inferno_set'),
    }
    assert shared_abilities(heroes) == {'citadel_ability_jump'}
    owners = hero_bound_abilities(heroes)
    assert 'citadel_ability_jump' not in owners
    assert owners['citadel_weapon_inferno_set'] == 'hero_inferno'
    assert owners['ability_melee_inferno'] == 'hero_inferno'
    shared = shared_abilities(heroes)
    assert ability_kind('citadel_ability_jump', {'_class': 'citadel_ability_jump'}, owners, shared) == 'shared'
    # a parry is a melee class, still every hero's
    assert ability_kind('citadel_ability_melee_parry', {'_class': 'citadel_ability_melee_parry'}, owners,
                        {'citadel_ability_melee_parry'}) == 'shared'
    # a zipline a container lends is not the unit's either
    units = {'npc_zipline_container': _hero('citadel_ability_jump')}
    assert unit_bound_abilities(units, owners, shared) == {}
    # an id naming a hero does not pull a shared ability back to him
    assert 'citadel_ability_jump' not in hero_bound_abilities(heroes, {'citadel_ability_jump': {}})


def test_a_tiny_roster_does_not_share_its_kit():
    heroes = {'hero_a': _hero('ability_a_one'), 'hero_b': _hero('ability_a_one')}
    assert shared_abilities(heroes) == set()          # 2 of 2 is "all", but too few to be a rule
    assert hero_bound_abilities(heroes)['ability_a_one'] == 'hero_a'


# ---- tracker upkeep commits -------------------------------------------------------------------

def _b(n, commit, files=('game/citadel/steam.inf',)):
    return tracker.Build(commit, '2026-10-04T00:00:00Z', n, tuple(files))


def test_head_build_skips_the_trackers_own_commits(monkeypatch):
    seq = (_b(6745, 'a' * 40), _b(None, 'b' * 40), _b(None, 'c' * 40))
    monkeypatch.setattr(tracker, 'builds', lambda: seq)
    assert tracker.head_build().build == 6745
    assert not tracker.is_game_build(seq[1])


def test_an_upkeep_commit_writes_no_record_and_moves_the_baseline(monkeypatch, tmp_path):
    from pipeline import history
    seq = (_b(5825, '1' * 40), _b(None, '2' * 40), _b(5826, '3' * 40))
    monkeypatch.setattr(history.tracker, 'builds', lambda: seq)
    monkeypatch.setattr(history, 'OUT', tmp_path)
    (tmp_path / f'None_{"2" * 8}.json.gz').write_bytes(b'')         # a stale record of the upkeep commit
    seen = []
    monkeypatch.setattr(history, 'remember', lambda lk, prev, cur, rec: seen.append(('remember', cur.build)))

    def fake_record(prev, cur, last_known=None):
        seen.append(('record', prev.build, cur.build))
        return {'v': history.FORMAT_VERSION, 'build': cur.build, 'commit': cur.commit, 'date': cur.date,
                'entities': [], 'loc': [{'key': 'x'}], 'convars': [], 'assets': None}
    monkeypatch.setattr(history, 'build_record', fake_record)
    history.run()
    assert seen == [('remember', None), ('record', 5825, 5826)]      # the build names the build before it
    assert sorted(p.name for p in tmp_path.iterdir()) == ['5826_33333333.json.gz', 'index.json']


# ---- flattening -------------------------------------------------------------------------------

def test_an_id_field_with_odd_capitals_still_keys_the_list():
    tier = {'m_vecAbilityUpgrades': [{}, {'m_vecPropertyUpgrades': [
        {'m_strPropertyName': 'BonusDamage', 'm_strBonus': '4m'},
        {'m_StrPropertyNAme': 'AbilityCooldown', 'm_strBonus': '-25'}]}]}       # Shadow Transformation, 2026-03-06
    flat = flatten(tier)
    assert flat['m_vecAbilityUpgrades[1].m_vecPropertyUpgrades{AbilityCooldown}.m_strBonus'] == -25
    assert not any('NAme' in p or 'm_vecPropertyUpgrades[' in p for p in flat)
    path = 'm_vecAbilityUpgrades[1].m_vecPropertyUpgrades{AbilityCooldown}.m_strBonus'
    assert semantics.direction(path, -25, -20, 'ability')[0] == 'nerf'          # a smaller cut off the cooldown


# ---- labels: source, sign, enemy wording -------------------------------------------------------

TOK = {'slowpercent_label': 'Move Speed', 'slowpercent_prefix': '-', 'slowpercent_postfix': '%',
       'firerateslow_label': 'Fire Rate', 'firerateslow_prefix': '-',
       'nanoshadowbulletarmorreductionheavy_label': 'Bullet Resist (Heavy)', 'nanoshadowbulletarmorreductionheavy_prefix': '-',
       'bonushealth_label': 'Bonus Health', 'bonushealth_prefix': '{s:sign}',
       'parrycooldownreduction_label': 'Parry Cooldown', 'parrycooldownreduction_prefix': '-'}


def test_describe_says_where_a_label_came_from_and_the_tooltips_sign():
    d = semantics.describe('m_mapAbilityProperties.SlowPercent.m_strValue', TOK, 'ability_x', 'ability')
    assert (d['label'], d['src'], d['sign'], d['unit']) == ('Move Speed', 'loc', '-', '%')
    d = semantics.describe('m_mapAbilityProperties.BonusHealth.m_strValue', TOK, 'upgrade_x', 'item')
    assert (d['src'], d['sign']) == ('loc', '')
    d = semantics.describe('m_mapAbilityProperties.RegenIncomingDamagePercent.m_strValue', {}, 'x', 'ability')
    # the field's own "Percent" is the value's unit (review 2026-10-05: "Non Hero Heal Pct — → 40")
    assert (d['label'], d['src'], d['sign'], d['unit']) == ('Regen Incoming Damage', 'fallback', None, '%')
    assert semantics.describe('m_mapWeaponInfos.primary.m_flBulletDamage', {})['src'] == 'curated'
    assert semantics.describe('m_projectileInfo.m_flHoverHeight', {})['src'] == 'fallback'
    # a tier's scaling bonus carries no sign: it is a coefficient
    t = semantics.describe('m_vecAbilityUpgrades[0].m_vecPropertyUpgrades{SlowPercent|EAddToScale}.m_strBonus', TOK)
    assert t['sign'] is None


def test_an_enemy_slow_reads_as_a_slow():
    assert semantics.enemy_label('Move Speed', 'SlowPercent') == 'Movement Slow'
    assert semantics.enemy_label('T1: Fire Rate', 'FireRateSlow') == 'T1: Fire Rate Slow'
    assert semantics.enemy_label('Max Move Speed', 'MaxSlowPercent') == 'Max Movement Slow'
    assert semantics.enemy_label('Bullet Resist (Heavy)', 'NanoShadowBulletArmorReductionHeavy') == \
        'Bullet Resist reduction (Heavy)'
    assert semantics.enemy_label('Parry Cooldown', 'ParryCooldownReduction') == 'Parry Cooldown reduction'
    # already said, said once (records may carry the wording already)
    assert semantics.enemy_label('Movement Slow', 'SlowPercent') == 'Movement Slow'
    # the size, not "-30%" under a slow's name: a stored −30 (another build) reads 30 too
    assert semantics.show(30, False, '%', magnitude=True) == '30%'
    assert semantics.show('-30', False, '%', magnitude=True) == '30%'
    assert semantics.show(-30, False, '%') == '-30%'
    # the tag still comes from the holder's side: a smaller slow is a nerf
    assert semantics.direction('m_mapAbilityProperties.SlowPercent.m_strValue', 30, 24, 'ability')[0] == 'nerf'


def test_one_label_unit_and_sign_per_field_over_its_history():
    path = 'm_mapAbilityProperties.RegenIncomingDamagePercent.m_strValue'
    recs = [
        {'entities': [{'file': 'abilities.vdata', 'id': 'beefy', 'kind': 'ability', 'changes': [
            {'path': path, 'label': 'Regen Incoming Damage Percent', 'label_src': 'fallback'}]}]},
        {'entities': [{'file': 'abilities.vdata', 'id': 'beefy', 'kind': 'ability', 'changes': [
            {'path': path, 'label': 'Damage regenerated', 'unit': '%'}]}]},
        {'entities': [{'file': 'abilities.vdata', 'id': 'beefy', 'kind': 'ability', 'changes': [
            {'path': path, 'label': 'Regen Incoming Damage Percent', 'label_src': 'fallback'}]}]},
    ]
    # the newest text no longer labels it: the last label Valve gave it, its newest unit
    fm = labels.build(recs, {})
    assert fm[f'abilities.vdata:beefy:{path}'] == {'label': 'Damage regenerated', 'unit': '%', 'sign': '', 'src': 'loc'}
    # the newest text labels it: that label wins
    fm = labels.build(recs, {'regenincomingdamagepercent_label': 'Damage Regenerated'})
    assert fm[f'abilities.vdata:beefy:{path}']['label'] == 'Damage Regenerated'
    # a slow whose newest tooltip prints the minus: one enemy wording for every row (old loc "Movement Slow",
    # new "Move Speed")
    slow = 'm_mapAbilityProperties.SlowPercent.m_strValue'
    recs = [{'entities': [{'file': 'abilities.vdata', 'id': 'colossus', 'kind': 'item', 'changes': [
        {'path': slow, 'label': 'Movement Slow', 'unit': '%'}]}]}]
    assert labels.build(recs, TOK)[f'abilities.vdata:colossus:{slow}'] == \
        {'label': 'Movement Slow', 'unit': '%', 'sign': '-', 'src': 'loc'}
    # a '@shared' rule's change counts for each of its targets
    recs = [{'entities': [{'file': 'heroes.vdata', 'id': '@shared', 'kind': 'shared', 'changes': [
        {'path': 'm_mapStartingStats.EMaxHealth', 'label': 'Max Health', 'targets': ['hero_a', 'hero_b']}]}]}]
    assert 'heroes.vdata:hero_b:m_mapStartingStats.EMaxHealth' in labels.collect(recs)


def test_old_bare_numbers_take_the_fields_unit():
    cn = {'label': 'Slash Radius', 'unit': 'm', 'sign': '', 'src': 'loc'}
    assert labels.display_unit({'unit': '', 'meters': False}, cn) == 'm'     # 2024's "50 → 45" is 50m
    assert labels.display_unit({'unit': 'm', 'speed_m': True}, cn) == 'm/s'  # a speed's "m" is m/s
    assert semantics.show(50, False, 'm') == '50m'


def test_window_changes_show_the_canonical_label_and_keep_their_own_for_matching():
    from pipeline.match import MChange, change_json, mark_retyped
    c = MChange('abilities.vdata', 'x', 'm_mapAbilityProperties.SlowPercent.m_strValue', 'change', 30, 24, 'balance',
                'ability', None, 'Move Speed', False, [1], shown='Movement Slow', unit='%', sign='-')
    j = change_json(c)
    assert (j['label'], j['old_s'], j['new_s'], j['dir']) == ('Movement Slow', '30%', '24%', 'nerf')
    assert c.label == 'Move Speed'
    # Card Trick 2026-08-12: stored −30 then 30 when the tooltip gained its "-": one value, nothing to show
    flip = MChange('abilities.vdata', 'x', 'm_mapAbilityProperties.ClubSlowPercent.m_strValue', 'change', -30, 30,
                   'balance', 'ability', None, 'Move Speed', False, [1], shown='Movement Slow', unit='%', sign='-')
    j = change_json(flip)
    assert j['old_s'] == j['new_s'] == '30%'
    # Riposte 2026-03-06: the provided type flipped with the sign — the same resist written the other way
    rip = MChange('abilities.vdata', 'r', 'm_mapAbilityProperties.MeleeResist.m_strValue', 'change', -22, 22,
                  'balance', 'ability', None, 'Melee Resist', False, [1], unit='%')
    typ = MChange('abilities.vdata', 'r', 'm_mapAbilityProperties.MeleeResist.m_eProvidedPropertyType', 'change',
                  'MODIFIER_VALUE_REDUCTION_PERCENT', 'MODIFIER_VALUE_INCREASE_PERCENT', 'mechanic', 'ability', None,
                  'Melee Resist · Provided Property Type', False, [1])
    lone = MChange('abilities.vdata', 'g', 'm_mapAbilityProperties.MeleeResist.m_strValue', 'change', 5, -5,
                   'balance', 'ability', None, 'Melee Resist', False, [1], unit='%')
    mark_retyped([rip, typ, lone])
    assert change_json(rip)['same'] and not change_json(lone)['same']


# ---- units ----------------------------------------------------------------------------------

def test_units_on_lengths_speeds_and_the_minus_one():
    # "-1" is the game's "no limit / default", never −0.0254 m
    assert semantics.display_value(-1, True) == '-1'
    assert semantics.display_value(-1, semantics.SPEED) == '-1'
    # a field already in m/s is not divided again; recoil and blends are not lengths
    assert semantics.engine_unit('m_flBonusMoveSpeedMeterPerSecond') == semantics.MPS
    assert semantics.engine_unit('m_flRecoilSpeed') is False
    assert semantics.engine_unit('m_flHoverSpeedDecay') is False
    assert semantics.engine_unit('m_flInitialOffsetLerpBias') is False
    # a field ending in a length word is a length ("Nearby Enemy Resist Range 2000" = 50.8 m)
    assert semantics.engine_unit('m_flNearbyEnemyResistRange') is True
    assert semantics.engine_unit('m_flRangeScale') is False
    # an ability property named like a length that no build gave a unit: engine units when big
    p = 'm_mapAbilityProperties.LiftHeight.m_strValue'
    assert semantics.length_in_units(p, '', ('120', '200'))
    assert semantics.show('200', True) == '5.08m'
    assert not semantics.length_in_units(p, 'm', ('120', '200'))        # Valve says metres
    assert not semantics.length_in_units(p, '', ('8', '10'))            # small: more likely metres
    assert not semantics.length_in_units('m_mapAbilityProperties.RadiusScale.m_strValue', '', ('50', '60'))
    # a speed property's "m" is m/s wherever "speed" sits in its name
    d = semantics.describe('m_mapAbilityProperties.ActiveMovespeedPenalty.m_strValue', {}, 'x', 'item')
    assert d['speed_m'] and semantics.show('4.5m', semantics.M_SPEED) == '4.5m/s'
    # a label does not repeat the unit its value carries; Valve's "Verticall" typo
    assert semantics.describe('m_mapAttacks.m_flDashJumpDistanceInMeters', {})['label'].endswith('Distance')
    assert semantics.humanize('m_flVerticallRecoil') == 'Vertical Recoil'


def test_a_map_key_that_is_an_item_reads_as_its_name():
    tok = {'upgrade_deflecting_armor': 'Return Fire'}
    assert semantics.context_label('m_mapItemDraftWeights.upgrade_deflecting_armor', tok=tok) == \
        'Item Draft Weights › Return Fire'
    assert semantics.context_label('m_mapThings{upgrade_deflecting_armor}.m_flSize', tok=tok) == \
        'Things Return Fire › Size'
    assert semantics._key_text('upgrade_deflecting_armor') == 'deflecting armor'          # no text: words


def test_weapon_upgrades_are_tiers():
    d = semantics.describe('m_vecAbilityUpgrades[1].m_vecPropertyUpgrades{BonusDamage}.m_strBonus', {}, 'w', 'weapon')
    assert d['label'].startswith('T2: ')          # Venator's ultimate is filed as a weapon by its class


# ---- names ------------------------------------------------------------------------------------

def test_npc_abilities_named_like_their_unit_keep_their_id():
    from pipeline.catalog import drop_unit_names
    ents = [{'file': 'npc_units.vdata', 'id': 'npc_boss_tier3', 'name': 'Patron'},
            {'file': 'abilities.vdata', 'id': 'citadel_ability_tier3boss_aoe_wave', 'name': 'Patron',
             'units': ['npc_boss_tier3']},
            # Forge's turret ability shares the turret's name, and no unit binds it: it keeps it
            {'file': 'abilities.vdata', 'id': 'citadel_ability_shieldedsentry', 'name': 'Mini Turret'},
            {'file': 'npc_units.vdata', 'id': 'npc_shielded_sentry', 'name': 'Mini Turret'}]
    drop_unit_names(ents)
    assert ents[1]['name'] == 'citadel_ability_tier3boss_aoe_wave' and ents[2]['name'] == 'Mini Turret'


def test_stand_in_names_say_what_tells_them_apart():
    from builders.common import pretty_id
    assert pretty_id('thumper_ability_1', 'hero_thumper') == 'Ability 1'
    assert pretty_id('citadel_weapon_astro_set_shotgun', 'hero_astro') == 'Weapon (shotgun)'
    assert pretty_id('citadel_weapon_astro_hand_cannon', 'hero_astro') == 'Weapon (hand cannon)'
    assert pretty_id('citadel_weapon_frank_set', 'hero_frank') == 'Weapon'
    assert pretty_id('citadel_weapon_frank_set2', 'hero_frank') == 'Alt weapon'
    assert pretty_id('citadel_ability_tier3boss_aoe_wave') == 'AoE wave'
    # review 2026-10-05: an item's, ability's or unit's stand-in is Title Case like the game's names
    from builders.common import display_name
    assert display_name({'file': 'abilities.vdata', 'id': 'ability_charged_bomb', 'name': 'ability_charged_bomb'}) \
        == 'Charged Bomb'
    assert display_name({'file': 'abilities.vdata', 'id': 'citadel_ability_tier2boss_aoe_wave'}) == 'AoE Wave'
    assert display_name({'file': 'misc.vdata', 'id': 'citadel_breakable_prop_box'}) == 'Breakable prop box'


def test_a_name_the_last_build_lost_comes_from_an_earlier_one(monkeypatch):
    """Review 2026-10-05: 57 removed items read "Ablative coat", "Aoe silence" (EMP Grenade): their text key left
    the files before they did. The newest earlier name, without "[Deprecated]"; "Bullet Resilience Disabled" is a
    mark, not a name; "DEPRICATED" none; a name a live item has gets "(old)"."""
    from types import SimpleNamespace
    from pipeline import catalog, loc, tracker
    builds = [SimpleNamespace(commit=c) for c in ('c1', 'c2', 'c3')]
    toks = {'c1': {'upgrade_aoe_silence': 'EMP Grenade', 'upgrade_bullet_armor_2': 'Improved Bullet Armor',
                   'upgrade_toughness_3': 'Toughness'},
            'c2': {'upgrade_aoe_silence': 'EMP Grenade', 'upgrade_bullet_armor_2': 'Bullet Resilience Disabled',
                   'upgrade_duration_extender': '[Deprecated] Duration Extender', 'upgrade_frenzy': 'DEPRICATED',
                   'upgrade_toughness_3': 'Toughness'},
            'c3': {}}
    monkeypatch.setattr(tracker, 'builds', lambda: builds)
    monkeypatch.setattr(loc, 'english_files', lambda rev: {'x': rev})
    monkeypatch.setattr(loc, 'tokens', lambda rev: toks[rev])
    ents = [{'file': 'abilities.vdata', 'id': i, 'name': i, 'alive': False} for i in
            ('upgrade_aoe_silence', 'upgrade_bullet_armor_2', 'upgrade_duration_extender', 'upgrade_frenzy',
             'upgrade_toughness_3')]
    live = {'file': 'abilities.vdata', 'id': 'upgrade_toughness', 'name': 'Toughness', 'alive': True}
    catalog.earlier_names(ents, ents + [live])
    names = {e['id']: e['name'] for e in ents}
    assert names == {'upgrade_aoe_silence': 'EMP Grenade', 'upgrade_bullet_armor_2': 'Improved Bullet Armor',
                     'upgrade_duration_extender': 'Duration Extender', 'upgrade_frenzy': 'upgrade_frenzy',
                     'upgrade_toughness_3': 'Toughness (old)'}


# ---- ability cards ------------------------------------------------------------------------

def test_cards_name_properties_like_the_history_and_list_them_once():
    from pipeline.abilities import card
    a = {'m_mapAbilityProperties': {'SlowPercent': {'m_strValue': '30'}, 'AbilityCastRange': {'m_strValue': '20m'}},
         'm_vecTooltipSectionInfo': [{'m_eAbilitySectionType': 'EArea_Active', 'm_vecSectionAttributes': [
             {'m_vecElevatedAbilityProperties': ['AbilityCastRange'],
              'm_vecAbilityProperties': ['SlowPercent', 'AbilityCastRange']}]}],
         'm_vecAbilityUpgrades': [{'m_vecPropertyUpgrades': [{'m_strPropertyName': 'SlowPercent', 'm_strBonus': '10'}]}]}
    c = card('upgrade_x', a, TOK, 'item', None)
    props = [(p['label'], p['value']) for p in c['sections'][0]['props']]
    assert props == [('Cast Range', '20m'), ('Movement Slow', '30%')] or props[1] == ('Movement Slow', '30%')
    assert [p['prop'] for p in c['sections'][0]['props']].count('AbilityCastRange') == 1
    # the canonical map wins over the newest text alone (the history row and the card agree)
    path = 'm_mapAbilityProperties.SlowPercent.m_strValue'
    fm = {f'abilities.vdata:upgrade_x:{path}': {'label': 'Movement Slow', 'unit': '%', 'sign': '-', 'src': 'loc'}}
    c = card('upgrade_x', a, {}, 'item', None, fm)
    assert ('Movement Slow', '30') in [(p['label'], p['value']) for p in c['sections'][0]['props']]
    c = card('ability_x', a, TOK, 'ability', 'hero_x')
    assert c['tiers'][0]['bonuses'] == [{'label': 'Movement Slow', 'value': '+10%'}]


# ---- builders ---------------------------------------------------------------------------------

def test_a_real_minus_one_is_not_no_limit():
    from builders.render import _sentinel, vals_html
    bonus = {'path': 'm_vecAbilityUpgrades[2].m_vecPropertyUpgrades{AbilityCooldown}.m_strBonus'}
    assert _sentinel('-1s', bonus, '-0.75s') == '-1s'                  # Djinn's Mark T3: a second off
    assert _sentinel('-1m/s', {'path': 'x'}, '-0.5m/s') == '-1m/s'      # Sharpshooter's penalty scale
    assert _sentinel('-1', {'path': 'm_mapAbilityProperties.ChannelMoveSpeed.m_strValue'}, '50') == 'no limit'
    html = vals_html({'op': 'change', 'cat': 'balance', 'old_s': '-0.75s', 'new_s': '-1s', 'dir': 'buff', 'pct': 33.3,
                      'path': bonus['path']})
    assert '>-1s<' in html and 'no limit' not in html


def test_a_sign_flip_is_a_change_unless_the_pipeline_says_same():
    from builders.cards import is_noop
    assert not is_noop({'op': 'change', 'old_s': '-22%', 'new_s': '22%'})
    assert not is_noop({'op': 'change', 'old_s': '−22%', 'new_s': '22%'})
    assert is_noop({'op': 'change', 'old_s': '-22%', 'new_s': '22%', 'same': True})
    assert is_noop({'op': 'change', 'old_s': 'Head Ignore Obscure Blockers', 'new_s': 'Head_IgnoreObscureBlockers'})


def test_a_replaced_bonus_with_another_unit_is_not_a_rename():
    from builders.cards import merge_renames
    p = 'm_vecAbilityUpgrades[0].m_vecPropertyUpgrades{%s}.m_strBonus'
    rows = [{'op': 'remove', 'label': 'T1: Weapon Damage', 'path': p % 'BaseAttackDamagePercent', 'old_s': '25%',
             'status': 'documented'},
            {'op': 'add', 'label': 'T1: Weapon Damage', 'path': p % 'WeaponDamageBonus', 'new_s': '2.2',
             'status': 'described'}]
    assert [c['op'] for c in merge_renames(rows)] == ['remove', 'add']        # not "25% → 2.2 −91%"
    renamed = [{'op': 'remove', 'label': 'DPS', 'path': p % 'DPS', 'old_s': '40'},
               {'op': 'add', 'label': 'DPS', 'path': p % 'DamagePerSecond', 'new_s': '40'}]
    assert merge_renames(renamed) == []                                       # a re-key with the same value
