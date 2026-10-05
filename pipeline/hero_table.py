"""Hero stats table with per-cell change history.

Columns follow the user's original Google Sheet (Damage / Melee / Vitality /
Mobility) plus Spirit and a few fields the sheet lacked. Every column is a
pure function of (hero, weapon, level info) evaluated on EVERY build that
changed heroes.vdata or abilities.vdata, so computed columns (DPS, max bullet
damage) get a history too.

    python -m pipeline.hero_table   ->  data/tables/heroes.json
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from typing import Callable

from . import cache, loc, tracker
from .semantics import UNITS_PER_METER

OUT = tracker.ROOT / 'data' / 'tables' / 'heroes.json'
WATCH = (tracker.SCRIPTS + 'heroes.vdata', tracker.SCRIPTS + 'abilities.vdata')
PLAYABLE_STATES = ('EHeroDevState_Release', 'EHeroDevState_PreRelease')


@dataclass(frozen=True)
class Col:
    key: str
    label: str
    group: str
    fn: Callable
    pol: int = 1            # +1 higher is better, -1 lower is better, 0 neutral
    digits: int = 2
    unit: str = ''
    note: str = ''
    scaling_stat: str = ''  # E-stat name; cell is marked when the hero scales it with spirit

    @property
    def path(self) -> str | None:
        """The game field the column reads (None for a computed one: DPS, reload, bullet speed …): the
        Hero Stats tooltip takes that field's direction from semantics.direction, as the hero page's tags."""
        return getattr(self.fn, 'path', None)


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(str(v).rstrip('m%s'))
    except ValueError:
        return None


def _stat(name):
    def f(h, w, g):
        return _num((h.get('m_mapStartingStats') or {}).get(name))
    f.path = f'm_mapStartingStats.{name}'
    return f


def _lvl(*names, meters=False):
    """A per-boon gain; the first key the hero has (Valve renames them: TECH_ARMOR_DAMAGE_RESIST is
    TECH_RESIST since build 6541 — the column read "—" after it); engine units as metres if asked."""
    def f(h, w, g):
        ups = h.get('m_mapStandardLevelUpUpgrades') or {}
        v = next((_num(ups[n]) for n in names if n in ups), None)
        return v / UNITS_PER_METER if v is not None and meters else v
    f.path = f'm_mapStandardLevelUpUpgrades.{names[-1]}'
    return f


def _wf(name, meters=False):
    def f(h, w, g):
        v = _num(w.get(name)) if w else None
        return v / UNITS_PER_METER if (v is not None and meters) else v
    f.path = f'm_WeaponInfo.{name}'
    return f


def bullet_speed(h, w, g):
    """m/s. Before build 5747 the speed was a curve (m_BulletSpeedCurve) whose points were all equal;
    since then m_flBulletSpeed (audit 2026-10-01: 18 changes of 12 heroes were invisible). Before 5747
    a flat curve wins over a field beside it (Haze: field 8000, curve 30000, and 30000 after 5747);
    after it the field wins — new guns carry a placeholder curve of 22500 (Graves, Silver, Apollo read
    571.5 m/s instead of 635 / 813 / 127)."""
    if not w:
        return None
    field = _num(w.get('m_flBulletSpeed'))
    spline = (w.get('m_BulletSpeedCurve') or {}).get('m_spline') or []
    ys = [_num(pt.get('y')) for pt in spline if isinstance(pt, dict)]
    curve = ys[0] if ys and None not in ys and max(ys) == min(ys) else None
    old_build = _BUILD[0] is not None and _BUILD[0] < CURVE_ERA_END
    v = (curve if curve is not None else field) if old_build or field is None else field
    return v / UNITS_PER_METER if v is not None else None


CURVE_ERA_END = 5747        # the build that replaced m_BulletSpeedCurve with m_flBulletSpeed
_BUILD: list = [None]       # the build evaluate() is looking at (bullet_speed reads it)


def burst_cycle(h, w, g):
    """An omitted m_flIntraBurstCycleTime is 0 (the game's default; build 6711 started writing it)."""
    return (_num(w.get('m_flIntraBurstCycleTime')) or 0.0) if w else None


def _dash(stat: str, ability_prop: str):
    """The hero's own dash time; before build 5706 one shared dash ability (the hero's Innate 1,
    citadel_ability_dash) held it for everyone."""
    def f(h, w, abilities):
        v = _num((h.get('m_mapStartingStats') or {}).get(stat))
        if v is not None or not abilities:
            return v
        aid = (h.get('m_mapBoundAbilities') or {}).get('ESlot_Ability_Innate_1')
        ab = abilities.get(aid) if aid else None
        prop = ((ab or {}).get('m_mapAbilityProperties') or {}).get(ability_prop) if isinstance(ab, dict) else None
        return _num(prop.get('m_strValue')) if isinstance(prop, dict) else None
    f.path = f'm_mapStartingStats.{stat}'
    return f


# a column whose source is missing from the build (the weapon id points at nothing: Valve cut unrevealed
# heroes' kits out of abilities.vdata until their reveal) — a hole in the data, bridged by history_changes;
# an absent FIELD is a real value ("—") and is not bridged
MISSING = 'missing'


PRIMARY_SLOT = 'ESlot_Weapon_Primary'
ALT_SLOT = 'ESlot_Weapon_Secondary'


def weapon_info(hero: dict, abilities: dict, slot: str = PRIMARY_SLOT) -> dict:
    """The weapon numbers of the gun bound to `slot` (the alt fire: ALT_SLOT) — a gun keeps its own under
    m_mapWeaponInfos.primary (m_WeaponInfo before build 6711)."""
    wid = (hero.get('m_mapBoundAbilities') or {}).get(slot)
    ab = abilities.get(wid) if wid else None
    if not isinstance(ab, dict):
        return {}
    infos = ab.get('m_mapWeaponInfos')
    if isinstance(infos, dict) and isinstance(infos.get('primary'), dict):
        return infos['primary']
    return ab.get('m_WeaponInfo') or {}


def boons(hero: dict) -> int:
    levels = hero.get('m_mapLevelInfo') or {}
    return sum(1 for v in levels.values() if isinstance(v, dict) and v.get('m_bUseStandardUpgrade'))


def bullets_per_sec(h, w, g):
    cyc = _num(w.get('m_flCycleTime')) if w else None
    if not cyc:
        return None
    burst = _num(w.get('m_iBurstShotCount')) or 1
    intra = _num(w.get('m_flIntraBurstCycleTime')) or 0
    return burst / ((burst - 1) * intra + cyc)


def dps(h, w, g, at_max=False):
    bps = bullets_per_sec(h, w, g)
    dmg = max_bullet(h, w, g) if at_max else _wf('m_flBulletDamage')(h, w, g)
    pellets = _num(w.get('m_iBullets')) or 1 if w else 1
    if bps is None or dmg is None:
        return None
    return dmg * pellets * bps


def max_bullet(h, w, g):
    dmg = _wf('m_flBulletDamage')(h, w, g)
    per = _lvl('MODIFIER_VALUE_BASE_BULLET_DAMAGE_FROM_LEVEL')(h, w, g) or 0
    return None if dmg is None else dmg + per * boons(h)


def reload_time(h, w, g):
    """Single-bullet reloaders (Abrams): start delay + one bullet, as in the
    original sheet; everyone else: the reload duration."""
    dur = _wf('m_reloadDuration')(h, w, g)
    if dur is None:
        return None
    if w.get('m_bReloadSingleBullets'):
        return (_num(w.get('m_flReloadSingleBulletsInitialDelay')) or 0) + dur
    return dur


def full_reload(h, w, g):
    dur = _wf('m_reloadDuration')(h, w, g)
    if dur is None:
        return None
    if w.get('m_bReloadSingleBullets'):
        clip = _wf('m_iClipSize')(h, w, g) or 0
        return (_num(w.get('m_flReloadSingleBulletsInitialDelay')) or 0) + dur * clip
    return dur


def full_clip(h, w, g):
    clip = _wf('m_iClipSize')(h, w, g)
    bps = bullets_per_sec(h, w, g)
    return clip / bps if clip and bps else None


COLUMNS: tuple[Col, ...] = (
    # --- Damage (weapon) ---
    Col('dps', 'DPS', 'Damage', dps, digits=1, note='Bullet damage × pellets × bullets per second, level 1.'),
    Col('dps_max', 'Max DPS', 'Damage', lambda h, w, g: dps(h, w, g, True), digits=1, note='DPS with every boon.'),
    Col('bullet_dmg', 'Bullet DMG', 'Damage', _wf('m_flBulletDamage'), scaling_stat='EBulletDamage'),
    Col('bullet_dmg_lvl', '+Bullet DMG / boon', 'Damage', _lvl('MODIFIER_VALUE_BASE_BULLET_DAMAGE_FROM_LEVEL'), digits=3),
    Col('bullet_dmg_max', 'Max Bullet DMG', 'Damage', max_bullet),
    Col('clip', 'Ammo', 'Damage', _wf('m_iClipSize'), digits=0, scaling_stat='EClipSize'),
    Col('full_clip', 'Full Clip (s)', 'Damage', full_clip, pol=0),
    # reloads to 2 decimals like the game's panel ("1.0575" was a sum no screen prints; no step of the 31 is lost),
    # fire intervals to 3 (2 dropped 7 real steps: Bebop 0.08 -> 0.084, Haze 0.1 -> 0.105; review 2026-10-05)
    Col('reload', 'Reload (s)', 'Damage', reload_time, pol=-1, digits=2, scaling_stat='EReloadSpeed',
        note='Single-bullet reloaders: start delay + one bullet.'),
    Col('reload_full', 'Full Reload (s)', 'Damage', full_reload, pol=-1, digits=2,
        note='Single-bullet reloaders: start delay + whole clip.'),
    Col('headshot', 'Headshot ×', 'Damage', _wf('m_flCritBonusStart')),
    Col('cycle', 'Fire Interval (s)', 'Damage', _wf('m_flCycleTime'), pol=-1, digits=3),
    Col('bps', 'Bullets / s', 'Damage', bullets_per_sec, scaling_stat='EFireRate'),
    Col('pellets', 'Pellets', 'Damage', _wf('m_iBullets'), digits=0),
    Col('burst', 'Burst', 'Damage', _wf('m_iBurstShotCount'), digits=0),
    Col('burst_cycle', 'Burst Interval (s)', 'Damage', burst_cycle, pol=-1, digits=3),
    Col('bullet_speed', 'Bullet Speed (m/s)', 'Damage', bullet_speed, digits=0),
    Col('bullet_radius', 'Bullet Radius', 'Damage', _wf('m_flBulletRadius')),
    Col('spread', 'Spread', 'Damage', _wf('m_Spread'), pol=-1),
    Col('pellet_spread', 'Pellet Spread', 'Damage', _wf('m_flPelletScatterSpreadFactor'), pol=-1),
    Col('gravity', 'Bullet Gravity', 'Damage', _wf('m_flBulletGravityScale'), pol=0),
    Col('lifetime', 'Bullet Lifetime (s)', 'Damage', _wf('m_flBulletLifetime'), pol=0),
    Col('range', 'Max Range (m)', 'Damage', _wf('m_flRange', True), digits=1),
    Col('falloff_start', 'Falloff Start (m)', 'Damage', _wf('m_flDamageFalloffStartRange', True), digits=1),
    Col('falloff_end', 'Falloff End (m)', 'Damage', _wf('m_flDamageFalloffEndRange', True), digits=1),
    # engine units: Bebop's 59 is 1.5 m, as the 2025-09-04 notes say
    Col('range_lvl', '+Range / boon (m)', 'Damage', _lvl('MODIFIER_VALUE_BONUS_ATTACK_RANGE', meters=True), digits=2),
    # --- Melee ---
    Col('light_melee', 'Light Melee', 'Melee', _stat('ELightMeleeDamage'), scaling_stat='ELightMeleeDamage'),
    Col('melee_lvl', '+Melee / boon', 'Melee', _lvl('MODIFIER_VALUE_BASE_MELEE_DAMAGE_FROM_LEVEL'), digits=3),
    Col('heavy_melee', 'Heavy Melee', 'Melee', _stat('EHeavyMeleeDamage'), scaling_stat='EHeavyMeleeDamage'),
    # --- Vitality ---
    Col('hp', 'Health', 'Vitality', _stat('EMaxHealth'), digits=0, scaling_stat='EMaxHealth'),
    Col('hp_lvl', '+HP / boon', 'Vitality', _lvl('MODIFIER_VALUE_BASE_HEALTH_FROM_LEVEL')),
    Col('hp_regen', 'HP Regen', 'Vitality', _stat('EBaseHealthRegen'), scaling_stat='EBaseHealthRegen'),
    Col('bullet_resist', 'Bullet Resist', 'Vitality', _stat('EBulletArmorDamageReduction'), scaling_stat='EBulletArmorDamageReduction'),
    Col('bullet_resist_lvl', '+Bullet Resist / boon', 'Vitality', _lvl('MODIFIER_VALUE_BULLET_ARMOR_DAMAGE_RESIST')),
    Col('spirit_resist', 'Spirit Resist', 'Vitality', _stat('ETechArmorDamageReduction'), scaling_stat='ETechArmorDamageReduction'),
    Col('spirit_resist_lvl', '+Spirit Resist / boon', 'Vitality',
        _lvl('MODIFIER_VALUE_TECH_ARMOR_DAMAGE_RESIST', 'MODIFIER_VALUE_TECH_RESIST')),
    Col('headshot_taken', 'Headshot Taken ×', 'Vitality', _stat('ECritDamageReceivedScale'), pol=-1),
    Col('collision_r', 'Collision Radius', 'Vitality', lambda h, w, g: _num(h.get('m_flCollisionRadius')), pol=-1,
        note='Removed from hero data in later builds; history ends there.'),
    Col('collision_h', 'Collision Height', 'Vitality', lambda h, w, g: _num(h.get('m_flCollisionHeight')), pol=-1),
    # --- Mobility ---
    # the unit in the label, like the gun's columns: the page puts it on the number (review 2026-10-05: "Crouch
    # Speed 4.75", "Stamina Regen 0.222" bare)
    Col('move', 'Move Speed (m/s)', 'Mobility', _stat('EMaxMoveSpeed'), scaling_stat='EMaxMoveSpeed'),
    Col('sprint', 'Sprint (m/s)', 'Mobility', _stat('ESprintSpeed'), scaling_stat='ESprintSpeed'),
    Col('stamina', 'Stamina', 'Mobility', _stat('EStamina'), digits=0, scaling_stat='EStamina'),
    Col('stamina_regen', 'Stamina Regen (/s)', 'Mobility', _stat('EStaminaRegenPerSecond'), digits=3, scaling_stat='EStaminaRegenPerSecond'),
    Col('crouch', 'Crouch Speed (m/s)', 'Mobility', _stat('ECrouchSpeed')),
    Col('ground_dash', 'Ground Dash (s)', 'Mobility', _dash('EGroundDashDuration', 'AbilityDuration'), pol=-1),
    Col('air_dash', 'Air Dash (s)', 'Mobility', _dash('EAirDashDuration', 'AirDashTravelTime'), pol=-1),
    # --- Spirit ---
    Col('spirit_lvl', '+Spirit / boon', 'Spirit', _lvl('MODIFIER_VALUE_TECH_POWER')),
)


# The alt fire (the gun bound to ESlot_Weapon_Secondary: Viscous' goo ball, Shiv's, Yamato's, Skyrunner's): the gun's
# columns that read the weapon alone — per-boon growth (Max DPS, +Bullet DMG / boon, +Range / boon) is the hero's —
# and what one alt shot costs of the clip (m_iAmmoConsumedPerShot: Viscous 5, Yamato 3). The weapon block showed only
# a slim "Alt fire" line: neither heroes.json nor abilities.json carried its numbers (review 2026-10-05).
ALT_KEYS = ('dps', 'bullet_dmg', 'pellets', 'bps', 'cycle', 'burst', 'burst_cycle', 'clip', 'reload', 'reload_full',
            'headshot', 'bullet_speed', 'range', 'falloff_start', 'falloff_end')
ALT_COLUMNS: tuple[Col, ...] = tuple(c for c in COLUMNS if c.key in ALT_KEYS) + (
    Col('ammo_shot', 'Ammo / Shot', 'Damage', _wf('m_iAmmoConsumedPerShot'), pol=-1, digits=0,
        note='Ammo one alt shot takes from the clip.'),
)


def _round(v, digits):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return None
    return round(v, max(digits, 3) + 1)


def borrowed_guns(heroes: dict) -> set[str]:
    """Heroes whose primary weapon another hero owns: a gun bound by several heroes belongs to the one
    its id names (citadel_weapon_inferno_set -> hero_inferno); the rest borrow it as a stand-in
    (heroes in development showed Infernus' DPS 52.38 as theirs)."""
    by_gun: dict[str, list[str]] = {}
    for hid, h in heroes.items():
        if hid.startswith('hero_') and isinstance(h, dict) and not h.get('_not_pickable'):
            gun = (h.get('m_mapBoundAbilities') or {}).get('ESlot_Weapon_Primary')
            if gun:
                by_gun.setdefault(gun, []).append(hid)
    out = set()
    for gun, hids in by_gun.items():
        owner = next((h for h in hids if f'_{h[5:]}_' in f'_{gun}_'), None)
        if len(hids) > 1 and owner:
            out |= {h for h in hids if h != owner}
    return out


def evaluate(hero: dict, abilities: dict, build: int | None = None, borrowed: bool = False) -> dict:
    """Every column for one hero at one build; a borrowed gun (borrowed_guns) counts as no gun."""
    _BUILD[0] = build
    w = weapon_info(hero, abilities)
    wid = (hero.get('m_mapBoundAbilities') or {}).get('ESlot_Weapon_Primary')
    weapon_cut = (bool(wid) and not isinstance(abilities.get(wid), dict)) or borrowed
    return {c.key: MISSING if weapon_cut and c.group == 'Damage' else _value(c, hero, w, abilities) for c in COLUMNS}


def _value(c: Col, hero: dict, w: dict, abilities: dict):
    try:
        return _round(c.fn(hero, w, abilities), c.digits)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def evaluate_alt(hero: dict, abilities: dict, build: int | None = None, borrowed: bool = False) -> dict | None:
    """Every ALT_COLUMNS value of the hero's alt fire at one build; None when it binds none. An alt fire the build
    cut from abilities.vdata, or one that comes with a borrowed gun (`evaluate`), is MISSING (bridged like the
    gun's): a stand-in's numbers are not the hero's."""
    aid = (hero.get('m_mapBoundAbilities') or {}).get(ALT_SLOT)
    if not aid:
        return None
    _BUILD[0] = build
    if borrowed or not isinstance(abilities.get(aid), dict):
        return {c.key: MISSING for c in ALT_COLUMNS}
    w = weapon_info(hero, abilities, ALT_SLOT)
    return {c.key: _value(c, hero, w, abilities) for c in ALT_COLUMNS}


def _add_point(series: dict[str, list], vals: dict, b) -> None:
    for k, v in vals.items():
        pts = series.setdefault(k, [])
        if not pts or pts[-1][2] != v:
            pts.append([b.build, b.date[:10], v])


def _history(series: dict[str, list]) -> dict[str, list]:
    return {k: ch for k, pts in series.items() for ch in [history_changes(pts)] if ch}


def _now(series: dict[str, list]) -> dict:
    return {k: (None if pts[-1][2] == MISSING else pts[-1][2]) for k, pts in series.items()}


def history_changes(pts: list[list]) -> list[list]:
    """[[build, date, value], …] -> [[build, date, old, new], …]. A stretch whose source is MISSING
    from the build (Billy's weapon cut from abilities.vdata, builds 5747-5788) is a hole in the data:
    it bridges into one old -> new on the build where the source returned (none if unchanged). An
    absent field (None) is a real state — a stat removed and later restored is two changes with their
    own dates (audit 2026-10-01: bridging those hid 54 item events). MISSING at the end reads as gone."""
    kept = [p for p in pts if p[2] != MISSING]
    if pts and pts[-1][2] == MISSING and kept and kept[-1][2] is not None:
        kept.append([pts[-1][0], pts[-1][1], None])
    out = []
    for prev, cur in zip(kept, kept[1:]):
        if prev[2] != cur[2]:
            out.append([cur[0], cur[1], prev[2], cur[2]])
    return out


def _sort_name(tok: dict[str, str], hero: dict, hid: str) -> str:
    """'#hero_doorman_sort' -> 'Doorman' (localized); heroes without one sort by their name."""
    key = str(hero.get('m_strHeroSortName') or '').lstrip('#').lower()
    return tok.get(key) or loc.hero_name(tok, hid)


def spirit_scaled(hero: dict) -> list[str]:
    stats = hero.get('m_mapScalingStats') or {}
    keys = []
    for c in COLUMNS:
        if c.scaling_stat and c.scaling_stat in stats:
            keys.append(c.key)
    return keys


def scaling_detail(hero: dict) -> dict:
    out = {}
    for stat, v in (hero.get('m_mapScalingStats') or {}).items():
        if isinstance(v, dict):
            out[stat] = _num(v.get('flScale'))
    return out


def snapshots():
    """Yield (build, heroes, abilities) for every build that changed a watched file."""
    last = (None, None)
    for b in tracker.builds():
        if b.build is None:
            continue
        if last != (None, None) and not any(p in b.files for p in WATCH):
            continue
        blobs = tuple(tracker.blob_id(b.commit, p) for p in WATCH)
        if blobs == last or None in blobs:
            continue
        last = blobs
        yield b, cache.vdata_blob(blobs[0]), cache.vdata_blob(blobs[1])


def build() -> dict:
    t0 = time.time()
    series: dict[str, dict[str, list]] = {}    # hero -> col -> [[build, date, value], ...]
    alt_series: dict[str, dict[str, list]] = {}    # the same for the hero's alt fire (ALT_COLUMNS)
    first_seen: dict[str, list] = {}
    last_heroes: dict = {}
    last_abilities: dict = {}
    last_build = None
    for b, heroes, abilities in snapshots():
        borrowed = borrowed_guns(heroes)
        for hid, hero in heroes.items():
            if not hid.startswith('hero_') or not isinstance(hero, dict) or hero.get('_not_pickable'):
                continue
            vals = evaluate(hero, abilities, b.build, hid in borrowed)
            first_seen.setdefault(hid, [b.build, b.date[:10]])
            _add_point(series.setdefault(hid, {}), vals, b)
            alt = evaluate_alt(hero, abilities, b.build, hid in borrowed)
            if alt is not None or hid in alt_series:
                # no alt fire at this build after one: its numbers are gone (None), not bridged
                _add_point(alt_series.setdefault(hid, {}), alt or {c.key: None for c in ALT_COLUMNS}, b)
        last_heroes, last_abilities, last_build = heroes, abilities, b
    tok = loc.tokens(last_build.commit)
    rows = []
    for hid, hero in sorted(last_heroes.items()):
        if not hid.startswith('hero_') or not isinstance(hero, dict):
            continue
        state = hero.get('m_eHeroDevelopmentState')
        if state not in PLAYABLE_STATES:
            continue
        hs = series.get(hid, {})
        history = _history(hs)
        wid = (hero.get('m_mapBoundAbilities') or {}).get('ESlot_Weapon_Primary')
        alt_id = (hero.get('m_mapBoundAbilities') or {}).get(ALT_SLOT)
        alt_hs = alt_series.get(hid) if alt_id else None
        rows.append({
            'id': hid,
            'name': loc.hero_name(tok, hid),
            'state': 'prerelease' if state == 'EHeroDevState_PreRelease' else 'release',
            'type': str(hero.get('m_eHeroType') or '').rsplit('_', 1)[-1],      # ECitadelHeroType_Marksman
            'complexity': hero.get('m_nComplexity'),
            # the hero grid's order in the game: the sort name ("The Doorman" sorts under D)
            'sort_name': _sort_name(tok, hero, hid),
            'new_player': str(hero.get('m_bNewPlayerRecommended')).lower() in ('true', '1'),
            'color': hero.get('m_colorUI'),          # the hero's UI colour: the name plate on the heroes index
            'weapon': wid,
            'weapon_name': loc.plain(loc.entity_name(tok, wid, hid)) if wid else None,
            'first_seen': first_seen.get(hid),
            'values': _now(hs),
            'history': history,
            'spirit_scaled': spirit_scaled(hero),
            'scaling': scaling_detail(hero),
            # the alt fire's numbers today and their history (ALT_COLUMNS); only a hero that binds one has it
            **({'alt': {'weapon': alt_id, 'values': _now(alt_hs), 'history': _history(alt_hs)}} if alt_hs else {}),
        })
    # the table is as of the newest game build, like Items and Units (it said "build 6742" beside their 6746: the
    # last build that changed a hero file, review 2026-10-05); that build is kept apart
    head = tracker.head_build()
    data = {
        'build': head.build or last_build.build,
        'date': head.date if head.build else last_build.date,
        'unchanged_since': last_build.build,
        'columns': [
            {'key': c.key, 'label': c.label, 'group': c.group, 'pol': c.pol, 'digits': c.digits, 'note': c.note}
            for c in COLUMNS
        ],
        'alt_columns': [
            {'key': c.key, 'label': c.label, 'group': c.group, 'pol': c.pol, 'digits': c.digits, 'note': c.note}
            for c in ALT_COLUMNS
        ],
        'heroes': sorted(rows, key=lambda r: r['name'].lower()),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'{len(rows)} heroes, {len(COLUMNS)} columns, {time.time() - t0:.0f}s -> {OUT}')
    return data


if __name__ == '__main__':
    build()
