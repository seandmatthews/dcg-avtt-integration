# 04 — P0: the presets publisher (pack installer)

**Status:** proposed
**Priority:** P1 (first code build, after the spikes)
**Area:** `src/avtt/presets.py`, `src/avtt/publish.py` (presets
subcommand), `packs/icrpg/`
**Found by:** spec §5.2, 2026-10-10

## Problem

The ICRPG preset is the repo's system-specific payload (README §1) and
the pack installer is its delivery mechanism — the first build item
once spikes 01–03 land. Nothing exists yet; `presets.py` is a stub.

## Proposal

Implement per README §3.4/§5.2:

1. Port the validator checks from Atlas's `presetValidation.ts` at the
   pinned version — exactly as strict as Atlas's own loader, since an
   invalid preset is silently ignored there (the worst failure mode).
2. `install()`: refuse-on-diff write to
   `atlas-vtt/system-presets/<pack>.json`; `--force` writes a
   `<pack>-v2` sibling (contract rule 3).
3. Built-in short-circuit: if the pack's system is one Atlas ships
   (`BUILTIN_SYSTEMS_0_6_0` — re-verify against the pinned release),
   write nothing and print "0.6.0 has Shadowdark built in — consider
   using it".
4. CLI: `publish.py <campaign> presets [--pack icrpg] [--force]
   [--dry-run]`.
5. Author `packs/icrpg/preset.json` — **values come from the table's
   house rules only** (icrpg DESIGN §13 checklist: dice, TN ladder,
   heart conventions, milestone cadence). No value is invented here;
   each knob's provenance goes in PACK.md.

## Acceptance criteria

- [ ] Ported validator refuses deliberately-broken presets (wrong id
      prefix `builtin:`, missing rules keys, bad condition shapes) —
      pinned by `tests/test_presets.py` (discipline 5, README §7.5).
- [ ] Refuse-on-diff and `--force` sibling semantics — pinned by
      `tests/test_presets.py`.
- [ ] Built-in-system short-circuit writes nothing, message printed —
      pinned by `tests/test_presets.py`.
- [ ] `preset.json` ships only when its values have PACK.md provenance
      lines (checkable by reading).

## Implementation notes (YYYY-MM-DD)

_lands here when the status flips._
