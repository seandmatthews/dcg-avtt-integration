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
   table below. (The UI import renames the image into `assets/` as a
   timestamped asset — that `background` path is capture-specific, and
   the structural comparison checks it as a string, not a value. 0.6.0
   re-encoded the image as `.webp`; 0.7.1 keeps the source format, so
   its golden's background is a `.png` — the imports-no-longer-
   recompressed change. 0.8.0 likewise: its golden is structurally
   identical to 0.7.1's apart from the timestamped asset name (the
   0.7.1→0.8.0 source diff touched no import code — ticket 09).)

Steps 1–3 are automated by `tools/capture-golden.py <version>` (needs
desktop Obsidian installed; Windows): it builds a throwaway vault,
installs the plugin build attached to the version's GitHub release,
launches an isolated Obsidian instance (own `--user-data-dir`, so the
owner's running Obsidian is untouched), clicks through the vault trust
modal, opens the asset manager, and drops `sample.uvtt` onto it — the
same drag a GM performs, synthesized through the plugin's own drop
handler. It then suppresses `WorkspaceLeaf.openFile` before the drop:
the UI import auto-opens the finished scene, whose map store autosaves
the full runtime envelope (widgets, initiative, fog state) over the
file — the golden must stay the pure import output (`newSceneFile`'s
envelope), because that is what README §3.3 holds the port to. A
postcondition refuses a capture carrying non-import state keys.

Optionally (same procedure, one more import): commit `sample-lit.atlasmap`
from the `sample-lit.uvtt` variant — it pins the ambient-luma branch the
baked sample cannot take (see below).

| version | captured | by |
|---|---|---|
| 0.6.0 | 2026-10-18 | `tools/capture-golden.py 0.6.0` |
| 0.7.1 | 2026-10-18 | `tools/capture-golden.py 0.7.1` |
| 0.8.0 | 2026-10-20 | `tools/capture-golden.py 0.8.0` |

## `sample.uvtt` — designed, not arbitrary

A small hand-built `.uvtt` (64×32 px PNG, 4×2 cells, `origin (1,1)`,
cellSize 16) that exercises **every** conversion rule (README §7.1), so
the golden match is meaningful. Its parts, by the rule each exercises:

| part | rule it exercises (README §3.3) |
|---|---|
| nonzero `origin (1,1)` | the `(p − origin) × cellSize` offset math |
| wall line through `[(0,0),(2,0),(2,3)]` | one segment per point pair, shared endpoints, `chain_uvtt_1` |
| wall line `[(0,1),(9,1)]` crossing the edge | Liang–Barsky clipping to one cell outside the image |
| wall line `[(20,20),(21,20)]`, fully outside | dropped, `skipped.outside` counted |
| `objects_line_of_sight` line | chains number across the merged line list (`chain_uvtt_4`) |
| closed portal | → door `wall_uvtt_5`, `type: 'door', closed: true` |
| open portal | Dungeondraft window → dropped, `skipped.windows` counted |
| outside portal | dropped, `skipped.outside` counted |
| light `range 2, intensity 1.5, color '#FF8800'` | cells → game units (`× 5`), `bright = dim/2`, intensity passthrough, color lowercased |
| light `range 0` | dropped, `skipped.unlit` counted |
| outside light | dropped, `skipped.outside` counted (still `on_image` — the importer counts it before the range check) |
| `ambient_light: '#ff334455'` | the `aarrggbb` alpha-strip color read |
| `baked_lighting: true` | lights import `hidden`; ambient is 1 even with a color named (the baked branch wins) |

Ambient rule in one file — `ambient = 1` when baked, else the Rec. 709
luma — cannot take both branches, so `sample.uvtt` pins the baked
branch (with a color present, proving precedence) and:

- `sample-lit.uvtt` — identical except `baked_lighting: false`: the
  luma branch (`#334455` → 0.26), lights not hidden. Unit-tested; a
  golden capture of it is the optional second capture above.
- `sample-nonsquare.uvtt` — `map_size {4,3}` against the same 64×32
  image: the ±2 px height check refuses it ("does not fit a map of
  4 × 3 squares") — the non-square-cell refusal variant the refusal
  test needs.

It landed with ticket 05, before the golden capture — the capture is
only meaningful if the sample exercises everything. The recipe for a
deliberately *crowded* variant (tripping Atlas's manual-import
`wallsCrowd` guard, ticket 03) is a wall stub per tile edge; it is not
committed — the publisher never hits that guard.
