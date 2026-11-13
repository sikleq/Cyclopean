"""The hand tables of field labels: stat and weapon, ranked-season, unit and level-up words, and the trooper's
fields against a boss (`boss_field`). Split out of `field_labels` 2026-11-13; every name is re-exported there."""
from __future__ import annotations

import re

from .field_units import FRACTION, SPEED


STAT_DESC_EXCEPTIONS = {
    'MaxMoveSpeed': 'RunSpeed',
    'ClipSize': 'ClipSizeBonus',
    'WeaponDPS': 'DPS',
    'OOCHealthRegen': 'OutOfCombatHealthRegen',
    'TechCooldownBetweenChargeUses': 'TechCooldownBetweenCharges',
    'BaseWeaponDamageIncrease': 'BaseWeaponDamage',
}


CUSTOM_STAT_LABELS = {
    'CrouchSpeed': 'Crouch Speed',
    'MoveAcceleration': 'Move Acceleration',
    'GroundDashDistanceInMeters': 'Ground Dash Distance',
    'GroundDashDuration': 'Ground Dash Duration',
    'AirDashDistanceInMeters': 'Air Dash Distance',
    'AirDashDuration': 'Air Dash Duration',
    'StaminaRegenPerSecond': 'Stamina Regen',
    'LightMeleeDamage': 'Light Melee Damage',
    'HeavyMeleeDamage': 'Heavy Melee Damage',
    'CritDamageReceivedScale': 'Headshot Damage Taken ×',
    'CritDamageBonusScale': 'Headshot Damage Bonus ×',
}


# our own words win over the game's for these: "Crit Reduction 0.75 → 0.65" read as a nerf of a
# reduction; the value is the multiplier on headshot damage taken (audit 2026-10-01)
CUSTOM_FIRST = ('CritDamageReceivedScale', 'CritDamageBonusScale')


LEVEL_UP_LABELS = {
    'MODIFIER_VALUE_BASE_HEALTH_FROM_LEVEL': 'Health per boon',
    'MODIFIER_VALUE_BASE_BULLET_DAMAGE_FROM_LEVEL': 'Bullet damage per boon',
    'MODIFIER_VALUE_BASE_BULLET_DAMAGE_FROM_LEVEL_ALT_FIRE': 'Alt-fire damage per boon',
    'MODIFIER_VALUE_BASE_MELEE_DAMAGE_FROM_LEVEL': 'Melee damage per boon',
    'MODIFIER_VALUE_TECH_POWER': 'Spirit power per boon',
    'MODIFIER_VALUE_BULLET_ARMOR_DAMAGE_RESIST': 'Bullet resist per boon',
    'MODIFIER_VALUE_TECH_ARMOR_DAMAGE_RESIST': 'Spirit resist per boon',
    'MODIFIER_VALUE_TECH_RESIST': 'Spirit resist per boon',          # the key's name since build 6541
    'MODIFIER_VALUE_BONUS_ATTACK_RANGE': 'Weapon range per boon',
    'MODIFIER_VALUE_BOON_COUNT': 'Boons per level',
    'MODIFIER_VALUE_OUT_OF_COMBAT_HEALTH_REGEN': 'Out-of-combat regen per boon',
    'MODIFIER_VALUE_TECH_DAMAGE_MULTIPLIER': 'Spirit damage multiplier per boon',
    'MODIFIER_VALUE_TECH_DAMAGE_PERCENT': 'Spirit damage % per boon',
}


# weapon fields (m_mapWeaponInfos.primary.*): label, meters?
WEAPON_FIELDS = {
    'm_flBulletDamage': ('Bullet Damage', False),
    'm_iBullets': ('Pellets per Shot', False),
    'm_flCycleTime': ('Fire Interval', False),
    'm_iBurstShotCount': ('Burst Size', False),
    'm_flIntraBurstCycleTime': ('Burst Interval', False),
    'm_iClipSize': ('Ammo', False),
    'm_reloadDuration': ('Reload Time', False),
    'm_flReloadSingleBulletsInitialDelay': ('Reload Start Delay', False),
    'm_flBulletSpeed': ('Bullet Velocity', SPEED),
    'm_flDamageFalloffStartRange': ('Falloff Start', True),
    'm_flDamageFalloffEndRange': ('Falloff End', True),
    'm_flDamageFalloffEndScale': ('Damage at Falloff End', FRACTION),
    'm_flRange': ('Max Range', True),
    'm_flCritBonusStart': ('Headshot Multiplier', False),
    'm_flCritBonusEnd': ('Headshot Multiplier (far)', False),
    'm_flCritBonusAgainstNPCs': ('Headshot Multiplier vs NPCs', False),
    'm_flBulletGravityScale': ('Bullet Gravity', False),
    'm_flBulletRadius': ('Bullet Radius', True),
    'm_Spread': ('Spread', False),
    'm_StandingSpread': ('Standing Spread', False),
    'm_flShootSpreadPenaltyPerShot': ('Spread per Shot', False),
    'm_flShootMoveSpeedPercent': ('Move Speed while Shooting', FRACTION),
    'm_flZoomMoveSpeedPercent': ('Move Speed while Zoomed', FRACTION),
    'm_flBulletLifetime': ('Bullet Lifetime', False),
    'm_flPelletScatterSpreadFactor': ('Pellet Spread', False),
    'm_flMaxSpinCycleTime': ('Spun-up Fire Interval', False),
    'm_flSpinIncreaseRate': ('Spin-up Rate', False),
    'm_flSpinDecayRate': ('Spin-down Rate', False),
    'm_flPenetrationPercent': ('Penetration', False),
    'm_flExplosionRadius': ('Explosion Radius', True),
    'm_iAmmoConsumedPerShot': ('Ammo per Shot', False),
    'm_flBuildUpRate': ('Proc Build-up', False),
}


# a ranked season's rules (scripts/ranked_seasons.vdata, 2026-11-13): the game gives them no text; the words follow the
# "Ranked - Beta Season 2" post ("The points for a game has been increased from 300 to 350"). Plain numbers, no unit
# ("Interval 2s" read a season's number as seconds)
_RANKED_ENTITY = re.compile(r'^(season_\d+|default_ranked)$')


RANKED_FIELDS = {
    'm_unBaseWinLossPointGrant': 'Rank Points per Match',
    'm_unMinWins': 'Wins to Play Ranked',
    'm_unMinHeroUnlocks': 'Heroes to Unlock',
    'm_unMinHeroWins': 'Hero Wins to Unlock a Hero',
    'm_unMinHeroUnlockPoints': 'Hero Points to Unlock a Hero',
    'm_unCalibrationMatches': 'Placement Matches',
    'm_unCalibrationMaxRank': 'Highest Placement Rank',
    'm_vecSubRankXP': 'Points per Subrank',
    'm_nBadgeShields': 'Badge Shields',
    'm_nSubRankShields': 'Subrank Shields',
    'm_unRankEnd': 'Last Rank',
    'm_unInterval': 'Season Number',
    'm_unLeaderboardID': 'Leaderboard',
    'm_vecValidPartySizes': 'Party Sizes',
}


# NPC / building fields: label, meters?
UNIT_FIELDS = {
    'm_nMaxHealth': ('Health', False),
    'm_iStartingHealth': ('Starting Health', False),
    'm_iHealthGainPerMinute': ('Health per Minute', False),
    'm_flPlayerDPS': ('DPS vs Heroes', False),
    'm_flTrooperDPS': ('DPS vs Troopers', False),
    'm_flPlayerDamageResistPct': ('Resist vs Heroes', False),
    'm_flTrooperDamageResistPct': ('Resist vs Troopers', False),
    'm_flInvulRange': ('Invulnerability Range', True),
    'm_flBackDoorProtectionRange': ('Backdoor Protection Range', True),
    'm_flGoldReward': ('Soul Bounty', False),
    'm_flGoldRewardBonusPercentPerMinute': ('Bounty Growth per Minute', False),
    'm_flWalkSpeed': ('Walk Speed', SPEED),
    'm_flRunSpeed': ('Run Speed', SPEED),
    'm_flMeleeDamage': ('Melee Damage', False),
    'm_flMeleeHitRange': ('Melee Range', True),
    'm_flStompDamage': ('Stomp Damage', False),
    'm_flStompDamageMaxHealthPercent': ('Stomp Damage (% max HP)', False),
    'm_flStunDuration': ('Stun Duration', False),
    'm_flDPSPctGrowthPerMinute': ('DPS Growth per Minute', False),
    'm_flBaseDPS': ('Base DPS', False),
    'm_flEndDPS': ('End DPS', False),
    'm_flEndDPSTimeInSeconds': ('End DPS Time', False),
    'm_flMaxRange': ('Max Range', True),
    'm_flDamageResist': ('Damage Resist', False),
    'm_flOOCRegen': ('Out-of-combat Regen', False),
    # Walker's / the Patron's shield around them and how far a guardian sees heroes (audit 2026-10-04:
    # "Invul Modifier Range", "Sight Range Players")
    'm_flInvulModifierRange': ('Invulnerability aura range', True),
    'm_flSightRangePlayers': ('Sight range vs heroes', True),
}


# a trooper's old flat fields for its fight against a boss ("T1 Boss DPS Max Resist", 859 rows on 26 pages read
# engine names; review 2026-10-05): by the boss's name, in the words the m_VS* structs that replaced them get on
# the same pages ("Base DPS vs Guardian"), so old and new rows read alike. T1 = Guardian, T2 = Walker, T3 = Patron,
# the barracks' boss = the Base Guardian (the site's name of npc_barrack_boss)
_BOSS_FIELD = re.compile(r'^m_fl(Attack)?(T1Boss|T2Boss|T3Boss(?:Phase2)?|BarrackBoss|BarrackGuardian)(\w+)$')


_BOSS_NAME = {'T1Boss': 'Guardian', 'T2Boss': 'Walker', 'T3Boss': 'Patron', 'T3BossPhase2': 'Patron Phase 2',
              'BarrackBoss': 'Base Guardian', 'BarrackGuardian': 'Base Guardian'}


# what the field is: (label, meters, unit)
_BOSS_WHAT = {'DPS': ('DPS', False, ''), 'DPSBase': ('Base DPS', False, ''), 'DPSMax': ('End DPS', False, ''),
              'DPSMaxTimeInSeconds': ('End DPS Time', False, 's'),
              'DPSBaseResist': ('Damage Resist at start', False, '%'),
              'DPSMaxResist': ('Damage Resist at most', False, '%'),
              'DPSMaxResistTimeInSeconds': ('Time to most Damage Resist', False, 's'),
              'DamageResistPct': ('Damage Resist', False, '%'), 'MaxRange': ('Max Range', True, '')}


def boss_field(leaf: str) -> dict | None:
    """{label, meters, unit} of a trooper's flat field against a boss (`_BOSS_FIELD`), else None."""
    m = _BOSS_FIELD.match(leaf)
    if not m or m.group(3) not in _BOSS_WHAT:
        return None
    label, meters, unit = _BOSS_WHAT[m.group(3)]
    return {'label': f'{label} vs {_BOSS_NAME[m.group(2)]}', 'meters': meters, 'unit': unit}
