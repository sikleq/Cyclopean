"""Name and description changes (builders/text_rows.py): word diffs and their values by build."""
import re


def test_a_description_diff_marks_words_not_confetti():
    """Review 2026-10-05: Active Reload 2025-05-19 struck "Rate, Bullet Lifesteal." and re-added the same words when
    only "Move Speed" came; Unstoppable's "Immune" → "immune" was a change; a band of a text change only read empty;
    "infront" → "in front" looked like no change at all."""
    from builders.text_rows import _marked, cosmetic, text_kind, text_rows
    old, new = _marked('Grants Fire Rate, Bullet Lifesteal.', 'Grants Fire Rate, Bullet Lifesteal and Move Speed.')
    assert '<del>' not in old and new.count('<ins>') == 1 and 'Move Speed' in new.split('<ins>')[1]
    old, new = _marked('Immune to stuns', 'immune to stuns')
    assert '<del>' not in old and '<ins>' not in new
    assert cosmetic('Press [[Iv attack]] to fire', 'Press [Attack] to fire') and not cosmetic('infront', 'in front')
    assert not cosmetic('+20 Damage', '+20% Damage')
    html = text_rows([{'part': 'desc', 'old': 'Hits [[Iv attack]] twice', 'new': 'Hits [Attack] twice.'}])
    assert 'Wording fixed' in html and '<details class="txt" open>' in html
    assert text_kind([{'part': 'desc', 'old': 'A b', 'new': 'A c'}]) == 'description changed'
    assert text_kind([{'part': 'name', 'old': 'A', 'new': 'B'}]) == 'renamed'
    assert text_kind([{'part': 'desc', 'old': 'A b', 'new': 'a b.'}]) is None
    filled = text_rows([{'part': 'desc', 'old': '[Hero name] hits once', 'new': '[Hero name] hits twice'}], 'Abrams')
    assert 'Abrams hits' in filled and '[Hero name]' not in filled


def test_a_description_with_values_no_build_record_knows_stays_folded():
    """Review 2026-10-05: opened, 552 of 980 description rows showed "[Ability Cooldown]s Cooldown · Applies [Fixation
    Stacks] Fixation Stacks". A value the pipeline could not read is a neutral gap, never the token, and such a row
    stays folded. The hero's own name and a key binding are no such value."""
    from builders.text_rows import GAP, text_rows
    tok = text_rows([{'part': 'desc', 'old': '{s:AbilityCooldown}s Cooldown', 'new': '{s:AbilityCooldown}s Cooldown, '
                      'applies {s:FixationStacks} stacks'}], 'Haze')
    assert '<details class="txt">' in tok and '<details class="txt" open>' not in tok
    assert '[Ability Cooldown]' not in tok and '[Fixation Stacks]' not in tok and f'{GAP}s Cooldown' in tok
    hero = text_rows([{'part': 'desc', 'old': '{s:hero_name} jumps', 'new': '{s:hero_name} jumps high'}], 'Haze')
    assert '<details class="txt" open>' in hero and 'Haze jumps' in hero
    key = text_rows([{'part': 'desc', 'old': 'Press {s:iv_attack} to fire', 'new': 'Hold {s:ability_key} to fire'}])
    assert '<details class="txt" open>' in key and GAP not in key and '[Ability key]' in re.sub(r'<[^>]+>', '', key)


def test_a_description_change_prints_each_builds_values():
    """Review 2026-10-05: ~550 description rows (Haze's Sleep Dagger T2 2026-07-28) showed Valve's unfilled tokens.
    The old text reads with the values at the window's start, the new one with those at its end, the text's unit
    once, as the game's tooltip prints them."""
    from builders.text_rows import text_kind, text_rows
    t = {'part': 't2', 'old': '<span class="highlight">{s:AbilityCooldown}s</span> Cooldown<br>Applies '
                              '{s:FixationStacks} Fixation Stacks',
         'new': '<span class="highlight">+{s:SleepDuration}s</span> Sleep Duration<br>Applies {s:FixationStacks} '
                'Fixation Stacks',
         'vals': {'old': {'AbilityCooldown': '-4', 'FixationStacks': '1'},
                  'new': {'SleepDuration': '0.5', 'FixationStacks': '2'}}}
    html = text_rows([t], 'Haze')
    assert '<details class="txt" open>' in html and '[' not in re.sub(r'<[^>]+>', '', html)
    plain = re.sub(r'<[^>]+>', '', html)
    assert '-4s Cooldown · Applies 1 Fixation Stacks' in plain and '+0.5s Sleep Duration · Applies 2 Fixation' in plain
    assert text_kind([t]) == 'description changed'
    # a value that carries the text's unit: "+{s:AbilityCastRange}m" with "3m" is "+3m", not "+3mm"
    rng = text_rows([{'part': 't3', 'old': '+{s:AbilityCastRange}m Cast Range', 'new': '+{s:AbilityCastRange}m Range',
                      'vals': {'old': {'AbilityCastRange': '3m'}, 'new': {'AbilityCastRange': '4m'}}}])
    rng = re.sub(r'<[^>]+>', '', rng)
    assert '+3m Cast Range' in rng and '+4m Range' in rng and 'mm' not in rng


def test_a_description_that_only_moves_numbers_its_rows_say_stays_folded():
    """A text that differs only in numbers the patch's own rows already show ("30s Cooldown" → "28s Cooldown" beside
    "Cooldown 30s → 28s") says nothing more: it stays folded. A number no row shows opens it."""
    from builders.text_rows import numbers_only, text_rows
    t = {'part': 'desc', 'old': 'Every {s:AbilityCooldown}s', 'new': 'Every {s:AbilityCooldown}s',
         'vals': {'old': {'AbilityCooldown': '30'}, 'new': {'AbilityCooldown': '28'}}}
    row = {'label': 'Cooldown', 'old_s': '30s', 'new_s': '28s'}
    assert '<details class="txt">' in text_rows([t], None, [row])
    assert '<details class="txt" open>' in text_rows([t], None, [])
    assert numbers_only('Every 30s', 'Every 28s', [row]) and not numbers_only('Every 30s', 'Each 28s', [row])
    assert not numbers_only('Every 30s', 'Every 30s', [row])
