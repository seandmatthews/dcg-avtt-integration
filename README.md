# dcg-avtt-integration

The seam between [`dnd-campaign-generator`](../dnd-campaign-generator) (the
canon core) and [Atlas VTT](https://github.com/atlas-vtt/atlas-vtt) (the
at-the-table surface).

**Status: both publishers built (2026-10-12).** `presets` (ticket 04 —
`presets.py`, the `presets` subcommand, `packs/icrpg/`) and `scenes`
(ticket 05 — the `.uvtt`→`.atlasmap` port, records, `avtt.yaml` config,
the CLI with the `_inbox/` degrade path) are built, as is the
machine-readable Atlas pin (ticket 07 — `_version.py`, the `version`
subcommand, the mismatch policy). `party` (ticket 06) stays parked,
`proposed`; the ICRPG fence templates (P1, §1) are unwritten content;
and the golden fixtures for 0.6.0 and 0.7.1 are captured (2026-10-18,
fixtures/README.md via `tools/capture-golden.py` — the capture is
automated; the pin itself still reads 0.6.0 until ticket 08 lands).
Everything below was verified against
Atlas VTT v0.6.0 source on 2026-10-09; see "The Atlas contract" for what was
checked and "Open questions" for what remains open.
**Tested against: Atlas VTT 0.6.0** (released 2026-10-05). This file is the
repo's constitution: when code and README disagree, one of them is wrong and
must be fixed the same day.

In one sentence:

> This repo owns **everything that writes Atlas-owned file formats, or
> carries system-specific table data** — so the canon core never has to know
> whether Atlas exists.

---

## 1. Why this repo exists (the residency ruling)

Decided 2026-10-10, after the Atlas seam analysis
(`dnd-campaign-generator/docs/design/atlas-seam.md`). Two axes cross:

1. **system-specific vs system-agnostic.** The canon core is deliberately
   setting- and system-agnostic — the founding ruling that evicted the
   ICRPG table companion to its own repo. System-specific data (an ICRPG
   preset, ICRPG statblock-fence templates) is the same animal and lives
   outside the core for the same reason.
2. **interchange vs app-owned formats.** The core commits to interchange
   formats (markdown, YAML, `.uvtt`, PNG, `statblock` fences — formats no
   single app owns) and adapts to apps. Adapters that write an app's *owned*
   formats live beside that app, because they inherit that app's churn.

| seam piece | lives in | axis that decides |
|---|---|---|
| `.atlasmap` scene conversion + records (P2) | **here** | app-owned format, release-churny |
| ICRPG preset `packs/icrpg/preset.json` (P0 content) | **here** | system-specific data |
| pack installer for presets (P0 mechanism) | **here** | serves only the packs |
| ICRPG fence templates (P1 content) | **here** | system-specific data |
| party tokens publisher (P4, parked) | **here** | app-owned format |
| `system:` field in `campaign.yaml` | core | canon metadata (Tier-1 prep wanted it pre-Atlas) |
| `statblock` fence convention + structural checks | core | ecosystem interchange format in spine-native markdown |
| session loop (`session_notes.py` + docs) | core | existing core machinery; system-agnostic by ruling |
| ATLAS.md tutorial (the campaign-running loop) | core `docs/for-new-gms/` | it is campaign documentation |

Precedent, for the record: `obsidian-integration.md` lives in-core because
the studio only ever writes spine-native formats there (markdown, YAML) —
Obsidian is a reader, not a dependency. `obsidian_vault.py` writes one tiny
foreign format (Obsidian's vault-list config) and earns its residency by
being small and stable for years. Atlas's formats are v0.x and changelog
every few days; adapters to them do not get the same exemption.

## 2. The contract (the whole relationship in four rules)

1. **This repo reads campaign directories and writes only inside
   `atlas-vtt/`** (plus `atlas-vtt/_inbox/` for the degrade path). It never
   writes spine files: no lore, no timeline, no `campaign.yaml`, no companion
   notes. (One licensed exception, added 2026-10-10: after publishing a
   scene it appends the scene-embed line to that site's companion note —
   the note is generated metadata, and the line is the publish record. The
   edit is append-only and idempotent.)
2. **Table state flows nowhere.** `atlas-vtt/` after publication (fog,
   token positions, HP, widget values) is chalk. This repo reads it never —
   idempotency comes from stable paths and refuse-on-diff, not from reading
   Atlas's state.
3. **Stable stems, refuse-on-diff.** Stems are site slugs. Atlas recovers
   asset ids deterministically from stems, so republishing the same slug
   targets the same asset. Target exists and differs → refuse.
   `--force` writes a `<slug>-v2` sibling. A hand-tuned scene (moved door,
   tweaked light) is an earned artifact; nothing overwrites it silently.
4. **Orchestration, not integration.** No imports in either direction, no
   shared runtime. The studio may one day *spawn* this repo's CLI
   (icrpg DESIGN §9.2: spawning a process is loose coupling; merging code
   is not the fix). Until then: the DM runs the commands.

## 3. The Atlas contract (source-read 2026-10-09, v0.6.0)

Everything below was verified by reading Atlas's TypeScript. The reference
clone lived at `%TEMP%\atlas-vtt` (ephemeral — re-clone and re-check the tag
before trusting any line here; paths are repo-relative).

### 3.1 File adoption (how externally-written files become Atlas assets)

`src/app/services/vault-sync/assetAdoption.ts` adopts JSON written at:

```
atlas-vtt/collections/<collectionId>/maps/<stem>.json
atlas-vtt/collections/<collectionId>/{scenes,encounters,players,characters,statblocks}/<stem>.json
```

- Record shape (minimum): `{id?, name, tags, collection, createdAt,
  modifiedAt, type: '<asset type>', …type-specific}`. A missing/blank name
  falls back to the prettified stem; timestamps fall back to adoption time.
- **Ids are recoverable, so we don't need to mint them:** a record without an
  id gets `<type>-recovered-<hash36>` where hash is a deterministic function
  of the path (`recoveredIds.ts:recoveredId`). Same stem → same id on every
  device, forever. Consequence: our stems (site slugs) are the identity.
- A **scene record** references its content: the *asset* carries
  `data: { mapPath: '<vault path to .atlasmap>' }` — the scene content
  file is referenced, not inlined — and on disk that payload is
  written at the record JSON's top level as `mapPath` (Atlas's own
  writer flattens `data` into the file, `recordFile.ts`; adoption reads
  the top-level key, `assetAdoption.ts`, with the sibling
  `<stem>.atlasmap` as fallback). Our scene records state the
  top-level `mapPath` (ticket 05, resolving ticket 02's bycatch
  question).
- A **map record** carries `mapFilePath` (the image); the image can live
  anywhere in the vault and the record states where — but a map whose
  stated image is missing is skipped at the vault check
  (`assetAdoption.ts` `adoptMapJson`), so the image must exist before
  its record is adopted.
- **Thumbnails are Atlas's job** (spike 2, ticket 02, v0.6.0): adoption
  ignores a `thumbnailPath` in the record JSON, and
  `AssetThumbnailService` background-generates thumbnails for every map
  lacking one (`atlas-vtt/assets/thumbnails/<name>-<digest>.webp`,
  recorded back onto the asset). We never supply thumbnails and never
  write into `atlas-vtt/assets/` — Atlas's own folder, where its UI
  importer drops drag-in images as `<name>_<timestamp>_<random>.webp`
  (`src/app/services/assetImageFiles.ts`, the importer's helper — not
  the adoption path). Our published image sits beside its record as
  `collections/<collectionId>/maps/<slug>.png`, stated by the record's
  `mapFilePath`.
- **ANSWERED (spike 1, ticket 01):** folder-only adoption works — verified
  live 2026-10-10 on both the 0.6.0 pin (release build) and the 0.7.1
  install, Obsidian 1.14.4. A record at
  `atlas-vtt/collections/<id>/maps/<stem>.json` whose `mapFilePath`
  exists is adopted at plugin load with no `collection.json` and no
  library index: Atlas derives the collection record, bootstraps
  `library.json` (the first collection becomes the default), and indexes
  the asset under `atlas-vtt/.atlas-data/`. So the publisher needs no
  bootstrap step and no UI-recorded id — but it still names a stable
  collection slug as its write target (`config.collection_id`, our
  choice, e.g. the campaign slug). Two corollaries from the same
  experiment: (a) **Atlas rewrites adopted record files in place** into
  canonical form (recovered `id`, added `collection`, an `atlasRecord`
  envelope) — so contract rule 3's refuse-on-diff must compare the
  `atlasRecord` payload against our intended record, never raw bytes;
  (b) a first run on a fresh vault also drops starter tokens into
  `assets/` and `tokens/` — first-run side effects, not ours to mimic.
  This repo still never writes `library.json` or `collection.json` —
  those are app internals (ruling; same lesson as obsidian-integration
  §6, where mimicking app-private storage killed the Fantasy Map
  investment).

### 3.2 The `.atlasmap` scene file

Written by `newSceneFile.ts`, consumed as `data.mapPath` of a scene record.
Envelope:

```json
{
  "state": {
    "schema": <ATLAS_SCHEMA>, "version": <ATLAS_VERSION>,
    "background": "<image path or null>",
    "grid": {"enabled": true, "visible": true, "snapToGrid": true,
             "type": "square", "size": <px per cell>, "offsetX": 0, "offsetY": 0,
             "opacity": 0.5, "lineType": "solid", "lineWidth": 1,
             "unitType": "...", "unitDistance": 5, "measurementType": "..."},
    "objects": {"tokens": {}, "fog": {}, "pins": {}, "texts": {}, "drawings": {},
                "walls": {...}, "lights": {...}},
    "camera": {"x": 0, "y": 0, "scale": 1},
    "tokenSettings": {...}, "lighting": {"enabled": true, "ambient": 0..1}
  },
  "version": <int>
}
```

`schema`/`version` values come from the pinned release's `MapPersistence.ts`
— the golden fixture is their source of truth, never this README.

### 3.3 `.uvtt` import semantics (what our converter must reproduce)

Universal VTT (`.uvtt`/`.dd2vtt`/`.df2vtt`) as parsed by
`src/app/import/uvtt/`: one JSON file with a base64 image and overlays.
**Every position is counted in grid cells.** Fields: `origin` (cell at the
image's top-left), `size` (cells the image spans), `image`, `polylines`
(wall lines through ordered points), `portals` (two-point `bounds` +
`closed`), `lights` (`position`, `range` in cells, `intensity`, `color`),
`ambientLight`, `bakedLighting`.

Limits (`uvttTypes.ts UVTT_LIMITS`) — a refused file gets a plain-words
reason, and ours should surface it: file ≤ 150 MB; ≤ 20,000 wall segments;
≤ 2,000 lights; ≤ 4,096 cells per side; ≥ 10 px per cell; image ≤
268,435,456 px (1 GiB decoded at four bytes/pixel).

Conversion (`uvttToScene.ts`, the code this repo ports):

- `cellSize = image.width / size.x`, refused unless
  `cellSize * size.y` matches `image.height` within ±2 px (non-square cells
  would misplace every wall).
- Every cell coordinate maps to world pixels as
  `(p − origin) × cellSize`; the image's top-left is (0,0).
- Nothing is placed farther than one cell outside the image: polylines are
  clipped to that rect (outside segments are dropped and counted), and
  fully-outside doors/lights are dropped.
- Each polyline becomes one wall segment per point pair
  (`{kind:'wall', type:'solid', chainId:'chain_uvtt_<line#>'}`,
  ids `wall_uvtt_<n>`); consecutive segments keep shared endpoints exactly.
- A **closed** portal becomes a door (`type:'door', closed:true`); an open
  portal is a Dungeondraft *window* — Atlas drops it (counted, not placed).
- Lights: `dim = range` (cells → the collection's game units),
  `bright = dim / 2`, `intensity` passthrough, both clamped to the
  collection's max light range; a light with `range 0` is dropped;
  **lights import hidden when `bakedLighting` is true** (the image already
  shows the glow).
- `ambient = 1` (daylight) when `bakedLighting` or no ambient named, else
  the Rec.709 luma of `ambientLight`.
- Grid: `size = cellSize`, offset `= −origin × cellSize` (normalized).
- **The id scheme is deterministic** (`wall_uvtt_1`, `chain_uvtt_1`,
  `light_uvtt_1`, …). The port must reproduce it exactly: identical `.uvtt`
  → byte-identical `.atlasmap` is the round-trip test's whole point.

The `lightPresets`-related helpers (`toGameUnits`, `maxLightRange`,
`unitScaleOf`) translate cells → the collection's unit system; the port
reimplements their arithmetic and pins it in the golden tests (for a
feet-based collection with 5 ft squares, 1 square = 5 ft).

### 3.4 System presets

User presets are plain files at `atlas-vtt/system-presets/<name>.json`,
watched live (`presetFiles.ts`; extension must be `.json`). Shape
(`systemPresetTypes.ts`):

```json
{"id": "<stable id, must not start with 'builtin:'>",
 "name": "ICRPG", "builtIn": false,
 "rules": {"gridDefaults": {...}, "conditions": [...], "widgets": [...],
           "defaultWidgets": {...}, "dice": {...}, "initiative": {...},
           "resources": [...], "defaultTokenVision": {...},
           "senses": [...], "lightPresets": [...]}}
```

Presets are validated on load (`presetValidation.ts`) — an invalid preset is
ignored by Atlas, so **the installer validates with equivalent strictness
before writing** (port the validator's checks; a silently-ignored preset is
the worst failure mode). Built-in presets already exist for D&D 5e,
Pathfinder 2e, Shadowdark, OSE, Cairn, Daggerheart, Draw Steel, Call of
Cthulhu, Cyberpunk RED — for those, the installer's correct behavior is to
publish nothing and say so.

### 3.5 Statblock fences and notes

Creature resolution (`creatures/linkedCreature.ts`) tries, in order:
Fantasy Statblocks bestiary (if the plugin runs) → the note's frontmatter
creature → a ` ```statblock ` fence in the note body → bestiary name match.
**Fences and frontmatter work with no plugin installed.** Our pack
templates emit fences (body-only; the core's frontmatter parser must never
see pack-specific keys). What Atlas parses mechanically from creature
fields is biased toward 5e-ish conventions (HP drives token HP); ICRPG
packs lean on token resources from the preset instead — by design, not
defect.

### 3.6 Useful extras (verified)

- Notes (and other Atlas scenes) can be embedded/linked in markdown since
  0.6.0 — the scene-publish step appends that link line to the site's
  companion note.
- Widgets: `counter`, `timer` (countdown seconds, persisted), `clock`
  (Blades-style progress wedges), scoped per scene or per collection —
  these are what the ICRPG pack's alarm clock and round counter use.
- Atlas is AGPL-3.0, desktop-only, offline; requires Obsidian ≥ 1.8.7.

## 4. Layout

```
dcg-avtt-integration/
  README.md                 this file
  run-tests.py              the gate: fast tier; --all adds the golden tier
  src/avtt/
    uvtt.py                 .uvtt parsing (fields + limits, plain-words refusals)
    image_headers.py        stdlib PNG/JPEG/WebP dimension readers
    scene.py                uvtt → .atlasmap (the port; deterministic ids)
    records.py              map/scene record writers (adoption shapes)
    presets.py              pack installer + preset validation port
    publish.py              the CLI (scenes, presets, version; party refuses
                            until built)
    config.py               campaign-side config: collection id, pack name,
                            grid defaults, default widgets — read from
                            <campaign>/avtt.yaml, fed-or-refused
    _version.py             VERSION + ATLAS_PIN + vault detection (ticket 07)
  packs/
    icrpg/
      preset.json           the Atlas system preset (shipped, ticket 04)
      fences/               statblock fence templates (npc, pc, mook) — not
                            yet written (P1, §1); rules in fences/README.md
      PACK.md               what's in the pack, where values come from
  fixtures/
    golden-0.6.0/           empty until the human capture (fixtures/README.md)
    sample.uvtt             small fixture exercising every conversion rule
    sample-lit.uvtt         the ambient-luma branch variant
    sample-nonsquare.uvtt   the non-square-cell refusal variant
  tests/                    test_pin, test_presets, test_records,
                            test_scenes, test_smoke
```

Python, stdlib-first (the core's old rule, kept here: `PyYAML` allowed for
config, `struct`-based image header reads, no Pillow, no LLM anywhere).
Subprocess discipline matches the core: list-form args, never `shell=True`.
Run via `uv` like everything else in the family.

## 5. Publishers

### 5.1 `scenes` (P2 — the main build)

```
input   <campaign>/maps/sites/<slug>/  {<slug>.png, <slug>.uvtt, <slug>.md}
output  <campaign>/atlas-vtt/collections/<collectionId>/
          maps/<slug>.png                 image copied (record states the path)
          maps/<slug>.json                map record
          scenes/<slug>.atlasmap          converted scene (walls, doors, lights, grid)
          scenes/<slug>.json              scene record → data.mapPath
also    companion note <slug>.md gains the Atlas scene-link line (append-only)
```

Idempotent per contract rule 3. `.uvtt` beyond Atlas's limits → refuse with
the importer's own plain-words reason before writing anything. Conversion
skips (walls/doors/lights left out, unlit, windows) are printed, not
swallowed. Atlas's walls-crowding refusal is the *manual* importer's guard,
not ours (ticket 03) — the publisher writes scenes past it.

**Degrade path (load-bearing):** the vault's detected Atlas version differs
from the pin (`ATLAS_PIN`, §7) → `scenes` refuses to write `.atlasmap`
files and instead drops the `.uvtt` into `atlas-vtt/_inbox/` with a printed
instruction ("drag it into Atlas; walls, doors and lights come along").
The interchange-format path always works; the adapter path is what needs
the test.

CLI: `uv run src/avtt/publish.py <campaign> scenes [--site <slug>] [--force] [--dry-run]`
(`--dry-run` prints the exact file plan and the first divergence from what
exists).

### 5.2 `presets` (P0 — the pack installer)

```
uv run src/avtt/publish.py <campaign> presets [--pack icrpg]
                                           [--force] [--dry-run]
  → validates packs/<pack>/preset.json (ported validator, strict)
  → writes atlas-vtt/system-presets/<pack>.json, refuse-on-diff
  → for a system Atlas ships built-in: writes nothing, says "<pin> has
    Shadowdark built in — consider using it"
```

**The gate (read contract, pinned — ticket 48):** `--pack` applies only
when the campaign's `campaign.yaml` declares a matching
`system:`. Read as `str(value).strip().lower()` — the exact semantics of
the core's `spine.campaign_system` (contract rule 4 forbids importing it,
so this line IS the shared definition; neither side may drift). Missing or
non-matching → refuse with "set `system: <system>` in
`campaign.yaml`" — never write a pack into a campaign that did not ask
for it. (Writing `campaign.yaml` itself stays forbidden: contract rule 1.)

The pack's preset *knobs* — hearts as a token resource, alarm-clock **timer**
widget, round **counter**, progress **clock**, d20 default roll + critical
rule, initiative rule, conditions, torch/lantern light presets, vision
defaults — have **values authored from the table's house rules**, never
invented here (icrpg DESIGN §13 is the checklist: which dice, which TN
ladder, heart conventions, milestone cadence). The pack carries `PACK.md`
recording each value's provenance.

### 5.3 `party` (P4 — parked)

Character + token records from a briefing roster. Parked because one-time
UI setup costs minutes per campaign and automation only pays when the party
churns. Un-park only with a fresh spike: token records
(`tokens/<id>.json` + art file) are the least-documented surface in Atlas.

## 6. The ICRPG pack

`packs/icrpg/` is the repo's first pack and its reason to exist as more
than a converter: it is the system-specific payload that cannot live in the
canon core. Contents: the preset (§5.2, shipped), fence templates whose
field vocabularies are ICRPG's (hearts, effort dice, abilities —
display-first; the mechanically-live number is the preset's hearts
resource), and PACK.md provenance. The fence templates are not yet
written (P1, §1) — `fences/README.md` holds the rules they must obey.
Future systems only join this repo if Atlas lacks them; a
system Atlas ships gets, at most, fence templates plus a PACK.md explaining
why no preset is published.

## 7. Testing discipline

1. **Golden-file test (the load-bearing one).** One real scene JSON,
   captured from Atlas <pinned version> by importing a fixture `.uvtt` in
   the Atlas UI and committing the resulting `.atlasmap` under
   `fixtures/golden-<version>/`. The port's output must match it
   structurally (keys, types, id scheme, math within float tolerance) —
   fixture `.uvtt` is designed to exercise every conversion rule: origin
   offset, polyline clipping, open/closed portals, zero-range light,
   baked lighting, ambient luma, non-square-cell refusal.
2. **Round-trip determinism:** same `.uvtt` twice → byte-identical output.
3. **Refusal tests:** every limit produces its plain-words reason; nothing
   is written on refusal.
4. **Degrade test:** simulate golden mismatch → `_inbox/` path taken,
   message printed, nothing else written.
5. **Preset validation port** tested against deliberately-broken presets
   (must be refused before Atlas ever sees them).

The pinned-release table lives here and moves only with a regenerated
golden fixture:

| Atlas version | pinned | notes |
|---|---|---|
| 0.6.0 | 2026-10-09 | initial analysis; library-sync semantics changed this release — bump carefully |

The pin is machine-readable (ticket 07): `src/avtt/_version.py` declares
`ATLAS_PIN` — the machine handle for the row above — alongside `VERSION`,
this repo's companion version (mirroring `pyproject.toml`). The fixture
directory `fixtures/golden-<ATLAS_PIN>/` is the pin's source of truth, and
`tests/test_pin.py::test_atlas_pin_matches_fixtures` holds constant and
fixture together. `publish.py <campaign> version` prints the companion
version, the pin, and the Atlas version detected in the vault's plugin
manifest (`.obsidian/plugins/atlas-vtt/manifest.json`; missing or
unreadable → `unknown`). On a mismatch `presets` prints
`atlas-pin-mismatch: pin=<v> detected=<v|unknown>` and installs anyway —
a preset is a watched plain file the DM can see and re-edit, so refusing
a file copy would trade a visible risk for a dead button — while `scenes`
(ticket 05) takes the §5.1 `_inbox/` degrade path on the same condition,
because scene content is where schema drift actually bites. Docstrings
and messages cite `_version.ATLAS_PIN` instead of restating a version;
only this table states one in prose.

## 8. When Atlas moves (the churn procedure)

Atlas shipped 0.5.0 → 0.6.0 in three days; assume monthly breakage.

1. Read the changelog; anything touching scenes/presets/adoption → treat as
   breaking until the golden test passes.
2. Install the new Atlas, import `fixtures/sample.uvtt`, commit the result
   as `fixtures/golden-<new>/`.
3. Run the suite against both goldens; move the pin only when green.
4. If red and the fix is nontrivial: ship the `_inbox/` degrade path and
   open the fix as a milestone, don't hack the port to pass.
5. One commit per pin bump (ticket 07): the `ATLAS_PIN` constant, the new
   `fixtures/golden-<version>/`, the §7 table row, and the `VERSION` bump
   move together, git-tagged `v<VERSION>`. Consumers pin tags, never main.

Upstream issues before forks; `dnd-mapping/vendor-patches/` is the
last-resort precedent for owning a patched dependency, not the default.

## 9. Non-goals

- Reading `atlas-vtt/` state (fog, HP, positions) into anything. Table
  state is not canon (core ruling R1).
- Writing spine files, canon, or anything outside `atlas-vtt/` (contract
  rule 1, incl. its one licensed exception).
- `library.json` / `collection.json` mimicry — app internals, never ours.
- Any runtime at the table. This repo is a prep-time CLI; Atlas owns the
  table. No server, no watcher daemon, no LLM.
- Forking Atlas (§8 is the escalation ladder, and forks are its last rung).
- Systems Atlas already ships (§5.2 behavior).

## 10. Licensing

**AGPL-3.0-only**, matching Atlas: `scene.py` is a port of Atlas's
AGPL `uvttToScene.ts` logic, and a port is a derivative work. Private
personal use triggers none of it, but the license is declared so the
derivative relationship is honest from day one. Interop via documented file
formats does not by itself create obligations; vendoring Atlas source would
— we don't. Pack content (preset values, fence text) is our own.

## 11. Sibling repos

| repo | role | relationship |
|---|---|---|
| `dnd-campaign-generator` | canon core | we read its campaign dirs; it never reads `atlas-vtt/`; it may spawn our CLI someday |
| `icrpg-companion` | frozen v0 phone app | unrelated runtime; not reopened, not deleted |
| `atlas-vtt` (upstream) | the table app | we write its formats; issues before forks; AGPL honored |

## 12. Open questions (the spike list, in build order)

1. ~~**Collection bootstrap** (§3.1)~~ — answered by ticket 01
   (2026-10-10, live on 0.6.0 and 0.7.1): folder-only adoption works;
   no bootstrap step. `publish.py scenes` still takes its write-target
   slug from config, and refuse-on-diff must compare Atlas's rewritten
   record content, never raw bytes.
2. ~~**Image path conventions** (§3.1)~~ — answered by ticket 02
   (2026-10-10, against 0.6.0): `assetImageFiles.ts` is the UI
   drag-in importer's helper, not the adoption path; keep
   `maps/<slug>.png` beside the record, and thumbnails are Atlas's job
   (generated in the background, never supplied). Details in ticket 02's
   Implementation notes.
3. ~~**Walls-crowding refusals**: dense generated maps may trip Atlas's
   `wallsCrowd` heuristic on *its* import path — irrelevant to ours (we
   write scenes directly), but the studio's manual-drag fallback hits it;
   document the refusal text where the tutorial mentions manual import.~~ —
   answered by ticket 03 (2026-10-12, source-read at the pin): the verbatim
   refusal text, the threshold (both `uvttCrowding.ts` caps), and a drafted
   plain-words paragraph for the core's ATLAS tutorial live in the archived
   ticket. Still open there, by hand: carrying that paragraph into the
   core repo's tutorial (a cross-repo edit) and the optional UI
   confirmation of the refusal.
