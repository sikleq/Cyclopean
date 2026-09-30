"""Classify diffed fields into categories and entities into kinds.

Categories (what kind of change a field path represents):
  availability — enabled/disabled/in-development flags (item left the shop, hero released)
  balance      — a number that affects gameplay (values, scaling, costs, tiers)
  mechanic     — non-numeric gameplay data (flags, enums, classes, new/removed props)
  meta         — testing/recommendation flags, hero role/tags, template links
  streetbrawl  — values that only apply in the Street Brawl mode
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
    r'Pose|Attachment|Bodygroup|Ragdoll|Gib|Portrait|Logo|Emblem|Sprite|Fov|Movie|Video|m_h[A-Z])'
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


STREET_BRAWL_RE = re.compile(r'StreetBrawl', re.I)


def category(path: str, old, new) -> str:
    if STREET_BRAWL_RE.search(path):
        return 'streetbrawl'
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


def unit_kind(uid: str, data: dict) -> str:
    cls = str(data.get('_class', '')) if isinstance(data, dict) else ''
    s = f'{uid} {cls}'.lower()
    if 'trooper' in s:
        return 'trooper'
    if 'neutral' in s:
        return 'neutral'
    if any(k in s for k in ('guard', 'walker', 'boss', 'barrack', 'shrine', 'patron', 'titan', 'base_defense', 'tower', 'destroyable')):
        return 'building'
    return 'unit'
