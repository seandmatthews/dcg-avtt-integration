# fixtures/

Two kinds of fixture, both load-bearing for the testing disciplines
(README §7):

## `golden-<version>/` — captured, never generated

One real scene JSON per pinned Atlas version, captured by importing
`sample.uvtt` in the Atlas UI at that version and committing the
resulting `.atlasmap` here. The port's output must match it
structurally — keys, types, id scheme, math within float tolerance.
The golden fixture is the source of truth for the `schema`/`version`
envelope values, above the README and above any docstring.

Capture procedure (per pin):

1. Install Atlas at the pinned version (pinned-release table, README §7).
2. Open a throwaway vault, import `sample.uvtt` via the UI.
3. Commit the resulting `.atlasmap` as
   `golden-<version>/sample.atlasmap` and note the version in the
   table below.

| version | captured | by |
|---|---|---|
| (none yet — first capture gates ticket 05's golden test) | | |

## `sample.uvtt` — designed, not arbitrary

A small hand-built `.uvtt` that exercises **every** conversion rule
(README §7.1), so the golden match is meaningful:

- nonzero `origin` (the offset math)
- a polyline crossing the image edge (clipping + dropped-segment count)
- a **closed** portal (→ door) and an **open** portal (→ dropped, counted)
- a zero-range light (→ dropped)
- `bakedLighting: true` (→ lights import hidden, ambient = 1)
- an `ambientLight` color (→ Rec.709 luma path)
- a non-square-cell variant kept separately for the refusal test

It lands with ticket 05, before the golden capture — the capture is
only meaningful if the sample exercises everything.
