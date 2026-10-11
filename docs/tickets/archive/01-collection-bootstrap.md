# 01 — Spike: collection bootstrap semantics

**Status:** completed (2026-10-10 — live experiment done same day; reviewer = the
recorded disk evidence, re-checkable by rerunning the experiment)
**Priority:** P1 (first in the build order, README §12)
**Area:** spike (Atlas UI experiment); output lands in `src/avtt/config.py`
and README §3.1
**Found by:** Atlas seam analysis + spec, 2026-10-09/10

## Problem

Unknown whether a collection that exists only as a folder
(`atlas-vtt/collections/<id>/maps/<stem>.json`, records written but no
collection metadata) is adopted by Atlas, or whether
`collection.json` plus the library index must exist first. README §3.1
flags this as UNKNOWN. It decides whether `publish.py scenes` needs a
config step at all: if folder-only works, `config.collection_id` can
stay `None` forever; if not, the id must be recorded per campaign.

Fallback if the answer is "needs a real collection": create it once in
the Atlas UI and record its id in the campaign's companion config. This
repo must never write `library.json` or `collection.json` either way —
those are app internals (ruling, README §3.1).

## Proposal

One experiment in the Atlas UI with a hand-written record:

1. Fresh/throwaway vault, Atlas 0.6.0 (or the current pin).
2. Hand-write a minimal valid map or scene record into
   `atlas-vtt/collections/<made-up-id>/maps/<stem>.json` — no
   `collection.json`, no library index — then open Atlas and observe:
   adopted, ignored, or error?
3. If ignored: create the collection in the UI, note the assigned id,
   and re-test adoption of the hand-written record inside it.

## Acceptance criteria

- [x] The experiment's result is written up in this ticket's
      Implementation notes: adopted vs UI-required, with what was
      observed (checkable by reading). — **adopted, folder-only**, on
      both versions tested; write-up below.
- [x] README §3.1's UNKNOWN paragraph is replaced by the answer, dated
      and tagged to the Atlas version tested. — done in the same change.
- [x] `src/avtt/config.py`'s `collection_id` field docstring states the
      decision (stays-None vs per-campaign) — pinned by
      `tests/test_smoke.py` importing config cleanly. — decision:
      **per-campaign slug, always present**; see the type change in the
      deviations below.

## Implementation notes (2026-10-10)

**Method.** Two throwaway vaults, one per version, each built by script:
the pinned **0.6.0 release build** (downloaded from the atlas-vtt GitHub
releases) and the **0.7.1 install** copied from the ember-coast campaign
vault (read-only copy, without its `data.json`). Each vault got the
plugin, `community-plugins.json: ["atlas-vtt"]`, and exactly the spike's
hand-written record — a 32×16 PNG at
`atlas-vtt/collections/spike01/maps/handwritten.png` plus
`handwritten.json` = `{name, tags, createdAt, modifiedAt, type: "map",
mapFilePath}` with **no** `id`, **no** `collection` field, and **no**
`collection.json` / `library.json` anywhere. Obsidian 1.14.4 opened each
vault, the trust dialog was accepted, and the vault's disk state was
read back after the plugin's startup check. Both vaults were deleted
afterwards; nothing outside `%TEMP%` and Obsidian's vault registry (a
backed-up, restored edit) was touched.

**Answer: folder-only adoption works. Identically on 0.6.0 and 0.7.1.**
After one plugin load, both vaults showed the same four facts:

1. The record was **adopted and rewritten in place** into Atlas's
   canonical form: the recovered `id: "handwritten"` (from the stem, as
   `recoveredIds.ts:stemOf` predicts), the derived
   `collection: "spike01"` filled in, and the whole payload wrapped in
   an `atlasRecord: {format: 1, ...}` envelope alongside the flat
   fields.
2. A **derived `atlas-vtt/collections/spike01/collection.json`**
   appeared (`uid: "collection-2faaveaf735"` — the same derived uid both
   times, so it is a pure function of the collection id), with default
   settings (an HP token resource).
3. **`atlas-vtt/library.json` was bootstrapped from nothing**:
   `{format: 1, defaultCollectionId: "spike01", starterTokensAdded:
   true}` — the first collection to exist becomes the default.
4. The hidden index `atlas-vtt/.atlas-data/assets-metadata.json`
   contains the map (`filePath`, `mapFilePath`, type `map`) under
   collection `spike01`.

**Consequences for this repo:**

- No bootstrap step and no UI-recorded id. The publisher still names a
  collection — as the **write-target folder slug**, which is ours to
  choose (e.g. the campaign slug); adoption does the rest.
- `config.collection_id` becomes `str` (was `str | None`): always
  present, always a slug of our choosing. Deviation from the ticket's
  original either/or framing — the experiment made the third option
  (free-form slug, no UI) the right one.
- **Atlas rewrites adopted record files.** Contract rule 3's
  refuse-on-diff can never compare raw bytes against what we wrote —
  after adoption the file is Atlas's canonical form. `publish.py` must
  parse the existing file and compare its `atlasRecord` payload (or
  accept the canonical form as "ours, unchanged in meaning"). This goes
  into README §3.1 and binds ticket 05.
- A first Atlas run on a fresh vault also drops **starter tokens** (ten
  class tokens into `assets/` + `tokens/` records). First-run side
  effect, not ours to mimic or clean up; worth knowing when reading a
  fresh campaign vault's tree.

**Manual-import note (bycatch).** The Atlas UI needed one trust-dialog
click per fresh vault and nothing else — no collection creation, no
onboarding steps blocking adoption.

**Verification.** All four facts above were read from the vault disk
after the run (the authoritative evidence, quoted in the README update);
the Atlas asset manager additionally showed the map under the spike01
collection on the 0.6.0 vault before cleanup.

**Left for the human:** nothing from this ticket.
