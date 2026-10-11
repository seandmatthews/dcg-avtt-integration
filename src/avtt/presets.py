"""System-preset pack installer + the ported preset validator.

Spec: README §3.4/§5.2. Presets are plain files at
``atlas-vtt/system-presets/<name>.json``, watched live by Atlas
(``presetFiles.ts``) and validated on load (``presetValidation.ts``).
An invalid preset is silently ignored by Atlas — the worst failure
mode — so the installer validates with equivalent strictness *before*
writing anything.

Contract rule 3 governs the write: refuse-on-diff; ``--force`` writes a
``<name>-v2`` sibling. For a system Atlas ships built-in (D&D 5e, PF2e,
Shadowdark, OSE, Cairn, Daggerheart, Draw Steel, CoC, Cyberpunk RED as
of 0.6.0), the correct behavior is to write nothing and say so.
"""

from __future__ import annotations

from pathlib import Path

BUILTIN_SYSTEMS_0_6_0 = frozenset({
    "dnd5e", "pf2e", "shadowdark", "ose", "cairn",
    "daggerheart", "draw-steel", "coc", "cyberpunk-red",
})


def validate_preset(preset: dict) -> list[str]:
    """Return the list of validation failures (empty = valid).

    A port of Atlas's ``presetValidation.ts`` checks at the pinned
    version — must stay exactly as strict as Atlas's own loader, or a
    broken preset sails through the installer and is then silently
    ignored by the app.
    """
    raise NotImplementedError("lands with the presets build (ticket 04); README §3.4")


def install(preset_path: Path, atlas_dir: Path, *, force: bool = False) -> Path:
    """Copy a validated pack preset to ``atlas-vtt/system-presets/<name>.json``.

    Refuse-on-diff when the target exists and differs; ``--force``
    writes a ``-v2`` sibling instead of overwriting.
    """
    raise NotImplementedError("lands with the presets build (ticket 04); README §5.2")


def load_pack_preset(pack: str) -> dict:
    """Load and JSON-decode ``packs/<pack>/preset.json``."""
    raise NotImplementedError("lands with the presets build (ticket 04)")
