"""Data review of the updates 2026-10-06…10-16 (builds 6757-6790) against Valve's notes.

A hero's release build is a window of its own (Deadman Danny's release and the 10-14 balance build had merged:
"Max Health 780 → 730" for the notes' 680 → 730, nine of his lines unmatched); its kit is the release itself, not
"not in patch notes"; pre-release heroes are work before release; a line naming an ability never falls back to the
hero's base stats; Street Brawl values, a light melee's launch and an exponent read right; new heroes' parts carry
the game's names."""
from pipeline.match import (MChange, annotate, annotate_line, change_json, mark_availability_moves, parse_pairs,
                            release_kit, release_pass)
from pipeline.news import TITLE_ONLY, Notes, Section
from pipeline.patches import Patch, group


def _notes(date: str, title: str = 'Minor Update') -> Notes:
    return Notes(f'{title} - {date}', date, 'n', 'steam',
                 [Section('General', [f'Hero{i}: Damage increased from {i} to {i + 1}' for i in range(5)])])


def _b(n: int, date: str, fields: int = 5, released=None) -> dict:
    row = {'build': n, 'date': date, 'file': f'{n}.json.gz', 'commit': f'c{n}', 'fields': {'balance': fields}}
    if released:
        row['released'] = released
    return row


# ---- 1 / 3. a hero's release is a window of its own ----------------------------------------------------------------

def test_a_release_build_beside_a_changelog_is_its_own_window_and_the_balance_build_goes_back():
    """Danny: released in 6779 (10-13 21:02, two minutes into the 10-14 notes' window), the notes' balance build 6785
    on 10-15. The release is "Fairfax Industries Employee Spotlight", 10-14 holds 6782 and 6785 only."""
    post = Notes('Fairfax Industries Employee Spotlight', '2026-10-13', 'u', TITLE_ONLY, [])
    builds = [_b(6779, '2026-10-13T21:02:10Z', 409, ['hero_deadpack']), _b(6782, '2026-10-14T17:45:06Z', 0),
              _b(6785, '2026-10-15T03:14:32Z', 34)]
    ps = group([_notes('2026-10-14'), post], builds)
    assert [p.id for p in ps] == ['build-6779', '2026-10-14']        # in the order their builds shipped
    rel, notes = ps
    assert rel.title == 'Fairfax Industries Employee Spotlight' and rel.release == ['hero_deadpack']
    assert rel.link == 'u' and rel.notes is None
    assert [b['build'] for b in rel.builds] == [6779]
    assert [b['build'] for b in notes.builds] == [6782, 6785]


def test_a_release_takes_its_days_hotfixes_and_the_notes_window_resumes_after():
    """Baba's 6757 (10-06 21:03) and its hotfix 6759 three hours later are the release; 6762 the next day is back in
    the 10-05 window, as 6753 before it."""
    post = Notes('Mind the Birds!', '2026-10-06', 'u', TITLE_ONLY, [])
    builds = [_b(6753, '2026-10-05T23:03:53Z', 41), _b(6757, '2026-10-06T21:03:12Z', 370, ['hero_baba']),
              _b(6759, '2026-10-07T00:03:03Z', 2), _b(6762, '2026-10-07T22:26:39Z', 1)]
    ps = group([_notes('2026-10-05'), post], builds)
    by_id = {p.id: [b['build'] for b in p.builds] for p in ps}
    assert by_id == {'2026-10-05': [6753, 6762], 'build-6757': [6757, 6759]}


def test_two_releases_hours_apart_keep_their_builds_and_a_balance_build_is_no_hotfix():
    """A second hero released inside the first one's 6 h is its own window; a build of many fields an hour after a
    release is the notes window's balance build, not a release-day hotfix."""
    post = Notes('Two heroes', '2026-10-06', 'u', TITLE_ONLY, [])
    builds = [_b(1, '2026-10-05T23:00:00Z', 41), _b(2, '2026-10-06T21:00:00Z', 300, ['hero_a']),
              _b(3, '2026-10-06T22:00:00Z', 300, ['hero_b']), _b(4, '2026-10-06T23:00:00Z', 1),
              _b(5, '2026-10-07T00:00:00Z', 40)]
    by_id = {p.id: [b['build'] for b in p.builds] for p in group([_notes('2026-10-05'), post], builds)}
    assert by_id == {'2026-10-05': [1, 5], 'build-2': [2], 'build-3': [3, 4]}


def test_a_window_a_release_interrupts_knows_the_builds_in_its_gap():
    from pipeline.patches import gap_builds
    rows = [_b(1, '2026-10-05T23:00:00Z'), _b(2, '2026-10-06T21:00:00Z'), _b(3, '2026-10-07T22:00:00Z')]
    assert gap_builds(Patch('x', 'x', '2026-10-05', None, [rows[0], rows[2]]), rows) == [rows[1]]
    assert gap_builds(Patch('x', 'x', '2026-10-05', None, rows), rows) == []


def test_a_release_with_its_own_days_changelog_stays_in_it():
    """01-17-2025: four heroes released the day of a changelog that announces them — the notes are the release's."""
    post = Notes('Holliday, Vyper, Calico', '2025-01-17', 'u', TITLE_ONLY, [])
    builds = [_b(5458, '2025-01-17T18:43:00Z', 900, ['hero_astro'])]
    assert [p.id for p in group([_notes('2025-01-17'), post], builds)] == ['2025-01-17']


def test_a_release_without_an_announcement_is_no_window():
    builds = [_b(1, '2026-10-05T20:00:00Z'), _b(2, '2026-10-06T20:00:00Z', 50, ['hero_x'])]
    assert [p.id for p in group([_notes('2026-10-05')], builds)] == ['2026-10-05']


def test_a_build_record_says_which_heroes_it_releases():
    from pipeline.history import released_heroes, summary
    rec = {'build': 1, 'commit': 'c', 'date': 'd', 'loc': [], 'convars': [], 'assets': None, 'entities': [
        {'file': 'heroes.vdata', 'id': 'hero_artist', 'status': 'changed', 'changes': [
            {'path': 'm_eHeroDevelopmentState', 'old': 'EHeroDevState_PreRelease', 'new': 'EHeroDevState_Release',
             'cat': 'availability'}]},
        {'file': 'heroes.vdata', 'id': 'hero_nurse', 'status': 'changed', 'changes': [
            {'path': 'm_eHeroDevelopmentState', 'old': 'EHeroDevState_InDevelopment', 'new': 'EHeroDevState_PreRelease',
             'cat': 'availability'}]}]}
    assert released_heroes(rec) == ['hero_artist']
    assert summary(rec, 'f')['released'] == ['hero_artist']


def _mc(file, eid, path, old, new, label, op='change', cat='balance', kind='ability', owner=None, **kw) -> MChange:
    return MChange(file, eid, path, op, old, new, cat, kind, owner, label, False, **kw)


def test_a_release_windows_kit_is_announced_and_the_rest_unannounced():
    """Violet's release (6790): her state turning Release is documented by the post, her kit, summons and sketch pickups
    are described; another hero's tuning and a shared edit in the same build stay unannounced (the eye)."""
    cat = {'heroes.vdata:hero_artist': {'file': 'heroes.vdata', 'id': 'hero_artist'},
           'abilities.vdata:ability_artist_tether': {'file': 'abilities.vdata', 'id': 'ability_artist_tether',
                                                     'owner': 'hero_artist'},
           'npc_units.vdata:citadel_artist_strokeblocker': {'file': 'npc_units.vdata', 'id': 'citadel_artist_strokeblocker'},
           'misc.vdata:pickup_artist_drawing_mystic': {'file': 'misc.vdata', 'id': 'pickup_artist_drawing_mystic'},
           'misc.vdata:partist_thing': {'file': 'misc.vdata', 'id': 'partist_thing'},
           'abilities.vdata:upgrade_medic_bullets': {'file': 'abilities.vdata', 'id': 'upgrade_medic_bullets'}}
    kit = release_kit('hero_artist', cat)
    assert 'misc.vdata:pickup_artist_drawing_mystic' in kit and 'npc_units.vdata:citadel_artist_strokeblocker' in kit
    assert 'misc.vdata:partist_thing' not in kit
    # a unit an ability makes bears its name (Solomon's bishop piece is "Setup Bishop")
    chess = {'abilities.vdata:ability_chessmaster_throwbishop': {'file': 'abilities.vdata', 'name': 'Setup Bishop',
                                                                 'id': 'ability_chessmaster_throwbishop',
                                                                 'owner': 'hero_chessmaster'},
             'npc_units.vdata:citadel_chesspiece_bishop': {'file': 'npc_units.vdata', 'id': 'citadel_chesspiece_bishop',
                                                           'name': 'Setup Bishop'},
             'npc_units.vdata:trooper_normal': {'file': 'npc_units.vdata', 'id': 'trooper_normal', 'name': 'Trooper'}}
    assert release_kit('hero_chessmaster', chess) == {'heroes.vdata:hero_chessmaster',
                                                      'abilities.vdata:ability_chessmaster_throwbishop',
                                                      'npc_units.vdata:citadel_chesspiece_bishop'}
    state = _mc('heroes.vdata', 'hero_artist', 'm_eHeroDevelopmentState', 'EHeroDevState_PreRelease',
                'EHeroDevState_Release', 'State', cat='availability', kind='hero')
    hp = _mc('heroes.vdata', 'hero_artist', 'm_mapStartingStats.EMaxHealth', 780, 710, 'Max Health', kind='hero')
    every = _mc('heroes.vdata', 'hero_artist', 'm_flX', 1, 2, 'X', kind='hero', shared=True)
    item = _mc('abilities.vdata', 'upgrade_medic_bullets', 'm_nAbilityTargetTypes', 'A', 'A | B', 'Can target',
               cat='mechanic', kind='item')
    changes = [state, hp, every, item]
    for c in changes:
        c.status = 'unannounced'
    events = [{'file': 'abilities.vdata', 'id': 'ability_artist_tether', 'change': {'status': 'unannounced'}},
              {'file': 'misc.vdata', 'id': 'pickup_artist_drawing_mystic', 'change': {'status': 'unannounced'}}]
    release_pass(['hero_artist'], changes, events, cat)
    assert (state.status, hp.status, every.status, item.status) == ('documented', 'described', 'unannounced',
                                                                    'unannounced')
    assert [e['change']['status'] for e in events] == ['described', 'described']


# ---- 4. pre-release is before release ------------------------------------------------------------------------------

def test_a_pre_release_hero_is_not_released(monkeypatch):
    from pipeline import match
    heroes = {'hero_nurse': {'m_eHeroDevelopmentState': 'EHeroDevState_PreRelease'},
              'hero_artist': {'m_eHeroDevelopmentState': 'EHeroDevState_Release'},
              'hero_old': {'m_bInDevelopment': 'true'}}
    monkeypatch.setattr(match.cache, 'vdata', lambda commit, path: heroes)
    assert match.unreleased_heroes('c') == {'hero_nurse', 'hero_old'}


def test_unreleased_is_judged_in_a_window_without_notes_too(monkeypatch):
    """Nurse Harrow's boon tuning in Violet's release build had the eye while she was pre-release."""
    from pipeline import match
    monkeypatch.setattr(match, 'unreleased_heroes', lambda commit: {'hero_nurse'})
    boon = _mc('heroes.vdata', 'hero_nurse', 'm_mapStandardLevelUpUpgrades.X', 0.53, 0.43, 'Bullet damage per boon',
               kind='hero', builds=[6790])
    other = _mc('heroes.vdata', 'hero_baba', 'm_flX', 1, 2, 'X', kind='hero', builds=[6790])
    boon.status = other.status = 'unannounced'
    p = Patch('build-6790', 'Paint the Town', '2026-10-16T21:01:56Z', None, [{'build': 6790, 'commit': 'c'}])
    match.mark_unreleased(p, 'c', [boon, other], [], {})
    assert boon.status == 'unreleased' and other.status == 'unannounced'


def test_the_in_development_flag_that_comes_with_a_release_is_part_of_it():
    """Baba and Violet read "OFF In Development no → yes" beside "ON Release" on their release day."""
    state = _mc('heroes.vdata', 'hero_baba', 'm_eHeroDevelopmentState', 'EHeroDevState_PreRelease',
                'EHeroDevState_Release', 'State', cat='availability', kind='hero')
    flag = _mc('heroes.vdata', 'hero_baba', 'm_bInDevelopment', False, True, 'In Development', cat='availability',
               kind='hero')
    lone = _mc('heroes.vdata', 'hero_x', 'm_bInDevelopment', False, True, 'In Development', cat='availability',
               kind='hero')
    mark_availability_moves([state, flag, lone])
    assert flag.moved and change_json(flag)['same'] and not state.moved and not lone.moved


# ---- 2. a named ability never falls back to the hero's base stats ---------------------------------------------------

_DANNY_TOK = {'hero_deadpack': 'Deadman Danny', 'ability_deadpack_chargeblast': 'Strix Salvo'}
_DANNY_CAT = {'heroes.vdata:hero_deadpack': {'file': 'heroes.vdata', 'id': 'hero_deadpack', 'kind': 'hero',
                                             'name': 'Deadman Danny'},
              'abilities.vdata:ability_deadpack_chargeblast': {'file': 'abilities.vdata',
                                                               'id': 'ability_deadpack_chargeblast', 'kind': 'ability',
                                                               'owner': 'hero_deadpack', 'name': 'Strix Salvo'}}


def _danny(changes, text):
    by_ent = {}
    for c in changes:
        by_ent.setdefault(f'{c.file}:{c.eid}', []).append(c)
    idx = {'deadman danny': ['heroes.vdata:hero_deadpack'], 'strix salvo': ['abilities.vdata:ability_deadpack_chargeblast']}
    return annotate_line(text, changes, by_ent, idx, _DANNY_CAT, _DANNY_TOK)


def test_a_line_naming_an_ability_does_not_take_the_heros_stamina():
    stamina = _mc('heroes.vdata', 'hero_deadpack', 'm_mapStartingStats.EStaminaRegenPerSecond', 0.2222, 0.2,
                  'Stamina Cooldown', kind='hero', invert=True)
    res = _danny([stamina], 'Deadman Danny: Strix Salvo - Cooldown from 30s to 25s')
    assert res['status'] == 'unmatched' and stamina.status == 'hidden'


def test_numbers_that_disagree_never_describe_a_field():
    """"Air Dash Duration 0.47s → 0.43s" is no "Slow effectiveness … reduced by 15%"; a hero line with a pair takes no
    field that moved the other way."""
    dash = _mc('heroes.vdata', 'hero_deadpack', 'm_mapStartingStats.EGroundDashDuration', 0.47, 0.43,
               'Ground Dash Duration', kind='hero')
    res = _danny([dash], 'Deadman Danny: Ground dash duration from 0.8s to 0.9s')
    assert res['status'] == 'unmatched' and dash.status == 'hidden'
    same_way = _mc('heroes.vdata', 'hero_deadpack', 'm_mapStartingStats.EGroundDashDuration', 0.47, 0.43,
                   'Ground Dash Duration', kind='hero')
    res = _danny([same_way], 'Deadman Danny: Ground dash duration from 0.9s to 0.8s')
    assert res['status'] == 'described' and same_way.status == 'described'


def test_a_reduction_the_notes_give_for_a_multiplier_agrees_with_it():
    """"Seven: Headshot reduction increased from 25% to 35%" is Headshot Damage Taken × 0.75 → 0.65: the numbers
    agree, the line keeps describing the field."""
    from pipeline.match import _same_way
    taken = _mc('heroes.vdata', 'hero_gigawatt', 'm_mapStartingStats.ECritDamageReceivedScale', 0.75, 0.65,
                'Headshot Damage Taken ×', kind='hero')
    assert _same_way(taken, [(25.0, 35.0)])
    assert not _same_way(taken, [(25.0, 50.0)])


def test_a_tier_bonus_without_from_is_a_pair():
    """Rat King "T1 +1m/s Move Speed to +2m/s Move Speed" matched exactly but read only "described"."""
    assert parse_pairs('T1 +1m/s Move Speed to +2m/s Move Speed') == [(1.0, 2.0)]
    assert parse_pairs('T1 now grants +10 Damage to allies') == []


def test_moved_to_a_tier_describes_that_tiers_bonus():
    """"Baba's Brew - Cooldown increased from 25s to 27s (moved to T2)": T2's -12s → -14s is that move."""
    tok = {'hero_baba': 'Baba', 'ability_baba_hexing_brew': "Baba's Brew"}
    cat = {'heroes.vdata:hero_baba': {'file': 'heroes.vdata', 'id': 'hero_baba', 'kind': 'hero'},
           'abilities.vdata:ability_baba_hexing_brew': {'file': 'abilities.vdata', 'id': 'ability_baba_hexing_brew',
                                                        'kind': 'ability', 'owner': 'hero_baba'}}
    base = _mc('abilities.vdata', 'ability_baba_hexing_brew', 'm_mapAbilityProperties.AbilityCooldown.m_strValue', 25,
               27, 'Cooldown', owner='hero_baba')
    t2 = _mc('abilities.vdata', 'ability_baba_hexing_brew',
             'm_vecAbilityUpgrades[1].m_vecPropertyUpgrades{AbilityCooldown}.m_strBonus', -12, -14, 'T2: Cooldown',
             owner='hero_baba')
    other = _mc('abilities.vdata', 'ability_baba_hexing_brew',
                'm_vecAbilityUpgrades[1].m_vecPropertyUpgrades{Radius}.m_strBonus', 1, 2, 'T2: Radius', owner='hero_baba')
    by_ent = {'abilities.vdata:ability_baba_hexing_brew': [base, t2, other]}
    idx = {'baba': ['heroes.vdata:hero_baba'], "baba's brew": ['abilities.vdata:ability_baba_hexing_brew']}
    res = annotate_line("Baba: Baba's Brew - Cooldown increased from 25s to 27s (moved to T2)", [base, t2, other],
                        by_ent, idx, cat, tok)
    assert res['status'] == 'documented' and base.status == 'documented'
    assert t2.status == 'described' and other.status == 'hidden'


def test_a_named_abilitys_fields_answer_a_word_with_another_ending():
    """"Scrap Grenade - Fixed some bugs with bouncing targeting": its Bounce Target Distance Check and Bounce Max
    Horizontal Speed kept the eye ("bouncing" is "bounce"); the hero's other abilities stay out."""
    tok = {'hero_ratking': 'Rat King', 'ability_ratking_scrap_grenade': 'Scrap Grenade', 'ability_ratking_x': 'Other'}
    cat = {'heroes.vdata:hero_ratking': {'file': 'heroes.vdata', 'id': 'hero_ratking', 'kind': 'hero'},
           'abilities.vdata:ability_ratking_scrap_grenade': {'file': 'abilities.vdata', 'kind': 'ability',
                                                             'id': 'ability_ratking_scrap_grenade', 'owner': 'hero_ratking'},
           'abilities.vdata:ability_ratking_x': {'file': 'abilities.vdata', 'id': 'ability_ratking_x', 'kind': 'ability',
                                                 'owner': 'hero_ratking'}}
    check = _mc('abilities.vdata', 'ability_ratking_scrap_grenade', 'm_flBounceTargetDistanceCheck', 300, 400,
                'Bounce Target Distance Check', owner='hero_ratking')
    other = _mc('abilities.vdata', 'ability_ratking_x', 'm_flBounceSpeed', 1, 2, 'Bounce Speed', owner='hero_ratking')
    by_ent = {'abilities.vdata:ability_ratking_scrap_grenade': [check], 'abilities.vdata:ability_ratking_x': [other]}
    idx = {'rat king': ['heroes.vdata:hero_ratking'], 'scrap grenade': ['abilities.vdata:ability_ratking_scrap_grenade']}
    res = annotate_line('Rat King: Scrap Grenade - Fixed some bugs with bouncing targeting', [check, other], by_ent, idx,
                        cat, tok)
    assert res['status'] == 'described' and check.status == 'described' and other.status == 'hidden'


def test_a_zero_damage_gun_block_on_an_ability_is_plumbing():
    """Aura of Suffering lost a default weapon block (damage 0, clip 0) on 2026-03-06; a wrong link to "Pain Battery now
    starts charged" had called its 100 rows described — they are no gameplay. A changed value inside stays; a real
    gun's block is the gun's."""
    from pipeline.match import mark_dud_guns
    dmg = _mc('abilities.vdata', 'ability_frank_painaura', 'm_mapWeaponInfos.primary.m_flBulletDamage', 0, None,
              'Bullet Damage', op='remove')
    spread = _mc('abilities.vdata', 'ability_frank_painaura', 'm_mapWeaponInfos.primary.m_Spread', 0.2, None, 'Spread',
                 op='remove')
    speed = _mc('abilities.vdata', 'ability_frank_painaura', 'm_mapWeaponInfos.primary.m_flBulletSpeed', 0, 10000,
                'Bullet Velocity')
    gun = _mc('abilities.vdata', 'citadel_weapon_x', 'm_mapWeaponInfos.primary.m_flBulletDamage', 0, None, 'Damage',
              op='remove', kind='weapon')
    mark_dud_guns([dmg, spread, speed, gun])
    assert (dmg.cat, spread.cat, speed.cat, gun.cat) == ('technical', 'technical', 'balance', 'balance')


def test_an_attacks_kind_names_no_field():
    """"Light melee upward launch reduced" is Granny Long Legs' light attack's Attack Impulse Max Upward; "Repeat light
    melees while airborne now have diminishing forward momentum" names nothing of it but the attack."""
    tok = {'hero_baba': 'Baba', 'ability_baba_bench_run': 'Granny Long Legs', 'ability_baba_bench_melee': 'Melee'}
    cat = {'heroes.vdata:hero_baba': {'file': 'heroes.vdata', 'id': 'hero_baba', 'kind': 'hero'},
           'abilities.vdata:ability_baba_bench_run': {'file': 'abilities.vdata', 'id': 'ability_baba_bench_run',
                                                      'kind': 'ability', 'owner': 'hero_baba'},
           'abilities.vdata:ability_baba_bench_melee': {'file': 'abilities.vdata', 'id': 'ability_baba_bench_melee',
                                                        'kind': 'melee', 'owner': 'hero_baba'}}
    idx = {'baba': ['heroes.vdata:hero_baba'], 'granny long legs': ['abilities.vdata:ability_baba_bench_run']}

    def run(text):
        up = _mc('abilities.vdata', 'ability_baba_bench_melee',
                 'm_mapAttacks.EBabaBenchMeleeAttack_Light.m_flAttackImpulseMaxUpward', None, 150,
                 'Baba Bench Melee Attack Light › Attack Impulse Max Upward', op='add', owner='hero_baba')
        res = annotate_line(text, [up], {'abilities.vdata:ability_baba_bench_melee': [up]}, idx, cat, tok)
        return res['status'], up.status
    assert run('Baba: Granny Long Legs - Light melee upward launch reduced') == ('described', 'described')
    assert run('Baba: Granny Long Legs - Repeat light melees while airborne now have diminishing forward '
               'momentum') == ('unmatched', 'hidden')


# ---- 6 / 7. objectives, Street Brawl ------------------------------------------------------------------------------

def test_half_damage_to_objectives_is_the_boss_damage_scale():
    tok = {'hero_magician': 'Sinclair', 'ability_magician_magicbolt': 'Vexing Bolt'}
    cat = {'heroes.vdata:hero_magician': {'file': 'heroes.vdata', 'id': 'hero_magician', 'kind': 'hero'},
           'abilities.vdata:ability_magician_magicbolt': {'file': 'abilities.vdata', 'id': 'ability_magician_magicbolt',
                                                          'kind': 'ability', 'owner': 'hero_magician'}}
    boss = _mc('abilities.vdata', 'ability_magician_magicbolt', 'm_flBossDamageScale', 1, 0.5, 'Boss Damage Scale',
               owner='hero_magician')
    idx = {'sinclair': ['heroes.vdata:hero_magician'], 'vexing bolt': ['abilities.vdata:ability_magician_magicbolt']}
    res = annotate_line('Sinclair: Vexing Bolt - Now does half damage to objectives', [boss],
                        {'abilities.vdata:ability_magician_magicbolt': [boss]}, idx, cat, tok)
    assert res['status'] == 'documented' and boss.status == 'documented'
    from pipeline.match import _HALF_DAMAGE
    assert _HALF_DAMAGE.search('Pocket: Affliction now does half damage on objectives')
    assert not _HALF_DAMAGE.search('Warden now takes half damage from troopers')


def test_street_brawl_values_are_balance_and_draft_weights_are_not():
    from pipeline.classify import category
    assert category('m_mapAbilityProperties.DebuffDuration.m_strStreetBrawlValue', None, 14) == 'balance'
    assert category('m_vecAbilityUpgrades[1].m_vecPropertyUpgrades{DebuffDuration}.m_strStreetBrawlBonus',
                    None, 5) == 'balance'
    assert category('m_mapItemDraftWeights.upgrade_x', None, 2.4) == 'streetbrawl'


def test_a_street_brawl_value_knows_the_value_it_replaces():
    from pipeline.enrich import street_brawl_base
    data = {'m_mapAbilityProperties': {'DebuffDuration': {'m_strValue': '22', 'm_strStreetBrawlValue': '14'}}}
    assert street_brawl_base(data, 'm_mapAbilityProperties.DebuffDuration.m_strStreetBrawlValue') == 22
    assert street_brawl_base(data, 'm_mapAbilityProperties.DebuffDuration.m_strValue') is None


def _brawl_patch(lines):
    sb = _mc('abilities.vdata', 'ability_baba_bubbling_brew', 'm_mapAbilityProperties.DebuffDuration.m_strStreetBrawlValue',
             None, 14, 'Debuff Duration (Street Brawl)', op='add', owner='hero_baba', base=22)
    cd = _mc('abilities.vdata', 'ability_baba_bubbling_brew', 'm_mapAbilityProperties.DebuffDuration.m_strValue', 18, 14,
             'Debuff Duration', owner='hero_baba')
    cat = {'heroes.vdata:hero_baba': {'file': 'heroes.vdata', 'id': 'hero_baba', 'kind': 'hero', 'name': 'Baba'},
           'abilities.vdata:ability_baba_bubbling_brew': {'file': 'abilities.vdata', 'id': 'ability_baba_bubbling_brew',
                                                          'kind': 'ability', 'owner': 'hero_baba', 'name': 'Threadsap'}}
    p = Patch('2026-10-14', 'x', '2026-10-14', Notes('x', '2026-10-14', 'u', 'steam', [Section('General', lines)]))
    secs = annotate(p, [sb, cd], cat, {'hero_baba': 'Baba', 'ability_baba_bubbling_brew': 'Threadsap'})
    return secs[0]['lines'], sb, cd


def test_a_street_brawl_line_matches_the_modes_value_by_its_percent():
    """"Street Brawl: Baba Threadsap duration lasts 35% less" is Debuff Duration (Street Brawl) 14 against 22 (−36%)."""
    lines, sb, cd = _brawl_patch(['Street Brawl: Baba Threadsap duration lasts 35% less'])
    assert lines[0]['status'] == 'documented' and sb.status == 'documented' and cd.status == 'hidden'


def test_a_line_about_the_normal_game_never_takes_a_street_brawl_value():
    lines, sb, cd = _brawl_patch(['Baba: Threadsap - Debuff duration reduced from 22s to 14s'])
    assert sb.status == 'hidden'


# ---- 8 / 10. what a field is ---------------------------------------------------------------------------------------

def test_a_light_melees_launch_is_gameplay():
    from pipeline.classify import category
    assert category('m_mapAttacks.EBabaBenchMeleeAttack_Light.m_flAttackImpulseMaxUpward', None, 150) == 'balance'
    assert category('m_LightAttackData.m_flCooldownOnHit', 0.5, 0.6) == 'balance'
    assert category('m_mapAttacks.EAttackType_Light.m_flCooldownOnMiss', None, 0.75) == 'balance'
    assert category('m_LightParticle', None, 'particles/x.vpcf') == 'visual'
    assert category('m_flLightRadius', 1, 2) == 'visual'


def test_an_exponent_is_no_length():
    from pipeline import semantics
    assert semantics.engine_unit('m_flBounceTargetDistancePower') is False
    assert semantics.engine_unit('m_flBounceTargetDistanceCheck') is True
    assert semantics.engine_unit('m_flSpiritPowerRange') is True


# ---- 5. a bound ability is never a template -------------------------------------------------------------------------

def test_an_ability_a_hero_binds_is_no_template():
    from pipeline.classify import is_template_entry
    assert not is_template_entry('ability_chessmaster_throwbishop', {'_not_pickable': 1}, {'ability_chessmaster_throwbishop'})
    assert is_template_entry('ability_base', {'_not_pickable': 1}, set())
    assert not is_template_entry('ability_x', {}, set())


def test_a_kit_part_no_slot_ever_bound_is_not_removed():
    """Solomon's "Move King" and "Move Piece" are in the files and bound by no slot: today's kit, not "Removed";
    Calico's Nekomata Ward was bound once; a gone ability is removed."""
    from builders.hero_page import removed_parts
    ents = {i: {'id': i, 'owner': 'hero_x', 'alive': alive, **({'ability_slot': slot} if slot else {})}
            for i, alive, slot in (('a_now', True, 'Signature_1'), ('a_move', True, None), ('a_old', True, 'Signature_3'),
                                   ('a_gone', False, None), ('a_melee', True, 'Weapon_Melee'))}
    mine = [{'id': 'a_now', 'slot': 'Signature_1'}]
    assert removed_parts('hero_x', mine, ents) == {'abilities.vdata:a_old', 'abilities.vdata:a_gone'}


# ---- 9. names --------------------------------------------------------------------------------------------------------

def test_a_gun_filed_as_an_ability_and_a_pickup_take_the_games_names():
    from pipeline import loc
    tok = {'citadel_weapon_deadpack_set': 'Chimera Peace Bringer', 'artist_drawing_mystic': 'Mystic Sketch',
           'citadel_weapon_familiar_set': 'Gun'}
    assert loc.entity_name(tok, 'ability_deadpack_primary_weapon_charge', 'hero_deadpack') == 'Chimera Peace Bringer'
    assert loc.entity_name(tok, 'pickup_artist_drawing_mystic') == 'Mystic Sketch'
    assert loc.entity_name(tok, 'ability_familiar_alt_weapon', 'hero_familiar') == 'ability_familiar_alt_weapon'
    assert loc.entity_name(tok, 'citadel_weapon_familiar_set_2', 'hero_familiar') == 'citadel_weapon_familiar_set_2'


def test_the_zip_line_reads_as_the_game_section_names_it():
    """citadel_ability_zip_line's only text is a status message: "Kit: Zip Line Knocked off Zipline → Zip line"."""
    from builders import common
    common._IDS_MEMO.update(src=None, out={})
    assert common.ids_to_names('citadel_ability_zip_line') == 'Zip Line'


# ---- 11. one counting rule ----------------------------------------------------------------------------------------

def test_an_entity_that_came_is_a_change_of_its_own_an_edit_over_many_is_one():
    from builders.render import same_change
    a = {'key': 'misc.vdata:pickup_a:@add', 'path': '@add', 'label': 'Added to the game files', 'old_s': '', 'new_s': ''}
    b = {**a, 'key': 'misc.vdata:pickup_b:@add'}
    x = {'key': 'misc.vdata:crate_a:m_flX', 'path': 'm_flX', 'label': 'X', 'old_s': '1', 'new_s': '2'}
    y = {**x, 'key': 'misc.vdata:crate_b:m_flX'}
    assert same_change(a) != same_change(b) and same_change(x) == same_change(y)


def test_the_patch_tiles_sum_to_all_changes():
    """2026-10-14's tiles summed to 65 over "All changes 61": a family's or a system's one edit was a tile per member."""
    import re
    from builders import archive, patches_pages
    from builders.patch_counts import for_id
    for pid in ('2026-10-14', '2026-10-05', 'build-6790'):
        html = patches_pages._summary(archive.patch(pid), '../')
        tiles = sum(int(n) for n in re.findall(r'<span class="n">(\d+)</span>', html))
        assert tiles == for_id(pid)['changes'], pid


def test_a_heros_icon_on_the_home_page_counts_what_its_band_counts():
    """Violet's release read 19 on the home page and 17 on her band: her abilities' nameless "trigger" parts repeat
    their parents' NEW rows, which her page says once (hero_page.history_folds)."""
    from builders import archive, patch_counts
    from builders.home_page import update_feed
    feed = update_feed(archive.patch('build-6790'), frozenset(), patch_counts.unit_main(), patch_counts.page_set())
    rows = feed['heroes']['heroes.vdata:hero_artist']['rows']
    assert not any('_trigger:' in c['key'] for _, c in rows)


def test_a_nameless_part_of_a_named_ability_reads_as_its(monkeypatch):
    from builders import common
    names = {'ability_artist_bamboogrove': 'Abstract Landscape'}
    assert common.sub_part_name('ability_artist_bamboogrove_trigger', names) == 'Abstract Landscape · trigger'
    assert common.sub_part_name('ability_artist_tether', names) is None
    assert common.sub_part_name('ability_y_trigger', names) is None
