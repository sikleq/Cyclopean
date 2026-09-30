# Cyclopean

Deadlock change history built from the game files.

Every Deadlock build is compared with the previous one field by field (abilities, items, heroes,
units, buildings, game rules, text, console variables, packed assets). Official patch notes are
checked against those diffs:

- **documented** — the notes list the exact numbers found in the files;
- **described** — the notes mention it only in general terms ("all slows reduced by ~20%");
- **hidden** — the notes don't mention it at all (marked with the eye);
- **mismatch** — the notes give different numbers than the files.

Pages: patches, every build, hero / item / unit histories, and a hero stats table where every cell
shows how that value changed over time.

## Build

```bash
pip install -r requirements.txt
python build_site.py            # site from committed data/ into dist/
python build_site.py --data     # refresh data/ from the tracker first (clones ~200 MB into vendor/)
python -m pytest
```

Data: [SteamTracking/GameTracking-Deadlock](https://github.com/SteamTracking/GameTracking-Deadlock),
Steam News API, official Deadlock forum. Icons are extracted from the game's own VPK.

Not affiliated with Valve. Deadlock is a trademark of Valve Corporation.
