# The ICRPG pack

The repo's first pack and its reason to exist as more than a converter:
the system-specific payload that cannot live in the canon core
(README §1, §6). Contents:

| file | what it is | status |
|---|---|---|
| `preset.json` | the Atlas system preset (widgets, dice, initiative, conditions, resources, lights) | **shipped (ticket 04)** |
| `fences/` | statblock fence templates: `npc`, `pc`, `mook` | **not yet written** (P1, README §1) — rules in `fences/README.md`; values awaited from the table's house conventions |
| this file | provenance for every knob below | complete for the preset |

## The rule that governs this pack

Preset knob values are **authored from the table's house rules, never
invented here** (README §5.2). icrpg DESIGN §13 (`icrpg-companion/DESIGN.md`,
"Data needed from the DM before building") is the checklist: which dice,
which TN ladder, heart conventions, milestone cadence. An invented value in
a system preset is worse than a missing one, because Atlas will happily use
it at the table.

## Provenance

`preset.json` is a **verbatim transcription** (JSON-value-identical,
machine-checked) of the table's own hand-authored preset:

> source: `dnd-campaign-generator/campaign-data/campaigns/ember-coast/`
> `atlas-vtt/system-presets/icrpg-house.json` — "ICRPG (house)", written by
> the DM into their campaign vault (no `builtIn` field, Atlas's stored
> `format: 1` shape), recorded in the campaigns repo at commit `674043c`
> (2026-10-10, a session-changes commit alongside that vault's live Atlas
> runtime state). The file the table already runs *is* the house ruling.

Nothing was added, removed, or edited — not even the `id`/`name` — so the
pack preset and the table's existing file are one preset to Atlas (same
id, `icrpg-house`): installing the pack into a vault that already carries
the DM's hand-made file leaves both in place, and Atlas keys presets by
id, keeping the first (`icrpg-house.json` sorts before `icrpg.json`).
The DM edits values **here** (in the pack) from now on; the installer is
the only writer.

| knob (DESIGN §13 item) | Atlas surface | value | source |
|---|---|---|---|
| grid default (§13.2 "what the table actually uses") | `rules.gridDefaults` | feet, 5 ft per square, numeric measurement, equidistant diagonals | vault file, verbatim |
| default roll + crit (§13.2 dice) | `rules.dice` | `1d20`, crit `natural` (nat 20 / nat 1) | vault file, verbatim |
| initiative (§13.2) | `rules.initiative` | `sides` mode, `1d20`, players first | vault file, verbatim |
| hearts (§13.3 heart conventions) | `rules.resources` | one resource `hearts` on `hp`, drains, red `#e11d48`, defeats when spent, player-visible | vault file, verbatim |
| conditions (§13.2/§13.3) | `rules.conditions` | six: Blinded, Burning, Dazed, Entangled, Feared, Prone — `icrpg-` ids, colors + icons as in the vault file | vault file, verbatim |
| alarm clock | `rules.widgets` `timer` | `icrpg-alarm`, 60 s default duration, stopwatch icon, on by default | vault file, verbatim |
| round counter | `rules.widgets` `counter` | `icrpg-rounds`, starts at 1, min 1, hourglass icon, on by default | vault file, verbatim |
| ultra/progress track | `rules.widgets` `clock` | `icrpg-progress`, 8 segments, starts empty, count shown, clover icon | vault file, verbatim |
| torch / lantern (§13.2) | `rules.lightPresets` | Torch 40/40 ft warm flicker; Lantern 30/30 ft steady — both radii equal (bright = dim) | vault file, verbatim |
| vision default | `rules.defaultTokenVision` | none set — new tokens start with no vision settings (a deliberate absence in the source file, carried over as such) | vault file, verbatim |
| milestone cadence (§13.6) | — | not a preset knob: Atlas presets carry no advancement field. Lives in table play (session reports), not in `preset.json` | DESIGN §13.6, by absence |
| TN ladder (§13.2) | — | not a preset knob: Atlas has no per-system TN field; the TN card is prep-packet/at-the-table material (core Tier 1), not collection settings | DESIGN §13.2, by absence |

Two carried-over oddities, present in the source and left untouched (a
transcription edits nothing): `measurementMode: "metric"` is Atlas's name
for *numeric* measurement (vs `abstract` range bands) and pairs normally
with `unitType: "feet"`; and the light presets set `bright` equal to
`dim`, which the 0.6.0 validator accepts as-is.

If the DM revises a value: change it here, rerun
`publish.py <campaign> presets`, and note the ruling in this table — the
provenance line above stays (values remain the table's, now revised).

## Fence templates (`fences/`)

Templates emit **body-only** ` ```statblock ` fences — the core's
frontmatter parser must never see pack-specific keys (README §3.5).
Field vocabulary is ICRPG's: hearts, effort dice, abilities —
display-first; the mechanically-live number is the preset's hearts
resource, by design and not by defect.
