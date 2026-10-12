# 03 — Spike: walls-crowding refusal text, for the manual-import doc

**Status:** completed (2026-10-12, reviewer sign-off same day)
**Priority:** P3
**Area:** spike (documentation); output lands here + the core's
`docs/for-new-gms/` ATLAS tutorial (cross-repo, by hand)
**Found by:** Atlas seam analysis + spec, 2026-10-09/10

## Problem

Dense generated maps may trip Atlas's `wallsCrowd` heuristic on *its*
import path (`src/app/import/uvtt/uvttCrowding.ts` in 0.6.0). This
repo's own publisher is unaffected (it writes scenes directly, README
§12.3), but the manual-drag fallback — the degrade path's `_inbox/`
instruction (README §5.1) — lands the DM in exactly that importer. When
it refuses, the DM needs to know what the message means and what to do.

## Proposal

1. In the pinned clone, read `uvttCrowding.ts` + the importer's user-
   facing refusal strings; capture the exact text and the threshold.
2. Trigger it once in the Atlas UI with a deliberately crowded
   `fixtures/sample.uvtt` variant (confirm the source read).
3. Write the explanation into the doc that mentions manual import —
   the ATLAS tutorial lives in the *core* repo
   (`dnd-campaign-generator/docs/for-new-gms/`), so the edit there is
   made by hand as a separate cross-repo change; the captured text and
   the guidance live in this ticket.

## Acceptance criteria

- [x] The refusal text + threshold are captured in this ticket's
      Implementation notes, tagged to the Atlas version (checkable by
      reading). — 0.6.0, commit `c5a99830`.
- [ ] The core tutorial's manual-import paragraph carries the
      plain-words explanation (cross-repo; note the edit here). — open
      by design: the edit in the core repo is made by hand; the drafted
      paragraph is below, and a 2026-10-12 grep confirms the tutorial
      does not yet carry it. The reviewer signed off with this left for
      the human (see "Left for the human").

## Implementation notes (2026-10-12)

### What the source says (Atlas 0.6.0)

Read 2026-10-12 from a fresh clone of tag `0.6.0` (HEAD
`c5a9983003f40054caff8d6f394a09816ababa31`, per AGENTS.md's re-clone
rule; paths below are repo-relative to the Atlas clone). Committer ran
`git ls-remote --tags` and `git rev-parse HEAD` to confirm the tag.

**The refusal, verbatim.** The DM sees an Obsidian notice for 12 s
(`runUvttImport.ts:9` `PROBLEM_NOTICE_MS = 12_000`, shown at
`runUvttImport.ts:50`):

> Could not import `<file name>`. The walls in the file end too close
> together in too many places for Atlas to join them.

The second sentence is the constant `CROWDED_WALLS`
(`src/app/import/uvtt/importUvttFile.ts:46`); it is returned from the
crowd check at `importUvttFile.ts:157` and again at `:173` — the second
check exists because the importer may scale a huge image down
("A map scaled down has its walls closer together", `:172`), so a file
that passes at full size can still be refused after scaling.

**The threshold.** `wallsCrowd` (`src/app/import/uvtt/uvttCrowding.ts`)
refuses when either counter passes its cap (`uvttCrowding.ts:11-12`):

- `MAX_COMPARISONS = 5_000_000` — every wall-segment *endpoint* is
  bucketed on a grid of cell size `max(tolerance, 1) * 4`, and the check
  counts each end against every end in its 3×3 grid neighbourhood;
- `MAX_JOINTS = 100_000` — pairs of endpoints of *different* walls
  within `sealTolerance` of each other (the gaps Atlas would weld shut
  with a bridge).

`sealTolerance(texel) = 2·(wallRadius + fieldMargin) + 2·texel`
(`src/app/lighting/lightingConstants.ts:178-180`), where
`wallRadius = max(3, texel·√2 + 0.01)` (`:131-133`),
`fieldMargin = 0.75·texel` (`:136-138`), and
`texel = max(2, longestImageSide / 4096)` world pixels
(`:6`, `:8`, `:123-125`). On an ordinary map (side ≤ 8192 px) that is
**13 px**; a 16,384 px map gets ≈ 25.3 px. Both counters are cumulative
over the whole map and either one tripping refuses the import.

The doc comment (`uvttCrowding.ts:8-10`) states the intent: the caps are
a performance guard on the wall-bridge welding that light and sight need
— at the caps, joining takes about a fifth of a second, and past them
opening the scene stalls. It is not a verdict that the map is wrong.

**What a dense map does wrong.** The check runs on the *converted*
scene, where each `.uvtt` polyline contributes one wall segment per
point pair (README §3.3) — so every interior vertex is two endpoints,
and an auto-walled map that puts a stub on every tile edge manufactures
millions of comparisons and >100,000 weldable pairs.

**Scope: manual import only.** A grep over the 0.6.0 tree shows
`wallsCrowd` is called only from `importUvttFile.ts`, whose only UI
caller is the asset-manager hook
`src/app/packages/components/asset-manager/hooks/useUvttImport.ts:77`.
Our publisher writes `.atlasmap` directly (README §12.3) and never runs
this code. Do not confuse the refusal with the *different* wall refusal
in the same importer: `parseUvtt.ts` refuses raw files over
`UVTT_LIMITS.wallSegments` (`uvttTypes.ts:14`, 20,000) with
"The file has more than 20,000 wall segments." — that check is first and
counts raw polylines; crowding can still trip under the count.

### The plain-words paragraph for the core tutorial

The ATLAS tutorial lives in the core repo
(`dnd-campaign-generator/docs/for-new-gms/`); per the proposal the edit
there is made by hand. Drafted text for its manual-import section:

> **If Atlas says the walls are too crowded.** When you drag in a
> `.uvtt`, Atlas checks the map's walls before importing. The notice
> "Could not import `<file>`. The walls in the file end too close
> together in too many places for Atlas to join them." means the walls
> are too finely chopped — not that the file is corrupt. To stop light
> leaking through hairline gaps, Atlas welds together wall ends that sit
> within about 13 pixels of each other (a bit more on very large maps).
> A map whose walls are drawn as thousands of tiny pieces — typical of
> auto-generated maps that put a wall stub on every tile edge — packs so
> many near-touching ends together that this welding becomes a job Atlas
> refuses to take on. Nothing was imported and the file is untouched, so
> retrying is safe. Fix it in the map's source: redraw the walls as a
> few long lines per room instead of one segment per tile edge, delete
> leftover duplicate segments, export a fresh `.uvtt`, and drag it in
> again. (A related refusal, "The file has more than 20,000 wall
> segments.", means the same fix.) The repo's `publish` command never
> hits this — it writes the scene file directly, past the importer.

### How it landed (2026-10-12)

One commit on `feature/03-walls-crowding-doc` — `docs(03): capture
walls-crowding refusal text + threshold at pin 0.6.0, draft
core-tutorial paragraph (Spike: walls-crowding refusal text, for the
manual-import doc)` — amended, per the implementer loop, to carry this
flip to `completed` and the move to `docs/tickets/archive/`
(CONVENTIONS.md: the flip and the archive move are the same change).
Gates at landing: ruff clean; `run-tests.py --all` 82 passed, 4 skipped
(the discipline placeholders awaiting ticket 05), integration tier
auto-skipped — no captured golden fixture yet.

**Deviations.** (a) The clone at the pin was shallow
(`git clone --branch 0.6.0 --depth 1`) — the same tree at the tag, with
`git rev-parse HEAD` checked against `git ls-remote` before trusting a
line of it. (b) No crowded `fixtures/sample.uvtt` variant was committed:
`sample.uvtt` itself lands with ticket 05 (fixtures/README.md), so the
variant belongs right behind it; the recipe is the source read above (a
wall stub per tile edge is the shape that trips both caps).

### Left for the human (criterion 2 open)

The core tutorial does not yet carry the explanation: a grep of
`dnd-campaign-generator/docs/for-new-gms/` on 2026-10-12 finds no
crowding text (the last commit touching `ATLAS.md` is `ad361bc`,
pre-spike). The edit stays by hand, as proposed: carry the drafted
paragraph above into `ATLAS.md`'s manual-drag material (Step 4 and the
troubleshooting table are the natural anchors) as a separate cross-repo
change, then tick criterion 2. The optional UI confirmation (proposal
step 2 — trigger the refusal once with a crowded sample variant) also
waits for an Atlas-UI session; the source read above stands on its own
until then.
