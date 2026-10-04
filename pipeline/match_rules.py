"""Matching rules learned from the audit of 'hidden' changes.

tests/fixtures/audit_verdicts.jsonl holds ~1000 judged changes; each rule
here closes one recurring miss (see docs/architecture.md, "Matching rules").
Score the effect with `python tools/audit_score.py`.
"""
from __future__ import annotations

import re

# ---- 4. words the notes use for units / objectives / rules that have internal ids ----
# note word -> [(file, entity id)]
ALIASES: dict[str, list[tuple[str, str]]] = {}


def _alias(words: tuple[str, ...], keys: list[tuple[str, str]]) -> None:
    for w in words:
        ALIASES[w] = keys


_alias(('guardian', 'guardians'), [('npc_units.vdata', 'npc_boss_tier1'), ('npc_units.vdata', 'alt_npc_boss_tier1'),
                                    ('generic_data.vdata', 'm_ObjectiveParams')])
_alias(('walker', 'walkers'), [('npc_units.vdata', 'npc_boss_tier2'), ('npc_units.vdata', 'alt_npc_boss_tier2'),
                                ('npc_units.vdata', 'npc_boss_tier2_weak'), ('npc_units.vdata', 'alt_npc_boss_tier2_weak'),
                                ('generic_data.vdata', 'm_ObjectiveParams'),
                                ('abilities.vdata', 'citadel_ability_tier2boss_stomp'),
                                ('abilities.vdata', 'citadel_ability_tier2boss_laser_beam'),
                                ('abilities.vdata', 'citadel_ability_tier2boss_rocket_barrage')])
_alias(('patron', 'patrons'), [('npc_units.vdata', 'npc_boss_tier3'), ('npc_units.vdata', 'alt_npc_boss_tier3')])
_alias(('base guardian', 'base guardians'), [('npc_units.vdata', 'npc_barrack_boss'),
                                              ('npc_units.vdata', 'npc_barrack_boss_amber'),
                                              ('npc_units.vdata', 'npc_barrack_boss_sapphire')])
_alias(('shrine', 'shrines'), [('npc_units.vdata', 'destroyable_building'), ('generic_data.vdata', 'm_ObjectiveParams')])
_alias(('mid boss', 'midboss', 'mid-boss'), [('npc_units.vdata', 'npc_super_neutral')])
# the vault is a unit, its spawn timers live on the camp ("Sinner's Sacrifice spawn/respawn time 8/4 -> 10/5")
_alias(("sinner's sacrifice", 'sinners sacrifice', 'sinner sacrifice', 'vault', 'vaults'),
       [('npc_units.vdata', 'neutral_sinners_sacrifice'), ('npc_units.vdata', 'neutral_vault'),
        ('misc.vdata', 'neutral_camp_vaults')])
_alias(('trooper', 'troopers'), [('npc_units.vdata', 'trooper_normal'), ('npc_units.vdata', 'trooper_medic'),
                                  ('npc_units.vdata', 'trooper_melee')])
_alias(('rejuvenator', 'rejuv'), [('generic_data.vdata', 'm_RejuvParams'), ('misc.vdata', 'citadel_item_pickup_rejuv'),
                                  ('npc_units.vdata', 'citadel_item_pickup_rejuv')])
_alias(('soul urn', 'urn'), [('generic_data.vdata', 'm_IdolParams'), ('abilities.vdata', 'ability_golden_idol'),
                              ('misc.vdata', 'citadel_idol_cashin'), ('misc.vdata', 'citadel_item_pickup_idol'),
                              ('misc.vdata', 'xp_orb_idol_dropoff')])
_alias(('neutral', 'neutrals', 'camps', 'jungle'), [('npc_units.vdata', 'neutral_trooper_weak'),
                                                    ('npc_units.vdata', 'neutral_trooper_normal'),
                                                    ('npc_units.vdata', 'neutral_trooper_strong'),
                                                    ('misc.vdata', 'neutral_camp_weak'),
                                                    ('misc.vdata', 'neutral_camp_medium'),
                                                    ('misc.vdata', 'neutral_camp_strong')])
# the statue's bonuses, and the containers that hold its timers ("Golden Statues bonuses upgrade time
# changed from 15 min to 10 min" is Match Time For Level2 Pickups on the item container)
_alias(('golden statue', 'golden statues', 'statue', 'statues'),
       [('misc.vdata', f'{kind}_permanent_pickup{lv}') for kind in ('hp', 'cd', 'ammo', 'bulletresist', 'techresist',
                                                                    'spirit', 'weapon', 'firerate', 'movespeed')
        for lv in ('', '_lv2', '_lv3')]
       + [('misc.vdata', 'citadel_breakable_item_container'), ('misc.vdata', 'citadel_breakable_prop_drop_powerups')])
_alias(('dash', 'dashes'), [('abilities.vdata', 'citadel_ability_dash')])
_alias(('jump', 'dash jump'), [('abilities.vdata', 'citadel_ability_jump')])
_alias(('slide', 'sliding'), [('abilities.vdata', 'citadel_ability_slide')])
_alias(('melee', 'parry'), [('abilities.vdata', 'citadel_ability_melee_parry')])


def alias_keys(text: str, longer: tuple[str, ...] = ()) -> set[str]:
    """Entities a line names by a common word ('walkers'). `longer`: names the line uses that contain
    such a word ("veil walker") — then the word is part of that name, not an alias."""
    low = text.lower()
    out = set()
    for word, keys in ALIASES.items():
        # a word INSIDE a longer name is not the alias; the alias that IS the name stays ("Base Guardian
        # Health increased by 20%" lost both and matched every +20% field of the patch, 2026-10-02)
        if re.search(rf'\b{re.escape(word)}\b', low) and not any(word in n and word != n for n in longer):
            out |= {f'{f}:{i}' for f, i in keys} | {f'{f}:{i}_herotest' for f, i in keys}
    return out


def name_variants(name: str) -> set[str]:
    """'The Doorman' / 'Doorman', 'Mo & Krill' / 'Mo and Krill'."""
    n = name.strip().lower()
    out = {n, n.replace('&', 'and'), n.replace(' and ', ' & ')}
    if n.startswith('the '):
        out.add(n[4:])
    return {x for x in out if x}


# ---- 5. label synonyms: words the notes use for a property ----
LABEL_SYNONYMS = {
    # a projectile's "collision size" / "hitbox" is its radius (Serrated Knives -10% tied with its velocity)
    'resist': {'armor', 'resistance'}, 'armor': {'resist'},
    'radius': {'range', 'aoe', 'area', 'size', 'collision', 'hitbox'}, 'health': {'hp'},
    'range': {'radius'}, 'multiplier': {'range'}, 'chargeup': {'cooldown'}, 'cooldown': {'cd'},
    'shock': {'chain'}, 'lifesteal': {'heal', 'healing'}, 'heal': {'healing', 'lifesteal'},
    'duration': {'time'}, 'charges': {'charge'}, 'barrier': {'shield'}, 'speed': {'velocity'},
    'velocity': {'speed'}, 'souls': {'bounty', 'gold'}, 'gold': {'souls', 'bounty'},
}


# a stat's growth is how much it gains per boon / per minute / with spirit: "Bullet damage growth",
# "Health growth". A phrase, not the word "boon" ("Level 21: gives a boon" grows nothing)
GROWTH_LABEL = re.compile(r'per (boon|minute)|\((boon|spirit) scaling\)|growth', re.I)


def stem(w: str) -> str:
    """The plural cut match.words applies ('radius' -> 'radiu', 'charges' -> 'charge')."""
    return w[:-1] if len(w) > 4 and w.endswith('s') and not w.endswith('ss') else w


# the words of the aliases ("guardian", "urn", "neutral"…): a line's subject, never the property it names
ALIAS_WORDS = {stem(w) for phrase in ALIASES for w in re.findall(r'[a-z]{3,}', phrase)} - {
    'dash', 'dashe', 'jump', 'slide', 'sliding', 'melee', 'parry', 'base'}     # these name a property too


def stemmed_synonyms(table: dict[str, set[str]]) -> dict[str, set[str]]:
    """Keys and words as match.words writes them: 'radius' and 'souls' never fired until 2026-10-02."""
    out: dict[str, set[str]] = {}
    for k, vs in table.items():
        out.setdefault(stem(k), set()).update(stem(v) for v in vs)
    return out


_LABEL_SYNONYMS = stemmed_synonyms(LABEL_SYNONYMS)


def expand_label_words(ws: set[str]) -> set[str]:
    out = set(ws)
    for w in ws:
        out |= _LABEL_SYNONYMS.get(w, set())
    return out


# ---- 1. global lines: "All ultimates' cooldowns increased by 15%" ----
GROUND_DASH = re.compile(r'GroundDash', re.I)
PROP_FAMILIES: tuple[tuple[re.Pattern, re.Pattern, bool], ...] = (
    # (line pattern, field path pattern, needs "all/global/every")
    (re.compile(r'dash slows?|ground dash'), GROUND_DASH, True),
    (re.compile(r'\bslows?\b'), re.compile(r'Slow', re.I), True),
    (re.compile(r'health per boon|hp per boon'), re.compile(r'BASE_HEALTH_FROM_LEVEL'), False),
    # "Base gun damage and gun damage growth increased by 10%" is global without saying "all"
    (re.compile(r'\b(gun|weapon|bullet) damage\b'), re.compile(r'm_flBulletDamage|BULLET_DAMAGE_FROM_LEVEL'), False),
    (re.compile(r'\b(spirit|ability|ap) damage\b'), re.compile(r'Damage|DPS', re.I), True),
    (re.compile(r'\bcooldowns?\b'), re.compile(r'Cooldown(?!BetweenCharge)|ChargeUpTime', re.I), True),
    (re.compile(r'\bdurations?\b'), re.compile(r'Duration', re.I), True),
    (re.compile(r'investment'), re.compile(r'm_MapModCostBonuses'), False),
    (re.compile(r'\b(boon|level)s? at\b|\bextra (boon|level)\b|\blevels? (at|to)\b'), re.compile(r'm_mapLevelInfo'), False),
    (re.compile(r'\bbount(y|ies)\b'), re.compile(r'Gold|Bounty|Reward|Souls', re.I), True),
    (re.compile(r'respawn'), re.compile(r'spawn_time|Respawn', re.I), False),
)
# families whose words turn up in lines about something else: they cover a line with a number only
NUMBER_FAMILIES = {f[0] for f in PROP_FAMILIES if f[0].pattern in (r'\b(gun|weapon|bullet) damage\b', 'respawn')}
SCOPES: tuple[tuple[re.Pattern, object], ...] = (
    # scope(entity, change) -> bool; the first matching pattern wins.
    # "AP upgrades" are the ability-point tier upgrades (T1-T3), not shop items.
    (re.compile(r'\bap\b.{0,20}\bupgrades?\b|\babilit(y|ies) upgrades?\b|\btier upgrades?\b'),
     lambda e, c: 'm_vecAbilityUpgrades' in c.path),
    (re.compile(r'\bultimates?\b'), lambda e, c: e.get('ability_slot') == 'Signature_4'),
    (re.compile(r'\b(items?|upgrades?)\b'), lambda e, c: e.get('kind') == 'item'),
    (re.compile(r'\babilit(y|ies)\b'), lambda e, c: e.get('kind') == 'ability'),
    # every hero's jump / dash / slide (kind 'shared' since 2026-10-04) is a hero thing too
    (re.compile(r'\bheroes\b'), lambda e, c: e.get('kind') in ('hero', 'ability', 'weapon', 'shared')),
)
_PCT = re.compile(r'(increased|reduced|decreased|lowered|raised|by)\D{0,12}?~?(\d+(?:\.\d+)?)\s*%', re.I)
_GLOBAL = re.compile(r'\b(all|every|global(ly)?|across the board)\b', re.I)


_ROUNDING = re.compile(r'nearest (multiple of )?(\d+(?:\.\d+)?)', re.I)


def ratio_ok(old, new, pct: float, sign: int, num, unit: float = 1.0) -> bool:
    o, n = num(old), num(new)
    if o in (None, 0) or n is None:
        return False
    r = abs(n) / abs(o)
    targets = [1 + pct / 100, 1 - pct / 100] if sign == 0 else [1 + sign * pct / 100]
    # "~20%" and rounded values: 3.5 points, or half a rounding unit ("nearest multiple of 5")
    tol = max(0.035, (unit / 2 + 0.01) / abs(o))
    return any(abs(r - t) <= tol for t in targets)


def global_line(text: str, changes: list, cat: dict, num) -> list | None:
    """Changes covered by a global line, or None when the line is not global."""
    low = text.lower()
    for line_re, path_re, needs_global in PROP_FAMILIES:
        if not line_re.search(low):
            continue
        if needs_global and not _GLOBAL.search(low):
            return None
        if line_re in NUMBER_FAMILIES and not _DIGIT.search(low):
            # respawn / gun damage words are everywhere: such a line needs a number ("Lowered volumes for
            # UI death notification sounds and respawn music" claimed every respawn field, P12 2026-10-02)
            continue
        scope = next((f for rx, f in SCOPES if rx.search(low)), None)
        m = _PCT.search(low)
        pct = float(m.group(2)) if m else None
        verb = m.group(1).lower() if m else ''
        sign = 1 if verb in ('increased', 'raised') else -1 if verb in ('reduced', 'decreased', 'lowered') else 0
        rm = _ROUNDING.search(low)
        unit = float(rm.group(2)) if rm else 1.0
        out = []
        for c in changes:
            if c.cat != 'balance' or not path_re.search(c.path):
                continue
            if path_re.pattern == 'Slow' and GROUND_DASH.search(c.path):
                continue
            if scope is not None and not scope(cat.get(f'{c.file}:{c.eid}', {}), c):
                continue
            if pct is not None and not any(ratio_ok(o, n, pct, sign, num, unit) for o, n in c.steps()):
                continue
            out.append(c)
        return out or None
    return None


# ---- 1b. global lines with an amount: "Base HP reduced by 10 for all heroes" ----
# The same edit applied to every hero (or every gun, every item…) arrives as dozens of
# "hidden" changes unless the line is read as a rule: field family + "by N" / "by N%".
# 2026-05-22: Max Health -10 on 27 heroes; 2025-12-16: move speed -0.1 on 13; 2025-07-04:
# fire interval +5% on 32 guns; 2025-05-11: spirit scaling -7% on 40+ abilities.
DELTA_FAMILIES: tuple[tuple[re.Pattern, re.Pattern, object], ...] = (
    # (line pattern, field path pattern, entity filter)
    (re.compile(r'\b(hp|health) (per boon|growth)|\bhealth growth|\bgrowth per boon|\b(hp|health)\b.*\bgrowth\b'),
     re.compile(r'BASE_HEALTH_FROM_LEVEL'), lambda e: e.get('kind') == 'hero'),
    (re.compile(r'\bsprint speed\b'), re.compile(r'm_mapStartingStats\.ESprintSpeed'), lambda e: e.get('kind') == 'hero'),
    (re.compile(r'\bmove ?speed\b'), re.compile(r'm_mapStartingStats\.EMaxMoveSpeed'), lambda e: e.get('kind') == 'hero'),
    (re.compile(r'(?<!bonus )\b(base )?(hp|health)\b(?! (per|growth|regen))'),
     re.compile(r'm_mapStartingStats\.EMaxHealth$'), lambda e: e.get('kind') == 'hero'),
    # "Light melee base damage reduced by 20% (except for Viscous, Calico and Bebop)": 50 heroes (hero audit #11)
    (re.compile(r'\blight melee\b|\bmelee damage\b'), re.compile(r'm_mapStartingStats\.ELightMeleeDamage$'),
     lambda e: e.get('kind') == 'hero'),
    (re.compile(r'\bheavy melee\b|\bmelee damage\b'), re.compile(r'm_mapStartingStats\.EHeavyMeleeDamage$'),
     lambda e: e.get('kind') == 'hero'),
    (re.compile(r'\b(bullet )?cycle time|\bfire interval'), re.compile(r'm_flCycleTime$'),
     lambda e: e.get('kind') == 'weapon'),
    (re.compile(r'\bspirit (power )?scaling'), re.compile(r'm_subclassScaleFunction\.m_flStatScale$'),
     lambda e: e.get('kind') in ('ability', 'ability_other', 'weapon')),
    (re.compile(r'\bbonus health\b.*\bitems?\b|\bitems?\b.*\bbonus health\b'),
     re.compile(r'\.BonusHealth\.m_strValue$'), lambda e: e.get('kind') == 'item'),
    (re.compile(r'\btrooper bounty\b'), re.compile(r'm_flGoldReward$'), lambda e: e.get('kind') == 'trooper'),
)
_DELTA = re.compile(r'\b(increased|reduced|decreased|lowered|raised)\s+(?:growth\s+)?by\s+(~)?([+-]?\d+(?:\.\d+)?)\s*(%)?',
                    re.I)
DELTA_MIN = 3          # one hero is a hero line, not a rule
# "Hero health growth increased by +3 and 4%": new = old * (1 + 4%) + 3, game values rounded
_COMBINED = re.compile(r'\bby\s+\+?(\d+(?:\.\d+)?)\s+and\s+\+?(\d+(?:\.\d+)?)\s*%', re.I)


def combined_ok(old, new, add: float, pct: float, sign: int, num) -> bool:
    o, n = num(old), num(new)
    if o is None or n is None or o == n or (n > o) != (sign > 0):
        return False
    candidates = (o * (1 + sign * pct / 100) + sign * add, (o + sign * add) * (1 + sign * pct / 100))
    # whole numbers in the files are rounded (46 * 1.04 + 3 = 50.8 -> 51); small fields are not
    return any(abs(n - c) <= (1.0 if abs(o) >= 10 else 0.03 * abs(c)) for c in candidates)


def delta_ok(old, new, amount: float, pct: bool, approx: bool, sign: int, num) -> bool:
    o, n = num(old), num(new)
    if o is None or n is None or o == n:
        return False
    d = n - o
    if sign and (d > 0) != (sign > 0):
        return False          # an "increased" line never covers a decrease
    if pct:
        # unit=0: no rounding allowance, so 0.5 -> 0.3 is not "+5%" on a small value
        return ratio_ok(o, n, amount, sign, num, unit=0.0)
    tol = abs(amount) * 0.3 if approx else max(abs(amount) * 0.005, 1e-6)
    return abs(abs(d) - abs(amount)) <= tol


def global_delta_line(text: str, changes: list, cat: dict, num) -> list | None:
    """Changes covered by a line that moves one stat of many entities by the same amount."""
    low = text.lower()
    m = _DELTA.search(low)
    if not m:
        return None
    verb, approx, amount, pct = m.group(1), bool(m.group(2)), abs(float(m.group(3))), bool(m.group(4))
    sign = 1 if verb in ('increased', 'raised') else -1
    # the stat is named before the number: "Hero health increased growth by +4 and 8%"
    head = low[:m.start(3)]
    cm = _COMBINED.search(low, m.start())
    if cm:
        add, cpct = float(cm.group(1)), float(cm.group(2))

        def moved(o, n):
            return combined_ok(o, n, add, cpct, sign, num)
    else:
        def moved(o, n):
            return delta_ok(o, n, amount, pct, approx, sign, num)
    # every family the words fit counts ("Move speed and sprint speed reduced by 0.1" is two
    # stats); a family joins only with DELTA_MIN entities of its own, so one coincidence never does
    out: list = []
    for line_re, path_re, keep in DELTA_FAMILIES:
        if not line_re.search(head):
            continue
        hit = [c for c in changes
               if c.cat == 'balance' and path_re.search(c.path) and keep(cat.get(f'{c.file}:{c.eid}', {}))
               and any(moved(o, n) for o, n in c.steps())]
        if len(hit) >= DELTA_MIN:
            out += [c for c in hit if c not in out]
    return out or None


# ---- 1c. boon rescales: a patch that changes how many boons there are rescales every per-boon value ----
# 2024-09-26: "Boon count increased from 11 to 14" + "Non-Health boon bonuses rescaled over the 14 levels
# (same total as before)" — the hero lines quote growth in the OLD scale: "Kelvin: Bullet damage growth
# reduced from 1.2 to 0.9" is 0.9 * 11/14 = 0.707 in the files. 2025-06-17: "total stat levels increased
# from 20 to 32 (but rescaled in value …)": Wraith "-18%" is 0.351 * 0.82 * 20/32 = 0.18.
_BOON_COUNT = re.compile(r'boon count (?:increased|reduced|decreased|changed) from (\d+) to (\d+)', re.I)
_STAT_LEVELS = re.compile(r'total stat levels (?:increased|reduced|decreased|changed) from (\d+) to (\d+)', re.I)
BOON_FIELD = re.compile(r'^m_mapStandardLevelUpUpgrades\.')


def boon_rescale(text: str) -> tuple[float, bool] | None:
    """(old count / new count, health left out?) when the notes rescale per-boon values, else None."""
    m = _BOON_COUNT.search(text)
    if m:
        return int(m.group(1)) / int(m.group(2)), bool(re.search(r'non-health', text, re.I))
    m = _STAT_LEVELS.search(text)
    if m and re.search(r'rescal', text, re.I):
        return int(m.group(1)) / int(m.group(2)), False
    return None


def rescaled_field(c, rescale: tuple[float, bool] | None) -> bool:
    return bool(rescale) and bool(BOON_FIELD.match(c.path)) and not (rescale[1] and 'HEALTH' in c.path)


def boon_lines(text: str, changes: list, rescale: tuple[float, bool] | None, num) -> list | None:
    """The patch-wide boon lines themselves: the boon count (the levels that give one) and the rescale
    (every per-boon value moved by old / new count)."""
    low = text.lower()
    if 'boon' not in low:
        return None
    out = []
    if _BOON_COUNT.search(text) or re.search(r'boons are distributed|extra boon', low):
        out += [c for c in changes if c.path.startswith('m_mapLevelInfo.')]
    if rescale and re.search(r'rescal', low):
        f = rescale[0]
        out += [c for c in changes if rescaled_field(c, rescale) and c not in out
                and any(num(o) and num(n) is not None and abs(num(n) / num(o) - f) <= 0.03 * f for o, n in c.steps())]
    return out or None


# ---- 2. components: "Now builds from Sprint Boots" ----
# "Headhunter: Now requires Headshot Booster", "Fortitude: Now upgrades from Extra Health" (2026-10-03)
COMPONENT_RE = re.compile(r'builds? (from|into)|no longer builds|component|\brequires\b|\bupgrades? (from|into)\b', re.I)
AFFECTS_UPGRADES_RE = re.compile(r'affects? (its )?upgrades', re.I)

# ---- 8. lines the compared data cannot carry ----
# Sound, effects, client UI, map geometry, bots, forum links: these live in sound
# events, particles, panorama and map files, not in the vdata we diff. Such a line
# is 'untracked' (with a topic), not a matcher failure. Lines with numbers are never
# untracked: "Side Walkers HP increased from 5,175 to 7,000" is data we should find.
_LINK = re.compile(r'^\s*inspired by\b|\(?(thanks to )?https?://\S+\)?', re.I)
UNTRACKED_TOPICS = (
    # 'sounds' as a noun of sound work only: "the sounds of the outside world fade away along with your
    # stamina" (Sunken Plaza) describes gameplay
    ('sound', re.compile(r'\b(sfx|sound ?effects?|sound design|sound (is|are|now|no longer|cues?|volume|mix)|'
                         r'(new|updated|improved|adjusted|reduced|lowered|increased|added|louder|quieter|missing)'
                         r'(\s\w+)? sounds?|sounds? (for|when|on|of (the|an?) (ability|hero|item|weapon))|'
                         r'audio|music|vo|voice ?lines?|voiceover|whizby|footsteps?|pings?|'
                         # "Updated McGinnis weapon sounds", "Haze's sounds" (audit 2026-10-01)
                         r"(weapon|ability|item|hero|impact|reload|gun)\s+sounds?|\w+'s\s+sounds?)\b", re.I)),
    # 'effects' alone is gameplay ("removes movement effects"): only the visual kinds
    ('visual', re.compile(r'\b(visuals?|vfx|(visual|particle|impact|cast|trail|ambient|preview|screen|hit|updated)'
                          r' effects?|effects? revisions?|particles?|animations?|models?|lighting|textures?|art|'
                          r'muzzle flash|tracers?|glow|cosmetics?|skins?|outline|silhouette|ragdoll)\b', re.I)),
    # never bare 'setting' (a verb: "rather than setting it to a low cap"), 'hotkey', 'indicator'
    ('interface', re.compile(r'\b(ui|hud|interface|scoreboard|tooltips?|icons?|menus?|dashboard|leaderboards?|'
                             r'build (browser|authoring|editor)|builds? browser|quickbuy|settings (menu|page|panel)|'
                             r'(in|to) (the )?settings|keybinds?|replays?|spectat\w*|dialog|minimap|crosshair|'
                             r'kill ?feed|chat|party|friends?|invites?|matchmaking|queue|lobby|profile|localization|'
                             r'translations?|sandbox|hero labs?|tutorial|camera|mouse|controller|damage report|'
                             r'default builds?|suggested|hud message|voice chat|text chat|mute|report(ing)? players?|'
                             r'settings? options?|options? (menu|to (show|hide|toggle)))\b',
                             re.I)),
    # map geometry only: "walls"/"cover"/"zipline"/"bounce pad"/"geometry" appear in gameplay
    # lines ("can be cast through walls", "no longer prevents zipline usage", Holliday's Bounce Pad)
    ('map', re.compile(r'\b(map|rooftops?|veils? (to|at|in|on|near|around)|terrain|garage|night ?club|courtyard|'
                       r'traversal|navigat\w*|spawn area|fountain|stairs|ledges?|balcon(y|ies)|alley|juke|'
                       # level geometry words of the map notes (audit 2026-10-01: ~300 unmatched lines)
                       r'hallways?|alcoves?|tunnels?|corridors?|signage|street ?lights|buildings)\b', re.I)),
    ('bots', re.compile(r'\bbots?\b', re.I)),
    ('performance', re.compile(r'\b(performance|optimi[sz]\w*|fps|memory|crash(es)?|stability|servers?|network\w*|'
                               r'netcode|tick ?rate|latency|hitch\w*|stutter\w*|loading|shaders?|dlss|fsr\d?|'
                               r'reflex|anti-?lag|upscal\w*|anti-?aliasing|vulkan|directx|dx1[12]|gpu|cpu|'
                               r'preload\w*|vram)\b', re.I)),
)
# engine vocabulary that is never balance data, even with numbers ("tick rate from 60hz to
# 64hz"); 'server' / 'latency' are not in it ("Soul Orbs have a 90ms buffer to allow the server")
_ENGINE_WITH_DIGITS = re.compile(r'\b(tick ?rate|fps|\d+ ?hz|shaders?|dlss|fsr\d?|reflex|anti-?lag|upscal\w*|'
                                 r'anti-?aliasing|vulkan|directx|dx1[12]|gpu|cpu|vram)\b', re.I)
# a line about a hero or an ability can only be untracked for its sound or looks:
# "Holliday: Bounce Pad now provides air control" is gameplay whatever the words
SUBJECT_TOPICS = ('sound', 'visual')
SECTION_TOPICS = (
    ('sound', re.compile(r'sound|music|\bvo\b|audio', re.I)),
    ('visual', re.compile(r'visual|art|cosmetic', re.I)),
    ('interface', re.compile(r'interface|\bui\b|build authoring|localization|social|client|spectat', re.I)),
    ('map', re.compile(r'\bmap\b', re.I)),
)
_DIGIT = re.compile(r'\d')


def untracked_topic(text: str, section: str = '', has_subject: bool = False) -> str | None:
    rest = _LINK.sub(' ', text).strip()
    if not rest.strip(' .:-') or (_LINK.search(text) and not _DIGIT.search(rest) and len(rest) < 40):
        return 'link'           # "Inspired by: https://…" — a numbered line with a link stays gameplay
    has_digit = bool(_DIGIT.search(rest))
    if has_digit:
        if not has_subject and _ENGINE_WITH_DIGITS.search(rest):
            return 'performance'
        return None
    for topic, rx in UNTRACKED_TOPICS:
        if has_subject and topic not in SUBJECT_TOPICS:
            continue
        if rx.search(rest):
            return topic
    if has_subject:
        return None
    for topic, rx in SECTION_TOPICS:
        if rx.search(section or ''):
            return topic
    return None


# ---- 7. one line = one feature = many fields ----
_CAMEL = re.compile(r'^m_[a-z]*((?:[A-Z][a-z0-9]+){1,3})')


def cluster_root(path: str) -> str:
    """Fields that belong to one feature: same top-level block, or for top-level
    scalars the same leading words (m_flParryCancelAirGlideDuration -> ParryCancelAir)."""
    first = path.split('.', 1)[0]
    if first == 'm_mapAbilityProperties':
        return '.'.join(path.split('.')[:2])
    if '.' in path or '{' in first or '[' in first:
        return re.sub(r'[\[{].*$', '', first)
    m = _CAMEL.match(path)
    return m.group(1) if m else path
