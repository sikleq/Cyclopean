# Original hero stats sheet (reference)

Source: the author's Google Sheet "Heroes" (built for Jan 2025 patch). Columns and the file fields noted in its cell comments.

| Group | Column | Note (from the sheet) |
|---|---|---|
| Hero | Hero |  |
| Aliases | Aliases |  |
| ID | ID | Файл: heroes.vdata Строка: m_HeroID |
| Damage | DPS |  |
| Damage | Max. DPS |  |
| Damage | Bullet DMG | Урон за 1 снаряд/пулю. Файл: abilities.vdata Строка: m_flBulletDamage |
| Damage | +Bullet DMG/LVL | Прирост к урону пули/снаряда за уровень. Файл: heroes.vdata Строка: MODIFIER_VALUE_BASE_BULLET_DAMAGE_FROM_LEVEL |
| Damage | Max. Bullet DMG | Максимально возможный урон за пулю/снаряд на последнем уровне (11). (27 сен. 2024) 11 → 14 уровней |
| Damage | Clip Size | Размер обоймы. Файл: abilities.vdata Строка: m_iClipSize |
| Damage | Full clip in (sec) | Как быстро разрядится вся обойма. |
| Damage | Reload (sec) | Время перезарядки. Файл: heroes.vdata Строка: m_reloadDuration Для Абрамса доп. строка: m_flReloadSingleBulletsInitialDelay |
| Damage | Headshot DMG | Множитель урона от попаданий в голову. Файл: heroes.vdata Строка: ECritDamageBonusScale |
| Damage | Bullet Cycle Time | Время, за которое пули вылетают друг за другом. Файл: abilities.vdata Строка: m_flCycleTime |
| Damage | Bullet Radius | Размер пули/снаряда. Файл: abilities.vdata Строка: m_flBulletRadius |
| Damage | Bullet Spread | Разброс пуль. Файл: abilities.vdata Строка: m_Spread |
| Damage | Bullets per 1 shot | Дробинок в 1 пуле/снаряде. Файл: abilities.vdata Строка: m_iBullets |
| Damage | Bullet Speed (m) | Скорость пули/снаряда. Значение/39,37. Файл: abilities.vdata Строка: m_vDomainMaxs |
| Damage | Bullets per sec. | Количество пуль/снарядов, которые возможно выпустить за 1 секунду. |
| Damage | Bullet Lifetime | Время жизни пули/снаряда. Файл: abilities.vdata Строка: m_flBulletLifetime |
| Damage | Bullet Gravity Scale | Влияние гравитации на пулю/снаряд. Чем выше значение, тем меньше влияние гравитации. Файл: abilities.vdata Строка: m_flBulletGravityScale |
| Damage | Bullet Range (m) | Максимально возможное расстояние для пули. Значение/39,37. Файл: abilities.vdata Строка: m_flRange |
| Damage | Pellet Spread | Если оружие стреляет дробью, то разброс между дробинками такой. Если нет, то 0. Файл: abilities.vdata Строка: m_flPelletScatterSpreadFactor |
| Damage | Burst amount | Сколько патронов в выстреле. Файл: abilities.vdata Строка: m_iBurstShotCount |
| Damage | Burst Cycle Time | Время между выстрелами (ЛКМ). Файл: abilities.vdata Строка: m_flIntraBurstCycleTime |
| Damage | Base Range (m) | Минимальное расстояние для потери урона/разброс выстрела. Значение/39,37. Файл: abilities.vdata Строка: m_flDamageFalloffStartRange |
| Damage | Max. Range (m) | Максимальное расстояние для потери урона/разброс выстрела. Значение/39,37. Файл: abilities.vdata Строка: m_flDamageFalloffEndRange |
| Damage | +Range/LVL |  |
| Melee | Light Melee | Файл: abilities.vdata Строки для интервала атак: ability_melee_[ИМЯ] m_Trigger = "light" m_flCooldownOnHit |
| Melee | +DMG/LVL |  |
| Melee | Heavy Melee | Файл: abilities.vdata Строкидля интервала атак: m_Trigger = "heavy" m_flCooldownOnHit |
| Vitality | HP |  |
| Vitality | +HP/LVL |  |
| Vitality | HP Regen |  |
| Vitality | Bullet Resist |  |
| Vitality | +BR/LVL |  |
| Vitality | Spirit Resist |  |
| Vitality | Collision Radius | Файл: heroes.vdata Строка: m_flCollisionRadius |
| Vitality | Collision Height | Файл: heroes.vdata Строка: m_flCollisionHeight |
| Vitality | Headshot DMG Received | Множитель урона от попаданий по вашей голове. Файл: heroes.vdata Строка: ECritDamageReceivedScale |
| Mobility | Movespeed |  |
| Mobility | Sprint |  |
| Mobility | Stamina |  |
| Mobility | Stamina Regen |  |
| Mobility | Crouch Speed |  |

Weapon ids per hero (sheet comments on the Hero column):

- Abrams: Оружие: citadel_weapon_bull_set
- Bebop: Оружие: citadel_weapon_bebop_set
- Calico: Оружие: citadel_weapon_nano_set
- Dynamo: Оружие: citadel_weapon_sumo_set
- Grey Talon: Оружие: citadel_weapon_archer_set
- Haze: Оружие: citadel_weapon_haze_set
- Holliday: Оружие: citadel_weapon_astro_set
- Infernus: Оружие: citadel_weapon_inferno_set
- Ivy: Оружие: citadel_weapon_tengu_set
- Kelvin: Оружие: citadel_weapon_kelvin_set
- Lady Geist: Оружие: citadel_weapon_ghost_set
- Lash: Оружие: citadel_weapon_lash_set
- McGinnis: Оружие: citadel_weapon_engineer_set
- Mo & Krill: Оружие: citadel_weapon_digger_set
- Paradox: Оружие: citadel_weapon_chrono_set
- Pocket: Оружие: citadel_weapon_synth_set
- Seven: Оружие: citadel_weapon_gigawatt_set
- Shiv: Оружие: citadel_weapon_shiv_set citadel_weapon_shiv_alt
- Sinclair: Оружие: citadel_weapon_magician_set
- Vindicta: Оружие: citadel_weapon_hornet_set
- Viscous: Оружие: citadel_weapon_viscous_set citadel_weapon_viscous_set_2
- Vyper: Оружие: citadel_weapon_kali_set
- Warden: Оружие: citadel_weapon_warden_set
- Wraith: Оружие: citadel_weapon_wraith_set
- Yamato: Оружие: citadel_weapon_yamato_set citadel_weapon_yamato_alt
