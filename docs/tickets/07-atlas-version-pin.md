# 07 — The Atlas version pin: declare, detect, degrade

**Status:** proposed
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

- [ ] Pin integrity: `tests/test_pin.py::test_atlas_pin_matches_fixtures`
- [ ] Manifest detection: present / absent / corrupt manifest —
      `tests/test_pin.py::test_detect_atlas_version`
- [ ] Preset mismatch warns and still writes, exit code 0 —
      `tests/test_pin.py::test_preset_mismatch_warns_not_refuses`
- [ ] `publish.py version` prints all three values —
      `tests/test_pin.py::test_version_report`
- [ ] Live check on this machine: the ember-coast vault (Atlas 0.7.1
      installed) produces the mismatch warning; the presets install still
      succeeds and the file appears in the watched folder.

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
