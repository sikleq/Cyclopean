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

**Boons are counted per build** (owner 2026-10-22): every per-boon sum (Max Bullet DMG, Max DPS) uses the boon count
of its own build, and a row's `values.boons` / `history.boons` is that count (no table column): Haze 11 → 14 (2024-09-26)
→ 15 → 19 → 20 → 32 → 33 → 35 (2025-11-21). A Max DPS step on a build where neither the bullet nor its per-boon gain
moved is a change of the boon count.

Game panels (`pipeline/hero_panels.py`, the hero page's Weapon / Vitality / Spirit Stats and Boon Rewards): a row also
carries `panels` (each panel's stat lists from `m_ShopStatDisplay`), `gun` (`m_eWeaponAttributes` tags; the game's
`m_strWeaponImage` picture is not used) and `panel_values` (today's value of every listed stat no column holds, read from
`m_mapStartingStats` the game's way: a 1.0 scale is 0%, Stamina Cooldown = 1 / `EStaminaRegenPerSecond`); the data
has `panel_labels` (stat names `StatDesc_*`, tags `Attribute_EWeaponAttribute_*`, the cards' words, one build's
localization).

Advanced switch (`pipeline/hero_panels.advanced`): every build also records the hero's starting stats (`values.h.<EStat>`)
and the gun's numeric fields (`values.g.<field>`, engine distances ÷ 39.37) that no column reads and no panel lists, with
their history like a column's; the hero page shows them behind its Advanced switch (no table column).

Heroes shown: `m_eHeroDevelopmentState` = Release or PreRelease (the latter marked PRE).

Alt fire (`ESlot_Weapon_Secondary`: Viscous, Shiv, Yamato): a hero row's `alt` = `{weapon, values, history}`
over `alt_columns` — the gun's columns that read the weapon alone (no per-boon growth: no Max DPS, +Bullet DMG / boon,
+Range / boon) plus Ammo / Shot (`m_iAmmoConsumedPerShot`, what one alt shot takes of the clip); a build without
an alt fire after one reads as removed. The hero page shows it as a compact row under the weapon block's
"Alt fire" line (`hero_page.alt_cells`); the Hero Stats table has no column for it.

Known gaps: spin-up weapons (McGinnis) use the starting fire interval.
