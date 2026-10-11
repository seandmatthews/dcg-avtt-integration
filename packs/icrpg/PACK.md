# The ICRPG pack

The repo's first pack and its reason to exist as more than a converter:
the system-specific payload that cannot live in the canon core
(README §1, §6). Contents when complete:

| file | what it is | status |
|---|---|---|
| `preset.json` | the Atlas system preset (widgets, dice, initiative, conditions, lights, vision) | **lands with ticket 04** |
| `fences/` | statblock fence templates: `npc`, `pc`, `mook` | values from the table's house conventions |
| this file | provenance for every knob below | started |

## The rule that governs this pack

Preset knob values are **authored from the table's house rules, never
invented here** (README §5.2). icrpg DESIGN §13 is the checklist: which
dice, which TN ladder, heart conventions, milestone cadence. Until the
human supplies the values, `preset.json` does not exist — an invented
value in a system preset is worse than a missing one, because Atlas
will happily use it at the table.

## Provenance

| knob | Atlas surface | value | source |
|---|---|---|---|
| hearts (HP convention) | token resource via `rules.resources` | TBD | house rules |
| alarm clock | `timer` widget, scoped | TBD | house rules |
| round counter | `counter` widget | TBD | house rules |
| ultra/progress track | `clock` widget (Blades-style wedges) | TBD | house rules |
| default roll | `rules.dice` (d20 default + critical rule) | TBD | house rules |
| initiative | `rules.initiative` | TBD | house rules |
| conditions | `rules.conditions` | TBD | house rules |
| torch / lantern | `rules.lightPresets` | TBD | house rules |
| vision default | `rules.defaultTokenVision` | TBD | house rules |

(Widget vocabularies per README §3.6: `counter`, `timer`, `clock`,
scoped per scene or per collection.)

## Fence templates (`fences/`)

Templates emit **body-only** ` ```statblock ` fences — the core's
frontmatter parser must never see pack-specific keys (README §3.5).
Field vocabulary is ICRPG's: hearts, effort dice, abilities —
display-first; the mechanically-live number is the preset's hearts
resource, by design and not by defect.
