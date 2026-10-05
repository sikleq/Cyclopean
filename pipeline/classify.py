"""Classify diffed fields into categories and entities into kinds.

Categories (what kind of change a field path represents):
  availability — enabled/disabled/in-development flags (item left the shop, hero released)
  balance      — a number that affects gameplay (values, scaling, costs, tiers)
  mechanic     — non-numeric gameplay data (flags, enums, classes, new/removed props)
  meta         — testing/recommendation flags, hero role/tags, template links
  streetbrawl  — values that only apply in the Street Brawl mode (incl. item draft weights)
  technical    — engine plumbing: scale-function wiring, pre-cast state bits, curve spline points
                 (a modifier's m_nEnabledStateMask is a mechanic: pipeline.flags)
  ui           — tooltip layout, CSS classes, display units, shop/stat panels
  visual       — particles, models, materials, images, colours, animations, camera
  audio        — sounds, voice lines, music
"""
from __future__ import annotations

import re

AUDIO_RE = re.compile(r'(Sound|[Vv][Oo](?:[A-Z_]|$)|Music|Audio|Voice|m_strLastHit|(?<!Reduce)Footstep|'
                      r'm_sSelfDestruct(Start|End)|BulletWhiz)')
# Light / Effect / Model also start gameplay words: LightMelee*, *Effectiveness, ModelScaleGrowth (a
# hero grows bigger) — 77 gameplay rows read as visual and lost their values (audit 2026-10-01)
VISUAL_RE = re.compile(
    r'(Particle|Material|Model(?!Scale)|Image|Icon|[Cc]olor|Anim|Decal|Effect(?!iveness)|Glow|Tracer|Muzzle|'
    r'Screen(?!ing)|Skin|Camera|Shake|Light(?!ning|Melee)|Vfx|VFX|Mesh|Cosmetic|Outline|Render|Tint|'
    r'Pose|Attachment|Bodygroup|Ragdoll|Gib|Portrait|Logo|Emblem|Sprite|[Ff][Oo][Vv]|Movie|Video|m_h[A-Z]|m_particle|DOF|'
    r'Desat|RangeRing|Dying|DeathFade|BreakableForce)'
)
UI_RE = re.compile(
    r'(Tooltip|m_strCSSClass|DisplayUnit|m_heroStatsUI|m_heroStatsDisplay|m_ShopStatDisplay|'
    r'UIOrder|m_bCanSetTokenOverride|m_strDisableValue|ImportantProperty|m_eStatsUsageFlags|'
    r'LocString|Localiz|m_strHeroSortName|m_strHeroSearchName|m_strHeroGender|Shopping|'
    r'Postgame|TopBar|Minimap|m_strUI|Hint|Keybind|m_strLoc|Description|m_bShowIn|m_bHideIn|'
    r'm_strAbilityHint|SortOrder|m_nSortIndex|m_eDisplay|m_strDisplay|m_bDisplay|StackLabel|m_strLabel)'
)


AVAILABILITY_RE = re.compile(
    r'(^|\.)(m_bDisabled|m_bInDevelopment|m_eHeroDevelopmentState|m_bPlayerSelectable|'
    r'm_vecDisabledOnHeroes|m_bBotSelectable|m_bAvailableInStreetBrawl|m_bPrereleaseOnly|'
    r'm_bAssignedPlayersOnly)$')
META_RE = re.compile(
    r'(^|\.)(m_bNeedsTesting|m_bLimitedTesting|m_bLaneTestingRecommended|m_bNewPlayerRecommended|'
    r'm_nComplexity|m_eHeroType|m_vecHeroTags|m_strGunTag|m_HeroID|_base|_multibase|_not_pickable)$')
# the camera's own motion; a gun's recoil moves the aim (gameplay) and Viscous' Puddle Punch is an ability
CAMERA_RE = re.compile(r'camera|viewpunch|(vertical|horizontal)punch|punchangle|viewkick|shake', re.I)


STREET_BRAWL_RE = re.compile(r'StreetBrawl|ItemDraft', re.I)

# Engine plumbing that changes with refactors but carries no balance meaning:
# scale-function wiring, state bit masks, property-type plumbing, spline
# internals of curves (the gameplay value, e.g. m_flBulletSpeed, is kept).
TECHNICAL_RE = re.compile(
    r'((^|\.)(_class|_my_subclass_name)$|m_vecScriptEventHandlers|m_vecScriptValues(?!.*m_value$)|'
    # a modifier's state mask is not here: "ignored by NPC targeting", "unstoppable" are gameplay
    # (pipeline.flags says which states, external audit 2026-10-04)
    r'm_bits\w*Mask|m_UsageFlags|m_ValueType|'
    r'm_strCancelAbilityKey|m_vecAutoRegisterModifierValueFromAbilityPropertyName|m_AutoIntrinsicModifiers|'
    r'm_strAG2SourceName|m_nShopVersion|m_strSelectionNameOverride|m_eShopFilters|m_eAdditionalShopFilters|'
    r'm_strDisableItemTarget|m_strPropertyName$|'
    r'Curve\.|m_spline|m_flSlope|flPercentOnGraph|m_vDomainM(in|ax)s|\.(x|y)$|'
    r'm_strContext$|m_strModifierContext|_editor)')
UI_EXTRA_RE = re.compile(
    r'((^|\.)m_bIsHidden$|m_bIsAbilityDamageProperty|m_bIsNegativeAttribute|m_eHudDisplayLocation|'
    r'm_eDrawOverheadStatus|m_strHudMessageText|m_eModifierDisplayLocai?ti?on|m_sMiniMapCssClass|'
    r'm_vecAlwaysShowInStatModifierUI|m_strSubCastUICSSClass|m_strConditionalLocTokenOverride)')
VISUAL_EXTRA_RE = re.compile(
    r'(m_CustomCrosshairSettings|m_DOFWhileZoomed|m_flFade|m_flChaseCam|m_vFinishOffset|m_flOrbSpawnOffsetZ|'
    r'm_strAG2|m_AG2|m_sAG2|HitReactClips|MovementBlockedClips|m_strVoteSticker|Readability|'
    # the screen flash when you take damage (generic_data m_mapDamageFlash: coverage, brightness…),
    # where a gun's bullets leave the model: 30-odd rows read as balance (audit 2026-10-01)
    r'^EFlashType_|m_vecOriginOffsets)')
# fields players never see as gameplay (audit 2026-10-01): HUD placement, presence text, unit name
# keys, collision hulls, the flight physics of soul orbs, what NPCs (not heroes) can see
UI_MORE_RE = re.compile(r'(RichPresence|m_eHudStyle|HudStyle|m_nNameOffset|HealthBarOffset|m_strLocUnitName|'
                        r'm_sLocUnitName|NameOffset|m_bIsHiddenOverhead|vOffset2D|HudSharedStyle|LocToken|'
                        r'SecondaryStatName|CrosshairCSSClass|SpectatePriority|ShowTargetingPreview|'
                        r'ReverseHudProgressBar|LowAmmoIndicator)')
META_EXTRA_RE = re.compile(r'(m_iUpdateTime|m_Recommended)')
TECH_EXTRA_RE = re.compile(r'((^|\.)(m_eScaleStatFilter|m_eUpgradeType)$|m_flHullCapsuleRadius|m_flSightRangeNPCs|'
                           r'm_flBurstSpeedDuration|m_flOrbSpawnDelayM(in|ax)|m_vecDependentAbilities|'
                           # physics / netcode / NPC steering, not a number a player plays against
                           # (a heavy melee's turn rate is how far a swing can be steered: gameplay)
                           r'DamageForce|MaxLagCompensation|HullCapsule|ClipCapsule|navHull|Squad|Strafe|'
                           r'(?<!HeavyMeleeMax)TurnRate|'
                           # the number that keys a table row (flatten.NUMERIC_ID_FIELDS) is the row's name
                           r'\{\d+\}\.(nGoldThreshold|m_nTier)$|'
                           # an editor check ("warn the designer if no ability is affected"), shown as NEW
                           # on five headshot items in 2026-01-30
                           r'm_bWarnIfNoAffectedAbilities)')


# whole entries that are scenery or presentation, not something a player plays with: the city's traffic
# and glass panes in misc.vdata, the team colours, minimap offsets, district names and timer placement in
# generic_data (coverage audit 9, 2026-10-04: 97 of City Never Sleeps' 226 "REMOVED" were these, and the
# colours / minimap rows came in as hidden NEW)
# (coverage audit, Game section 2026-10-05: the outline and objective colours, the healing sounds and the damage
# indicator's look were "Other rules" on the Game pages)
DECOR_ID_RE = re.compile(r'^(?:vehicle_|citadel_base_glass_)|^m_(?:Color[A-Z]|MiniMap|OutlineColor)|'
                         r'^m_enemy[A-Za-z]*Color$|^m_HealingReceivedSounds$|^m_mapDamageIndicatorParamSets$|'
                         r'Localization$|TimerHeight$|TimerShowDistance$|TextDuration$|EffectStaggerInterval$')


def decor_entity(eid: str) -> bool:
    return bool(DECOR_ID_RE.search(eid or ''))


def _zero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) == 0.0


# what a value scales with / which stat it feeds: a CHANGE is a real one ("Damage now scales with light
# melee damage", "Regen instead of max health": 273 rows hidden as technical); adding or removing the
# wiring alongside a new property is scaffolding
WIRING_RE = re.compile(r'(m_eSpecificStatScaleType|m_vecScalingStats|m_eProvidedPropertyType)')
# the shape of a value says what it is, whatever the field's name (audit 2026-10-01)
SOUND_VALUE = re.compile(r'^[A-Z][A-Za-z0-9]*(\.[A-Za-z0-9_]+){1,5}$')        # Ability.Bebop.Hook.ImpactGeo
FILE_VALUE = re.compile(r'(\.(vcss|vpcf|vmdl|vsnd|vtex|vmat|vxml|xml|png|psd|vjs)\b|file://|^panorama/)', re.I)
LOC_KEY_VALUE = re.compile(r'^#[A-Za-z]\w+$')                                   # #AbilityButtonHint_AltCast
UNIX_TIME = (1.2e9, 2.5e9)                                                    # "Added Time 1737133200"
_NUMISH = re.compile(r'^\s*[-+]?(\d+\.?\d*|\.\d+)\s*(m|s|%|u)?\s*$')


def _value_kind(v) -> str | None:
    if isinstance(v, str):
        if FILE_VALUE.search(v):
            return 'ui' if '.vcss' in v.lower() else 'visual'
        if LOC_KEY_VALUE.match(v):
            return 'ui'
        if SOUND_VALUE.match(v) and not v.isupper():
            return 'audio'
    return None


def category(path: str, old, new) -> str:
    if STREET_BRAWL_RE.search(path):
        return 'streetbrawl'
    if TECHNICAL_RE.search(path) or TECH_EXTRA_RE.search(path):
        return 'technical'
    if UI_EXTRA_RE.search(path) or UI_MORE_RE.search(path):
        return 'ui'
    if VISUAL_EXTRA_RE.search(path):
        return 'visual'
    if META_EXTRA_RE.search(path):
        return 'meta'
    # a property added with value 0 (or a 0 removed) is scaffolding for an upgrade
    if (old is None and _zero(new)) or (new is None and _zero(old)):
        return 'technical'
    if WIRING_RE.search(path):
        return 'mechanic' if old is not None and new is not None else 'technical'
    shape = _value_kind(new) or _value_kind(old)
    if shape:
        return shape
    if 'Time' in path and any(isinstance(v, (int, float)) and not isinstance(v, bool)
                              and UNIX_TIME[0] < float(v) < UNIX_TIME[1] for v in (old, new)):
        return 'meta'
    if AVAILABILITY_RE.search(path):
        return 'availability'
    if META_RE.search(path):
        return 'meta'
    if CAMERA_RE.search(path):
        return 'visual'
    if AUDIO_RE.search(path):
        return 'audio'
    if VISUAL_RE.search(path):
        return 'visual'
    if UI_RE.search(path):
        return 'ui'
    if _is_num(old) or _is_num(new):
        return 'balance'
    return 'mechanic'


def _is_num(v) -> bool:
    """A number — also as the records store one with its unit ("20m", "2s"): enrich re-derives the
    category from the JSON, and "20m" read as text filed 986 balance rows as mechanics (audit 2026-10-01)."""
    if isinstance(v, bool):
        return False
    return isinstance(v, (int, float)) or (isinstance(v, str) and bool(_NUMISH.match(v)))


# ---- entity kinds -------------------------------------------------------

TEMPLATE_HEROES = ('hero_base', 'hero_genericperson', 'hero_targetdummy', 'hero_testhero')
_OWN_PREFIX = re.compile(r'^(?:citadel_)?(?:ability|weapon)_(?:melee_)?([a-z0-9]+)_')
# a shared ability needs at least this many heroes binding it, whatever the roster's size (a test
# build with two heroes must not make each one's kit "everybody's")
SHARED_MIN_BINDERS = 3


def _real_heroes(heroes: dict) -> list[tuple[str, dict]]:
    """Heroes a player can be, in file order: not the templates (hero_base…) nor `_not_pickable`."""
    return [(hid, h) for hid, h in heroes.items() if isinstance(h, dict) and hid.startswith('hero_')
            and hid not in TEMPLATE_HEROES and not h.get('_not_pickable')]


def shared_abilities(heroes: dict) -> set[str]:
    """Abilities more than half of the real heroes bind: jump, dash, mantle, slide, sprint, the zipline,
    parry, the voting poster… They belong to every hero, so to none of them. The first real hero in the
    file (Infernus) had taken all of them, and 135 of the 295 rows on his page were game-wide changes
    (audit 2026-10-04). A hero's own gun or melee is bound by one hero, or a few stand-ins."""
    real = _real_heroes(heroes)
    binders: dict[str, int] = {}
    for _, hero in real:
        for ab in {a for a in (hero.get('m_mapBoundAbilities') or {}).values() if isinstance(a, str) and a}:
            binders[ab] = binders.get(ab, 0) + 1
    return {ab for ab, n in binders.items() if n >= SHARED_MIN_BINDERS and n * 2 > len(real)}


def hero_bound_abilities(heroes: dict, abilities: dict | None = None) -> dict[str, str]:
    """{ability_id: hero_id} from every hero's m_mapBoundAbilities — real heroes first: the
    templates (hero_base…) bind defaults too, and hero_base, first in the file, had taken Infernus'
    gun and melee (audit 2026-10-01). With `abilities`, a sub-ability no hero binds (a recast, an
    ultimate's second part: 112 orphans of Silver, Venator, Drifter…) goes to the hero its id names
    ('ability_werewolf_x' -> hero_werewolf). A shared ability (`shared_abilities`) has no owner."""
    owner: dict[str, str] = {}
    shared = shared_abilities(heroes)
    heroes_ = [(hid, h) for hid, h in heroes.items() if isinstance(h, dict) and hid.startswith('hero_')]
    template = lambda hid, h: hid in TEMPLATE_HEROES or bool(h.get('_not_pickable'))     # noqa: E731
    for hid, hero in sorted(heroes_, key=lambda kv: template(*kv)):       # stable: file order otherwise
        for ab in (hero.get('m_mapBoundAbilities') or {}).values():
            if isinstance(ab, str) and ab and ab not in shared:
                owner.setdefault(ab, hid)
    if abilities:
        codes = {hid[5:]: hid for hid, h in heroes_ if not template(hid, h)}
        for aid in abilities:
            m = _OWN_PREFIX.match(aid) or _BARE_PREFIX.match(aid)
            if aid not in owner and aid not in shared and m and m.group(1) in codes:
                owner[aid] = codes[m.group(1)]
        for aid in abilities:
            if aid not in owner and aid not in shared:
                parent = sub_ability_parent(aid, owner)
                if parent:
                    owner[aid] = owner[parent]
    return owner


# a hero's kit in development names its abilities after the hero's code, bare: 'slork_scald', 'tokamak_hot_shot',
# 'cadence_ability_lullaby' (coverage finding 6: 2024 kits sat in Game › Abilities with no hero)
_BARE_PREFIX = re.compile(r'^([a-z0-9]+)_')
# the second part of an ability: its trigger, cancel or teleport (Frozen Shelter's 'ability_ice_dome_trigger',
# McGinnis' 'citadel_ability_fissure_wall_cancel', Drifter's 'drifter_shadow_mark_teleport' — Ambush)
_SUB_SUFFIX = re.compile(r'_(?:cancel_trigger|cancel|trigger|teleport|recast)$')


def sub_ability_parent(aid: str, owner: dict[str, str]) -> str | None:
    """The owned ability `aid` is a part of ('ability_ice_dome_trigger' -> 'ability_ice_dome'), or None."""
    base = aid
    while True:
        m = _SUB_SUFFIX.search(base)
        if not m:
            return None
        base = base[:m.start()]
        if base in owner:
            return base


def unit_bound_abilities(units: dict, owners: dict[str, str] | None = None,
                         shared: set[str] | frozenset[str] = frozenset()) -> dict[str, list[str]]:
    """{ability_id: [unit ids]} from the NPCs' m_mapBoundAbilities: Walker's Stomp / Laser Beam /
    Rocket Barrage, Patron's gun. They are the unit's, not a player's: UP/DOWN like the unit, shown on
    its page (audit B10: 120 rows tagged BUFF/NERF from the boss's side, on no unit page). An ability a
    hero binds too (the zipline a container lends) stays the hero's — or every hero's (`shared`)."""
    out: dict[str, set[str]] = {}
    for uid, unit in units.items():
        if not isinstance(unit, dict):
            continue
        for ab in (unit.get('m_mapBoundAbilities') or {}).values():
            if isinstance(ab, str) and ab and ab not in (owners or {}) and ab not in shared:
                out.setdefault(ab, set()).add(uid)
    return {ab: sorted(us) for ab, us in out.items()}


def ability_kind(aid: str, data: dict, owners: dict[str, str],
                 shared: set[str] | frozenset[str] = frozenset()) -> str:
    cls = str(data.get('_class', '')) if isinstance(data, dict) else ''
    if aid.startswith('upgrade_') or cls == 'citadel_item' or 'm_iItemTier' in (data or {}):
        return 'item'
    if aid in shared:
        return 'shared'          # every hero's: jump, dash, mantle, slide, zipline, parry (no owner)
    if 'weapon' in cls or aid.startswith('citadel_weapon_'):
        return 'weapon'
    if aid.startswith('ability_melee') or 'melee' in cls:
        return 'melee'
    if aid in owners:
        return 'ability'
    return 'ability_other'


_BUILDING_WORDS = ('guard', 'walker', 'boss', 'barrack', 'shrine', 'patron', 'titan', 'base_defense', 'tower',
                   'destroyable')


_GAMEPLAY = ('balance', 'mechanic', 'availability')


def unit_is_helper(uid: str, data: dict) -> bool:
    """A unit entry nobody fights or tunes (owner asked to sort them out, 2026-10-01): the Hideout's
    toys (basketball, clock, target spawner), the bots' brain, and entries that carry only looks —
    a model, particles, sounds — for an ability or a map prop (Paradox's time wall, the bounce pad,
    an animated cat). Abilities do not name them (the code spawns them by class), so their own
    fields decide: not one gameplay field means a helper."""
    from .flatten import flatten
    cls = str(data.get('_class', '')) if isinstance(data, dict) else ''
    if 'hideout' in f'{uid} {cls}'.lower() or 'bot_brain' in uid:
        return True
    if not isinstance(data, dict) or not data:
        return False                           # nothing left to judge (a removed unit)
    return not any(category(p, None, v) in _GAMEPLAY for p, v in flatten(data).items())


def unit_kind(uid: str, data: dict) -> str:
    """The id decides before the class: neutral camps and Guardians are npc_trooper
    subclasses in the data ('neutral_lantern_weak', 'npc_boss_tier1'), yet neither is a trooper."""
    cls = str(data.get('_class', '')) if isinstance(data, dict) else ''
    u = uid.lower()
    if u.startswith('npc_super_neutral'):
        return 'neutral'                       # Mid Boss: a neutral objective
    if any(k in u for k in _BUILDING_WORDS):
        return 'building'
    if u.startswith(('neutral_', 'npc_neutral_')):
        return 'neutral'
    s = f'{u} {cls}'.lower()
    if 'trooper' in s:
        return 'trooper'
    if 'neutral' in s:
        return 'neutral'
    if any(k in s for k in _BUILDING_WORDS):
        return 'building'
    return 'unit'
