# Hero stats table

Built by `pipeline/hero_table.py` → `data/tables/heroes.json` → `builders/tables_pages.py`.

Columns follow the original Google Sheet (Damage / Melee / Vitality / Mobility) plus Spirit.
Every column is a pure function of `(hero, primary weapon, level info)` and is evaluated on every
build that changed `heroes.vdata` or `abilities.vdata`; consecutive equal values collapse, so each
cell's history is the list of `[build, date, old, new]` where the value moved. Computed columns
(DPS, max bullet damage, full clip time) get histories too.

| Column | Source |
|---|---|
| Bullet DMG | weapon `m_flBulletDamage` |
| +Bullet DMG / boon | `m_mapStandardLevelUpUpgrades.MODIFIER_VALUE_BASE_BULLET_DAMAGE_FROM_LEVEL` |
| Max Bullet DMG | bullet dmg + per-boon × boons (levels with `m_bUseStandardUpgrade`) |
| Bullets / s | burst / ((burst − 1) × `m_flIntraBurstCycleTime` + `m_flCycleTime`) |
| DPS | bullet dmg × `m_iBullets` × bullets/s (level 1); Max DPS uses max bullet dmg |
| Ammo, Reload | `m_iClipSize`, `m_reloadDuration`; single-bullet reloaders (`m_bReloadSingleBullets`): Reload = `m_flReloadSingleBulletsInitialDelay` + one bullet (the sheet's convention), Full Reload = delay + clip × per-bullet |
| Headshot × | weapon `m_flCritBonusStart` |
| Bullet speed, ranges | `m_flBulletSpeed`, `m_flRange`, `m_flDamageFalloff{Start,End}Range` ÷ 39.37 |
| Melee | `m_mapStartingStats.E{Light,Heavy}MeleeDamage`, `…BASE_MELEE_DAMAGE_FROM_LEVEL` |
| Vitality | `EMaxHealth`, `EBaseHealthRegen`, `EBulletArmorDamageReduction`, `ETechArmorDamageReduction`, `ECritDamageReceivedScale`, collision (removed in later builds) |
| Mobility | `EMaxMoveSpeed`, `ESprintSpeed`, `EStamina`, `EStaminaRegenPerSecond`, `ECrouchSpeed`, dash durations |
| Spirit | `MODIFIER_VALUE_TECH_POWER` per boon |

Purple cells: the stat is in the hero's `m_mapScalingStats` (scales with Spirit Power).

Heroes shown: `m_eHeroDevelopmentState` = Release or PreRelease (the latter marked PRE).

Known gaps: spin-up weapons (McGinnis) use the starting fire interval; alt-fire / secondary weapon
(`ESlot_Weapon_Secondary`) is not a separate row yet.
