"""Classify diffed fields into categories and entities into kinds.

Categories (what kind of change a field path represents):
  availability — enabled/disabled/in-development flags (item left the shop, hero released)
  balance      — a number that affects gameplay (values, scaling, costs, tiers)
  mechanic     — non-numeric gameplay data (flags, enums, classes, new/removed props)
  meta         — testing/recommendation flags, hero role/tags, template links
  streetbrawl  — values that only apply in the Street Brawl mode (incl. item draft weights)
  technical    — engine plumbing: scale-function wiring, state masks, curve spline points
  ui           — tooltip layout, CSS classes, display units, shop/stat panels
  visual       — particles, models, materials, images, colours, animations, camera
  audio        — sounds, voice lines, music
"""
from __future__ import annotations

import re

AUDIO_RE = re.compile(r'(Sound|[Vv][Oo](?:[A-Z_]|$)|Music|Audio|Voice|m_strLastHit|Footstep)')
VISUAL_RE = re.compile(
    r'(Particle|Material|Model|Image|Icon|[Cc]olor|Anim|Decal|Effect|Glow|Tracer|Muzzle|'
    r'Screen(?!ing)|Skin|Camera|Shake|Light(?!ning)|Vfx|VFX|Mesh|Cosmetic|Outline|Render|Tint|'
    r'Pose|Attachment|Bodygroup|Ragdoll|Gib|Portrait|Logo|Emblem|Sprite|Fov|Movie|Video|m_h[A-Z]|m_particle|DOF)'
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
CAMERA_RE = re.compile(r'camera|recoil|punch|viewkick|shake', re.I)


STREET_BRAWL_RE = re.compile(r'StreetBrawl|ItemDraft', re.I)

# Engine plumbing that changes with refactors but carries no balance meaning:
# scale-function wiring, state bit masks, property-type plumbing, spline
# internals of curves (the gameplay value, e.g. m_flBulletSpeed, is kept).
TECHNICAL_RE = re.compile(
    r'((^|\.)(_class|_my_subclass_name)$|m_vecScript(Values|EventHandlers)|m_eSpecificStatScaleType|m_vecScalingStats|'
    r'm_bits\w*Mask|m_nEnabledStateMask|m_UsageFlags|m_eProvidedPropertyType|m_ValueType|'
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
    r'm_strAG2|m_AG2|m_sAG2|HitReactClips|MovementBlockedClips|m_strVoteSticker|Readability)')
# fields players never see as gameplay (audit 2026-10-01): HUD placement, presence text, unit name
# keys, collision hulls, the flight physics of soul orbs, what NPCs (not heroes) can see
UI_MORE_RE = re.compile(r'(RichPresence|m_eHudStyle|HudStyle|m_nNameOffset|HealthBarOffset|m_strLocUnitName|'
                        r'm_sLocUnitName|NameOffset)')
META_EXTRA_RE = re.compile(r'(m_iUpdateTime|m_Recommended)')
TECH_EXTRA_RE = re.compile(r'((^|\.)(m_eScaleStatFilter|m_eUpgradeType)$|m_flHullCapsuleRadius|m_flSightRangeNPCs|'
                           r'm_flBurstSpeedDuration|m_flOrbSpawnDelayM(in|ax)|m_vecDependentAbilities)')


def _zero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) == 0.0


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
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ---- entity kinds -------------------------------------------------------

def hero_bound_abilities(heroes: dict) -> dict[str, str]:
    """{ability_id: hero_id} from every hero's m_mapBoundAbilities."""
    owner: dict[str, str] = {}
    for hid, hero in heroes.items():
        if not isinstance(hero, dict) or not hid.startswith('hero_'):
            continue
        for ab in (hero.get('m_mapBoundAbilities') or {}).values():
            if isinstance(ab, str) and ab:
                owner.setdefault(ab, hid)
    return owner


def ability_kind(aid: str, data: dict, owners: dict[str, str]) -> str:
    cls = str(data.get('_class', '')) if isinstance(data, dict) else ''
    if aid.startswith('upgrade_') or cls == 'citadel_item' or 'm_iItemTier' in (data or {}):
        return 'item'
    if 'weapon' in cls or aid.startswith('citadel_weapon_'):
        return 'weapon'
    if aid.startswith('ability_melee') or 'melee' in cls:
        return 'melee'
    if aid in owners:
        return 'ability'
    return 'ability_other'


_BUILDING_WORDS = ('guard', 'walker', 'boss', 'barrack', 'shrine', 'patron', 'titan', 'base_defense', 'tower',
                   'destroyable')


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
