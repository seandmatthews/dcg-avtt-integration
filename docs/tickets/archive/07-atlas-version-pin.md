# 07 — The Atlas version pin: declare, detect, degrade

**Status:** completed — 2026-10-12 (implemented on
`feature/07-atlas-version-pin` the same day; reviewer sign-off and the
`archive/` move are part of this change)
**Priority:** P1 — the core's bundle work (its tickets 51–53) pins a
companion release and reports Atlas compatibility; nothing to pin until a
release can say which Atlas it targets
**Area:** `src/avtt/_version.py` (new), `src/avtt/publish.py`,
`src/avtt/presets.py` (docstring demotion), `tests/`, `fixtures/`,
`README.md` §7/§8
**Found by:** the distribution design session, 2026-10-12. The pin exists
only as prose (README §7's table, module docstrings) while the machine
this repo serves runs Atlas **0.7.1** against the **0.6.0** pin — nothing
mechanical notices. Ground truth on that machine today:
`campaign-data/campaigns/ember-coast/.obsidian/plugins/atlas-vtt/manifest.json`
reads:

```json
{
  "id": "atlas-vtt",
  "name": "Atlas VTT",
  "version": "0.7.1",
  "minAppVersion": "1.8.7",
  ...
}
```

## Problem

README §7 pins this repo to Atlas 0.6.0 and §8 makes moving the pin a
human ritual (import `fixtures/sample.uvtt` in the UI, commit
`fixtures/golden-<new>/`, run the suite against both goldens, move the pin
only when green). But the pin is not machine-readable, so the ritual has
nothing to bite on:

- No constant names it. `presets.py` carries "v0.6.0" in docstrings; the
  golden fixtures directory name (`golden-0.6.0/` — currently a README
  placeholder, the capture is ticket 05's step 8) encodes it, but nothing
  reads that as a contract.
- No runtime compares it. `publish.py presets` writes into whatever vault
  it is pointed at and never asks which Atlas is installed. The failure
  mode README §3.4 calls the worst — a silently-ignored preset after
  Atlas tightens `presetValidation.ts` — is exactly what an unnoticed pin
  skew produces.
- No release declares it. The repo has no tags and no version discipline
  (pyproject says 0.1.0, never bumped), so a consumer that wants to pin a
  known-good companion has nothing version-shaped to pin.

## Proposal

1. `src/avtt/_version.py`: `VERSION = "0.1.0"` (mirrors pyproject; one
   place) and `ATLAS_PIN = "0.6.0"`. Docstrings across `presets.py` and
   `scene.py` lose their normative version claims — they cite
   `_version.ATLAS_PIN` instead. The README §7 table stays the human
   record.
2. Pin-integrity test: the `fixtures/golden-<version>/` directories must
   include `golden-{ATLAS_PIN}/`. The fixture set is the pin's source of
   truth; the constant is its machine handle.
3. Detection: read the vault's
   `.obsidian/plugins/atlas-vtt/manifest.json` and take `version`
   (shape above; `community-plugins.json` lists the id). Missing,
   unparseable, or plugin absent → `"unknown"`. This reads Obsidian
   config, not `atlas-vtt/` state — contract rule 2 governs the data
   folder; rule 1 allows reading the campaign directory.
4. Mismatch policy, decided here:
   - **presets**: installed ≠ pin → print a loud machine-readable line
     (`atlas-pin-mismatch: pin=<v> detected=<v|unknown>`) and proceed. A
     preset is a watched plain file the DM can see and re-edit; refusing
     a file copy would trade a visible risk for a dead button.
   - **scenes** (ticket 05's build): installed ≠ pin → the `_inbox/`
     degrade path, not a warning — scene content is where schema drift
     actually bites.
   - **unknown** → treated as mismatch (warn; degrade for scenes).
5. `publish.py version`: prints companion `VERSION`, `ATLAS_PIN`, and the
   detected Atlas version — the line the core's table-setup card
   (core ticket 53) renders.
6. Release discipline: every pin bump is one commit (constant + fixture
   + README §7 table row + VERSION bump) and is git-tagged `v<VERSION>`.
   Consumers pin tags, never main.

## Acceptance criteria

- [x] Pin integrity: `tests/test_pin.py::test_atlas_pin_matches_fixtures`
- [x] Manifest detection: present / absent / corrupt manifest —
      `tests/test_pin.py::test_detect_atlas_version`
- [x] Preset mismatch warns and still writes, exit code 0 —
      `tests/test_pin.py::test_preset_mismatch_warns_not_refuses`
- [x] `publish.py version` prints all three values —
      `tests/test_pin.py::test_version_report`
- [x] Live check on this machine: the ember-coast vault (Atlas 0.7.1
      installed) produces the mismatch warning; the presets install still
      succeeds and the file appears in the watched folder.

## Implementation notes (2026-10-12)

Landed as the branch's single feat(07) commit on
`feature/07-atlas-version-pin` (this commit — the status flip and the
`archive/` move are folded into it). Before sign-off: ruff clean;
`run-tests.py --all` green (82 passed, 4 skipped — the skips are
ticket 05's discipline placeholders). Nothing left for a human; the
golden-fixture capture remains ticket 05's human step, not this
ticket's.

- `src/avtt/_version.py` declares `VERSION = "0.1.0"` and
  `ATLAS_PIN = "0.6.0"`; `detect_atlas_version()` reads
  `<campaign>/.obsidian/plugins/atlas-vtt/manifest.json` (missing,
  unreadable, unparseable, non-object, or no usable `version` string →
  `"unknown"`). `presets` prints
  `atlas-pin-mismatch: pin=<v> detected=<v|unknown>` and proceeds;
  `publish.py <campaign> version` prints all three values; README
  §7/§8 document the machine handle and the one-commit-per-bump,
  `v<VERSION>`-tagged release ritual.
- Deliberate deviations from the proposal:
  - Detection is manifest-only: a plugin *disabled* in Obsidian is
    not treated as `"unknown"` — the manifest on disk states which
    Atlas wrote the vault's file formats, and that is what the pin is
    about. "Plugin absent" maps to the manifest/plugin folder being
    missing, matching the criterion's present/absent/corrupt cases.
    Documented in the `_version.py` docstring.
  - The builtin short-circuit message ("0.6.0 has Shadowdark built
    in — consider using it") cites `ATLAS_PIN` now too — a runtime
    version claim, not just a docstring one; today's output is
    byte-identical, so the existing test needed no change.
  - `BUILTIN_SYSTEMS_0_6_0` / `BUILTIN_DISPLAY_NAMES_0_6_0` keep
    their names: they name the pinned-release snapshot they hold,
    re-verified per §8 when the pin moves.
  - Provenance lines of the form "verified against v0.6.0"
    (`records.py`, `uvtt.py`, `config.py`, test docstrings) are left
    as-is: historical verification records, not normative pin
    claims — the same standing as README §3's source-read date.
- Live check: run against the real ember-coast vault
  (`campaign-data/campaigns/ember-coast`, manifest `0.7.1`) — the
  mismatch warning printed from the real manifest via both `version`
  and `presets`. The install half ran on a faithful temp copy (the
  real `manifest.json` bytes verbatim; the real `campaign.yaml` plus
  `system: icrpg`), because the vault's `campaign.yaml` declares no
  `system:` and ticket 04's gate correctly refuses to write a pack
  into a campaign that did not ask — hand-editing the live campaign
  data was out of scope. On the copy: the warning line, then
  `wrote .../system-presets/icrpg.json`, exit 0, file present in the
  watched folder. The temp copy was deleted after the check.
- Guards beyond the criteria: `tests/test_pin.py` also pins the
  README §7 table row to `ATLAS_PIN` and `VERSION` to pyproject's
  `[project] version` (regex-read, stdlib-only — `tomllib` is
  3.11+); `test_smoke.py`'s surface pin covers `_version`.
- No git tag: the constants are declared at the existing
  0.1.0 / 0.6.0 values — a declaration, not a bump. §8's tag ritual
  triggers on actual bumps.
